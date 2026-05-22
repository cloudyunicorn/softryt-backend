"""
SoftRYT Backend — Tools Router
==================================
CRUD endpoints for managing SaaS tools in the database.
"""

from fastapi import APIRouter, HTTPException, Query
from uuid import UUID

from app.database import get_db
from app.models.tools import ToolCreate, ToolUpdate, ToolResponse, ToolListResponse

router = APIRouter(prefix="/api/v1/tools", tags=["Tools"])


@router.post("/", response_model=ToolResponse, status_code=201)
async def create_tool(tool: ToolCreate):
    """
    Create a new SaaS tool entry.
    
    This is the first step before scraping — register a tool with its
    website URL and pricing page URL.
    """
    db = get_db()

    try:
        result = db.table("tools").insert(tool.model_dump()).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create tool")

        return result.data[0]

    except Exception as e:
        if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail=f"Tool with slug '{tool.slug}' already exists",
            )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=ToolListResponse)
async def list_tools(
    category: str | None = Query(None, description="Filter by category"),
    active_only: bool = Query(True, description="Only return active tools"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List all tools with optional category filtering.
    Used by the frontend for tool directory pages and by the pipeline
    to enumerate tools for batch scraping.
    """
    db = get_db()
    query = db.table("tools").select("*", count="exact")

    if active_only:
        query = query.eq("is_active", True)
    if category:
        query = query.eq("category", category)

    query = query.order("name").range(offset, offset + limit - 1)
    result = query.execute()

    return ToolListResponse(
        tools=result.data or [],
        total=result.count or 0,
    )


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(tool_id: UUID):
    """Fetch a single tool by ID."""
    db = get_db()

    result = db.table("tools").select("*").eq("id", str(tool_id)).single().execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Tool not found")

    return result.data


@router.patch("/{tool_id}", response_model=ToolResponse)
async def update_tool(tool_id: UUID, update: ToolUpdate):
    """
    Update a tool's information.
    Only provided fields are updated (partial update).
    """
    db = get_db()

    # Filter out None values for partial update
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = db.table("tools").update(update_data).eq("id", str(tool_id)).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Tool not found")

    return result.data[0]


@router.delete("/{tool_id}", status_code=204)
async def delete_tool(tool_id: UUID):
    """
    Delete a tool and its associated scraped data.
    Cascading delete removes tool_features automatically.
    """
    db = get_db()

    result = db.table("tools").delete().eq("id", str(tool_id)).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Tool not found")

    return None
