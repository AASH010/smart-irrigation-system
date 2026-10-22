import json
import sqlite3

import pytest

from database import database_manager
from services import invalid_telemetry_processor as processor


@pytest.fixture
def isolated_pipeline(tmp_path, monkeypatch):
    """Keep integration tests isolated from real project storage."""

    invalid_dir = tmp_path / "storage" / "invalid"
    reprocessed_dir = tmp_path / "storage" / "reprocessed"
    database_dir = tmp_path / "storage" / "databases"

    invalid_dir.mkdir(parents=True)
    reprocessed_dir.mkdir(parents=True)
    database_dir.mkdir(parents=True)

    monkeypatch.setattr(processor, "INVALID_DIR", invalid_dir)
    monkeypatch.setattr(processor, "REPROCESSED_DIR", reprocessed_dir)
    monkeypatch.setattr(database_manager, "DATABASE_DIR", database_dir)

    return {
        "invalid_dir": invalid_dir,
        "reprocessed_dir": reprocessed_dir,
        "database_dir": database_dir,
    }


def make_payload(
    *,
    device_id="esp32-test-01",
    timestamp=1792569600,
    soil_moisture=42.5,
):
    """Build a payload using the supported legacy field aliases."""

    return {
        "deviceId": device_id,
        "timestamp": timestamp,
        "sensors": {
            "soil_moisture": soil_moisture,
            "soil_temperature": 25.5,
            "soil_ph_value": 6.8,
            "nitrogen": 30.0,
            "phosphorus": 15.0,
            "potassium": 20.0,
        },
        "actuators": {
            "pumpState": False,
        },
    }


def write_invalid_record(invalid_dir, payload, filename="invalid_test.jsonl"):
    """Write one JSONL record and return its path and raw line."""

    file_path = invalid_dir / filename
    raw_line = json.dumps(payload)

    file_path.write_text(raw_line + "\n", encoding="utf-8")

    return file_path, raw_line


def read_audit_records(reprocessed_dir):
    """Read all audit entries written by the processor."""

    records = []

    for file_path in reprocessed_dir.glob("reprocessed_*.jsonl"):
        with file_path.open("r", encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    records.append(json.loads(line))

    return records


def read_all_telemetry(database_dir):
    """Read telemetry rows from all managed database files."""

    rows = []

    for database_path in database_manager.get_database_paths():
        with sqlite3.connect(database_path) as connection:
            rows.extend(
                connection.execute(
                    """
                    SELECT
                        device_id,
                        timestamp,
                        soil_moisture_pct,
                        soil_temperature_c,
                        soil_ph,
                        nitrogen_mg_kg,
                        phosphorus_mg_kg,
                        potassium_mg_kg,
                        pump_state
                    FROM telemetry
                    """
                ).fetchall()
            )

    return rows


def test_legacy_aliases_are_repaired_and_saved(isolated_pipeline):
    paths = isolated_pipeline

    original_file, _ = write_invalid_record(
        paths["invalid_dir"],
        make_payload(),
    )

    result = processor.process_invalid_files()

    assert result["saved"] == 1
    assert result["retry"] == 0
    assert result["invalid"] == 0

    # The original source file must remain available.
    assert original_file.exists()

    rows = read_all_telemetry(paths["database_dir"])

    assert len(rows) == 1

    row = rows[0]
    assert row[0] == "esp32-test-01"
    assert row[2] == pytest.approx(42.5)
    assert row[3] == pytest.approx(25.5)
    assert row[4] == pytest.approx(6.8)
    assert row[5] == pytest.approx(30.0)
    assert row[6] == pytest.approx(15.0)
    assert row[7] == pytest.approx(20.0)
    assert row[8] == 0

    audit_records = read_audit_records(paths["reprocessed_dir"])

    assert len(audit_records) == 1
    assert audit_records[0]["status"] == "saved"


def test_terminal_record_is_not_processed_twice(isolated_pipeline):
    paths = isolated_pipeline

    original_file, _ = write_invalid_record(
        paths["invalid_dir"],
        make_payload(),
    )

    first_result = processor.process_invalid_files()

    assert first_result["saved"] == 1
    assert original_file.exists()
    assert len(read_all_telemetry(paths["database_dir"])) == 1

    second_result = processor.process_invalid_files()

    assert second_result["saved"] == 0
    assert second_result["duplicate"] == 0
    assert second_result["invalid"] == 0
    assert second_result["conflict"] == 0
    assert second_result["retry"] == 0

    # No extra audit entry should be created for the same terminal record.
    assert len(read_audit_records(paths["reprocessed_dir"])) == 1
    assert len(read_all_telemetry(paths["database_dir"])) == 1


def test_identical_reading_is_recorded_as_duplicate(isolated_pipeline):
    paths = isolated_pipeline

    first_file, first_raw_line = write_invalid_record(
        paths["invalid_dir"],
        make_payload(),
        filename="invalid_first.jsonl",
    )

    first_result = processor.process_invalid_record(
        first_file,
        1,
        first_raw_line,
    )

    assert first_result == "saved"

    second_file, second_raw_line = write_invalid_record(
        paths["invalid_dir"],
        make_payload(),
        filename="invalid_second.jsonl",
    )

    second_result = processor.process_invalid_record(
        second_file,
        1,
        second_raw_line,
    )

    assert second_result == "duplicate"
    assert len(read_all_telemetry(paths["database_dir"])) == 1


def test_same_device_and_timestamp_with_different_values_is_conflict(
    isolated_pipeline,
):
    paths = isolated_pipeline

    first_file, first_raw_line = write_invalid_record(
        paths["invalid_dir"],
        make_payload(soil_moisture=42.5),
        filename="invalid_first.jsonl",
    )

    first_result = processor.process_invalid_record(
        first_file,
        1,
        first_raw_line,
    )

    assert first_result == "saved"

    second_file, second_raw_line = write_invalid_record(
        paths["invalid_dir"],
        make_payload(soil_moisture=55.0),
        filename="invalid_second.jsonl",
    )

    second_result = processor.process_invalid_record(
        second_file,
        1,
        second_raw_line,
    )

    assert second_result == "conflict"
    assert len(read_all_telemetry(paths["database_dir"])) == 1

    audit_statuses = {
        record["status"]
        for record in read_audit_records(paths["reprocessed_dir"])
    }

    assert "saved" in audit_statuses
    assert "conflict" in audit_statuses


def test_transient_database_error_can_be_retried(
    isolated_pipeline,
    monkeypatch,
):
    paths = isolated_pipeline

    original_file, _ = write_invalid_record(
        paths["invalid_dir"],
        make_payload(),
    )

    real_save_telemetry = processor.save_telemetry
    calls = {"count": 0}

    def fail_once(telemetry):
        calls["count"] += 1

        if calls["count"] == 1:
            raise RuntimeError("Simulated temporary database failure")

        return real_save_telemetry(telemetry)

    monkeypatch.setattr(processor, "save_telemetry", fail_once)

    first_result = processor.process_invalid_files()

    assert first_result["retry"] == 1
    assert first_result["saved"] == 0
    assert original_file.exists()
    assert len(read_all_telemetry(paths["database_dir"])) == 0

    # The failed attempt must not mark the record as terminal.
    retry_result = processor.process_invalid_files()

    assert retry_result["saved"] == 1
    assert retry_result["retry"] == 0
    assert len(read_all_telemetry(paths["database_dir"])) == 1
    assert original_file.exists()


def test_unrepairable_record_is_audited_and_original_is_preserved(
    isolated_pipeline,
):
    paths = isolated_pipeline

    bad_payload = {
        "deviceId": "esp32-invalid",
        "timestamp": "not-a-valid-timestamp",
        "sensors": {},
        "actuators": {},
    }

    original_file, _ = write_invalid_record(
        paths["invalid_dir"],
        bad_payload,
    )

    result = processor.process_invalid_files()

    assert result["invalid"] == 1
    assert result["saved"] == 0
    assert original_file.exists()
    assert len(read_all_telemetry(paths["database_dir"])) == 0

    audit_records = read_audit_records(paths["reprocessed_dir"])

    assert len(audit_records) == 1
    assert audit_records[0]["status"] == "invalid"
