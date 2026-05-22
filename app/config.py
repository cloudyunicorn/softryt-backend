"""
SoftRYT Backend — Application Configuration
============================================
Centralizes all environment variables using Pydantic Settings.
Values are loaded from .env file automatically.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── Supabase ──────────────────────────────────────────────
    supabase_url: str
    supabase_key: str  # Publishable key for new Supabase

    # ── OpenAI & NVIDIA ───────────────────────────────────────
    openai_api_key: str
    nvidia_api_key: str | None = None

    # ── Frontend ──────────────────────────────────────────────
    frontend_url: str = "http://localhost:3000"

    # ── Revalidation ──────────────────────────────────────────
    revalidation_secret: str = "softryt-revalidation-secret-change-me"

    # ── API Security ──────────────────────────────────────────
    api_key: str  # Required — protects all endpoints

    # ── AI Model Configuration ────────────────────────────────
    writer_model: str = "gpt-4o-mini"
    fact_checker_model: str = "gpt-4o-mini"
    scraper_model: str = "gpt-4o-mini"  # Model for AI-powered pricing extraction
    max_retries: int = 2  # Max fact-check → rewrite cycles

    # ── Scraper Configuration ─────────────────────────────────
    scraper_timeout: int = 30000  # Playwright timeout in ms
    scraper_headless: bool = True

    # ── Deep Scraper Configuration ────────────────────────────
    deep_scrape_model: str = "meta/llama-3.3-70b-instruct"
    deep_scrape_max_urls: int = 15

    # ── ScrapingBee (Anti-Bot Fallback) ───────────────────────
    scrapingbee_api_key: str | None = None

    # ── Blog Configuration ────────────────────────────────────
    blog_writer_model: str = "moonshotai/kimi-k2.6"
    blog_research_max_urls: int = 8

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Cached singleton for application settings."""
    return Settings()
