from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from models.telemetry import ActuatorStates, SensorReadings, Telemetry
from repositories.telemetry_repository import (
    get_latest_telemetry,
    get_telemetry_by_device,
)

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_HISTORY_LIMIT = 50
MAX_HISTORY_LIMIT = 100
EGYPT_TIMEZONE = ZoneInfo("Africa/Cairo")


class TelemetryRecord(BaseModel):
    """API representation of a persisted telemetry reading."""

    model_config = ConfigDict(extra="forbid")

    id: int
    database_file: str
    device_id: str
    timestamp: int
    sensors: SensorReadings
    actuators: ActuatorStates


class LatestTelemetryResponse(BaseModel):
    data: Optional[TelemetryRecord] = None
    message: Optional[str] = None


class TelemetryHistoryResponse(BaseModel):
    count: int
    limit: int
    device_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    data: list[TelemetryRecord] = Field(default_factory=list)


def _to_record(row: dict) -> TelemetryRecord:
    """Convert a flattened SQLite row into the canonical telemetry model."""
    try:
        telemetry = Telemetry.model_validate(
            {
                "device_id": row["device_id"],
                "timestamp": row["timestamp"],
                "sensors": {
                    "soil_moisture_pct": row["soil_moisture_pct"],
                    "soil_temperature_c": row["soil_temperature_c"],
                    "soil_ph": row["soil_ph"],
                    "nitrogen_mg_kg": row["nitrogen_mg_kg"],
                    "phosphorus_mg_kg": row["phosphorus_mg_kg"],
                    "potassium_mg_kg": row["potassium_mg_kg"],
                },
                "actuators": {
                    "pump_state": bool(row["pump_state"]),
                },
            }
        )

        return TelemetryRecord(
            id=row["id"],
            database_file=row["database_file"],
            **telemetry.model_dump(),
        )

    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise ValueError(
            "Stored telemetry record has an invalid format."
        ) from exc


def _normalize_datetime(
    value: Optional[datetime],
) -> Optional[datetime]:
    """Interpret naive input as Egypt local time; preserve explicit timezones."""
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=EGYPT_TIMEZONE)

    return value


def _get_rows(
    limit: int,
    device_id: Optional[str],
    start_time: Optional[datetime],
    end_time: Optional[datetime],
):
    """Read managed telemetry and apply inclusive time filters."""
    start_time = _normalize_datetime(start_time)
    end_time = _normalize_datetime(end_time)

    start_ts = int(start_time.timestamp()) if start_time else None
    end_ts = int(end_time.timestamp()) if end_time else None

    if (
        start_ts is not None
        and end_ts is not None
        and start_ts > end_ts
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start_time must be earlier than or equal to end_time.",
        )

    # Fetch the full supported history window before filtering by time.
    if device_id:
        rows = get_telemetry_by_device(
            device_id,
            limit=MAX_HISTORY_LIMIT,
        )
    else:
        rows = get_latest_telemetry(limit=MAX_HISTORY_LIMIT)

    filtered = [
        row
        for row in rows
        if (start_ts is None or row["timestamp"] >= start_ts)
        and (end_ts is None or row["timestamp"] <= end_ts)
    ]

    return filtered[:limit]


def _handle_read_error(
    exc: Exception,
    operation: str,
) -> HTTPException:
    logger.error(
        "Telemetry %s failed: %s",
        operation,
        type(exc).__name__,
    )

    if operation == "history":
        detail = "Unable to retrieve telemetry history."
    else:
        detail = "Unable to retrieve telemetry data."

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail,
    )


@router.get(
    "/latest",
    response_model=LatestTelemetryResponse,
    summary="Get latest telemetry record",
)
def latest_telemetry(
    device_id: Optional[str] = Query(
        None,
        min_length=1,
        max_length=64,
    ),
):
    try:
        rows = (
            get_telemetry_by_device(device_id, limit=1)
            if device_id
            else get_latest_telemetry(limit=1)
        )

        if not rows:
            return LatestTelemetryResponse(
                data=None,
                message="No telemetry records found.",
            )

        return LatestTelemetryResponse(data=_to_record(rows[0]))

    except (sqlite3.Error, OSError, RuntimeError, ValueError) as exc:
        raise _handle_read_error(exc, "latest") from exc


@router.get(
    "/history",
    response_model=TelemetryHistoryResponse,
    summary="Get telemetry history",
)
def telemetry_history(
    limit: int = Query(
        DEFAULT_HISTORY_LIMIT,
        ge=1,
        le=MAX_HISTORY_LIMIT,
    ),
    device_id: Optional[str] = Query(
        None,
        min_length=1,
        max_length=64,
    ),
    start_time: Optional[datetime] = Query(
        None,
        description=(
            "Inclusive start time in ISO 8601 format. "
            "Naive datetimes are interpreted as Africa/Cairo local time."
        ),
    ),
    end_time: Optional[datetime] = Query(
        None,
        description=(
            "Inclusive end time in ISO 8601 format. "
            "Naive datetimes are interpreted as Africa/Cairo local time."
        ),
    ),
):
    start_time = _normalize_datetime(start_time)
    end_time = _normalize_datetime(end_time)

    if start_time and end_time and start_time > end_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start_time must be earlier than or equal to end_time.",
        )

    try:
        rows = _get_rows(
            limit,
            device_id,
            start_time,
            end_time,
        )
        records = [_to_record(row) for row in rows]

        return TelemetryHistoryResponse(
            count=len(records),
            limit=limit,
            device_id=device_id,
            start_time=start_time,
            end_time=end_time,
            data=records,
        )

    except HTTPException:
        raise

    except (sqlite3.Error, OSError, RuntimeError, ValueError) as exc:
        raise _handle_read_error(exc, "history") from exc