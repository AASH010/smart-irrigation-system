
import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from models.telemetry import Telemetry
from repositories.telemetry_repository import (
    TelemetryConflictError,
    save_telemetry,
)


BACKEND_DIR = Path(__file__).resolve().parents[1]
STORAGE_DIR = BACKEND_DIR / "storage"
INVALID_DIR = STORAGE_DIR / "invalid"
REPROCESSED_DIR = STORAGE_DIR / "reprocessed"

FILE_LOCK = threading.Lock()

TERMINAL_STATUSES = {
    "saved",
    "duplicate",
    "invalid",
    "conflict",
}


class InvalidPayloadError(ValueError):
    """Raised when a stored message cannot be safely interpreted."""


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _ensure_directories():
    INVALID_DIR.mkdir(parents=True, exist_ok=True)
    REPROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def _source_id(file_path, line_number, raw_line):
    """Prefer the persistent record_id from the raw JSONL envelope."""
    try:
        record = json.loads(raw_line)

        if isinstance(record, dict):
            record_id = record.get("record_id")

            if isinstance(record_id, str) and record_id:
                return record_id

    except (json.JSONDecodeError, TypeError):
        pass

    identity = (
        f"{Path(file_path).name}\n"
        f"{line_number}\n"
        f"{raw_line}"
    )

    return hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()


def _audit_path():
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return REPROCESSED_DIR / f"reprocessed_{day}.jsonl"


def _append_audit(record):
    _ensure_directories()

    line = json.dumps(
        record,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"

    with FILE_LOCK:
        with _audit_path().open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())


def load_terminal_source_ids():
    """Return source IDs whose latest recorded status is terminal."""
    _ensure_directories()
    statuses = {}

    for path in sorted(REPROCESSED_DIR.glob("reprocessed_*.jsonl")):
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue

                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if not isinstance(record, dict):
                        continue

                    source_id = record.get("source_id")
                    status = record.get("status")

                    if source_id and status:
                        statuses[source_id] = status

        except OSError as exc:
            print(
                f"[PROCESSOR] Could not read {path.name}: {exc}"
            )

    return {
        source_id
        for source_id, status in statuses.items()
        if status in TERMINAL_STATUSES
    }


def _rename_keys(data, aliases):
    """Rename known aliases without overwriting canonical fields."""
    if not isinstance(data, dict):
        return data

    result = dict(data)

    for old_name, new_name in aliases.items():
        if old_name not in result:
            continue

        if new_name in result:
            raise InvalidPayloadError(
                f"Both alias '{old_name}' and canonical field "
                f"'{new_name}' are present."
            )

        result[new_name] = result.pop(old_name)

    return result


def _normalize_timestamp(value):
    """
    Convert a valid ISO-8601 timestamp to Unix seconds.
    Never invent a timestamp for an invalid or missing value.
    """
    if isinstance(value, bool):
        raise InvalidPayloadError(
            "Boolean timestamp is not supported."
        )

    if isinstance(value, int):
        return value

    if not isinstance(value, str):
        raise InvalidPayloadError(
            "Timestamp must be a positive integer or valid ISO-8601 string."
        )

    text = value.strip()

    if not text:
        raise InvalidPayloadError("Timestamp is empty.")

    # Support ISO timestamps ending in Z.
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise InvalidPayloadError(
            f"Invalid ISO-8601 timestamp: {value!r}"
        ) from exc

    # A timestamp without timezone is ambiguous. Do not assume UTC.
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InvalidPayloadError(
            "ISO-8601 timestamp must include a timezone."
        )

    try:
        return int(parsed.timestamp())
    except (ValueError, OverflowError, OSError) as exc:
        raise InvalidPayloadError(
            "Timestamp is outside the supported range."
        ) from exc


def normalize_payload(payload):
    """
    Normalize known legacy field names and message layouts.
    Sensor values are never guessed or silently clamped.
    """
    if not isinstance(payload, dict):
        raise InvalidPayloadError(
            "Payload must be a JSON object."
        )

    data = _rename_keys(
        payload,
        {
            "deviceId": "device_id",
            "deviceID": "device_id",
        },
    )

    if "timestamp" in data:
        data["timestamp"] = _normalize_timestamp(
            data["timestamp"]
        )

    root_sensor_names = {
        "soil_moisture_pct",
        "soil_temperature_c",
        "soil_ph",
        "nitrogen_mg_kg",
        "phosphorus_mg_kg",
        "potassium_mg_kg",
    }

    root_sensor_fields = root_sensor_names.intersection(data)

    # Convert the simulator's legacy flat sensor fields to sensors.
    if root_sensor_fields:
        if "sensors" in data:
            raise InvalidPayloadError(
                "Both nested sensors and root-level sensor fields "
                "are present; refusing to merge ambiguous data."
            )

        data["sensors"] = {
            name: data.pop(name)
            for name in root_sensor_fields
        }

    if isinstance(data.get("sensors"), dict):
        data["sensors"] = _rename_keys(
            data["sensors"],
            {
                "soil_moisture": "soil_moisture_pct",
                "soil_moisture_percent": "soil_moisture_pct",
                "soil_temperature": "soil_temperature_c",
                "soil_ph_value": "soil_ph",
                "nitrogen": "nitrogen_mg_kg",
                "phosphorus": "phosphorus_mg_kg",
                "potassium": "potassium_mg_kg",
            },
        )

    # Convert the simulator's legacy root-level pump field.
    if "pump_state" in data:
        if "actuators" in data:
            raise InvalidPayloadError(
                "Both nested actuators and root-level pump_state "
                "are present; refusing to merge ambiguous data."
            )

        data["actuators"] = {
            "pump_state": data.pop("pump_state")
        }

    if isinstance(data.get("actuators"), dict):
        data["actuators"] = _rename_keys(
            data["actuators"],
            {
                "pumpState": "pump_state",
            },
        )

    return data


def _extract_payload(record):
    """Extract the payload from a stored raw-message envelope."""
    if not isinstance(record, dict):
        raise InvalidPayloadError(
            "Stored record must be a JSON object."
        )

    if "raw_payload" not in record:
        return record

    payload = record["raw_payload"]

    if isinstance(payload, dict):
        return payload

    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise InvalidPayloadError(
                f"raw_payload is not valid JSON: {exc}"
            ) from exc

        if not isinstance(parsed, dict):
            raise InvalidPayloadError(
                "raw_payload must decode to a JSON object."
            )

        return parsed

    raise InvalidPayloadError(
        "raw_payload must be a JSON object or JSON string."
    )


def _process_payload(raw_record):
    payload = normalize_payload(
        _extract_payload(raw_record)
    )

    telemetry = Telemetry.model_validate(payload)
    result = save_telemetry(telemetry)

    return telemetry.model_dump(), result


def process_invalid_record(file_path, line_number, raw_line):
    """
    Process one invalid JSONL record.

    Returns:
        saved, duplicate, invalid, conflict, or retry.
    """
    file_path = Path(file_path)
    source_id = _source_id(
        file_path,
        line_number,
        raw_line,
    )

    try:
        record = json.loads(raw_line)
        saved_data, save_result = _process_payload(record)

        status = (
            "duplicate"
            if save_result == "duplicate"
            else "saved"
        )

        audit = {
            "processed_at": _utc_now(),
            "source_id": source_id,
            "source_file": file_path.name,
            "source_line": line_number,
            "status": status,
            "reason": (
                "Identical telemetry already exists."
                if status == "duplicate"
                else "Payload normalized, validated and saved."
            ),
            "device_id": saved_data.get("device_id"),
            "timestamp": saved_data.get("timestamp"),
        }

    except (
        json.JSONDecodeError,
        InvalidPayloadError,
        ValidationError,
        ValueError,
    ) as exc:
        status = "invalid"
        audit = {
            "processed_at": _utc_now(),
            "source_id": source_id,
            "source_file": file_path.name,
            "source_line": line_number,
            "status": status,
            "reason": str(exc),
        }

    except TelemetryConflictError as exc:
        status = "conflict"
        audit = {
            "processed_at": _utc_now(),
            "source_id": source_id,
            "source_file": file_path.name,
            "source_line": line_number,
            "status": status,
            "reason": str(exc),
        }

    except Exception as exc:
        # Unexpected database/filesystem failures remain retryable.
        status = "retry"
        audit = {
            "processed_at": _utc_now(),
            "source_id": source_id,
            "source_file": file_path.name,
            "source_line": line_number,
            "status": status,
            "reason": f"{type(exc).__name__}: {exc}",
        }

    try:
        _append_audit(audit)
    except OSError as exc:
        print(f"[PROCESSOR] Audit write failed: {exc}")
        return "retry"

    print(
        f"[PROCESSOR] {status.upper()} "
        f"{file_path.name}:{line_number} - {audit['reason']}"
    )

    return status


def iter_pending_records():
    """Yield records that do not have a terminal audit status."""
    terminal_ids = load_terminal_source_ids()

    for file_path in sorted(INVALID_DIR.glob("invalid_*.jsonl")):
        try:
            with file_path.open("r", encoding="utf-8") as handle:
                for line_number, raw_line in enumerate(handle, start=1):
                    if not raw_line.strip():
                        continue

                    source_id = _source_id(
                        file_path,
                        line_number,
                        raw_line,
                    )

                    if source_id in terminal_ids:
                        continue

                    yield file_path, line_number, raw_line

        except OSError as exc:
            print(
                f"[PROCESSOR] Could not read "
                f"{file_path.name}: {exc}"
            )


def process_invalid_files(batch_size=100):
    """Process up to batch_size pending records."""
    if (
        isinstance(batch_size, bool)
        or not isinstance(batch_size, int)
        or batch_size < 1
    ):
        raise ValueError(
            "batch_size must be a positive integer."
        )

    counts = {
        "saved": 0,
        "duplicate": 0,
        "invalid": 0,
        "conflict": 0,
        "retry": 0,
    }

    for file_path, line_number, raw_line in iter_pending_records():
        if sum(counts.values()) >= batch_size:
            break

        status = process_invalid_record(
            file_path,
            line_number,
            raw_line,
        )

        if status not in counts:
            status = "retry"

        counts[status] += 1

    return counts
