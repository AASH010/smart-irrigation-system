
from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import socket
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Optional

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from database.database_manager import (
    get_connection,
    get_database_paths,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

MQTT_HOST: str = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT: int = int(os.getenv("MQTT_BROKER_PORT", "1883"))

CHECK_TIMEOUT_SECONDS: float = float(
    os.getenv("HEALTH_CHECK_TIMEOUT", "2.0")
)

# A device is considered online if its latest telemetry is no older
# than this many seconds.
DEVICE_ONLINE_WINDOW_SECONDS: int = int(
    os.getenv("DEVICE_ONLINE_WINDOW_SECONDS", "300")
)

if CHECK_TIMEOUT_SECONDS <= 0:
    raise ValueError("HEALTH_CHECK_TIMEOUT must be positive.")

if DEVICE_ONLINE_WINDOW_SECONDS <= 0:
    raise ValueError("DEVICE_ONLINE_WINDOW_SECONDS must be positive.")


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class OverallStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ServiceState(str, Enum):
    UP = "up"
    DOWN = "down"


class ServiceStatus(BaseModel):
    status: ServiceState = Field(
        ...,
        description="Current state of the service.",
    )
    latency_ms: Optional[float] = Field(
        None,
        description="Time taken by the health probe in milliseconds.",
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional non-sensitive diagnostic information.",
    )
    error: Optional[str] = Field(
        None,
        description="Short error description if the service is down.",
    )


class ServicesHealth(BaseModel):
    database: ServiceStatus
    mqtt_broker: ServiceStatus
    devices: ServiceStatus


class HealthResponse(BaseModel):
    status: OverallStatus
    timestamp: str
    services: ServicesHealth


# --------------------------------------------------------------------------- #
# Service checks
# --------------------------------------------------------------------------- #


async def _check_database() -> Dict[str, Any]:
    """Verify connectivity to the configured primary database."""
    connection = None

    try:
        connection = get_connection()
        connection.execute("SELECT 1").fetchone()

        return {
            "engine": "sqlite",
            "connection": "ok",
        }

    finally:
        if connection is not None:
            connection.close()


async def _check_mqtt_broker() -> Dict[str, Any]:
    """Check whether the configured MQTT broker accepts TCP connections."""
    writer: Optional[asyncio.StreamWriter] = None

    try:
        _, writer = await asyncio.open_connection(
            MQTT_HOST,
            MQTT_PORT,
        )

        return {
            "host": MQTT_HOST,
            "port": MQTT_PORT,
            "connection": "ok",
        }

    finally:
        if writer is not None:
            writer.close()

            try:
                await writer.wait_closed()
            except (OSError, socket.error):
                pass


async def _check_devices() -> Dict[str, Any]:
    """
    Determine ESP device activity from persisted telemetry.

    A device is online when its latest stored Unix timestamp falls
    within DEVICE_ONLINE_WINDOW_SECONDS of the current UTC time.

    Only managed database files returned by get_database_paths()
    are inspected.
    """
    latest_by_device: dict[str, int] = {}

    for database_path in get_database_paths():
        connection = None

        try:
            connection = sqlite3.connect(
                str(database_path),
                timeout=10,
            )

            rows = connection.execute(
                """
                SELECT device_id, MAX(timestamp) AS last_timestamp
                FROM telemetry
                GROUP BY device_id
                """
            ).fetchall()

            for device_id, last_timestamp in rows:
                if not device_id or last_timestamp is None:
                    continue

                try:
                    timestamp = int(last_timestamp)
                except (TypeError, ValueError, OverflowError):
                    logger.warning(
                        "Ignoring invalid telemetry timestamp in %s",
                        database_path.name,
                    )
                    continue

                previous = latest_by_device.get(device_id)

                if previous is None or timestamp > previous:
                    latest_by_device[device_id] = timestamp

        except sqlite3.Error as exc:
            logger.error(
                "Could not inspect device telemetry in %s: %s",
                database_path.name,
                type(exc).__name__,
            )
            raise RuntimeError(
                "Could not inspect stored device telemetry."
            ) from exc

        finally:
            if connection is not None:
                connection.close()

    now = int(time.time())
    cutoff = now - DEVICE_ONLINE_WINDOW_SECONDS

    registered = len(latest_by_device)

    online = sum(
        1
        for last_timestamp in latest_by_device.values()
        if cutoff <= last_timestamp <= now
    )

    offline = registered - online

    return {
        "source": "persisted_telemetry",
        "registered": registered,
        "online": online,
        "offline": offline,
        "online_window_seconds": DEVICE_ONLINE_WINDOW_SECONDS,
    }


async def _run_check(
    check: Callable[[], Awaitable[Dict[str, Any]]],
) -> ServiceStatus:
    """Execute a health check with timeout and error handling."""
    loop = asyncio.get_running_loop()
    started = loop.time()

    try:
        details = await asyncio.wait_for(
            check(),
            timeout=CHECK_TIMEOUT_SECONDS,
        )

        return ServiceStatus(
            status=ServiceState.UP,
            latency_ms=round(
                (loop.time() - started) * 1000,
                2,
            ),
            details=details,
        )

    except asyncio.TimeoutError:
        logger.warning("Health check %s timed out", check.__name__)
        error = f"Timed out after {CHECK_TIMEOUT_SECONDS}s"

    except Exception as exc:
        logger.error(
            "Health check %s failed: %s",
            check.__name__,
            type(exc).__name__,
        )
        error = "Dependency check failed."

    return ServiceStatus(
        status=ServiceState.DOWN,
        latency_ms=round(
            (loop.time() - started) * 1000,
            2,
        ),
        error=error,
    )


def _aggregate_status(services: ServicesHealth) -> OverallStatus:
    """
    Database unavailable -> unhealthy.
    MQTT unavailable or device telemetry unavailable -> degraded.
    All checks successful -> healthy.
    """
    if services.database.status is ServiceState.DOWN:
        return OverallStatus.UNHEALTHY

    if (
        services.mqtt_broker.status is ServiceState.DOWN
        or services.devices.status is ServiceState.DOWN
    ):
        return OverallStatus.DEGRADED

    if (
        services.devices.details is not None
        and services.devices.details.get("registered", 0) > 0
        and services.devices.details.get("offline", 0) > 0
    ):
        return OverallStatus.DEGRADED

    return OverallStatus.HEALTHY


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


@router.get(
    "/",
    response_model=HealthResponse,
    summary="System health check",
    description=(
        "Returns the health of the database, MQTT broker, and ESP devices. "
        "Returns HTTP 503 when the primary database is unavailable."
    ),
    responses={
        503: {
            "description": "A core dependency is unavailable.",
            "model": HealthResponse,
        },
    },
)
async def health_check() -> JSONResponse:
    """Return the aggregated health status of AeroSoil services."""
    try:
        database, mqtt_broker, devices = await asyncio.gather(
            _run_check(_check_database),
            _run_check(_check_mqtt_broker),
            _run_check(_check_devices),
        )

        services = ServicesHealth(
            database=database,
            mqtt_broker=mqtt_broker,
            devices=devices,
        )

        overall = _aggregate_status(services)

        payload = HealthResponse(
            status=overall,
            timestamp=datetime.now(timezone.utc).isoformat(),
            services=services,
        )

        http_status = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if overall is OverallStatus.UNHEALTHY
            else status.HTTP_200_OK
        )

        return JSONResponse(
            status_code=http_status,
            content=payload.model_dump(mode="json"),
        )

    except Exception as exc:
        logger.error(
            "Unexpected error while building health report: %s",
            type(exc).__name__,
        )

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": OverallStatus.UNHEALTHY.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": "Health check failed.",
            },
        )
