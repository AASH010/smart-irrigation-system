
import json

import pytest

import services.telemetry_recovery_service as recovery
from models.telemetry import Telemetry


@pytest.fixture
def isolated_storage(tmp_path, monkeypatch):
    """Keep recovery tests isolated from real project storage."""
    storage = tmp_path / "storage"

    failed_dir = storage / "failed"
    invalid_dir = storage / "invalid"
    reprocessed_dir = storage / "reprocessed"

    for directory in (failed_dir, invalid_dir, reprocessed_dir):
        directory.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(recovery, "STORAGE_DIR", storage)
    monkeypatch.setattr(recovery, "FAILED_DIR", failed_dir)
    monkeypatch.setattr(recovery, "INVALID_DIR", invalid_dir)
    monkeypatch.setattr(recovery, "REPROCESSED_DIR", reprocessed_dir)

    return {
        "storage": storage,
        "failed": failed_dir,
        "invalid": invalid_dir,
        "reprocessed": reprocessed_dir,
    }


@pytest.fixture
def valid_payload():
    return {
        "device_id": "device-001",
        "timestamp": 1797000000,
        "sensors": {
            "soil_moisture_pct": 45.5,
            "soil_temperature_c": 24.2,
            "soil_ph": 6.5,
            "nitrogen_mg_kg": 20.0,
            "phosphorus_mg_kg": 10.0,
            "potassium_mg_kg": 15.0,
        },
        "actuators": {
            "pump_state": False,
        },
    }


def read_jsonl(path):
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as file:
        return [
            json.loads(line)
            for line in file
            if line.strip()
        ]


def read_all_jsonl(directory):
    records = []

    for path in sorted(directory.glob("*.jsonl")):
        records.extend(read_jsonl(path))

    return records


def write_failed_record(directory, payload, attempts=0):
    path = directory / "failed_test.jsonl"

    record = {
        "raw_payload": payload,
        "reason": "Temporary database failure",
        "attempts": attempts,
    }

    path.write_text(
        json.dumps(record, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return path


def test_record_failed_writes_message_to_disk(
    isolated_storage,
    valid_payload,
):
    path = recovery.record_failed(
        raw_payload=valid_payload,
        reason="Database temporarily unavailable",
    )

    assert path.exists()
    assert path.parent == isolated_storage["failed"]

    records = read_jsonl(path)

    assert len(records) == 1
    assert records[0]["raw_payload"] == valid_payload
    assert records[0]["reason"] == "Database temporarily unavailable"
    assert records[0]["attempts"] == 0
    assert records[0]["recorded_at"]


def test_record_invalid_writes_message_to_invalid_storage(
    isolated_storage,
):
    invalid_payload = {"device_id": "device-001"}

    path = recovery.record_invalid(
        raw_payload=invalid_payload,
        reason="Missing required telemetry fields",
    )

    assert path.exists()
    assert path.parent == isolated_storage["invalid"]

    records = read_jsonl(path)

    assert len(records) == 1
    assert records[0]["raw_payload"] == invalid_payload
    assert records[0]["reason"] == "Missing required telemetry fields"


def test_record_reprocessed_writes_processing_result(
    isolated_storage,
    valid_payload,
):
    path = recovery.record_reprocessed(
        raw_payload=valid_payload,
        status="recovered",
        attempts=1,
    )

    assert path.exists()
    assert path.parent == isolated_storage["reprocessed"]

    records = read_jsonl(path)

    assert len(records) == 1
    assert records[0]["status"] == "recovered"
    assert records[0]["raw_payload"] == valid_payload
    assert records[0]["attempts"] == 1


def test_recover_failed_messages_recovers_valid_record(
    isolated_storage,
    valid_payload,
    monkeypatch,
):
    source_path = write_failed_record(
        isolated_storage["failed"],
        valid_payload,
    )

    saved_records = []

    def fake_save_telemetry(telemetry):
        assert isinstance(telemetry, Telemetry)
        saved_records.append(telemetry)
        return "saved"

    monkeypatch.setattr(
        recovery,
        "save_telemetry",
        fake_save_telemetry,
    )

    result = recovery.recover_failed_messages()

    assert result["files_processed"] == 1
    assert result["recovered"] == 1
    assert result["duplicates"] == 0
    assert result["still_failed"] == 0
    assert result["invalid"] == 0

    assert len(saved_records) == 1
    assert not source_path.exists()

    audit_records = read_all_jsonl(isolated_storage["reprocessed"])

    assert any(
        record["status"] == "recovered"
        for record in audit_records
    )


def test_recover_failed_messages_handles_duplicate(
    isolated_storage,
    valid_payload,
    monkeypatch,
):
    source_path = write_failed_record(
        isolated_storage["failed"],
        valid_payload,
    )

    monkeypatch.setattr(
        recovery,
        "save_telemetry",
        lambda telemetry: "duplicate",
    )

    result = recovery.recover_failed_messages()

    assert result["duplicates"] == 1
    assert result["recovered"] == 0
    assert result["still_failed"] == 0
    assert not source_path.exists()

    audit_records = read_all_jsonl(isolated_storage["reprocessed"])

    assert any(
        record["status"] == "duplicate"
        for record in audit_records
    )


def test_invalid_payload_is_recorded_and_removed_from_failed(
    isolated_storage,
    monkeypatch,
):
    invalid_payload = {"device_id": "device-001"}

    source_path = write_failed_record(
        isolated_storage["failed"],
        invalid_payload,
    )

    monkeypatch.setattr(
        recovery,
        "save_telemetry",
        lambda telemetry: "saved",
    )

    result = recovery.recover_failed_messages()

    assert result["invalid"] == 1
    assert result["recovered"] == 0
    assert result["still_failed"] == 0
    assert not source_path.exists()

    invalid_records = read_all_jsonl(isolated_storage["invalid"])

    assert len(invalid_records) == 1
    assert invalid_records[0]["raw_payload"] == json.dumps(
        invalid_payload,
        ensure_ascii=False,
        allow_nan=False,
    )

    audit_records = read_all_jsonl(isolated_storage["reprocessed"])

    assert any(
        record["status"] == "invalid"
        for record in audit_records
    )


def test_temporary_database_error_retains_failed_record(
    isolated_storage,
    valid_payload,
    monkeypatch,
):
    source_path = write_failed_record(
        isolated_storage["failed"],
        valid_payload,
    )

    def fail_to_save(telemetry):
        raise RuntimeError("Database temporarily unavailable")

    monkeypatch.setattr(
        recovery,
        "save_telemetry",
        fail_to_save,
    )

    result = recovery.recover_failed_messages()

    assert result["still_failed"] == 1
    assert source_path.exists()

    remaining = read_jsonl(source_path)

    assert len(remaining) == 1
    assert remaining[0]["attempts"] == 1
    assert "Database temporarily unavailable" in remaining[0]["last_error"]


def test_max_retries_keeps_record_without_another_save_attempt(
    isolated_storage,
    valid_payload,
    monkeypatch,
):
    source_path = write_failed_record(
        isolated_storage["failed"],
        valid_payload,
        attempts=3,
    )

    calls = []

    def fake_save_telemetry(telemetry):
        calls.append(telemetry)
        return "saved"

    monkeypatch.setattr(
        recovery,
        "save_telemetry",
        fake_save_telemetry,
    )

    result = recovery.recover_failed_messages(max_retries=3)

    assert result["still_failed"] == 1
    assert result["recovered"] == 0
    assert calls == []
    assert source_path.exists()


def test_invalid_max_retries_is_rejected(
    isolated_storage,
):
    with pytest.raises(ValueError):
        recovery.recover_failed_messages(max_retries=0)


def test_original_invalid_files_are_not_deleted(
    isolated_storage,
    valid_payload,
):
    original_path = (
        isolated_storage["invalid"] / "invalid_original.jsonl"
    )

    original_path.write_text(
        json.dumps(valid_payload) + "\n",
        encoding="utf-8",
    )

    recovery._ensure_directories()

    assert original_path.exists()
    assert len(read_jsonl(original_path)) == 1
id="recovery-tests-01"
