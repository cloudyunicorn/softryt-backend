"""
SoftRYT Backend — Supabase Database Client
============================================
Factory for creating and reusing the Supabase client.
Uses the publishable key for all database operations.
"""

from supabase import create_client, Client
from app.config import get_settings
from functools import lru_cache


@lru_cache
def get_supabase_client() -> Client:
    """
    Creates a cached Supabase client singleton.
    
    Uses the publishable key (stored as SUPABASE_SERVICE_ROLE_KEY in .env)
    for all backend operations including reads and writes.
    """
    settings = get_settings()
    client = create_client(
        settings.supabase_url,
        settings.supabase_key,
    )
    return client


def get_db() -> Client:
    """
    Dependency injection helper for FastAPI routes.
    Returns the Supabase client for database operations.
    """
    return get_supabase_client()
