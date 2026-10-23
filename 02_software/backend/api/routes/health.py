
from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Optional

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

MQTT_HOST: str = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT: int = int(os.getenv("MQTT_BROKER_PORT", "1883"))

# Max time (seconds) any single dependency check may take before it is
# reported as unhealthy. Keeps the health endpoint responsive.
CHECK_TIMEOUT_SECONDS: float = float(os.getenv("HEALTH_CHECK_TIMEOUT", "2.0"))


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class OverallStatus(str, Enum):
    """Aggregate system status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ServiceState(str, Enum):
    """Status of an individual dependency."""

    UP = "up"
    DOWN = "down"


class ServiceStatus(BaseModel):
    """Health information for a single dependency."""

    status: ServiceState = Field(..., description="Current state of the service.")
    latency_ms: Optional[float] = Field(
        None, description="Time taken by the health probe in milliseconds."
    )
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional non-sensitive diagnostic information."
    )
    error: Optional[str] = Field(
        None, description="Short error description if the service is down."
    )


class ServicesHealth(BaseModel):
    """Health information for all monitored services."""

    database: ServiceStatus
    mqtt_broker: ServiceStatus
    devices: ServiceStatus


class HealthResponse(BaseModel):
    """Response model for the system health endpoint."""

    status: OverallStatus = Field(..., description="Aggregate system status.")
    timestamp: str = Field(..., description="Current UTC time in ISO 8601 format.")
    services: ServicesHealth


# --------------------------------------------------------------------------- #
# Service checks
# --------------------------------------------------------------------------- #


async def _check_database() -> Dict[str, Any]:
    """
    Check database connectivity.

    Mock implementation. Replace with a real probe, for example::

        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    """
    await asyncio.sleep(0)  # Yield control; stands in for real async I/O.
    return {"engine": "postgresql", "mock": True}


async def _check_mqtt_broker() -> Dict[str, Any]:
    """
    Check MQTT broker reachability via a plain TCP connection.

    Opens a socket to the broker's host/port, which verifies the broker is
    listening without requiring an MQTT client session.

    Raises:
        OSError: If the broker cannot be reached.
    """
    writer: Optional[asyncio.StreamWriter] = None
    try:
        _, writer = await asyncio.open_connection(MQTT_HOST, MQTT_PORT)
        return {"host": MQTT_HOST, "port": MQTT_PORT}
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except (OSError, socket.error):
                pass


async def _check_devices() -> Dict[str, Any]:
    """
    Report the status of registered IoT devices.

    Mock implementation. Replace with a query against the device registry,
    e.g. counting devices whose last heartbeat is within an acceptable window.
    """
    await asyncio.sleep(0)
    registered, online = 12, 11  # Mock values.
    return {"registered": registered, "online": online, "offline": registered - online}


async def _run_check(check: Callable[[], Awaitable[Dict[str, Any]]]) -> ServiceStatus:
    """
    Execute a single service check with timing, timeout and error handling.

    Never raises: any failure is captured and returned as a ``DOWN`` status so
    one failing dependency cannot break the whole health report.

    Args:
        check: Async callable returning a dict of diagnostic details.

    Returns:
        A populated ``ServiceStatus``.
    """
    loop = asyncio.get_running_loop()
    started = loop.time()
    try:
        details = await asyncio.wait_for(check(), timeout=CHECK_TIMEOUT_SECONDS)
        return ServiceStatus(
            status=ServiceState.UP,
            latency_ms=round((loop.time() - started) * 1000, 2),
            details=details,
        )
    except asyncio.TimeoutError:
        logger.warning("Health check %s timed out", check.__name__)
        error = f"Timed out after {CHECK_TIMEOUT_SECONDS}s"
    except Exception as exc:  # noqa: BLE001 - health probe must never raise.
        logger.exception("Health check %s failed", check.__name__)
        error = f"{type(exc).__name__}: {exc}"

    return ServiceStatus(
        status=ServiceState.DOWN,
        latency_ms=round((loop.time() - started) * 1000, 2),
        error=error,
    )


def _aggregate_status(services: ServicesHealth) -> OverallStatus:
    """
    Derive the overall system status from individual service states.

    - Database down            -> UNHEALTHY (core dependency).
    - Any other service down   -> DEGRADED.
    - Everything up            -> HEALTHY.
    """
    if services.database.status is ServiceState.DOWN:
        return OverallStatus.UNHEALTHY
    if (
        services.mqtt_broker.status is ServiceState.DOWN
        or services.devices.status is ServiceState.DOWN
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
        "Returns the aggregate health of the AeroSoil backend along with the "
        "status of the database, MQTT broker, and registered devices. "
        "Responds with HTTP 503 when a core dependency is unavailable."
    ),
    responses={
        503: {"description": "A core dependency is unavailable.", "model": HealthResponse},
    },
)
async def health_check() -> JSONResponse:
    """
    Check overall system health.

    All service probes run concurrently, each guarded by a timeout, so the
    endpoint stays fast and resilient even when a dependency is slow or down.
    """
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
        return JSONResponse(status_code=http_status, content=payload.model_dump(mode="json"))

    except Exception as exc:  # noqa: BLE001 - last-resort guard.
        logger.exception("Unexpected error while building health report")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": OverallStatus.UNHEALTHY.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": f"Health check failed: {type(exc).__name__}",
            },
        )