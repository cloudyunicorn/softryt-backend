"""
SoftRYT Backend — Entry Point
================================
Starts the FastAPI server with uvicorn.
Run with: uv run python main.py
Or: uv run uvicorn app.main:app --reload --port 8000
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
