"""
Cloudy Unicorn Backend — Blog API Router
============================================
Endpoints for generating and managing blog posts.
Completely separate from the SaaS comparison/review routes.

All endpoints require API key authentication.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import get_supabase_client
from app.services.blog_orchestrator import generate_blog_post

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/blog", tags=["Blog"])


# ── Request / Response Models ────────────────────────────────

class GenerateBlogRequest(BaseModel):
    """Request body for blog generation."""
    topic: str
    tags: list[str] | None = None


class GenerateBlogResponse(BaseModel):
    """Response from blog generation pipeline."""
    post_id: str | None
    slug: str | None
    title: str | None
    status: str
    error: str | None = None
    duration_ms: int
    pages_researched: int
    research_urls: list[str]


class BlogPostSummary(BaseModel):
    """Summary of a blog post for list views."""
    id: str
    slug: str
    title: str
    meta_description: str
    topic: str
    tags: list[str]
    cover_image_url: str | None
    published_status: str
    published_at: str | None
    view_count: int
    created_at: str
    updated_at: str


# ── Endpoints ────────────────────────────────────────────────

@router.post("/generate", response_model=GenerateBlogResponse)
async def generate_blog(request: GenerateBlogRequest):
    """
    Generate a blog post from a topic.

    Pipeline: Research (Playwright scraping) → Write (Kimi K2.6) → Save (Supabase)

    This is a long-running endpoint (~60-120s) that:
    1. Researches the topic by scraping Google, TechCrunch, HackerNews, etc.
    2. Generates a full MDX blog post using moonshotai/kimi-k2.6 via NVIDIA NIM
    3. Saves the post to the blog_posts table (separate from generated_pages)
    """
    if not request.topic.strip():
        raise HTTPException(status_code=400, detail="Topic cannot be empty")

    logger.info(f"📝 Blog generation requested: '{request.topic}'")

    try:
        result = await generate_blog_post(
            topic=request.topic.strip(),
            tags=request.tags,
        )
        return GenerateBlogResponse(**result)

    except Exception as e:
        logger.error(f"Blog generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_blog_posts(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """
    List all blog posts, optionally filtered by status.
    Returns posts ordered by creation date (newest first).
    """
    db = get_supabase_client()

    query = db.table("blog_posts").select(
        "id, slug, title, meta_description, topic, tags, "
        "cover_image_url, published_status, published_at, "
        "view_count, created_at, updated_at"
    )

    if status:
        query = query.eq("published_status", status)

    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
    result = query.execute()

    return {
        "posts": result.data or [],
        "count": len(result.data or []),
    }


@router.get("/{slug}")
async def get_blog_post(slug: str):
    """
    Get a single blog post by slug.
    Returns the full post including markdown content.
    """
    db = get_supabase_client()

    result = db.table("blog_posts").select("*").eq("slug", slug).single().execute()

    if not result.data:
        raise HTTPException(status_code=404, detail=f"Blog post '{slug}' not found")

    return result.data
