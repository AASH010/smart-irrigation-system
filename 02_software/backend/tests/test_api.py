
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.api.routes import health, telemetry

# --------------------------------------------------------------------------- #
# Fake repositories
# --------------------------------------------------------------------------- #

_NOW = datetime.now(timezone.utc)

SAMPLE_RECORDS: List[Dict[str, Any]] = [
    {
        "id": 1000 - i,
        "device_id": "esp32-001" if i % 2 == 0 else "esp32-002",
        "soil_moisture": 40.0 + i * 0.1,
        "temperature": 24.0,
        "humidity": 55.0,
        "pump_active": False,
        "timestamp": _NOW - timedelta(minutes=5 * i),
    }
    for i in range(150)
]  # Newest first, alternating between two devices.


class EmptyTelemetryRepository:
    """Simulates a database with no telemetry rows yet."""

    async def get_latest(self, device_id: Optional[str] = None) -> None:
        return None

    async def get_history(
        self, limit: int, device_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return []


class PopulatedTelemetryRepository:
    """Simulates a database containing ``SAMPLE_RECORDS`` (newest first)."""

    @staticmethod
    def _filter(device_id: Optional[str]) -> List[Dict[str, Any]]:
        if device_id is None:
            return SAMPLE_RECORDS
        return [r for r in SAMPLE_RECORDS if r["device_id"] == device_id]

    async def get_latest(self, device_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        rows = self._filter(device_id)
        return rows[0] if rows else None

    async def get_history(
        self, limit: int, device_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return self._filter(device_id)[:limit]


class FailingTelemetryRepository:
    """Simulates a database outage."""

    async def get_latest(self, device_id: Optional[str] = None) -> Any:
        raise RuntimeError("database unavailable")

    async def get_history(self, limit: int, device_id: Optional[str] = None) -> Any:
        raise RuntimeError("database unavailable")


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """
    TestClient bound to a fresh app instance with the default dependencies.
    """
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def _client_with_repo(repo: Any) -> Iterator[TestClient]:
    """Build a TestClient whose telemetry repository is replaced by ``repo``."""
    app = create_app()
    app.dependency_overrides[telemetry.get_telemetry_repository] = lambda: repo
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def empty_db_client() -> Iterator[TestClient]:
    """TestClient whose telemetry database is empty."""
    yield from _client_with_repo(EmptyTelemetryRepository())


@pytest.fixture()
def populated_db_client() -> Iterator[TestClient]:
    """TestClient whose telemetry database contains sample records."""
    yield from _client_with_repo(PopulatedTelemetryRepository())


@pytest.fixture()
def failing_db_client() -> Iterator[TestClient]:
    """TestClient whose telemetry database raises on every call."""
    yield from _client_with_repo(FailingTelemetryRepository())


@pytest.fixture()
def healthy_services(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch all health probes so every dependency reports as up."""

    async def _check_database() -> Dict[str, Any]:
        return {"engine": "test"}

    async def _check_mqtt_broker() -> Dict[str, Any]:
        return {"host": "test", "port": 1883}

    async def _check_devices() -> Dict[str, Any]:
        return {"registered": 3, "online": 3, "offline": 0}

    monkeypatch.setattr(health, "_check_database", _check_database)
    monkeypatch.setattr(health, "_check_mqtt_broker", _check_mqtt_broker)
    monkeypatch.setattr(health, "_check_devices", _check_devices)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _assert_telemetry_record_shape(record: Dict[str, Any]) -> None:
    """Assert that a serialized telemetry record has the expected fields."""
    for field in (
        "id",
        "device_id",
        "soil_moisture",
        "temperature",
        "humidity",
        "pump_active",
        "timestamp",
    ):
        assert field in record, f"Missing field '{field}' in telemetry record"
    assert isinstance(record["device_id"], str)
    datetime.fromisoformat(record["timestamp"])  # Must be valid ISO 8601.


# --------------------------------------------------------------------------- #
# Root endpoint
# --------------------------------------------------------------------------- #


class TestRootEndpoint:
    """Tests for ``GET /``."""

    def test_root_returns_200(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200

    def test_root_reports_online_status(self, client: TestClient) -> None:
        body = client.get("/").json()
        assert body["status"] == "online"
        assert isinstance(body["message"], str) and body["message"]

    def test_root_content_type_is_json(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.headers["content-type"].startswith("application/json")

    def test_cors_allows_any_origin(self, client: TestClient) -> None:
        response = client.get("/", headers={"Origin": "http://example.com"})
        assert response.headers.get("access-control-allow-origin") == "*"


# --------------------------------------------------------------------------- #
# Health endpoint
# --------------------------------------------------------------------------- #


class TestHealthEndpoint:
    """Tests for ``GET /api/health/``."""

    def test_health_structure_when_all_services_up(
        self, client: TestClient, healthy_services: None
    ) -> None:
        response = client.get("/api/health/")
        assert response.status_code == 200

        body = response.json()
        assert body["status"] == "healthy"
        assert set(body["services"]) == {"database", "mqtt_broker", "devices"}
        for name, service in body["services"].items():
            assert service["status"] == "up", f"{name} should be up"
            assert "latency_ms" in service

    def test_health_timestamp_is_utc_iso_format(
        self, client: TestClient, healthy_services: None
    ) -> None:
        body = client.get("/api/health/").json()
        parsed = datetime.fromisoformat(body["timestamp"])
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == timedelta(0)

    def test_health_is_degraded_when_mqtt_down(
        self, client: TestClient, healthy_services: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _check_mqtt_broker() -> Dict[str, Any]:
            raise ConnectionRefusedError("broker offline")

        monkeypatch.setattr(health, "_check_mqtt_broker", _check_mqtt_broker)

        response = client.get("/api/health/")
        assert response.status_code == 200  # Non-core outage is not a 503.

        body = response.json()
        assert body["status"] == "degraded"
        assert body["services"]["mqtt_broker"]["status"] == "down"
        assert body["services"]["mqtt_broker"]["error"]
        assert body["services"]["database"]["status"] == "up"

    def test_health_is_unhealthy_with_503_when_database_down(
        self, client: TestClient, healthy_services: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _check_database() -> Dict[str, Any]:
            raise RuntimeError("connection lost")

        monkeypatch.setattr(health, "_check_database", _check_database)

        response = client.get("/api/health/")
        assert response.status_code == 503

        body = response.json()
        assert body["status"] == "unhealthy"
        assert body["services"]["database"]["status"] == "down"

    def test_health_responds_without_mocks(self, client: TestClient) -> None:
        """
        Smoke test with the real probes: depending on whether a local MQTT
        broker is running the result may be healthy or degraded, but the
        endpoint must respond with a well-formed report and never crash.
        """
        response = client.get("/api/health/")
        assert response.status_code in (200, 503)

        body = response.json()
        assert body["status"] in {"healthy", "degraded", "unhealthy"}
        assert "timestamp" in body
        assert set(body["services"]) == {"database", "mqtt_broker", "devices"}


# --------------------------------------------------------------------------- #
# Telemetry: latest
# --------------------------------------------------------------------------- #


class TestTelemetryLatest:
    """Tests for ``GET /api/telemetry/latest``."""

    def test_latest_with_empty_database_returns_200_and_null_data(
        self, empty_db_client: TestClient
    ) -> None:
        response = empty_db_client.get("/api/telemetry/latest")
        assert response.status_code == 200

        body = response.json()
        assert body["data"] is None
        assert body["message"]

    def test_latest_returns_newest_record(self, populated_db_client: TestClient) -> None:
        response = populated_db_client.get("/api/telemetry/latest")
        assert response.status_code == 200

        record = response.json()["data"]
        assert record is not None
        _assert_telemetry_record_shape(record)
        assert record["id"] == SAMPLE_RECORDS[0]["id"]

    def test_latest_filters_by_device_id(self, populated_db_client: TestClient) -> None:
        response = populated_db_client.get(
            "/api/telemetry/latest", params={"device_id": "esp32-002"}
        )
        assert response.status_code == 200
        assert response.json()["data"]["device_id"] == "esp32-002"

    def test_latest_unknown_device_returns_empty_not_error(
        self, populated_db_client: TestClient
    ) -> None:
        response = populated_db_client.get(
            "/api/telemetry/latest", params={"device_id": "does-not-exist"}
        )
        assert response.status_code == 200
        assert response.json()["data"] is None

    def test_latest_returns_500_when_database_fails(
        self, failing_db_client: TestClient
    ) -> None:
        response = failing_db_client.get("/api/telemetry/latest")
        assert response.status_code == 500
        assert response.json()["detail"] == "Unable to retrieve telemetry data."

    def test_latest_works_with_default_repository(self, client: TestClient) -> None:
        """The default (mock) repository must also respond cleanly."""
        response = client.get("/api/telemetry/latest")
        assert response.status_code == 200
        assert "data" in response.json()


# --------------------------------------------------------------------------- #
# Telemetry: history
# --------------------------------------------------------------------------- #


class TestTelemetryHistory:
    """Tests for ``GET /api/telemetry/history``."""

    def test_history_with_empty_database_returns_empty_list(
        self, empty_db_client: TestClient
    ) -> None:
        response = empty_db_client.get("/api/telemetry/history")
        assert response.status_code == 200

        body = response.json()
        assert body["count"] == 0
        assert body["data"] == []

    def test_history_default_limit_is_50(self, populated_db_client: TestClient) -> None:
        body = populated_db_client.get("/api/telemetry/history").json()
        assert body["limit"] == 50
        assert body["count"] == 50
        assert len(body["data"]) == 50
        assert body["device_id"] is None

    def test_history_respects_custom_limit(self, populated_db_client: TestClient) -> None:
        body = populated_db_client.get(
            "/api/telemetry/history", params={"limit": 5}
        ).json()
        assert body["limit"] == 5
        assert body["count"] == 5
        for record in body["data"]:
            _assert_telemetry_record_shape(record)

    def test_history_accepts_maximum_limit(self, populated_db_client: TestClient) -> None:
        response = populated_db_client.get("/api/telemetry/history", params={"limit": 100})
        assert response.status_code == 200
        assert response.json()["count"] == 100

    @pytest.mark.parametrize("invalid_limit", [0, -1, 101, 1000, "abc"])
    def test_history_rejects_invalid_limit(
        self, populated_db_client: TestClient, invalid_limit: Any
    ) -> None:
        response = populated_db_client.get(
            "/api/telemetry/history", params={"limit": invalid_limit}
        )
        assert response.status_code == 422

    def test_history_filters_by_device_id(self, populated_db_client: TestClient) -> None:
        body = populated_db_client.get(
            "/api/telemetry/history", params={"device_id": "esp32-001", "limit": 10}
        ).json()
        assert body["device_id"] == "esp32-001"
        assert body["count"] == 10
        assert all(r["device_id"] == "esp32-001" for r in body["data"])

    def test_history_unknown_device_returns_empty_list(
        self, populated_db_client: TestClient
    ) -> None:
        response = populated_db_client.get(
            "/api/telemetry/history", params={"device_id": "does-not-exist"}
        )
        assert response.status_code == 200
        assert response.json()["data"] == []

    @pytest.mark.parametrize("invalid_device_id", ["", "x" * 65])
    def test_history_rejects_invalid_device_id(
        self, populated_db_client: TestClient, invalid_device_id: str
    ) -> None:
        response = populated_db_client.get(
            "/api/telemetry/history", params={"device_id": invalid_device_id}
        )
        assert response.status_code == 422

    def test_history_is_ordered_newest_first(self, populated_db_client: TestClient) -> None:
        data = populated_db_client.get(
            "/api/telemetry/history", params={"limit": 20}
        ).json()["data"]
        timestamps = [datetime.fromisoformat(r["timestamp"]) for r in data]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_history_returns_500_when_database_fails(
        self, failing_db_client: TestClient
    ) -> None:
        response = failing_db_client.get("/api/telemetry/history")
        assert response.status_code == 500
        assert response.json()["detail"] == "Unable to retrieve telemetry history."

    def test_history_works_with_default_repository(self, client: TestClient) -> None:
        """The default (mock) repository must also respond cleanly."""
        response = client.get(
            "/api/telemetry/history", params={"limit": 3, "device_id": "esp32-001"}
        )
        assert response.status_code == 200

        body = response.json()
        assert body["count"] == 3
        assert all(r["device_id"] == "esp32-001" for r in body["data"])