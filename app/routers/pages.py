"""
SoftRYT Backend — Pages Router
==================================
Endpoints for fetching AI-generated pages (used by the Next.js frontend).
"""

from fastapi import APIRouter, HTTPException, Query
from uuid import UUID

from app.database import get_db
from app.models.pages import PageResponse, PageListResponse, PageSlugResponse

router = APIRouter(prefix="/api/v1/pages", tags=["Pages"])


@router.get("/", response_model=PageListResponse)
async def list_pages(
    page_type: str | None = Query(None, description="Filter by page type"),
    status: str = Query("published", description="Filter by publish status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List all generated pages, optionally filtered by type and status.
    Used by the frontend for sitemap generation and page listings.
    """
    db = get_db()
    query = db.table("generated_pages").select("*", count="exact")

    if status:
        query = query.eq("published_status", status)
    if page_type:
        query = query.eq("page_type", page_type)

    query = query.order("updated_at", desc=True).range(offset, offset + limit - 1)
    result = query.execute()

    return PageListResponse(
        pages=result.data or [],
        total=result.count or 0,
    )


@router.get("/slugs", response_model=list[PageSlugResponse])
async def list_slugs():
    """
    List all published page slugs with their update timestamps.
    Used by Next.js generateStaticParams() for ISR.
    """
    db = get_db()
    result = (
        db.table("generated_pages")
        .select("slug, updated_at, page_type")
        .eq("published_status", "published")
        .order("updated_at", desc=True)
        .execute()
    )

    return result.data or []


@router.get("/{slug}", response_model=PageResponse)
async def get_page_by_slug(slug: str):
    """
    Fetch a single generated page by its URL slug.
    
    This is the primary endpoint used by the Next.js frontend
    to render comparison/review pages with ISR.
    """
    db = get_db()
    result = (
        db.table("generated_pages")
        .select("*")
        .eq("slug", slug)
        .eq("published_status", "published")
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Page not found")

    # Increment view count (fire-and-forget, don't block response)
    try:
        current_views = result.data.get("view_count", 0)
        db.table("generated_pages").update(
            {"view_count": current_views + 1}
        ).eq("slug", slug).execute()
    except Exception:
        pass  # Non-critical, don't fail the page load

    return result.data


@router.get("/id/{page_id}", response_model=PageResponse)
async def get_page_by_id(page_id: UUID):
    """Fetch a single generated page by its UUID (for admin/pipeline use)."""
    db = get_db()
    result = (
        db.table("generated_pages")
        .select("*")
        .eq("id", str(page_id))
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Page not found")

    return result.data
