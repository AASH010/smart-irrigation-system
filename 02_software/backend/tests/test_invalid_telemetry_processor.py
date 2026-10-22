
import json

import pytest

import services.invalid_telemetry_processor as processor
from models.telemetry import Telemetry
from repositories.telemetry_repository import TelemetryConflictError


@pytest.fixture
def isolated_storage(tmp_path, monkeypatch):
    """Isolate processor files from the project's real storage."""
    invalid_dir = tmp_path / "invalid"
    reprocessed_dir = tmp_path / "reprocessed"

    invalid_dir.mkdir()
    reprocessed_dir.mkdir()

    monkeypatch.setattr(processor, "INVALID_DIR", invalid_dir)
    monkeypatch.setattr(processor, "REPROCESSED_DIR", reprocessed_dir)

    return {
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


def write_invalid_record(directory, payload, record_id="record-001"):
    """Write one invalid JSONL envelope and return its path and line."""
    path = directory / "invalid_test.jsonl"

    envelope = {
        "record_id": record_id,
        "received_at": "2026-10-21T08:00:00+00:00",
        "raw_payload": payload,
        "reason": "Original validation failed",
    }

    raw_line = json.dumps(envelope, ensure_ascii=False) + "\n"
    path.write_text(raw_line, encoding="utf-8")

    return path, raw_line


def read_jsonl(path):
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as handle:
        return [
            json.loads(line)
            for line in handle
            if line.strip()
        ]


def read_all_audits(directory):
    records = []

    for path in sorted(directory.glob("reprocessed_*.jsonl")):
        records.extend(read_jsonl(path))

    return records


def test_normalize_payload_corrects_known_aliases(valid_payload):
    payload = {
        "deviceId": "device-001",
        "timestamp": valid_payload["timestamp"],
        "sensors": {
            "soil_moisture": 45.5,
            "soil_temperature": 24.2,
            "soil_ph_value": 6.5,
            "nitrogen": 20.0,
            "phosphorus": 10.0,
            "potassium": 15.0,
        },
        "actuators": {
            "pumpState": False,
        },
    }

    normalized = processor.normalize_payload(payload)

    assert normalized["device_id"] == "device-001"
    assert normalized["sensors"]["soil_moisture_pct"] == 45.5
    assert normalized["sensors"]["soil_temperature_c"] == 24.2
    assert normalized["sensors"]["soil_ph"] == 6.5
    assert normalized["sensors"]["nitrogen_mg_kg"] == 20.0
    assert normalized["sensors"]["phosphorus_mg_kg"] == 10.0
    assert normalized["sensors"]["potassium_mg_kg"] == 15.0
    assert normalized["actuators"]["pump_state"] is False


def test_normalize_payload_does_not_overwrite_canonical_field(
    valid_payload,
):
    payload = {
        **valid_payload,
        "deviceId": "another-device",
    }

    with pytest.raises(processor.InvalidPayloadError):
        processor.normalize_payload(payload)


def test_normalize_payload_rejects_non_object():
    with pytest.raises(processor.InvalidPayloadError):
        processor.normalize_payload(["not", "an", "object"])


def test_process_invalid_record_saves_valid_payload(
    isolated_storage,
    valid_payload,
    monkeypatch,
):
    path, raw_line = write_invalid_record(
        isolated_storage["invalid"],
        valid_payload,
    )

    saved = []

    def fake_save(telemetry):
        assert isinstance(telemetry, Telemetry)
        saved.append(telemetry)
        return "saved"

    monkeypatch.setattr(processor, "save_telemetry", fake_save)

    status = processor.process_invalid_record(path, 1, raw_line)

    assert status == "saved"
    assert len(saved) == 1
    assert saved[0].device_id == "device-001"

    audits = read_all_audits(isolated_storage["reprocessed"])
    assert len(audits) == 1
    assert audits[0]["status"] == "saved"
    assert audits[0]["source_id"] == "record-001"
    assert audits[0]["source_file"] == path.name
    assert audits[0]["source_line"] == 1


def test_process_invalid_record_saves_payload_with_known_aliases(
    isolated_storage,
    valid_payload,
    monkeypatch,
):
    payload = {
        "deviceID": "device-001",
        "timestamp": valid_payload["timestamp"],
        "sensors": {
            "soil_moisture_percent": 45.5,
            "soil_temperature": 24.2,
            "soil_ph": 6.5,
            "nitrogen": 20.0,
            "phosphorus": 10.0,
            "potassium": 15.0,
        },
        "actuators": {
            "pump_state": False,
        },
    }

    path, raw_line = write_invalid_record(
        isolated_storage["invalid"],
        payload,
    )

    saved = []

    def fake_save(telemetry):
        saved.append(telemetry)
        return "saved"

    monkeypatch.setattr(processor, "save_telemetry", fake_save)

    status = processor.process_invalid_record(path, 1, raw_line)

    assert status == "saved"
    assert len(saved) == 1
    assert saved[0].sensors.soil_moisture_pct == 45.5
    assert saved[0].sensors.soil_temperature_c == 24.2


def test_process_invalid_record_marks_invalid_payload(
    isolated_storage,
    monkeypatch,
):
    payload = {"device_id": "device-001"}

    path, raw_line = write_invalid_record(
        isolated_storage["invalid"],
        payload,
    )

    def should_not_save(telemetry):
        pytest.fail("Invalid payload must not reach the repository")

    monkeypatch.setattr(processor, "save_telemetry", should_not_save)

    status = processor.process_invalid_record(path, 1, raw_line)

    assert status == "invalid"

    audits = read_all_audits(isolated_storage["reprocessed"])
    assert len(audits) == 1
    assert audits[0]["status"] == "invalid"
    assert audits[0]["reason"]


def test_process_invalid_record_rejects_alias_collision(
    isolated_storage,
    valid_payload,
    monkeypatch,
):
    payload = {
        **valid_payload,
        "deviceId": "device-001",
    }

    path, raw_line = write_invalid_record(
        isolated_storage["invalid"],
        payload,
    )

    monkeypatch.setattr(
        processor,
        "save_telemetry",
        lambda telemetry: pytest.fail("Must reject conflicting aliases"),
    )

    status = processor.process_invalid_record(path, 1, raw_line)

    assert status == "invalid"


def test_process_invalid_record_handles_duplicate(
    isolated_storage,
    valid_payload,
    monkeypatch,
):
    path, raw_line = write_invalid_record(
        isolated_storage["invalid"],
        valid_payload,
    )

    monkeypatch.setattr(
        processor,
        "save_telemetry",
        lambda telemetry: "duplicate",
    )

    status = processor.process_invalid_record(path, 1, raw_line)

    assert status == "duplicate"

    audits = read_all_audits(isolated_storage["reprocessed"])
    assert audits[0]["status"] == "duplicate"


def test_process_invalid_record_handles_conflict(
    isolated_storage,
    valid_payload,
    monkeypatch,
):
    path, raw_line = write_invalid_record(
        isolated_storage["invalid"],
        valid_payload,
    )

    def raise_conflict(telemetry):
        raise TelemetryConflictError("Different telemetry already exists")

    monkeypatch.setattr(processor, "save_telemetry", raise_conflict)

    status = processor.process_invalid_record(path, 1, raw_line)

    assert status == "conflict"

    audits = read_all_audits(isolated_storage["reprocessed"])
    assert audits[0]["status"] == "conflict"
    assert "Different telemetry" in audits[0]["reason"]


def test_process_invalid_record_retries_database_error(
    isolated_storage,
    valid_payload,
    monkeypatch,
):
    path, raw_line = write_invalid_record(
        isolated_storage["invalid"],
        valid_payload,
    )

    def raise_database_error(telemetry):
        raise RuntimeError("Database temporarily unavailable")

    monkeypatch.setattr(
        processor,
        "save_telemetry",
        raise_database_error,
    )

    status = processor.process_invalid_record(path, 1, raw_line)

    assert status == "retry"

    audits = read_all_audits(isolated_storage["reprocessed"])
    assert audits[0]["status"] == "retry"
    assert "Database temporarily unavailable" in audits[0]["reason"]


def test_audit_failure_returns_retry(
    isolated_storage,
    valid_payload,
    monkeypatch,
):
    path, raw_line = write_invalid_record(
        isolated_storage["invalid"],
        valid_payload,
    )

    monkeypatch.setattr(
        processor,
        "save_telemetry",
        lambda telemetry: "saved",
    )

    def fail_audit(record):
        raise OSError("Disk unavailable")

    monkeypatch.setattr(processor, "_append_audit", fail_audit)

    status = processor.process_invalid_record(path, 1, raw_line)

    assert status == "retry"


def test_original_invalid_file_is_not_deleted(
    isolated_storage,
    valid_payload,
    monkeypatch,
):
    path, raw_line = write_invalid_record(
        isolated_storage["invalid"],
        valid_payload,
    )

    monkeypatch.setattr(
        processor,
        "save_telemetry",
        lambda telemetry: "saved",
    )

    status = processor.process_invalid_record(path, 1, raw_line)

    assert status == "saved"
    assert path.exists()
    assert len(read_jsonl(path)) == 1


def test_iter_pending_records_skips_terminal_source_ids(
    isolated_storage,
    valid_payload,
    monkeypatch,
):
    path, raw_line = write_invalid_record(
        isolated_storage["invalid"],
        valid_payload,
        record_id="already-processed",
    )

    audit_path = (
        isolated_storage["reprocessed"] / "reprocessed_test.jsonl"
    )
    audit_path.write_text(
        json.dumps({
            "source_id": "already-processed",
            "status": "saved",
        }) + "\n",
        encoding="utf-8",
    )

    pending = list(processor.iter_pending_records())

    assert pending == []
    assert path.exists()


def test_iter_pending_records_keeps_nonterminal_records(
    isolated_storage,
    valid_payload,
):
    path, raw_line = write_invalid_record(
        isolated_storage["invalid"],
        valid_payload,
        record_id="retry-record",
    )

    audit_path = (
        isolated_storage["reprocessed"] / "reprocessed_test.jsonl"
    )
    audit_path.write_text(
        json.dumps({
            "source_id": "retry-record",
            "status": "retry",
        }) + "\n",
        encoding="utf-8",
    )

    pending = list(processor.iter_pending_records())

    assert len(pending) == 1
    assert pending[0][0] == path
    assert pending[0][1] == 1
    assert pending[0][2] == raw_line


def test_process_invalid_files_respects_batch_size(
    isolated_storage,
    valid_payload,
    monkeypatch,
):
    path = isolated_storage["invalid"] / "invalid_batch.jsonl"

    records = []
    for index in range(3):
        envelope = {
            "record_id": f"batch-{index}",
            "raw_payload": {
                **valid_payload,
                "device_id": f"device-{index}",
            },
        }
        records.append(json.dumps(envelope))

    path.write_text("\n".join(records) + "\n", encoding="utf-8")

    saved = []

    def fake_save(telemetry):
        saved.append(telemetry.device_id)
        return "saved"

    monkeypatch.setattr(processor, "save_telemetry", fake_save)

    result = processor.process_invalid_files(batch_size=2)

    assert result["saved"] == 2
    assert result["duplicate"] == 0
    assert result["invalid"] == 0
    assert result["conflict"] == 0
    assert result["retry"] == 0
    assert len(saved) == 2


@pytest.mark.parametrize("batch_size", [0, -1, True, 1.5, "10", None])
def test_process_invalid_files_rejects_invalid_batch_size(
    batch_size,
):
    with pytest.raises(ValueError):
        processor.process_invalid_files(batch_size=batch_size)
