from __future__ import annotations

import logging
from typing import Dict

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import health_routes as health
from api.routes import telemetry_routes as telemetry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

APP_TITLE: str = "AeroSoil API"
APP_VERSION: str = "1.0.0"
APP_DESCRIPTION: str = (
    "Backend API for **AeroSoil**, a smart irrigation and soil monitoring "
    "system. Provides system health checks and access to sensor telemetry "
    "reported by ESP32 devices."
)


def create_app() -> FastAPI:
    """
    Application factory.

    Builds the FastAPI instance, configures middleware, registers routers and
    defines the root endpoint.

    Returns:
        A fully configured ``FastAPI`` application.
    """
    application = FastAPI(
        title=APP_TITLE,
        description=APP_DESCRIPTION,
        version=APP_VERSION,
    )

    # ----------------------------------------------------------------------- #
    # Middleware
    # ----------------------------------------------------------------------- #
    # Wide-open CORS for development flexibility. Restrict ``allow_origins``
    # to known frontend URLs before deploying to production.
    # Note: browsers reject wildcard origins combined with credentials, so
    # ``allow_credentials`` is intentionally left disabled.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ----------------------------------------------------------------------- #
    # Routers
    # ----------------------------------------------------------------------- #
    application.include_router(
        health.router,
        prefix="/api/health",
        tags=["Health"],
    )
    application.include_router(
        telemetry.router,
        prefix="/api/telemetry",
        tags=["Telemetry"],
    )

    # ----------------------------------------------------------------------- #
    # Root endpoint
    # ----------------------------------------------------------------------- #
    @application.get(
        "/",
        response_model=Dict[str, str],
        tags=["Root"],
        summary="API root",
        description="Returns a welcome message and the current system status.",
    )
    async def root() -> Dict[str, str]:
        """Welcome endpoint confirming that the API is online."""
        return {
            "message": "Welcome to the AeroSoil API",
            "status": "online",
            "version": APP_VERSION,
            "docs": "/docs",
        }

    logger.info("%s v%s initialized", APP_TITLE, APP_VERSION)
    return application


app: FastAPI = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "backend.api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )