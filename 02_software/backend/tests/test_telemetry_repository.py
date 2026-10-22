
import pytest

import database.database_manager as database_manager
import repositories.telemetry_repository as repository
from models.telemetry import Telemetry


@pytest.fixture
def isolated_database_dir(tmp_path, monkeypatch):
    """Keep repository tests isolated from project databases."""
    database_dir = tmp_path / "databases"
    database_dir.mkdir()

    monkeypatch.setattr(
        database_manager,
        "DATABASE_DIR",
        database_dir,
    )

    return database_dir


@pytest.fixture
def valid_telemetry():
    return Telemetry.model_validate(
        {
            "device_id": "device-001",
            "timestamp": 1_797_000_000,
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
    )


def test_save_telemetry_inserts_valid_record(
    isolated_database_dir,
    valid_telemetry,
):
    result = repository.save_telemetry(valid_telemetry)

    assert result == "saved"

    rows = repository.get_telemetry_by_device("device-001")

    assert len(rows) == 1
    assert rows[0]["device_id"] == "device-001"
    assert rows[0]["timestamp"] == 1_797_000_000


def test_save_identical_telemetry_does_not_duplicate(
    isolated_database_dir,
    valid_telemetry,
):
    first_result = repository.save_telemetry(valid_telemetry)
    second_result = repository.save_telemetry(valid_telemetry)

    assert first_result == "saved"
    assert second_result == "duplicate"

    rows = repository.get_telemetry_by_device("device-001")
    assert len(rows) == 1


def test_conflicting_telemetry_raises_error(
    isolated_database_dir,
    valid_telemetry,
):
    repository.save_telemetry(valid_telemetry)

    conflicting_data = valid_telemetry.model_dump()
    conflicting_data["sensors"]["soil_moisture_pct"] = 80.0

    conflicting_telemetry = Telemetry.model_validate(
        conflicting_data
    )

    with pytest.raises(repository.TelemetryConflictError):
        repository.save_telemetry(conflicting_telemetry)

    rows = repository.get_telemetry_by_device("device-001")

    assert len(rows) == 1
    assert rows[0]["soil_moisture_pct"] == 45.5


def test_rejects_invalid_telemetry(
    isolated_database_dir,
):
    invalid_data = {
        "device_id": "device-001",
        "timestamp": 1_797_000_000,
        "sensors": {
            "soil_moisture_pct": 150,
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

    with pytest.raises((ValueError, TypeError)):
        repository.save_telemetry(invalid_data)

    assert repository.get_latest_telemetry() == []


def test_get_latest_telemetry_returns_newest_first(
    isolated_database_dir,
    valid_telemetry,
):
    repository.save_telemetry(valid_telemetry)

    newer_data = valid_telemetry.model_dump()
    newer_data["timestamp"] += 100

    repository.save_telemetry(
        Telemetry.model_validate(newer_data)
    )

    rows = repository.get_latest_telemetry(limit=10)

    assert len(rows) == 2
    assert rows[0]["timestamp"] > rows[1]["timestamp"]


def test_get_telemetry_by_device_filters_device(
    isolated_database_dir,
    valid_telemetry,
):
    repository.save_telemetry(valid_telemetry)

    other_data = valid_telemetry.model_dump()
    other_data["device_id"] = "device-002"
    other_data["timestamp"] += 1

    repository.save_telemetry(
        Telemetry.model_validate(other_data)
    )

    rows = repository.get_telemetry_by_device("device-001")

    assert len(rows) == 1
    assert rows[0]["device_id"] == "device-001"


def test_get_latest_telemetry_respects_limit(
    isolated_database_dir,
    valid_telemetry,
):
    for offset in range(3):
        data = valid_telemetry.model_dump()
        data["timestamp"] += offset

        repository.save_telemetry(
            Telemetry.model_validate(data)
        )

    rows = repository.get_latest_telemetry(limit=2)

    assert len(rows) == 2


def test_get_telemetry_by_device_rejects_invalid_limit(
    isolated_database_dir,
):
    with pytest.raises(ValueError):
        repository.get_telemetry_by_device(
            "device-001",
            limit=0,
        )


def test_get_latest_telemetry_rejects_invalid_limit(
    isolated_database_dir,
):
    with pytest.raises(ValueError):
        repository.get_latest_telemetry(limit=0)
id="repo-tests-01"
