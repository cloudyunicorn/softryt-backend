"""
SoftRYT Backend — Comprehensive Scraper Router
==================================================
FastAPI endpoints for the deep-crawl comprehensive scraping pipeline.

POST /api/v1/tools/comprehensive-scrape
  - Single tool: accepts a tool_id and base_url

POST /api/v1/tools/comprehensive-scrape-all
  - Batch: scrapes ALL active tools from the database sequentially
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional

from app.database import get_db
from app.models.comprehensive_scraper import (
    ComprehensiveScrapeRequest,
    ComprehensiveScrapeResponse,
    ComprehensiveToolData,
)
from app.services.scraper_pipeline import run_comprehensive_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tools", tags=["Comprehensive Scraper"])


# ── Response Models ──────────────────────────────────────────

class ToolScrapeResult(BaseModel):
    """Result for a single tool in a batch scrape."""
    tool_id: str
    tool_name: str
    status: str  # "completed" | "failed" | "skipped"
    urls_scraped: int = 0
    markdown_chars: int = 0
    error: Optional[str] = None


class BatchScrapeResponse(BaseModel):
    """Response for the batch scrape-all endpoint."""
    status: str = "completed"
    total_tools: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[ToolScrapeResult] = Field(default_factory=list)


# ── Single Tool Endpoint ─────────────────────────────────────

@router.post("/comprehensive-scrape", response_model=ComprehensiveScrapeResponse)
async def comprehensive_scrape(request: ComprehensiveScrapeRequest):
    """
    Run the deep-crawl comprehensive scraping pipeline for a **single tool**.

    This endpoint:
      1. Discovers up to 15 high-value URLs from the tool's sitemap or homepage
      2. Scrapes each page to full-fidelity Markdown (preserving tables, lists, code)
      3. Sends the combined payload to Llama 3.3 70B for enterprise-grade analysis
      4. Upserts the structured result into the `tool_features` table

    **WARNING:** This is a long-running operation (30-90 seconds depending on site size).
    """
    try:
        result = await run_comprehensive_pipeline(
            tool_id=request.tool_id,
            base_url=request.base_url,
        )

        return ComprehensiveScrapeResponse(
            tool_id=request.tool_id,
            tool_name=result["tool_name"],
            status="completed",
            urls_discovered=result["urls_discovered"],
            urls_scraped=result["urls_scraped"],
            markdown_chars=result["markdown_chars"],
            data=ComprehensiveToolData(**result["data"]),
            message=(
                f"Successfully scraped {result['urls_scraped']} pages "
                f"({result['markdown_chars']} chars) and synthesized comprehensive data"
            ),
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Comprehensive scrape failed for {request.tool_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline failed: {str(e)[:500]}",
        )


# ── Batch Scrape All Endpoint ────────────────────────────────

@router.post("/comprehensive-scrape-all", response_model=BatchScrapeResponse)
async def comprehensive_scrape_all(
    category: Optional[str] = Query(None, description="Filter tools by category (optional)"),
    limit: int = Query(100, ge=1, le=500, description="Max number of tools to scrape"),
    skip_existing: bool = Query(False, description="Skip tools that already have comprehensive_data"),
):
    """
    Run the comprehensive scraping pipeline on **ALL active tools** in the database.

    For each tool, it:
      1. Reads `website_url` from the `tools` table
      2. Runs the full deep-crawl pipeline (discover → scrape → synthesize → upsert)
      3. Continues to the next tool even if one fails

    **Query Parameters:**
    - `category`: Only scrape tools in a specific category
    - `limit`: Maximum number of tools to process (default: 100)
    - `skip_existing`: If true, skips tools that already have `comprehensive_data` in `tool_features`

    **WARNING:** This is an extremely long-running operation.
    Expect ~60 seconds per tool. 74 tools ≈ ~75 minutes.
    """
    db = get_db()

    # Fetch all active tools
    query = db.table("tools").select("id, name, website_url").eq("is_active", True)
    if category:
        query = query.eq("category", category)
    query = query.order("name").limit(limit)

    tools_result = query.execute()
    tools = tools_result.data or []

    if not tools:
        return BatchScrapeResponse(
            status="completed",
            total_tools=0,
            message="No active tools found",
        )

    # If skip_existing, check which tools already have comprehensive_data
    skip_ids: set[str] = set()
    if skip_existing:
        existing_result = (
            db.table("tool_features")
            .select("tool_id")
            .not_.is_("comprehensive_data", "null")
            .execute()
        )
        skip_ids = {row["tool_id"] for row in (existing_result.data or [])}

    results: list[ToolScrapeResult] = []
    succeeded = 0
    failed = 0
    skipped = 0

    for i, tool in enumerate(tools, 1):
        tool_id = tool["id"]
        tool_name = tool["name"]
        website_url = tool.get("website_url")

        # Skip if no URL
        if not website_url:
            logger.warning(f"[{i}/{len(tools)}] Skipping {tool_name}: no website_url")
            results.append(ToolScrapeResult(
                tool_id=tool_id, tool_name=tool_name,
                status="skipped", error="No website_url",
            ))
            skipped += 1
            continue

        # Skip if already scraped
        if tool_id in skip_ids:
            logger.info(f"[{i}/{len(tools)}] Skipping {tool_name}: already has comprehensive_data")
            results.append(ToolScrapeResult(
                tool_id=tool_id, tool_name=tool_name,
                status="skipped", error="Already has comprehensive_data",
            ))
            skipped += 1
            continue

        logger.info(f"[{i}/{len(tools)}] Processing {tool_name} ({website_url})...")

        try:
            result = await run_comprehensive_pipeline(
                tool_id=tool_id,
                base_url=website_url,
            )
            results.append(ToolScrapeResult(
                tool_id=tool_id,
                tool_name=tool_name,
                status="completed",
                urls_scraped=result["urls_scraped"],
                markdown_chars=result["markdown_chars"],
            ))
            succeeded += 1
            logger.info(f"[{i}/{len(tools)}] {tool_name} completed successfully")

        except Exception as e:
            error_msg = str(e)[:200]
            logger.error(f"[{i}/{len(tools)}] {tool_name} failed: {error_msg}")
            results.append(ToolScrapeResult(
                tool_id=tool_id,
                tool_name=tool_name,
                status="failed",
                error=error_msg,
            ))
            failed += 1

    return BatchScrapeResponse(
        status="completed",
        total_tools=len(tools),
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        results=results,
    )
