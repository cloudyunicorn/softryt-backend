"""
SoftRYT Backend — FastAPI Application Factory
=================================================
Main application module with CORS, lifespan events, and router registration.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.auth import require_api_key
from app.routers import tools, pages, pipeline, comprehensive_scraper, blog

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.
    
    Startup:
    - Validate configuration
    - Initialize database connection
    - Install Playwright browsers (if needed)
    
    Shutdown:
    - Clean up resources
    """
    settings = get_settings()
    logger.info("🚀 SoftRYT Backend starting up...")
    logger.info(f"   Frontend URL: {settings.frontend_url}")
    logger.info(f"   Writer model: {settings.writer_model}")
    logger.info(f"   Fact-checker model: {settings.fact_checker_model}")
    logger.info(f"   API Key protection: ✅ ENABLED")

    # Validate Supabase connection
    from app.database import get_supabase_client
    try:
        db = get_supabase_client()
        logger.info("   ✅ Supabase connection established")
    except Exception as e:
        logger.error(f"   ❌ Supabase connection failed: {e}")

    yield

    logger.info("👋 SoftRYT Backend shutting down...")


def create_app() -> FastAPI:
    """
    Factory function to create and configure the FastAPI application.
    
    Registers:
    - Global API key authentication on ALL routes
    - CORS middleware for frontend access
    - API routers for tools, pages, and pipeline
    - Health check endpoint
    """
    settings = get_settings()

    # Disable Swagger UI / ReDoc in production for extra security
    is_production = os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RENDER")
    
    app = FastAPI(
        title="SoftRYT API",
        description="Automation engine for programmatic SEO affiliate content generation",
        version="1.0.0",
        lifespan=lifespan,
        # In production: docs are hidden. Locally: still accessible.
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
    )

    # ── CORS Middleware ───────────────────────────────────────
    # Allow the Next.js frontend to make requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            settings.frontend_url,
            "http://localhost:3000",
            "http://localhost:3001",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Register Routers ─────────────────────────────────────
    # Apply API key requirement to all API routes
    api_auth = [Depends(require_api_key)]
    app.include_router(tools.router, dependencies=api_auth)
    app.include_router(pages.router, dependencies=api_auth)
    app.include_router(pipeline.router, dependencies=api_auth)
    app.include_router(comprehensive_scraper.router, dependencies=api_auth)
    app.include_router(blog.router, dependencies=api_auth)

    # ── Health Check ──────────────────────────────────────────
    @app.get("/health", tags=["System"])
    async def health_check():
        """Simple health check endpoint for monitoring."""
        return {
            "status": "healthy",
            "service": "softryt-backend",
            "version": "1.0.0",
        }

    @app.get("/", tags=["System"])
    async def root():
        """Root endpoint with API info."""
        return {
            "name": "SoftRYT API",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health",
        }

    return app


# Create the app instance (used by uvicorn)
app = create_app()
