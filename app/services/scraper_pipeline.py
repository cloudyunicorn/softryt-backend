"""
SoftRYT Backend — Comprehensive Scraper Pipeline
====================================================
Deep-crawl data extraction and AI synthesis pipeline.

Pipeline stages:
  1. discover_comprehensive_urls() — Sitemap parsing + fallback Playwright spider
  2. scrape_to_markdown()           — Full-fidelity HTML → Markdown extraction
  3. synthesize_deep_data()         — LLM-powered structured data synthesis
  4. run_comprehensive_pipeline()   — Orchestrator: discover → scrape → synthesize → upsert

Uses sync Playwright inside ThreadPoolExecutor to avoid Windows asyncio
subprocess limitations (same pattern as the existing scraper.py).
"""

import re
import logging
import asyncio
import hashlib
import random
from typing import Optional
from uuid import UUID
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import httpx
import html2text
from playwright.sync_api import sync_playwright
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.models.comprehensive_scraper import ComprehensiveToolData

logger = logging.getLogger(__name__)

# Thread pool for sync Playwright operations
_executor = ThreadPoolExecutor(max_workers=2)

# ── Stealth Configuration ────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
]

# URL patterns that indicate high-value pages for SaaS analysis
HIGH_VALUE_PATTERNS = re.compile(
    r"/(pricing|plans|buy|compare|features|capabilities|tour|specs|overview|product|docs|documentation|use-cases|usecases|"
    r"integrations|security|enterprise|about|platform|solutions|api|changelog|comparison)",
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════════
# STEP 1: Deep Sitemap & URL Discovery
# ═══════════════════════════════════════════════════════════════

def _discover_urls_from_sitemap(base_url: str, max_urls: int) -> list[str]:
    """
    Fetch and parse /sitemap.xml for high-value URLs.
    Handles nested sitemap indexes (e.g. sitemap_index.xml -> pages-sitemap.xml).
    """
    urls: list[str] = []
    
    # We will use a queue to handle nested sitemaps (max depth 2)
    sitemap_queue = [
        (f"{base_url.rstrip('/')}/sitemap.xml", 0),
        (f"{base_url.rstrip('/')}/sitemap_index.xml", 0),
    ]
    visited_sitemaps = set()
    MAX_DEPTH = 2

    while sitemap_queue and len(urls) < max_urls:
        sitemap_url, depth = sitemap_queue.pop(0)
        
        if sitemap_url in visited_sitemaps or depth > MAX_DEPTH:
            continue
            
        visited_sitemaps.add(sitemap_url)

        try:
            resp = httpx.get(sitemap_url, follow_redirects=True, timeout=15)
            if resp.status_code != 200:
                continue

            # Extract all <loc> entries
            loc_matches = re.findall(r"<loc>\s*(.*?)\s*</loc>", resp.text)
            
            for loc in loc_matches:
                loc = loc.strip()
                # If it's a nested sitemap, add it to the queue
                if loc.endswith(".xml"):
                    if loc not in visited_sitemaps and depth < MAX_DEPTH:
                        sitemap_queue.append((loc, depth + 1))
                # Otherwise, check if it's a high-value page
                elif HIGH_VALUE_PATTERNS.search(loc):
                    if loc not in urls:
                        urls.append(loc)
                        if len(urls) >= max_urls:
                            break

            if len(urls) > 0 and depth == 0:
                 logger.info(f"Sitemap: found high-value matches at {sitemap_url}")

        except Exception as e:
            logger.warning(f"Sitemap fetch failed for {sitemap_url}: {e}")
            continue

    # Always include the base URL itself
    base_clean = base_url.rstrip("/")
    if base_clean not in urls:
        urls.insert(0, base_clean)

    # Deduplicate and cap
    seen = set()
    unique: list[str] = []
    for u in urls:
        normalized = u.rstrip("/")
        if normalized not in seen:
            seen.add(normalized)
            unique.append(u)

    return unique[:max_urls]


def _discover_urls_via_spider(base_url: str, max_urls: int) -> list[str]:
    """
    Fallback: use Playwright to visit the homepage and extract
    all internal hrefs matching high-value patterns.
    """
    settings = get_settings()
    urls: list[str] = [base_url.rstrip("/")]
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=settings.scraper_headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        page = browser.new_page(
            user_agent=random.choice(USER_AGENTS),
            viewport=random.choice(VIEWPORTS),
        )
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=settings.scraper_timeout)
            page.wait_for_timeout(2000)

            # Extract all hrefs and their inner text from the page
            links = page.evaluate('''() => {
                return Array.from(document.querySelectorAll('a[href]')).map(el => ({
                    href: el.href,
                    text: el.innerText.trim().toLowerCase()
                }));
            }''')

            # Keywords that strongly suggest a high-value page, even if the URL is weird
            high_value_text = ["pricing", "plans", "buy", "features", "capabilities", "compare"]

            for link in links:
                href = link["href"]
                text = link["text"]
                parsed = urlparse(href)
                
                # Only internal links
                if parsed.netloc and parsed.netloc != base_domain:
                    continue
                    
                full_url = urljoin(base_url, href).rstrip("/")
                
                # Add if it matches our regex OR if the link text strongly suggests it's a pricing/feature page
                if (HIGH_VALUE_PATTERNS.search(full_url) or any(keyword in text for keyword in high_value_text)):
                    if full_url not in urls:
                        urls.append(full_url)

        except Exception as e:
            logger.error(f"Spider fallback failed for {base_url}: {e}")
        finally:
            browser.close()

    return urls[:max_urls]


def discover_comprehensive_urls(base_url: str) -> list[str]:
    """
    Main URL discovery function.
    Tries sitemap first, falls back to a Playwright spider.
    """
    settings = get_settings()
    max_urls = settings.deep_scrape_max_urls

    logger.info(f"Discovering URLs for {base_url} (max {max_urls})...")

    urls = _discover_urls_from_sitemap(base_url, max_urls)

    # If sitemap only returned the base URL, fall back to spider
    if len(urls) <= 1:
        logger.info("Sitemap yielded few results, falling back to Playwright spider...")
        urls = _discover_urls_via_spider(base_url, max_urls)

    logger.info(f"Discovered {len(urls)} high-value URLs")
    return urls


# ═══════════════════════════════════════════════════════════════
# STEP 2: Full-Fidelity Markdown Extraction
# ═══════════════════════════════════════════════════════════════

def _create_html2text_converter() -> html2text.HTML2Text:
    """Configure html2text for maximum data preservation."""
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.ignore_emphasis = False
    h.body_width = 0  # Don't wrap lines
    h.protect_links = True
    h.unicode_snob = True
    h.skip_internal_links = False
    h.single_line_break = False
    return h


def _scrape_single_page_html(page, url: str, timeout: int) -> Optional[str]:
    """Navigate to a URL and extract the main content HTML, excluding nav/header/footer."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        page.wait_for_timeout(3000)  # Let SPAs hydrate

        # Extract main content HTML, excluding nav/header/footer
        content_html = page.evaluate("""
            () => {
                // Try <main> first, then fall back to <body>
                let root = document.querySelector('main') || document.body;
                
                // Clone so we don't modify the live DOM
                let clone = root.cloneNode(true);
                
                // Remove noise elements
                const removeSelectors = [
                    'nav', 'header', 'footer', 'script', 'style', 'noscript',
                    'svg', 'iframe', '.cookie-banner', '.cookie-consent',
                    '[role="navigation"]', '[role="banner"]', '[role="contentinfo"]'
                ];
                removeSelectors.forEach(sel => {
                    clone.querySelectorAll(sel).forEach(el => el.remove());
                });
                
                return clone.innerHTML;
            }
        """)
        return content_html

    except Exception as e:
        logger.warning(f"Failed to scrape {url}: {e}")
        return None


def scrape_to_markdown(urls: list[str]) -> tuple[str, int]:
    """
    Visit each URL with Playwright, extract content HTML, convert to Markdown.
    Returns (concatenated_markdown, pages_scraped_count).
    """
    settings = get_settings()
    converter = _create_html2text_converter()
    markdown_parts: list[str] = []
    pages_scraped = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=settings.scraper_headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport=random.choice(VIEWPORTS),
            locale="en-US",
            timezone_id="America/New_York",
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

        for url in urls:
            logger.info(f"  Scraping: {url}")
            raw_html = _scrape_single_page_html(page, url, settings.scraper_timeout)

            if raw_html:
                md = converter.handle(raw_html)
                # Only include pages with meaningful content (>200 chars)
                if len(md.strip()) > 200:
                    markdown_parts.append(f"\n\n### SOURCE URL: {url} ###\n\n{md}")
                    pages_scraped += 1
                else:
                    logger.info(f"  Skipped (too short): {url}")

        browser.close()

    full_markdown = "\n".join(markdown_parts)
    logger.info(f"Extracted {len(full_markdown)} chars of markdown from {pages_scraped} pages")

    return full_markdown, pages_scraped


# ═══════════════════════════════════════════════════════════════
# STEP 3: Solutions Architect AI Synthesis
# ═══════════════════════════════════════════════════════════════

SYNTHESIS_SYSTEM_PROMPT = """You are an Enterprise SaaS Solutions Architect conducting a rigorous technical evaluation. You have been given the full extracted content from a software tool's website spanning multiple pages (pricing, features, docs, integrations, security, etc.).

YOUR MANDATE:
- Extract ONLY hard technical facts, capabilities, and constraints.
- IGNORE all marketing language, superlatives, and vague claims.
- Be exhaustive: capture every feature, integration, pricing tier, and security certification mentioned.
- For pricing: extract EXACT prices, billing periods, and per-tier limitations.
- For features: distinguish between core capabilities available to all users vs. advanced/enterprise-only features.
- For developer experience: note API types (REST, GraphQL), SDK languages, CLI availability, webhook support.
- For compliance: list specific certifications (SOC 2 Type II, not just "SOC 2"), data residency options, encryption standards.

If information is not present in the source material, return an empty list for that field. Do NOT hallucinate or infer capabilities not explicitly stated."""


def synthesize_deep_data(markdown_payload: str, tool_name: str) -> ComprehensiveToolData:
    """
    Send the massive markdown payload to the LLM for structured extraction.
    Uses LangChain's .with_structured_output() for strict schema enforcement.
    """
    settings = get_settings()

    llm_kwargs = {
        "model": settings.deep_scrape_model,
        "temperature": 0.1,
        "max_tokens": 8000,
        "timeout": 300,
    }

    if settings.nvidia_api_key and "/" in settings.deep_scrape_model:
        llm_kwargs["api_key"] = settings.nvidia_api_key
        llm_kwargs["base_url"] = "https://integrate.api.nvidia.com/v1"
    else:
        llm_kwargs["api_key"] = settings.openai_api_key

    print(f"🤖 [MODEL USAGE] Invoking Deep Scraper synthesis LLM: {settings.deep_scrape_model}", flush=True)
    logger.info(f"Using deep scraper model: '{settings.deep_scrape_model}' for technical evaluation synthesis")
    llm = ChatOpenAI(**llm_kwargs)

    # Bind to our structured output schema
    structured_llm = llm.with_structured_output(ComprehensiveToolData)

    # Truncate to fit context window (~300K chars for safety with Kimi K2.6)
    truncated = markdown_payload[:300000]

    user_message = f"""Tool under evaluation: {tool_name}

The following is the full extracted content from {tool_name}'s website, spanning multiple pages (pricing, features, docs, integrations, security, etc.):

{truncated}

Perform a comprehensive technical evaluation and extract all structured data according to the schema."""

    logger.info(f"Sending {len(truncated)} chars to {settings.deep_scrape_model} for synthesis...")

    result = structured_llm.invoke([
        {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ])

    logger.info(
        f"Synthesis complete for {tool_name}: "
        f"{len(result.core_capabilities)} core capabilities, "
        f"{len(result.pricing_architecture)} pricing tiers, "
        f"{len(result.integration_ecosystem)} integrations"
    )

    return result


# ═══════════════════════════════════════════════════════════════
# STEP 4: Pipeline Orchestrator
# ═══════════════════════════════════════════════════════════════

def _sync_run_pipeline(tool_id_str: str, base_url: str) -> dict:
    """
    Synchronous pipeline runner that executes inside a thread.
    
    Pipeline:
      1. Fetch tool info from DB
      2. Discover high-value URLs (sitemap + spider fallback)
      3. Scrape all URLs to markdown
      4. Synthesize via LLM
      5. Upsert into tool_features table
    """
    settings = get_settings()

    # Create a fresh Supabase client for this thread
    from supabase import create_client
    db = create_client(settings.supabase_url, settings.supabase_key)

    # Step 1: Get tool info
    tool_result = db.table("tools").select("*").eq("id", tool_id_str).single().execute()
    if not tool_result or not tool_result.data:
        raise ValueError(f"Tool with ID {tool_id_str} not found")

    tool = tool_result.data
    tool_name = tool["name"]
    logger.info(f"═══ Starting comprehensive scrape for {tool_name} ({base_url}) ═══")

    # Step 2: Discover URLs
    urls = discover_comprehensive_urls(base_url)

    # Force inject explicit DB URLs to guarantee they are scraped
    explicit_urls = []
    if tool.get("pricing_url"):
        explicit_urls.append(tool["pricing_url"].rstrip("/"))
    if tool.get("website_url"):
        explicit_urls.append(tool["website_url"].rstrip("/"))
        
    for eu in explicit_urls:
        if eu not in urls:
            urls.insert(0, eu) # Prepend so they are scraped first (highest priority)

    # Step 3: Scrape to markdown (Layer 1: direct Playwright — FREE)
    markdown_payload, pages_scraped = scrape_to_markdown(urls)

    # Step 3b: Evaluate scrape quality — layered fallback if insufficient
    from app.services.fallback_scraper import (
        is_bot_blocked, is_data_insufficient,
        scrape_aggregator_sites_playwright, scrape_via_scrapingbee,
    )

    bot_blocked = is_bot_blocked(markdown_payload)
    insufficient = is_data_insufficient(markdown_payload)

    if bot_blocked or insufficient:
        logger.warning(
            f"Layer 1 (Direct Playwright) insufficient for {tool_name} "
            f"(blocked={bot_blocked}, insufficient={insufficient}, "
            f"chars={len(markdown_payload.strip())})"
        )

        # Layer 2: G2/Capterra via direct Playwright (FREE)
        logger.info(f"Trying Layer 2: G2/Capterra via Playwright for {tool_name}...")
        agg_markdown, agg_pages = scrape_aggregator_sites_playwright(tool_name)

        if agg_markdown.strip():
            markdown_payload += "\n\n" + agg_markdown
            pages_scraped += agg_pages
            logger.info(
                f"Layer 2 added {len(agg_markdown)} chars from {agg_pages} aggregator pages"
            )

        # Layer 3: ScrapingBee proxy (PAID — absolute last resort)
        if is_data_insufficient(markdown_payload) and settings.scrapingbee_api_key:
            logger.warning(
                f"Layer 2 still insufficient ({len(markdown_payload.strip())} chars). "
                f"Trying Layer 3: ScrapingBee proxy (paid)..."
            )
            sb_markdown, sb_pages = scrape_via_scrapingbee(urls)

            if len(sb_markdown.strip()) > len(markdown_payload.strip()):
                markdown_payload = sb_markdown
                pages_scraped = sb_pages
                logger.info(
                    f"Layer 3 (ScrapingBee) improved data: "
                    f"{len(sb_markdown)} chars from {sb_pages} pages"
                )

    if not markdown_payload.strip():
        raise ValueError(f"No content could be extracted from {base_url} (all 3 layers failed)")

    logger.info(
        f"Final scrape result for {tool_name}: {len(markdown_payload)} chars "
        f"from {pages_scraped} pages"
    )

    # Step 4: AI Synthesis
    comprehensive_data = synthesize_deep_data(markdown_payload, tool_name)

    # Step 5: Compute content hash for change detection
    content_hash = hashlib.sha256(markdown_payload.encode("utf-8")).hexdigest()

    # Step 6: Upsert into tool_features table
    # We store the comprehensive data in the `comprehensive_data` JSONB column
    upsert_data = {
        "tool_id": tool_id_str,
        "comprehensive_data": comprehensive_data.model_dump(),
        "raw_content": markdown_payload[:150000],  # Keep first 150K for reference
        "content_hash": content_hash,
        "last_scraped_at": "now()",
    }

    # Also update pricing_tiers and key_features from the comprehensive data
    # for backward compatibility with the existing scraper
    if comprehensive_data.pricing_architecture:
        upsert_data["pricing_tiers"] = [
            {
                "name": t.tier_name,
                "price": t.price,
                "billing_period": t.billing_period,
                "features": t.included_features,
            }
            for t in comprehensive_data.pricing_architecture
        ]

    if comprehensive_data.core_capabilities:
        upsert_data["key_features"] = comprehensive_data.core_capabilities

    db.table("tool_features").upsert(
        upsert_data,
        on_conflict="tool_id",
    ).execute()

    logger.info(f"═══ Comprehensive scrape complete for {tool_name} ═══")

    return {
        "tool_id": tool_id_str,
        "tool_name": tool_name,
        "urls_discovered": len(urls),
        "urls_scraped": pages_scraped,
        "markdown_chars": len(markdown_payload),
        "data": comprehensive_data.model_dump(),
    }


async def run_comprehensive_pipeline(tool_id: UUID, base_url: str) -> dict:
    """
    Main async entry point. Runs the sync pipeline in a thread executor.
    """
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        _executor,
        _sync_run_pipeline,
        str(tool_id),
        base_url,
    )
    return result
