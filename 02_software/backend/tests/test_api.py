
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.routes import health_routes as health
from api.routes import telemetry_routes as telemetry


NOW = int(datetime.now(timezone.utc).timestamp())



def row(
    record_id: int = 1,
    device_id: str = "ESP32-FIELD-TEST",
    timestamp: int = NOW,
    moisture: float = 45.5,
    pump_state: int = 0,
) -> dict[str, Any]:
    return {
        "id": record_id,
        "database_file": "telemetry_test.db",
        "device_id": device_id,
        "timestamp": timestamp,
        "soil_moisture_pct": moisture,
        "soil_temperature_c": 26.0,
        "soil_ph": 6.8,
        "nitrogen_mg_kg": 40.0,
        "phosphorus_mg_kg": 20.0,
        "potassium_mg_kg": 30.0,
        "pump_state": pump_state,
    }


ROWS = [
    row(10, "ESP32-FIELD-TEST", NOW),
    row(9, "ESP32-SECOND", NOW - 3600, 51.0, 1),
    row(8, "ESP32-FIELD-TEST", NOW - 7200, 42.0),
]


@pytest.fixture
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def telemetry_rows(monkeypatch: pytest.MonkeyPatch):
    rows = [dict(item) for item in ROWS]

    def latest(limit: int = 100, **kwargs: Any):
        return rows[:limit]

    def by_device(device_id: str, limit: int = 100, **kwargs: Any):
        return [item for item in rows if item["device_id"] == device_id][:limit]

    monkeypatch.setattr(telemetry, "get_latest_telemetry", latest)
    monkeypatch.setattr(telemetry, "get_telemetry_by_device", by_device)
    return rows


@pytest.fixture
def healthy_services(monkeypatch: pytest.MonkeyPatch):
    async def database():
        return {"engine": "sqlite"}

    async def mqtt():
        return {"host": "test", "port": 1883}

    async def devices():
        return {
            "source": "persisted_telemetry",
            "registered": 3,
            "online": 3,
            "offline": 0,
            "window_seconds": 300,
        }

    monkeypatch.setattr(health, "_check_database", database)
    monkeypatch.setattr(health, "_check_mqtt_broker", mqtt)
    monkeypatch.setattr(health, "_check_devices", devices)


# Root endpoint

def test_root_returns_online_json(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["status"] == "online"


def test_cors_allows_any_origin_under_current_configuration(client):
    response = client.get("/", headers={"Origin": "http://example.com"})
    assert response.headers.get("access-control-allow-origin") == "*"


# Health endpoint

def test_health_is_healthy_when_all_probes_are_up(client, healthy_services):
    response = client.get("/api/health/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert set(body["services"]) == {"database", "mqtt_broker", "devices"}
    for service in body["services"].values():
        assert service["status"] == "up"
        assert "latency_ms" in service


def test_health_timestamp_is_timezone_aware(client, healthy_services):
    timestamp = datetime.fromisoformat(client.get("/api/health/").json()["timestamp"])
    assert timestamp.tzinfo is not None
    assert timestamp.utcoffset() is not None


def test_health_is_degraded_when_mqtt_is_down(
    client, healthy_services, monkeypatch: pytest.MonkeyPatch
):
    async def failed_mqtt():
        raise ConnectionRefusedError("broker offline")

    monkeypatch.setattr(health, "_check_mqtt_broker", failed_mqtt)
    response = client.get("/api/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["services"]["mqtt_broker"]["status"] == "down"


def test_health_is_unhealthy_503_when_database_is_down(
    client, healthy_services, monkeypatch: pytest.MonkeyPatch
):
    async def failed_database():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(health, "_check_database", failed_database)
    response = client.get("/api/health/")
    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
    assert response.json()["services"]["database"]["status"] == "down"


def test_health_is_degraded_when_devices_are_offline(
    client, healthy_services, monkeypatch: pytest.MonkeyPatch
):
    async def some_offline():
        return {
            "source": "persisted_telemetry",
            "registered": 3,
            "online": 2,
            "offline": 1,
            "window_seconds": 300,
        }

    monkeypatch.setattr(health, "_check_devices", some_offline)
    response = client.get("/api/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


# Latest telemetry endpoint

def test_latest_empty_repository_returns_null_data(client, monkeypatch):
    monkeypatch.setattr(telemetry, "get_latest_telemetry", lambda limit=100: [])
    response = client.get("/api/telemetry/latest")
    assert response.status_code == 200
    assert response.json()["data"] is None
    assert response.json()["message"]


def test_latest_returns_nested_canonical_record(client, telemetry_rows):
    response = client.get("/api/telemetry/latest")
    assert response.status_code == 200
    record = response.json()["data"]
    assert record["id"] == 10
    assert record["database_file"] == "telemetry_test.db"
    assert record["device_id"] == "ESP32-FIELD-TEST"
    assert record["sensors"]["soil_moisture_pct"] == 45.5
    assert record["sensors"]["soil_temperature_c"] == 26.0
    assert record["sensors"]["soil_ph"] == 6.8
    assert record["actuators"]["pump_state"] is False
    assert "soil_moisture" not in record


def test_latest_filters_device_id(client, telemetry_rows):
    response = client.get(
        "/api/telemetry/latest", params={"device_id": "ESP32-SECOND"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["device_id"] == "ESP32-SECOND"
    assert response.json()["data"]["actuators"]["pump_state"] is True


def test_latest_unknown_device_returns_null_data(client, telemetry_rows):
    response = client.get(
        "/api/telemetry/latest", params={"device_id": "UNKNOWN-DEVICE"}
    )
    assert response.status_code == 200
    assert response.json()["data"] is None


@pytest.mark.parametrize("device_id", ["", "x" * 65])
def test_latest_rejects_invalid_device_id(client, device_id):
    assert client.get(
        "/api/telemetry/latest", params={"device_id": device_id}
    ).status_code == 422


def test_latest_repository_failure_returns_500(client, monkeypatch):
    def failed(limit=100, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(telemetry, "get_latest_telemetry", failed)
    response = client.get("/api/telemetry/latest")
    assert response.status_code == 500
    assert response.json()["detail"] == "Unable to retrieve telemetry data."


# History endpoint

def test_history_empty_repository_returns_empty_list(client, monkeypatch):
    monkeypatch.setattr(telemetry, "get_latest_telemetry", lambda limit=100: [])
    response = client.get("/api/telemetry/history")
    assert response.status_code == 200
    assert response.json()["count"] == 0
    assert response.json()["data"] == []


def test_history_default_limit_and_shape(client, telemetry_rows):
    response = client.get("/api/telemetry/history")
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 50
    assert body["count"] == 3
    assert body["device_id"] is None
    assert "sensors" in body["data"][0]
    assert "actuators" in body["data"][0]


def test_history_respects_custom_limit(client, telemetry_rows):
    body = client.get("/api/telemetry/history", params={"limit": 2}).json()
    assert body["limit"] == 2
    assert body["count"] == 2
    assert len(body["data"]) == 2


@pytest.mark.parametrize("limit", [0, -1, 101, 1000, "abc"])
def test_history_rejects_invalid_limit(client, limit):
    assert client.get("/api/telemetry/history", params={"limit": limit}).status_code == 422


def test_history_filters_device_id(client, telemetry_rows):
    response = client.get(
        "/api/telemetry/history",
        params={"device_id": "ESP32-FIELD-TEST", "limit": 10},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert all(item["device_id"] == "ESP32-FIELD-TEST" for item in body["data"])


def test_history_unknown_device_returns_empty_list(client, telemetry_rows):
    response = client.get(
        "/api/telemetry/history", params={"device_id": "UNKNOWN-DEVICE"}
    )
    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.parametrize("device_id", ["", "x" * 65])
def test_history_rejects_invalid_device_id(client, device_id):
    assert client.get(
        "/api/telemetry/history", params={"device_id": device_id}
    ).status_code == 422


def test_history_is_newest_first(client, telemetry_rows):
    timestamps = [
        item["timestamp"]
        for item in client.get("/api/telemetry/history").json()["data"]
    ]
    assert timestamps == sorted(timestamps, reverse=True)


def test_history_filters_inclusive_time_range(client, telemetry_rows):
    start = datetime.fromtimestamp(NOW - 3600, timezone.utc).isoformat()
    end = datetime.fromtimestamp(NOW, timezone.utc).isoformat()
    response = client.get(
        "/api/telemetry/history",
        params={"start_time": start, "end_time": end},
    )
    assert response.status_code == 200
    assert [item["timestamp"] for item in response.json()["data"]] == [
        NOW,
        NOW - 3600,
    ]


def test_history_naive_datetime_is_interpreted_as_cairo_time(client, telemetry_rows):
    cairo = ZoneInfo("Africa/Cairo")
    naive = datetime.fromtimestamp(NOW - 3600, cairo).replace(tzinfo=None)
    response = client.get(
        "/api/telemetry/history", params={"start_time": naive.isoformat()}
    )
    assert response.status_code == 200
    parsed = datetime.fromisoformat(response.json()["start_time"])
    assert parsed.utcoffset() == naive.replace(tzinfo=cairo).utcoffset()


def test_history_rejects_start_after_end(client, telemetry_rows):
    start = datetime.fromtimestamp(NOW, timezone.utc)
    end = start - timedelta(hours=1)
    response = client.get(
        "/api/telemetry/history",
        params={"start_time": start.isoformat(), "end_time": end.isoformat()},
    )
    assert response.status_code == 422
    assert "start_time" in response.json()["detail"]


def test_history_repository_failure_returns_500(client, monkeypatch):
    def failed(limit=100, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(telemetry, "get_latest_telemetry", failed)
    response = client.get("/api/telemetry/history")
    assert response.status_code == 500
    assert response.json()["detail"] == "Unable to retrieve telemetry history."


def test_invalid_stored_row_returns_500(client, monkeypatch):
    invalid = row()
    invalid["soil_ph"] = 99.0
    monkeypatch.setattr(telemetry, "get_latest_telemetry", lambda limit=100: [invalid])
    response = client.get("/api/telemetry/latest")
    assert response.status_code == 500
    assert response.json()["detail"] == "Unable to retrieve telemetry data."
