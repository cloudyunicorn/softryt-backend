"""
SoftRYT Backend — In-Process Scheduler
==========================================
APScheduler-based alternative for environments where GitHub Actions
cannot reach the backend (e.g., Railway, Render).

Runs the scrape → regenerate pipeline weekly.
To enable: import and call `start_scheduler()` in the app lifespan.
"""

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import get_supabase_client
from app.services.scraper import scrape_tool
from app.services.orchestrator import generate_comparison

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def weekly_scrape_and_regenerate():
    """
    Weekly job: scrapes all active tools and regenerates comparison pages
    where content has changed.
    
    Flow:
    1. Fetch all active tools from the database
    2. Scrape each tool's pricing page
    3. Check which tools had content changes (via content_hash)
    4. Regenerate comparison pages for affected tools
    """
    db = get_supabase_client()
    logger.info("🔄 Starting weekly scrape & regeneration job...")

    try:
        # Step 1: Fetch all active tools
        tools_result = db.table("tools").select("id, name, slug").eq("is_active", True).execute()
        tools = tools_result.data or []
        logger.info(f"Found {len(tools)} active tools to scrape")

        # Step 2: Scrape each tool
        changed_tool_ids = set()
        for tool in tools:
            try:
                # Get existing hash
                existing = (
                    db.table("tool_features")
                    .select("content_hash")
                    .eq("tool_id", tool["id"])
                    .maybe_single()
                    .execute()
                )
                old_hash = existing.data.get("content_hash") if existing.data else None

                # Scrape
                scraped = await scrape_tool(tool["id"])

                # Check for changes
                if scraped.content_hash != old_hash:
                    changed_tool_ids.add(tool["id"])
                    logger.info(f"  ✅ {tool['name']}: Content changed")
                else:
                    logger.info(f"  ⏭️  {tool['name']}: No changes")

            except Exception as e:
                logger.error(f"  ❌ {tool['name']}: Scrape failed - {e}")

        # Step 3: Regenerate affected comparison pages
        if changed_tool_ids:
            logger.info(f"Regenerating pages for {len(changed_tool_ids)} changed tools...")

            pages_result = db.table("generated_pages").select(
                "tool_a_id, tool_b_id, slug"
            ).eq("published_status", "published").execute()

            for page in (pages_result.data or []):
                tool_a_id = page.get("tool_a_id")
                tool_b_id = page.get("tool_b_id")

                if tool_a_id in changed_tool_ids or tool_b_id in changed_tool_ids:
                    try:
                        logger.info(f"  Regenerating: {page['slug']}")
                        await generate_comparison(tool_a_id, tool_b_id)
                        logger.info(f"  ✅ Regenerated: {page['slug']}")
                    except Exception as e:
                        logger.error(f"  ❌ Regeneration failed for {page['slug']}: {e}")

        logger.info("✅ Weekly scrape & regeneration job completed")

    except Exception as e:
        logger.error(f"❌ Weekly job failed: {e}")


def start_scheduler():
    """
    Start the APScheduler with the weekly scrape job.
    Call this during application startup if using in-process scheduling.
    """
    scheduler.add_job(
        weekly_scrape_and_regenerate,
        CronTrigger(day_of_week="sun", hour=2, minute=0),  # Every Sunday at 2 AM
        id="weekly_scrape",
        name="Weekly Scrape & Regeneration",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("📅 Scheduler started: Weekly scrape job scheduled for Sundays at 2:00 AM")


def stop_scheduler():
    """Gracefully stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("📅 Scheduler stopped")
