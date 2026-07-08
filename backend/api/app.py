"""
TREDO — FastAPI Application
Creates the FastAPI app with lifespan management.
This is the entry point for the backend server.

Run:
    uvicorn backend.api.app:app --reload --port 8000
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.lifespan import lifespan
from backend.api.routes import router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title="TREDO",
        description="Autonomous Trading Intelligence — API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS for Electron
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routes
    application.include_router(router)

    return application


# The app instance that uvicorn will use
app = create_app()
