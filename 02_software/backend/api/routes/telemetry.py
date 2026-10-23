from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Protocol, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_HISTORY_LIMIT: int = 50
MAX_HISTORY_LIMIT: int = 100


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class TelemetryRecord(BaseModel):
    """A single sensor telemetry reading reported by an ESP32 device."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = Field(None, description="Database record identifier.")
    device_id: str = Field(..., description="Identifier of the reporting ESP32 device.")
    soil_moisture: Optional[float] = Field(
        None, ge=0, le=100, description="Soil moisture in percent."
    )
    temperature: Optional[float] = Field(None, description="Temperature in °C.")
    humidity: Optional[float] = Field(
        None, ge=0, le=100, description="Relative air humidity in percent."
    )
    pump_active: Optional[bool] = Field(
        None, description="Whether the irrigation pump was active at reading time."
    )
    timestamp: datetime = Field(..., description="UTC time the reading was recorded.")


class LatestTelemetryResponse(BaseModel):
    """Response for the latest-telemetry endpoint."""

    data: Optional[TelemetryRecord] = Field(
        None, description="Latest record, or null when no telemetry exists."
    )
    message: Optional[str] = Field(None, description="Informational message.")


class TelemetryHistoryResponse(BaseModel):
    """Response for the telemetry-history endpoint."""

    count: int = Field(..., description="Number of records returned.")
    limit: int = Field(..., description="Limit that was applied to the query.")
    device_id: Optional[str] = Field(None, description="Device filter applied, if any.")
    data: List[TelemetryRecord] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Repository abstraction (SubTask 2 integration point)
# --------------------------------------------------------------------------- #


class TelemetryRepository(Protocol):
    """
    Interface the telemetry router expects from the data layer.

    Any SubTask 2 repository implementing these async methods can be plugged in.
    """

    async def get_latest(self, device_id: Optional[str] = None) -> Optional[Any]:
        """Return the newest telemetry record, or ``None`` if none exist."""
        ...

    async def get_history(
        self, limit: int, device_id: Optional[str] = None
    ) -> Sequence[Any]:
        """Return up to ``limit`` records, newest first."""
        ...


class MockTelemetryRepository:
    """
    In-memory repository producing deterministic sample data.

    Used as the default until the real database repository is wired in, and
    handy for local development and tests.
    """

    _DEVICES = ("esp32-001", "esp32-002")

    def _generate(self, count: int, device_id: Optional[str]) -> List[TelemetryRecord]:
        now = datetime.now(timezone.utc)
        devices = (device_id,) if device_id else self._DEVICES
        records: List[TelemetryRecord] = []
        for i in range(count):
            device = devices[i % len(devices)]
            records.append(
                TelemetryRecord(
                    id=count - i,
                    device_id=device,
                    soil_moisture=round(45.0 + (i % 10) * 0.8, 1),
                    temperature=round(24.0 + (i % 5) * 0.3, 1),
                    humidity=round(55.0 + (i % 7) * 0.5, 1),
                    pump_active=(i % 12 == 0),
                    timestamp=now - timedelta(minutes=5 * i),
                )
            )
        return records

    async def get_latest(self, device_id: Optional[str] = None) -> Optional[TelemetryRecord]:
        records = self._generate(1, device_id)
        return records[0] if records else None

    async def get_history(
        self, limit: int, device_id: Optional[str] = None
    ) -> List[TelemetryRecord]:
        return self._generate(limit, device_id)


# --------------------------------------------------------------------------- #
# Dependencies
# --------------------------------------------------------------------------- #


def get_telemetry_repository() -> TelemetryRepository:
    """
    Provide the telemetry repository.

    Replace the body with the SubTask 2 repository bound to a DB session
    (see module docstring), or override via ``app.dependency_overrides``.
    """
    return MockTelemetryRepository()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


@router.get(
    "/latest",
    response_model=LatestTelemetryResponse,
    summary="Get latest telemetry record",
    description=(
        "Returns the most recent sensor telemetry record. If no telemetry has "
        "been recorded yet, responds with HTTP 200 and ``data: null``."
    ),
    responses={
        500: {"description": "Failed to retrieve telemetry from the database."},
    },
)
async def get_latest_telemetry(
    device_id: Optional[str] = Query(
        None,
        min_length=1,
        max_length=64,
        description="Restrict the lookup to a specific ESP32 device.",
    ),
    repo: TelemetryRepository = Depends(get_telemetry_repository),
) -> LatestTelemetryResponse:
    """Retrieve the latest telemetry record, gracefully handling an empty table."""
    try:
        record = await repo.get_latest(device_id=device_id)
    except Exception:  # noqa: BLE001 - translate data-layer errors to HTTP.
        logger.exception("Failed to fetch latest telemetry (device_id=%s)", device_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve telemetry data.",
        )

    if record is None:
        return LatestTelemetryResponse(
            data=None, message="No telemetry records found."
        )

    return LatestTelemetryResponse(data=TelemetryRecord.model_validate(record))


@router.get(
    "/history",
    response_model=TelemetryHistoryResponse,
    summary="Get telemetry history",
    description=(
        "Returns historical telemetry records, newest first. Supports an "
        f"optional ``limit`` (default {DEFAULT_HISTORY_LIMIT}, max "
        f"{MAX_HISTORY_LIMIT}) and an optional ``device_id`` filter."
    ),
    responses={
        422: {"description": "Invalid query parameters."},
        500: {"description": "Failed to retrieve telemetry from the database."},
    },
)
async def get_telemetry_history(
    limit: int = Query(
        DEFAULT_HISTORY_LIMIT,
        ge=1,
        le=MAX_HISTORY_LIMIT,
        description="Maximum number of records to return.",
    ),
    device_id: Optional[str] = Query(
        None,
        min_length=1,
        max_length=64,
        description="Filter records by a specific ESP32 device.",
    ),
    repo: TelemetryRepository = Depends(get_telemetry_repository),
) -> TelemetryHistoryResponse:
    """Retrieve historical telemetry; returns an empty list when none exist."""
    try:
        rows = await repo.get_history(limit=limit, device_id=device_id)
    except Exception:  # noqa: BLE001 - translate data-layer errors to HTTP.
        logger.exception(
            "Failed to fetch telemetry history (limit=%s, device_id=%s)",
            limit,
            device_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve telemetry history.",
        )

    records = [TelemetryRecord.model_validate(row) for row in (rows or [])]
    return TelemetryHistoryResponse(
        count=len(records),
        limit=limit,
        device_id=device_id,
        data=records,
    )