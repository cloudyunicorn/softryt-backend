"""
SoftRYT Backend — Pipeline Router
=====================================
Endpoints for triggering the scrape → generate → fact-check pipeline.
"""

import logging
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.config import get_settings
from app.database import get_db
from app.models.scraper import ScrapeRequest, ScrapeResponse
from app.models.pages import ComparisonRequest, ComparisonResponse, ReviewRequest, ReviewResponse, BulkReviewRequest
from app.services.scraper import scrape_tool, check_for_changes
from app.services.orchestrator import generate_comparison
from app.services.review_orchestrator import generate_review

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Pipeline"])


@router.post("/scrape", response_model=ScrapeResponse)
async def trigger_scrape(request: ScrapeRequest):
    """
    Trigger a scrape for a specific tool.
    
    Launches a headless browser, navigates to the tool's pricing page,
    and extracts structured pricing/feature data into the database.
    """
    db = get_db()

    # Verify the tool exists
    tool = db.table("tools").select("name").eq("id", str(request.tool_id)).single().execute()
    if not tool.data:
        raise HTTPException(status_code=404, detail="Tool not found")

    try:
        # Check if we need to force re-scrape
        if not request.force:
            existing = (
                db.table("tool_features")
                .select("last_scraped_at")
                .eq("tool_id", str(request.tool_id))
                .maybe_single()
                .execute()
            )
            if existing.data:
                from datetime import datetime, timezone, timedelta

                last_scraped = datetime.fromisoformat(existing.data["last_scraped_at"].replace("Z", "+00:00"))
                if datetime.now(timezone.utc) - last_scraped < timedelta(hours=24):
                    return ScrapeResponse(
                        tool_id=request.tool_id,
                        tool_name=tool.data["name"],
                        status="skipped",
                        changed=False,
                        message="Data is fresh (scraped within 24 hours). Use force=true to override.",
                    )

        # Run the scraper
        scraped_data = await scrape_tool(request.tool_id)

        return ScrapeResponse(
            tool_id=request.tool_id,
            tool_name=scraped_data.tool_name,
            status="completed",
            changed=True,
            pricing_tiers_count=len(scraped_data.pricing_tiers),
            features_count=len(scraped_data.key_features),
            message=f"Successfully scraped {scraped_data.tool_name}",
        )

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Scrape failed for tool {request.tool_id}: {e}\n{tb}")
        raise HTTPException(status_code=500, detail=f"Scraping failed: {repr(e)}\n{tb}")


async def scrape_all_task(force: bool):
    """Background task to scrape all tools sequentially."""
    db = get_db()
    
    # Fetch all tool IDs
    tools = db.table("tools").select("id, name").execute()
    if not tools.data:
        logger.info("No tools found to scrape.")
        return

    logger.info(f"Starting bulk scrape of {len(tools.data)} tools (force={force})")
    
    success_count = 0
    fail_count = 0
    
    for tool in tools.data:
        try:
            # Respect 24-hour cache if not forced
            if not force:
                existing = (
                    db.table("tool_features")
                    .select("last_scraped_at")
                    .eq("tool_id", tool["id"])
                    .maybe_single()
                    .execute()
                )
                if existing.data:
                    from datetime import datetime, timezone, timedelta
                    last_scraped = datetime.fromisoformat(existing.data["last_scraped_at"].replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) - last_scraped < timedelta(hours=24):
                        logger.info(f"Skipping {tool['name']} - scraped recently.")
                        continue
            
            await scrape_tool(UUID(tool["id"]))
            success_count += 1
            # Add a small delay between scrapes to be polite to the target servers
            await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"Failed to bulk-scrape {tool['name']}: {e}")
            fail_count += 1
            
    logger.info(f"Bulk scrape finished: {success_count} success, {fail_count} failed.")

import asyncio
from pydantic import BaseModel

class BulkScrapeRequest(BaseModel):
    force: bool = False

@router.post("/scrape/all")
async def trigger_bulk_scrape(request: BulkScrapeRequest, background_tasks: BackgroundTasks):
    """
    Trigger a scrape for ALL tools in the database.
    This runs in the background. Use force=true to ignore the 24-hour cache.
    """
    db = get_db()
    
    tools = db.table("tools").select("id").execute()
    count = len(tools.data) if tools.data else 0
    
    if count == 0:
        raise HTTPException(status_code=404, detail="No tools found in the database")

    background_tasks.add_task(scrape_all_task, request.force)

    return {
        "status": "queued",
        "message": f"Bulk scrape started for {count} tools in the background.",
        "force": request.force
    }


@router.post("/generate-comparison", response_model=ComparisonResponse)
async def trigger_comparison(request: ComparisonRequest, background_tasks: BackgroundTasks):
    """
    Generate a comparison page for two tools.
    
    This triggers the full LangGraph pipeline:
    1. Writer (GPT-4o-mini) generates MDX content
    2. Fact-Checker (GPT-4o-mini) validates accuracy
    3. Content is saved to the `generated_pages` table
    
    If both tools have scraped data, it's used for factual content.
    If not, the writer will work with the tool metadata only.
    """
    db = get_db()

    # Verify both tools exist
    tool_a = db.table("tools").select("name, slug").eq("id", str(request.tool_a_id)).single().execute()
    tool_b = db.table("tools").select("name, slug").eq("id", str(request.tool_b_id)).single().execute()

    if not tool_a.data or not tool_b.data:
        raise HTTPException(status_code=404, detail="One or both tools not found")

    # Check if comparison already exists (unless force_regenerate)
    if not request.force_regenerate:
        sorted_slugs = sorted([tool_a.data["slug"], tool_b.data["slug"]])
        existing_slug = f"{sorted_slugs[0]}-vs-{sorted_slugs[1]}"

        existing = (
            db.table("generated_pages")
            .select("id, slug")
            .eq("slug", existing_slug)
            .maybe_single()
            .execute()
        )

        if existing and existing.data:
            return ComparisonResponse(
                page_id=existing.data["id"],
                slug=existing.data["slug"],
                status="exists",
                message=f"Comparison page already exists. Use force_regenerate=true to overwrite.",
            )

    try:
        # Run the pipeline
        result = await generate_comparison(request.tool_a_id, request.tool_b_id)

        if result["status"] == "completed":
            # Trigger Next.js revalidation in the background
            background_tasks.add_task(_trigger_revalidation, result["slug"])

            return ComparisonResponse(
                page_id=result["page_id"],
                slug=result["slug"],
                status="completed",
                message=f"Comparison page generated successfully in {result['duration_ms']}ms ({result['retries']} retries)",
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Pipeline failed: {result.get('error', 'Unknown error')}",
            )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Comparison generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.post("/revalidate")
async def trigger_revalidation(slug: str):
    """
    Manually trigger Next.js ISR revalidation for a specific page.
    Called after content regeneration to bust the cache.
    """
    await _trigger_revalidation(slug)
    return {"status": "ok", "message": f"Revalidation triggered for /{slug}"}


@router.post("/batch-scrape")
async def batch_scrape(background_tasks: BackgroundTasks):
    """
    Trigger a batch scrape of all active tools.
    Runs in the background and returns immediately.
    """
    db = get_db()
    tools = db.table("tools").select("id, name").eq("is_active", True).execute()

    if not tools.data:
        return {"status": "no_tools", "message": "No active tools found"}

    # Queue each scrape as a background task
    for tool in tools.data:
        background_tasks.add_task(_background_scrape, tool["id"], tool["name"])

    return {
        "status": "queued",
        "message": f"Queued {len(tools.data)} tools for scraping",
        "tools": [t["name"] for t in tools.data],
    }


class BulkComparisonRequest(BaseModel):
    category: str | None = None
    force_regenerate: bool = False


async def generate_all_comparisons_task(category: str | None, force_regenerate: bool):
    """
    Background task to generate comparison pages for all tool pairs
    within the same category. If category is None, generates for ALL categories.
    """
    from itertools import combinations

    db = get_db()

    # Fetch tools, optionally filtered by category
    query = db.table("tools").select("id, name, slug, category")
    if category:
        query = query.eq("category", category)
    tools_result = query.execute()

    if not tools_result.data:
        logger.info(f"No tools found for category={category}")
        return

    # Group tools by category
    categories: dict[str, list[dict]] = {}
    for tool in tools_result.data:
        cat = tool["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(tool)

    total_pairs = 0
    generated = 0
    skipped = 0
    failed = 0

    for cat, tools in categories.items():
        if len(tools) < 2:
            logger.info(f"Skipping category '{cat}' — only {len(tools)} tool(s)")
            continue

        pairs = list(combinations(tools, 2))
        total_pairs += len(pairs)
        logger.info(f"Category '{cat}': {len(tools)} tools → {len(pairs)} comparison pairs")

        for tool_a, tool_b in pairs:
            sorted_slugs = sorted([tool_a["slug"], tool_b["slug"]])
            slug = f"{sorted_slugs[0]}-vs-{sorted_slugs[1]}"

            # Skip if already exists (unless forced)
            if not force_regenerate:
                existing = (
                    db.table("generated_pages")
                    .select("id")
                    .eq("slug", slug)
                    .maybe_single()
                    .execute()
                )
                if existing and existing.data:
                    logger.info(f"Skipping {slug} — already exists")
                    skipped += 1
                    continue

            try:
                logger.info(f"Generating: {tool_a['name']} vs {tool_b['name']} ({slug})")
                result = await generate_comparison(
                    UUID(tool_a["id"]),
                    UUID(tool_b["id"]),
                )
                if result["status"] == "completed":
                    generated += 1
                    logger.info(f"✓ {slug} generated in {result['duration_ms']}ms")
                else:
                    failed += 1
                    logger.error(f"✗ {slug} failed: {result.get('error')}")
            except Exception as e:
                failed += 1
                logger.error(f"✗ {slug} exception: {e}")

            # Delay between generations to avoid rate-limiting
            await asyncio.sleep(3)

    logger.info(
        f"Bulk comparison complete: {generated} generated, {skipped} skipped, "
        f"{failed} failed out of {total_pairs} total pairs"
    )


@router.post("/generate-comparison/all")
async def trigger_bulk_comparison(
    request: BulkComparisonRequest,
    background_tasks: BackgroundTasks,
):
    """
    Generate comparison pages for all tool pairs within the same category.

    - If `category` is provided, only generates for that category.
    - If `category` is null/omitted, generates for ALL categories.
    - Set `force_regenerate=true` to overwrite existing pages.

    Examples:
      POST /api/v1/generate-comparison/all
      Body: {"category": "project-management"}

      POST /api/v1/generate-comparison/all
      Body: {}   ← generates for ALL categories
    """
    db = get_db()

    query = db.table("tools").select("id, category")
    if request.category:
        query = query.eq("category", request.category)
    tools = query.execute()

    if not tools.data:
        raise HTTPException(
            status_code=404,
            detail=f"No tools found{' for category: ' + request.category if request.category else ''}",
        )

    # Count pairs per category
    from itertools import combinations

    categories: dict[str, int] = {}
    for tool in tools.data:
        cat = tool["category"]
        categories[cat] = categories.get(cat, 0) + 1

    total_pairs = sum(
        len(list(combinations(range(count), 2))) for count in categories.values()
    )

    background_tasks.add_task(
        generate_all_comparisons_task, request.category, request.force_regenerate
    )

    return {
        "status": "queued",
        "message": f"Bulk comparison generation started in background.",
        "categories": {cat: count for cat, count in categories.items()},
        "total_pairs": total_pairs,
        "force_regenerate": request.force_regenerate,
    }



# ──────────────────────────────────────────────────────────────
# REVIEW GENERATION ENDPOINTS
# ──────────────────────────────────────────────────────────────

@router.post("/generate-review", response_model=ReviewResponse)
async def trigger_review(request: ReviewRequest, background_tasks: BackgroundTasks):
    db = get_db()
    tool = db.table("tools").select("name, slug").eq("id", str(request.tool_id)).single().execute()
    if not tool.data:
        raise HTTPException(status_code=404, detail="Tool not found")

    if not request.force_regenerate:
        existing_slug = f"review/{tool.data['slug']}"
        existing = db.table("generated_pages").select("id, slug").eq("slug", existing_slug).maybe_single().execute()
        if existing and existing.data:
            return ReviewResponse(
                page_id=existing.data["id"],
                slug=existing.data["slug"],
                status="exists",
                message="Review page already exists. Use force_regenerate=true to overwrite.",
            )

    try:
        result = await generate_review(request.tool_id)
        if result["status"] == "completed":
            background_tasks.add_task(_trigger_revalidation, result["slug"])
            return ReviewResponse(
                page_id=result["page_id"],
                slug=result["slug"],
                status="completed",
                message=f"Review generated successfully in {result['duration_ms']}ms ({result['retries']} retries)",
            )
        else:
            raise HTTPException(status_code=500, detail=f"Pipeline failed: {result.get('error', 'Unknown error')}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Review generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


async def generate_all_reviews_task(category: str | None, force_regenerate: bool):
    db = get_db()
    query = db.table("tools").select("id, name, slug, category")
    if category:
        query = query.eq("category", category)
    tools_result = query.execute()

    if not tools_result.data:
        logger.info(f"No tools found for category={category}")
        return

    total_tools = len(tools_result.data)
    generated = 0
    skipped = 0
    failed = 0

    for tool in tools_result.data:
        slug = f"review/{tool['slug']}"
        if not force_regenerate:
            existing = db.table("generated_pages").select("id").eq("slug", slug).maybe_single().execute()
            if existing and existing.data:
                logger.info(f"Skipping {slug} — already exists")
                skipped += 1
                continue

        try:
            logger.info(f"Generating review for: {tool['name']} ({slug})")
            result = await generate_review(UUID(tool["id"]))
            if result["status"] == "completed":
                generated += 1
                logger.info(f"✓ {slug} generated in {result['duration_ms']}ms")
            else:
                failed += 1
                logger.error(f"✗ {slug} failed: {result.get('error')}")
        except Exception as e:
            failed += 1
            logger.error(f"✗ {slug} exception: {e}")

        import asyncio
        await asyncio.sleep(3)

    logger.info(f"Bulk review complete: {generated} generated, {skipped} skipped, {failed} failed out of {total_tools}")


@router.post("/generate-review/all")
async def trigger_bulk_reviews(request: BulkReviewRequest, background_tasks: BackgroundTasks):
    db = get_db()
    query = db.table("tools").select("id, category")
    if request.category:
        query = query.eq("category", request.category)
    tools = query.execute()

    if not tools.data:
        raise HTTPException(status_code=404, detail=f"No tools found")

    background_tasks.add_task(generate_all_reviews_task, request.category, request.force_regenerate)

    return {
        "status": "queued",
        "message": "Bulk review generation started in background.",
        "total_tools": len(tools.data),
        "force_regenerate": request.force_regenerate,
    }


# ──────────────────────────────────────────────────────────────
# BACKGROUND TASK HELPERS
# ──────────────────────────────────────────────────────────────

async def _trigger_revalidation(slug: str):
    """Send a revalidation request to the Next.js frontend."""
    settings = get_settings()
    revalidation_url = f"{settings.frontend_url}/api/revalidate"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                revalidation_url,
                json={"slug": slug, "secret": settings.revalidation_secret},
                timeout=10.0,
            )
            logger.info(f"Revalidation response for /{slug}: {response.status_code}")
    except Exception as e:
        logger.warning(f"Revalidation failed for /{slug}: {e}")


async def _background_scrape(tool_id: str, tool_name: str):
    """Background task for scraping a single tool."""
    try:
        await scrape_tool(tool_id)
        logger.info(f"Background scrape completed for {tool_name}")
    except Exception as e:
        logger.error(f"Background scrape failed for {tool_name}: {e}")
