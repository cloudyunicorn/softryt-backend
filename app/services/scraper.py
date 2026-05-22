"""
SoftRYT Backend — Playwright Web Scraper
==========================================
Async scraper that extracts pricing and feature data from SaaS tool websites.

Key Features:
  - Headless Chromium with stealth settings (user-agent rotation, viewport randomization)
  - AI-powered structured extraction of pricing tiers and feature lists via GPT-4o-mini
  - Content hashing for change detection on re-scrape
  - Stores results in the `tool_features` Supabase table

NOTE: On Windows, asyncio's default event loop does not support subprocess creation.
      Playwright's sync API is used inside a thread executor to work around this.
"""

import hashlib
import json
import random
import logging
import asyncio
from typing import Optional
from uuid import UUID
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI
from playwright.sync_api import sync_playwright, Page as SyncPage
from app.config import get_settings
from app.database import get_supabase_client
from app.models.scraper import ScrapedToolData, PricingTier

logger = logging.getLogger(__name__)

# Thread pool for running sync Playwright in async context
_executor = ThreadPoolExecutor(max_workers=2)

# ──────────────────────────────────────────────────────────────
# STEALTH CONFIGURATION
# Rotate user agents and viewports to avoid basic bot detection
# ──────────────────────────────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1366, "height": 768},
]

# ──────────────────────────────────────────────────────────────
# AI EXTRACTION PROMPT
# Sent to GPT-4o-mini to extract structured pricing/features
# from raw scraped text
# ──────────────────────────────────────────────────────────────

AI_EXTRACTION_PROMPT = """You are a data extraction expert. Analyze the following raw text from a SaaS tool's pricing page and extract ALL pricing tiers and key features.

IMPORTANT RULES:
- Extract EVERY pricing tier/plan mentioned (Free, Starter, Plus, Pro, Business, Enterprise, etc.)
- For each tier, capture the exact plan name, price (monthly or annual), and ALL listed features
- If a price is not shown or says "Contact Sales", use "Contact Sales"
- Include the billing period if mentioned (e.g., "/month per user", "/year")
- Extract up to 30 key features that differentiate this tool
- Be thorough — missing a tier is worse than including an extra one

Return your response as valid JSON with this exact structure:
{
  "pricing_tiers": [
    {
      "name": "Plan Name",
      "price": "$X/month per user",
      "features": ["Feature 1", "Feature 2", "Feature 3"]
    }
  ],
  "key_features": ["Feature 1", "Feature 2", "Feature 3"]
}

Return ONLY valid JSON, no markdown fences, no explanations."""


def _compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content for change detection."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _extract_raw_text(page: SyncPage) -> str:
    """
    Extracts clean visible text content from the current page.
    Waits for load state and SPA hydration before extracting.
    """
    settings = get_settings()

    # Wait for main content to load (use 'load' instead of 'networkidle' 
    # because many SaaS sites have persistent connections that never settle)
    page.wait_for_load_state("load", timeout=settings.scraper_timeout)
    # Give SPAs time to hydrate/render pricing cards
    page.wait_for_timeout(3000)

    # Extract the full visible text content of the page
    raw_text = page.evaluate("""
        () => {
            // Remove script/style elements to get clean text
            const clone = document.body.cloneNode(true);
            clone.querySelectorAll('script, style, noscript, svg').forEach(el => el.remove());
            return clone.innerText;
        }
    """)

    return raw_text


def _ai_extract_pricing(raw_text: str, tool_name: str) -> tuple[list[dict], list[str]]:
    """
    Uses GPT-4o-mini to extract structured pricing tiers and key features
    from the raw scraped text content.
    
    This is far more reliable than CSS-selector-based extraction because:
    - Every SaaS site has different HTML structure
    - SPAs render pricing dynamically with custom components
    - The AI can understand context and extract ALL tiers accurately
    
    Returns: (pricing_tiers, key_features)
    """
    settings = get_settings()
    
    # Build OpenAI client kwargs — route to NVIDIA NIM if model has a slash
    client_kwargs = {}
    if settings.nvidia_api_key and "/" in settings.scraper_model:
        client_kwargs["api_key"] = settings.nvidia_api_key
        client_kwargs["base_url"] = "https://integrate.api.nvidia.com/v1"
    else:
        client_kwargs["api_key"] = settings.openai_api_key

    client = OpenAI(**client_kwargs)
    
    # Truncate raw text to fit in context window (keep first 15K chars which 
    # typically contains all pricing info on the page)
    truncated_text = raw_text[:15000]
    
    user_message = f"""Tool name: {tool_name}

Raw text from their pricing page:

{truncated_text}"""

    try:
        response = client.chat.completions.create(
            model=settings.scraper_model,
            messages=[
                {"role": "system", "content": AI_EXTRACTION_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,  # Low temperature for precise extraction
            max_tokens=4000,
        )

        result_text = response.choices[0].message.content.strip()
        
        # Handle potential markdown code fences around JSON
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()
        
        data = json.loads(result_text)
        
        pricing_tiers = data.get("pricing_tiers", [])
        key_features = data.get("key_features", [])
        
        logger.info(
            f"AI extracted {len(pricing_tiers)} pricing tiers and "
            f"{len(key_features)} key features for {tool_name}"
        )
        
        return pricing_tiers, key_features

    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"AI extraction failed for {tool_name}: {e}")
        # Return empty results on failure — the raw text is still stored
        return [], []


def _sync_scrape_tool(tool_id_str: str) -> dict:
    """
    Synchronous scraping function that runs inside a thread.
    
    This uses Playwright's sync API to avoid Windows asyncio subprocess issues.
    
    Pipeline:
    1. Fetch tool info from DB
    2. Launch stealth browser & navigate to pricing page
    3. Extract raw text content
    4. Send raw text to GPT-4o-mini for structured extraction
    5. Upsert results into tool_features table
    
    Returns a dict with all scraped data.
    """
    settings = get_settings()

    # Create a fresh Supabase client for this thread
    # (the cached singleton may not be thread-safe when used from ThreadPoolExecutor)
    from supabase import create_client
    db = create_client(settings.supabase_url, settings.supabase_key)

    # Step 1: Get the tool's pricing URL from the database
    tool_result = db.table("tools").select("*").eq("id", tool_id_str).single().execute()

    if not tool_result or not tool_result.data:
        raise ValueError(f"Tool with ID {tool_id_str} not found")

    tool = tool_result.data

    # Use pricing_url if available, otherwise fall back to website_url
    scrape_url = tool.get("pricing_url") or tool.get("website_url")
    logger.info(f"Scraping {tool['name']} at {scrape_url}")

    with sync_playwright() as pw:
        # Step 2: Launch stealth browser
        browser = pw.chromium.launch(
            headless=settings.scraper_headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        # Create stealth page with randomized fingerprint
        user_agent = random.choice(USER_AGENTS)
        viewport = random.choice(VIEWPORTS)

        context = browser.new_context(
            user_agent=user_agent,
            viewport=viewport,
            locale="en-US",
            timezone_id="America/New_York",
        )

        page = context.new_page()

        # Remove the navigator.webdriver flag that exposes automation
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        try:
            # Step 3: Navigate and extract raw text
            page.goto(scrape_url, wait_until="domcontentloaded", timeout=settings.scraper_timeout)
            raw_text = _extract_raw_text(page)

            # Step 4: Compute content hash for change detection
            content_hash = _compute_content_hash(raw_text)

            # Step 5: Use AI to extract structured pricing & features
            logger.info(f"Sending {len(raw_text)} chars to {settings.scraper_model} for extraction...")
            pricing_tiers_raw, key_features = _ai_extract_pricing(raw_text, tool["name"])

            # Structure the pricing tiers
            pricing_tiers = []
            for tier in pricing_tiers_raw:
                pricing_tiers.append(
                    PricingTier(
                        name=tier.get("name", "Unknown"),
                        price=tier.get("price", "Contact Sales"),
                        features=tier.get("features", []),
                    ).model_dump()
                )

            # Step 6: Upsert into tool_features table
            upsert_data = {
                "tool_id": tool_id_str,
                "pricing_tiers": pricing_tiers,
                "key_features": key_features,
                "raw_content": raw_text[:50000],
                "content_hash": content_hash,
                "last_scraped_at": "now()",
            }

            db.table("tool_features").upsert(
                upsert_data,
                on_conflict="tool_id",
            ).execute()

            logger.info(f"Successfully scraped {tool['name']}: {len(pricing_tiers)} tiers, {len(key_features)} features")

            return {
                "tool_id": tool_id_str,
                "tool_name": tool["name"],
                "pricing_tiers": pricing_tiers,
                "key_features": key_features,
                "raw_content": raw_text[:50000],
                "content_hash": content_hash,
            }

        finally:
            browser.close()


async def scrape_tool(tool_id: UUID) -> ScrapedToolData:
    """
    Main async scraping function. Runs Playwright's sync API in a thread executor
    to avoid Windows asyncio subprocess limitations.
    
    Returns: ScrapedToolData with all extracted information
    """
    loop = asyncio.get_running_loop()

    # Run the sync scraper in a thread to avoid Windows asyncio limitations
    result = await loop.run_in_executor(
        _executor,
        _sync_scrape_tool,
        str(tool_id),
    )

    return ScrapedToolData(
        tool_id=tool_id,
        tool_name=result["tool_name"],
        pricing_tiers=[PricingTier(**t) if isinstance(t, dict) else t for t in result["pricing_tiers"]],
        key_features=result["key_features"],
        raw_content=result["raw_content"],
        content_hash=result["content_hash"],
    )


async def check_for_changes(tool_id: UUID) -> bool:
    """
    Re-scrapes a tool and compares the content hash to detect changes.
    Returns True if the content has changed since the last scrape.
    """
    db = get_supabase_client()

    # Get the current hash from the database
    existing = db.table("tool_features").select("content_hash").eq("tool_id", str(tool_id)).single().execute()
    old_hash = existing.data.get("content_hash") if existing.data else None

    # Re-scrape and get new data
    new_data = await scrape_tool(tool_id)

    # Compare hashes
    return new_data.content_hash != old_hash
