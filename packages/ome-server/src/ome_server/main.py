"""Ome Server — FastAPI application entry point.

Usage:
    ome-server                    # Start on port 8000
    ome-server --port 9000        # Custom port
    uvicorn ome_server.main:app   # Direct uvicorn
"""

from __future__ import annotations

import argparse
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ome_server.routes import agents, anon, auth, chat, life, memories, skills

log = logging.getLogger("ome_server")

# Global Ome store directory
OME_DATA_ROOT = Path(os.environ.get("OME_DATA_ROOT", "~/.ome-server/data")).expanduser()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown."""
    OME_DATA_ROOT.mkdir(parents=True, exist_ok=True)
    log.info("Ome Server starting — data root: %s", OME_DATA_ROOT)
    yield
    log.info("Ome Server shutting down")


app = FastAPI(
    title="Ome Server",
    description="Your AI twin backend — powers the Ome App",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: allow mobile app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount route modules
app.include_router(anon.router, prefix="/api/anon", tags=["anonymous"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(life.router, prefix="/api", tags=["life"])
app.include_router(memories.router, prefix="/api", tags=["memories"])
app.include_router(skills.router, prefix="/api", tags=["skills"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])


@app.get("/")
async def root():
    return {"service": "ome-server", "version": "0.1.0", "status": "running"}


@app.get("/api/health")
async def health():
    return {"ok": True}


def cli():
    parser = argparse.ArgumentParser(prog="ome-server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    uvicorn.run(
        "ome_server.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    cli()
