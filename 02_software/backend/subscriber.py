
import json
import os
import queue
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from pydantic import ValidationError

load_dotenv()

from database.database_manager import initialize_database
from database.raw_database_manager import (
    initialize_raw_database,
    save_raw_message,
    update_raw_message_status,
)
from models.telemetry import Telemetry
from repositories.telemetry_repository import (
    TelemetryConflictError,
    save_telemetry,
)


from services.telemetry_recovery_service import recovery_worker


BACKEND_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BACKEND_DIR / "storage"

INVALID_DIR = STORAGE_DIR / "invalid"
FAILED_DIR = STORAGE_DIR / "failed"
REPROCESSED_DIR = STORAGE_DIR / "reprocessed"
RAW_DATABASE_DIR = STORAGE_DIR / "raw_databases"

MAX_FILE_SIZE_BYTES = (
    int(os.getenv("INVALID_FILE_MAX_MB", "500")) * 1024 * 1024
)

if MAX_FILE_SIZE_BYTES <= 0:
    raise ValueError("INVALID_FILE_MAX_MB must be greater than zero.")

MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_TOPIC = os.getenv(
    "MQTT_TOPIC",
    "smart-irrigation/telemetry",
)
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "nexus-subscriber")

RETRY_DELAY_SECONDS = float(os.getenv("RETRY_DELAY_SECONDS", "5"))

PROCESSING_QUEUE = queue.Queue()
FILE_LOCK = threading.RLock()
QUEUE_LOCK = threading.RLock()
QUEUED_IDS = set()
STOP_EVENT = threading.Event()


def utc_now() -> str:
    """Return the current UTC time in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def ensure_directories():
    """Create all required storage directories."""
    for directory in (
        STORAGE_DIR,
        INVALID_DIR,
        FAILED_DIR,
        REPROCESSED_DIR,
        RAW_DATABASE_DIR,
        STORAGE_DIR / "databases",
    ):
        directory.mkdir(parents=True, exist_ok=True)


def _append_rotating_jsonl(
    directory: Path,
    prefix: str,
    record: dict,
):
    """Append a JSON record to a size-limited JSONL file."""
    directory.mkdir(parents=True, exist_ok=True)

    record = dict(record)
    record.setdefault("record_id", str(uuid.uuid4()))

    encoded_line = (
        json.dumps(
            record,
            ensure_ascii=False,
            allow_nan=False,
            default=str,
        )
        + "\n"
    )
    encoded_bytes = encoded_line.encode("utf-8")

    with FILE_LOCK:
        date_part = datetime.now().strftime("%Y-%m-%d")
        sequence = 1

        while True:
            file_path = directory / (
                f"{prefix}_{date_part}_{sequence:04d}.jsonl"
            )

            if not file_path.exists():
                break

            if (
                file_path.stat().st_size + len(encoded_bytes)
                <= MAX_FILE_SIZE_BYTES
            ):
                break

            sequence += 1

        with file_path.open("ab") as file:
            file.write(encoded_bytes)
            file.flush()
            os.fsync(file.fileno())

    return file_path, encoded_line, record["record_id"]


def _find_record_line_number(file_path: Path, record_id: str):
    """Find a JSONL record's 1-based line number."""
    try:
        with FILE_LOCK:
            with file_path.open("r", encoding="utf-8") as file:
                for line_number, raw_line in enumerate(file, start=1):
                    try:
                        record = json.loads(raw_line)
                    except (json.JSONDecodeError, TypeError):
                        continue

                    if (
                        isinstance(record, dict)
                        and record.get("record_id") == record_id
                    ):
                        return line_number

    except OSError as exc:
        print(f"[INVALID] Could not locate record line number: {exc}")

    return None


def _queue_key(file_path, line_number, raw_line):
    """Create a consistent in-memory key for a recovery task."""
    return (
        f"{Path(file_path).resolve()}:{line_number}:"
        f"{hash(raw_line)}"
    )


def save_invalid_message(raw_payload, topic: str, reason: str):
    """Persist an invalid message and enqueue it for recovery."""
    record = {
        "received_at": utc_now(),
        "topic": topic,
        "reason": reason,
        "raw_payload": raw_payload,
    }

    file_path, stored_line, record_id = _append_rotating_jsonl(
        INVALID_DIR,
        "invalid",
        record,
    )

    line_number = _find_record_line_number(file_path, record_id)

    task = (str(file_path), line_number, stored_line)
    task_key = _queue_key(file_path, line_number, stored_line)

    with QUEUE_LOCK:
        if task_key not in QUEUED_IDS:
            QUEUED_IDS.add(task_key)
            PROCESSING_QUEUE.put(task)

    print(
        f"[INVALID] Stored and queued: {file_path} "
        f"(record_id={record_id}, line={line_number})"
    )
    return file_path


def save_failed_message(raw_payload, topic: str, reason: str):
    """Persist a message that could not be processed."""
    record = {
        "received_at": utc_now(),
        "topic": topic,
        "reason": reason,
        "attempts": 0,
        "raw_payload": raw_payload,
    }

    file_path, _, record_id = _append_rotating_jsonl(
        FAILED_DIR,
        "failed",
        record,
    )

    if not file_path.is_file():
        raise OSError(
            f"Failed JSONL file was not created: {file_path}"
        )

    print(f"[FAILED] Stored: {file_path} (record_id={record_id})")
    return file_path


def _store_failed_and_update_raw(
    raw_record_id,
    payload,
    topic,
    reason,
):
    """Persist failed message and update its raw database status."""
    try:
        failed_path = save_failed_message(payload, topic, reason)

    except Exception as storage_exc:
        combined_reason = (
            f"{reason}; failed-file persistence error: "
            f"{type(storage_exc).__name__}: {storage_exc}"
        )

        print(
            "[FAILED] PERSISTENCE ERROR: could not write failed JSONL. "
            f"reason={combined_reason!r}; target_dir={FAILED_DIR}"
        )

        _update_raw_status(
            raw_record_id,
            "valid",
            "failed",
            combined_reason,
        )
        return False

    print(f"[FAILED] File persisted successfully: {failed_path}")

    _update_raw_status(
        raw_record_id,
        "valid",
        "failed",
        reason,
    )
    return True


def _rebuild_queue():
    """Restore pending invalid-message tasks after startup."""
    try:
        from services.invalid_telemetry_processor import (
            iter_pending_records,
        )

        for file_path, line_number, raw_line in iter_pending_records():
            task = (str(file_path), line_number, raw_line)
            task_key = _queue_key(
                file_path,
                line_number,
                raw_line,
            )

            with QUEUE_LOCK:
                if task_key in QUEUED_IDS:
                    continue

                QUEUED_IDS.add(task_key)
                PROCESSING_QUEUE.put(task)

        print("[RECOVERY] Pending invalid-message queue rebuilt.")

    except Exception as exc:
        print(f"[RECOVERY] Could not rebuild queue: {exc}")


def invalid_processor_worker():
    """Process queued invalid-message recovery tasks."""
    from services.invalid_telemetry_processor import (
        process_invalid_record,
    )

    while not STOP_EVENT.is_set():
        try:
            task = PROCESSING_QUEUE.get(timeout=1)

        except queue.Empty:
            continue

        file_path = None
        line_number = None
        raw_line = None
        task_key = None
        retry_task = False

        try:
            if not isinstance(task, (tuple, list)) or len(task) != 3:
                raise ValueError(
                    f"Unexpected recovery task format: {task!r}"
                )

            file_path, line_number, raw_line = task

            task_key = _queue_key(
                file_path,
                line_number,
                raw_line,
            )

            status = process_invalid_record(
                file_path,
                line_number,
                raw_line,
            )

            if status == "retry":
                retry_task = True
                print(
                    "[RECOVERY] Record remains retryable; "
                    f"will retry {Path(file_path).name}:{line_number}"
                )

        except Exception as exc:
            retry_task = True
            print(f"[RECOVERY] Processing error: {exc}")

            if file_path is not None and raw_line is not None:
                task_key = _queue_key(
                    file_path,
                    line_number,
                    raw_line,
                )

        finally:
            with QUEUE_LOCK:
                if task_key is not None:
                    QUEUED_IDS.discard(task_key)

            PROCESSING_QUEUE.task_done()

        if (
            retry_task
            and not STOP_EVENT.is_set()
            and file_path is not None
            and raw_line is not None
        ):
            time.sleep(RETRY_DELAY_SECONDS)

            with QUEUE_LOCK:
                if task_key not in QUEUED_IDS:
                    QUEUED_IDS.add(task_key)
                    PROCESSING_QUEUE.put(
                        (str(file_path), line_number, raw_line)
                    )



def start_invalid_processor():
    """Start invalid-message processing and failed-telemetry recovery."""
    _rebuild_queue()

    invalid_worker = threading.Thread(
        target=invalid_processor_worker,
        name="invalid-telemetry-processor",
        daemon=True,
    )
    invalid_worker.start()

    failed_worker = threading.Thread(
        target=recovery_worker,
        args=(STOP_EVENT, 30),
        name="failed-telemetry-recovery",
        daemon=True,
    )
    failed_worker.start()

    print("[RECOVERY] Invalid-message processor started.")
    print("[RECOVERY] Failed-telemetry recovery worker started.")

    return invalid_worker, failed_worker



def validate_telemetry(payload):
    """Validate the payload using the Telemetry model."""
    if not isinstance(payload, dict):
        return False, "Telemetry payload must be a JSON object."

    try:
        Telemetry.model_validate(payload)
        return True, "Valid telemetry."

    except (ValidationError, ValueError, TypeError) as exc:
        return False, str(exc)


def _update_raw_status(
    record_id,
    validation_status,
    processing_status,
    reason=None,
):
    """Update raw database status without masking pipeline errors."""
    if record_id is None:
        return

    try:
        update_raw_message_status(
            record_id=record_id,
            validation_status=validation_status,
            processing_status=processing_status,
            reason=reason,
        )

    except Exception as exc:
        print(f"[RAW] Could not update record id={record_id}: {exc}")


def _record_conflict(payload, reason: str):
    """Audit a telemetry conflict using the recovery service."""
    from services.telemetry_recovery_service import record_reprocessed

    record_reprocessed(payload, reason)


def on_connect(client, userdata, flags, reason_code, properties):
    """Subscribe to the configured MQTT topic after connecting."""
    if reason_code == 0:
        print(f"[MQTT] Connected to {MQTT_BROKER}:{MQTT_PORT}")

        try:
            result = client.subscribe(MQTT_TOPIC, qos=1)

            if result is None:
                print(f"[MQTT] Subscribed to {MQTT_TOPIC}")
                return

            if isinstance(result, tuple):
                subscribe_result = result[0]
            else:
                subscribe_result = result

            if subscribe_result == mqtt.MQTT_ERR_SUCCESS:
                print(f"[MQTT] Subscribed to {MQTT_TOPIC}")
            else:
                print(
                    "[MQTT] Subscription failed: "
                    f"result={subscribe_result}, topic={MQTT_TOPIC}"
                )

        except Exception as exc:
            print(f"[MQTT] Subscription error: {exc}")

    else:
        print(f"[MQTT] Connection failed: {reason_code}")


def on_disconnect(
    client,
    userdata,
    disconnect_flags,
    reason_code,
    properties,
):
    """Log MQTT disconnections."""
    print(f"[MQTT] Disconnected: {reason_code}")


def on_message(client, userdata, message):
    """Archive raw MQTT bytes, then validate and process telemetry."""
    raw_bytes = message.payload
    topic = message.topic
    raw_record_id = None

    # 1. Archive the exact incoming payload.
    try:
        raw_record_id = save_raw_message(
            raw_payload=raw_bytes,
            topic=topic,
        )
        print(f"[RAW] Stored message id={raw_record_id}, topic={topic}")

    except Exception as exc:
        print(f"[RAW] CRITICAL: Could not archive incoming message: {exc}")

    # 2. Decode UTF-8.
    try:
        raw_text = raw_bytes.decode("utf-8")

    except UnicodeDecodeError as exc:
        reason = f"Invalid UTF-8: {exc}"

        try:
            save_invalid_message(
                raw_bytes.decode("utf-8", errors="replace"),
                topic,
                reason,
            )
            _update_raw_status(
                raw_record_id,
                "invalid",
                "queued_invalid",
                reason,
            )

        except Exception as storage_exc:
            _update_raw_status(
                raw_record_id,
                "invalid",
                "failed",
                reason,
            )
            print(
                f"[INVALID] Could not store invalid message: {storage_exc}"
            )

        return

    # 3. Parse JSON.
    try:
        payload = json.loads(raw_text)

    except (json.JSONDecodeError, ValueError) as exc:
        reason = f"Malformed JSON: {exc}"

        try:
            save_invalid_message(raw_text, topic, reason)
            _update_raw_status(
                raw_record_id,
                "invalid",
                "queued_invalid",
                reason,
            )

        except Exception as storage_exc:
            _update_raw_status(
                raw_record_id,
                "invalid",
                "failed",
                reason,
            )
            print(
                f"[INVALID] Could not store malformed JSON: {storage_exc}"
            )

        return

    # 4. Validate telemetry structure.
    is_valid, validation_reason = validate_telemetry(payload)

    if not is_valid:
        try:
            save_invalid_message(
                payload,
                topic,
                validation_reason,
            )
            _update_raw_status(
                raw_record_id,
                "invalid",
                "queued_invalid",
                validation_reason,
            )

        except Exception as storage_exc:
            _update_raw_status(
                raw_record_id,
                "invalid",
                "failed",
                validation_reason,
            )
            print(
                f"[INVALID] Could not store invalid telemetry: {storage_exc}"
            )

        return

    # 5. Save valid telemetry.
    try:
        telemetry = Telemetry.model_validate(payload)
        result = save_telemetry(telemetry)

        if result == "duplicate":
            _update_raw_status(
                raw_record_id,
                "valid",
                "duplicate",
            )
            print(
                "[MQTT] Duplicate telemetry ignored: "
                f"device_id={getattr(telemetry, 'device_id', 'unknown')}"
            )

        else:
            _update_raw_status(
                raw_record_id,
                "valid",
                "saved",
            )
            print(
                "[MQTT] Telemetry saved: "
                f"device_id={getattr(telemetry, 'device_id', 'unknown')}"
            )

    except TelemetryConflictError as exc:
        reason = str(exc)

        try:
            _record_conflict(payload, reason)
            _update_raw_status(
                raw_record_id,
                "valid",
                "conflict",
                reason,
            )
            print(f"[CONFLICT] Telemetry conflict audited: {reason}")

        except Exception as audit_exc:
            _store_failed_and_update_raw(
                raw_record_id,
                payload,
                topic,
                f"Conflict audit failed: {audit_exc}",
            )

    except ValueError as exc:
        reason = str(exc)

        try:
            save_invalid_message(payload, topic, reason)
            _update_raw_status(
                raw_record_id,
                "invalid",
                "queued_invalid",
                reason,
            )

        except Exception as storage_exc:
            _update_raw_status(
                raw_record_id,
                "invalid",
                "failed",
                reason,
            )
            print(f"[INVALID] Could not store message: {storage_exc}")

    except (RuntimeError, OSError) as exc:
        _store_failed_and_update_raw(
            raw_record_id,
            payload,
            topic,
            f"{type(exc).__name__}: {exc}",
        )

    except Exception as exc:
        _store_failed_and_update_raw(
            raw_record_id,
            payload,
            topic,
            f"Unexpected error: {type(exc).__name__}: {exc}",
        )


def main():
    """Initialize databases and start the MQTT subscriber."""
    ensure_directories()
    initialize_raw_database()
    initialize_database()

    start_invalid_processor()

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=MQTT_CLIENT_ID,
    )

    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    try:
        print(f"[MQTT] Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
        client.connect(
            MQTT_BROKER,
            MQTT_PORT,
            keepalive=60,
        )
        client.loop_forever()

    except KeyboardInterrupt:
        print("\n[MQTT] Shutdown requested.")

    except Exception as exc:
        print(f"[MQTT] Subscriber stopped due to error: {exc}")
        raise

    finally:
        STOP_EVENT.set()

        try:
            client.disconnect()
        except Exception:
            pass

        print("[MQTT] Subscriber stopped.")


if __name__ == "__main__":
    main()
