"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.routes import api_router
from app.api.websocket import websocket_endpoint, ws_manager
from app.database import init_database
from app.services.trading_engine import initialize_engine
from utils.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    setup_logging()
    logger.info("Starting Weather Trader application...")

    # Initialize database
    await init_database()
    logger.info("Database initialized")

    # Initialize trading engine
    engine = await initialize_engine()
    logger.info("Trading engine initialized")

    yield

    # Shutdown
    logger.info("Shutting down Weather Trader...")
    await engine.stop()


# Create FastAPI application
app = FastAPI(
    title="Weather Trader",
    description="Polymarket Weather Trading System",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(api_router, prefix="/api/v1")


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_route(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket_endpoint(websocket)


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "connections": ws_manager.connection_count}


# Serve frontend in production
frontend_path = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=frontend_path / "assets"), name="static")

    @app.get("/")
    async def serve_frontend():
        """Serve the frontend application."""
        return FileResponse(frontend_path / "index.html")

    @app.get("/{path:path}")
    async def serve_frontend_routes(path: str):
        """Serve frontend routes."""
        file_path = frontend_path / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_path / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8741,
        reload=True,
    )
