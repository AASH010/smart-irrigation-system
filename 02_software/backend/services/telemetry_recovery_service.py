
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from models.telemetry import Telemetry
from repositories.telemetry_repository import (
    TelemetryConflictError,
    save_telemetry,
)


BACKEND_DIR = Path(__file__).resolve().parents[1]
STORAGE_DIR = BACKEND_DIR / "storage"

FAILED_DIR = STORAGE_DIR / "failed"
INVALID_DIR = STORAGE_DIR / "invalid"
REPROCESSED_DIR = STORAGE_DIR / "reprocessed"

MAX_RETRIES = int(
    os.getenv("TELEMETRY_RECOVERY_MAX_RETRIES", "3")
)

# Internal marker used only in memory while preserving a malformed
# JSONL source line. It is never written as a replacement for that line.
_PRESERVE_RAW_LINE_KEY = "__recovery_preserve_raw_jsonl_line__"

_lock = threading.RLock()


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_directories() -> None:
    for directory in (
        FAILED_DIR,
        INVALID_DIR,
        REPROCESSED_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def _append_jsonl(
    directory: Path,
    record: dict[str, Any],
) -> Path:
    """Append a durable JSON record, rotating failed/invalid files."""
    _ensure_directories()

    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    serialized = (
        json.dumps(
            record,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")

    if directory == REPROCESSED_DIR:
        with _lock:
            path = directory / f"reprocessed_{day}.jsonl"

            with path.open("ab") as file:
                file.write(serialized)
                file.flush()
                os.fsync(file.fileno())

        return path

    max_size = int(
        os.getenv("INVALID_FILE_MAX_MB", "500")
    ) * 1024 * 1024

    if max_size < 1 or len(serialized) > max_size:
        raise ValueError(
            "JSONL record exceeds the configured file size limit."
        )

    prefix = directory.name

    with _lock:
        index = 1

        while True:
            path = directory / (
                f"{prefix}_{day}_{index:04d}.jsonl"
            )

            current_size = (
                path.stat().st_size if path.exists() else 0
            )

            if current_size + len(serialized) <= max_size:
                with path.open("ab") as file:
                    file.write(serialized)
                    file.flush()
                    os.fsync(file.fileno())

                return path

            index += 1


def record_failed(
    raw_payload: Any,
    reason: str,
    attempts: int = 0,
) -> Path:
    return _append_jsonl(
        FAILED_DIR,
        {
            "recorded_at": _timestamp(),
            "raw_payload": raw_payload,
            "reason": reason,
            "attempts": attempts,
        },
    )


def record_invalid(
    raw_payload: Any,
    reason: str,
) -> Path:
    return _append_jsonl(
        INVALID_DIR,
        {
            "received_at": _timestamp(),
            "topic": "telemetry-recovery",
            "reason": reason,
            "raw_payload": raw_payload,
        },
    )


def record_reprocessed(
    raw_payload: Any,
    status: str,
    reason: str | None = None,
    attempts: int = 0,
) -> Path:
    return _append_jsonl(
        REPROCESSED_DIR,
        {
            "processed_at": _timestamp(),
            "status": status,
            "raw_payload": raw_payload,
            "reason": reason,
            "attempts": attempts,
        },
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """
    Read JSON objects while preserving malformed source lines.

    A malformed line is audited and returned as an internal marker.
    The caller must keep that marker in the source file until it can
    be safely handled. If auditing fails, the exception propagates,
    and the original source file is left untouched.
    """
    records: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                # Audit first. If this fails, do not rewrite the source.
                record_reprocessed(
                    raw_payload=line.rstrip("\r\n"),
                    status="invalid_jsonl_record",
                    reason=(
                        f"Malformed JSONL at "
                        f"{path.name}:{line_number}: {exc}"
                    ),
                )

                # Preserve the exact original line, including its newline.
                records.append(
                    {
                        _PRESERVE_RAW_LINE_KEY: line,
                    }
                )
                continue

            if isinstance(record, dict):
                records.append(record)
            else:
                record_reprocessed(
                    raw_payload=line.rstrip("\r\n"),
                    status="invalid_jsonl_record",
                    reason=(
                        f"Expected JSON object at "
                        f"{path.name}:{line_number}"
                    ),
                )

                records.append(
                    {
                        _PRESERVE_RAW_LINE_KEY: line,
                    }
                )

    return records


def _serialize_payload(payload: Any) -> str:
    if isinstance(payload, str):
        return payload

    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
    )


def _decode_payload(raw_payload: Any) -> dict[str, Any]:
    if isinstance(raw_payload, dict):
        payload = raw_payload
    elif isinstance(raw_payload, str):
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Stored payload is not valid JSON: {exc}"
            ) from exc
    else:
        raise ValueError(
            "Stored telemetry payload must be a JSON object or string."
        )

    if not isinstance(payload, dict):
        raise ValueError(
            "Telemetry payload must decode to a JSON object."
        )

    return payload


def _archive_processed_file(path: Path) -> None:
    """
    Remove a failed source file only after every record has a durable
    outcome. This function does not delete files in INVALID_DIR.
    """
    path.unlink(missing_ok=True)


def _write_remaining_records(
    source_path: Path,
    records: list[dict[str, Any]],
) -> None:
    """
    Atomically replace the failed source with records that still need
    attention. Malformed JSONL lines are written back verbatim.
    """
    temporary_path = source_path.with_suffix(".tmp")

    try:
        with temporary_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as file:
            for record in records:
                if _PRESERVE_RAW_LINE_KEY in record:
                    raw_line = record[_PRESERVE_RAW_LINE_KEY]
                    file.write(raw_line)

                    if not raw_line.endswith(("\n", "\r")):
                        file.write("\n")

                    continue

                file.write(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                        allow_nan=False,
                    )
                    + "\n"
                )

            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary_path, source_path)

        # Best-effort directory sync so the replacement is more durable
        # across an unexpected system shutdown. Not all platforms support it.
        try:
            directory_fd = os.open(
                str(source_path.parent),
                os.O_RDONLY,
            )
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass

    except OSError:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def recover_failed_messages(
    max_retries: int | None = None,
) -> dict[str, int]:
    """Retry failed telemetry and retain records needing further attention."""
    retries_allowed = (
        MAX_RETRIES if max_retries is None else max_retries
    )

    if (
        isinstance(retries_allowed, bool)
        or not isinstance(retries_allowed, int)
        or retries_allowed < 1
    ):
        raise ValueError("max_retries must be a positive integer.")

    _ensure_directories()

    summary = {
        "files_processed": 0,
        "recovered": 0,
        "duplicates": 0,
        "conflicts": 0,
        "still_failed": 0,
        "invalid": 0,
    }

    # Prevent overlapping recovery cycles from rewriting the same file.
    with _lock:
        files = sorted(FAILED_DIR.glob("failed_*.jsonl"))

        for path in files:
            summary["files_processed"] += 1

            try:
                records = _read_jsonl(path)
            except OSError as exc:
                print(
                    f"[RECOVERY] Could not read or audit "
                    f"{path.name}: {exc}"
                )
                summary["still_failed"] += 1
                continue

            remaining_records: list[dict[str, Any]] = []

            for record in records:
                # Never attempt to decode or discard a malformed source
                # line. Keep it verbatim in the failed file.
                if _PRESERVE_RAW_LINE_KEY in record:
                    remaining_records.append(record)
                    summary["still_failed"] += 1
                    continue

                raw_payload = record.get("raw_payload")
                attempts = record.get("attempts", 0)

                if (
                    isinstance(attempts, bool)
                    or not isinstance(attempts, int)
                    or attempts < 0
                ):
                    attempts = 0

                if attempts >= retries_allowed:
                    remaining_records.append(record)
                    summary["still_failed"] += 1
                    continue

                try:
                    serialized_payload = _serialize_payload(raw_payload)
                    payload = _decode_payload(raw_payload)
                    telemetry = Telemetry.model_validate(payload)
                    result = save_telemetry(telemetry)

                except (ValueError, TypeError, ValidationError) as exc:
                    try:
                        record_invalid(
                            raw_payload=serialized_payload,
                            reason=f"Recovery validation failed: {exc}"
                        )
                        record_reprocessed(
                            raw_payload=raw_payload,
                            status="invalid",
                            reason=str(exc),
                            attempts=attempts + 1,
                        )
                    except (OSError, ValueError) as audit_exc:
                        updated = dict(record)
                        updated["attempts"] = attempts + 1
                        updated["last_error"] = str(audit_exc)
                        updated["last_attempt_at"] = _timestamp()
                        remaining_records.append(updated)
                        summary["still_failed"] += 1
                        continue

                    summary["invalid"] += 1

                except TelemetryConflictError as exc:
                    try:
                        record_reprocessed(
                            raw_payload=raw_payload,
                            status="conflict",
                            reason=str(exc),
                            attempts=attempts + 1,
                        )
                    except (OSError, ValueError) as audit_exc:
                        updated = dict(record)
                        updated["attempts"] = attempts + 1
                        updated["last_error"] = str(audit_exc)
                        updated["last_attempt_at"] = _timestamp()
                        remaining_records.append(updated)
                        summary["still_failed"] += 1
                        continue

                    summary["conflicts"] += 1

                except Exception as exc:
                    # Keep the source record if the database or another
                    # dependency fails. Record the retry information.
                    updated = dict(record)
                    updated["attempts"] = attempts + 1
                    updated["last_attempt_at"] = _timestamp()
                    updated["last_error"] = str(exc)
                    remaining_records.append(updated)

                    try:
                        record_reprocessed(
                            raw_payload=raw_payload,
                            status="failed",
                            reason=str(exc),
                            attempts=attempts + 1,
                        )
                    except (OSError, ValueError) as audit_exc:
                        print(
                            "[RECOVERY] Could not write failure audit "
                            f"for {path.name}: {audit_exc}"
                        )

                    summary["still_failed"] += 1

                else:
                    try:
                        record_reprocessed(
                            raw_payload=raw_payload,
                            status=(
                                "duplicate"
                                if result == "duplicate"
                                else "recovered"
                            ),
                            attempts=attempts + 1,
                        )
                    except (OSError, ValueError) as audit_exc:
                        # A DB write may have succeeded. Keep the original
                        # record so a later retry can be safely deduplicated.
                        updated = dict(record)
                        updated["attempts"] = attempts + 1
                        updated["last_error"] = (
                            f"Audit write failed: {audit_exc}"
                        )
                        updated["last_attempt_at"] = _timestamp()
                        remaining_records.append(updated)
                        summary["still_failed"] += 1
                        continue

                    if result == "duplicate":
                        summary["duplicates"] += 1
                    else:
                        summary["recovered"] += 1

            # Do not remove the source file unless every record has a
            # durable outcome and no records need to be retained.
            if remaining_records:
                try:
                    _write_remaining_records(path, remaining_records)
                except OSError as exc:
                    # The original file should remain if replacement fails.
                    print(
                        f"[RECOVERY] Could not update "
                        f"{path.name}: {exc}"
                    )
                    summary["still_failed"] += 1
            else:
                try:
                    _archive_processed_file(path)
                except OSError as exc:
                    print(
                        f"[RECOVERY] Could not archive "
                        f"{path.name}: {exc}"
                    )
                    summary["still_failed"] += 1

    return summary


def recovery_worker(
    stop_event,
    interval_seconds=30,
):
    """Retry failed telemetry periodically until shutdown."""
    if (
        isinstance(interval_seconds, bool)
        or not isinstance(interval_seconds, (int, float))
        or interval_seconds < 1
    ):
        raise ValueError("interval_seconds must be at least 1")

    print(
        f"[RECOVERY] Failed-telemetry worker started "
        f"(interval={interval_seconds}s)."
    )

    while not stop_event.is_set():
        try:
            summary = recover_failed_messages()

            if any(summary.values()):
                print(f"[RECOVERY] Cycle summary: {summary}")

        except Exception as exc:
            print(
                "[RECOVERY] Worker cycle failed: "
                f"{type(exc).__name__}: {exc}"
            )

        if stop_event.wait(interval_seconds):
            break

    print("[RECOVERY] Failed-telemetry worker stopped.")
