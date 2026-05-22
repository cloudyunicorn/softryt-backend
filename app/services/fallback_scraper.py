"""
SoftRYT Backend — Fallback Scraper
====================================
When direct Playwright scraping fails due to bot protection or returns
insufficient data, this module provides a layered fallback strategy:

  Layer 1: Direct Playwright       — Official site (free)
  Layer 2: G2/Capterra via Playwright — Aggregator data (free)
  Layer 3: ScrapingBee proxy       — Last resort, paid API (~5 credits/page)

ScrapingBee is ONLY used as the final layer when both direct Playwright
and aggregator scraping have failed to produce sufficient data.
"""

import re
import random
import logging
from typing import Optional
from urllib.parse import quote_plus, urlparse

import httpx
import html2text
from playwright.sync_api import sync_playwright

from app.config import get_settings

logger = logging.getLogger(__name__)

# ScrapingBee API endpoint
SCRAPINGBEE_API = "https://app.scrapingbee.com/api/v1/"

# Timeout for ScrapingBee requests (JS rendering can be slow)
SB_TIMEOUT = 90.0

# Common bot-block indicators in page content
BOT_BLOCK_PATTERNS = re.compile(
    r"(access\s+denied|please\s+verify\s+you\s+are\s+human|"
    r"checking\s+your\s+browser|just\s+a\s+moment|"
    r"ray\s+id|captcha|cf-browser-verification|"
    r"blocked\s+by\s+security|pardon\s+our\s+interruption|"
    r"enable\s+javascript\s+and\s+cookies)",
    re.IGNORECASE,
)

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


# ═══════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════

def _create_html2text_converter() -> html2text.HTML2Text:
    """Configure html2text for maximum data preservation."""
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.ignore_emphasis = False
    h.body_width = 0
    h.protect_links = True
    h.unicode_snob = True
    h.skip_internal_links = False
    h.single_line_break = False
    return h


def is_bot_blocked(markdown_content: str) -> bool:
    """
    Check if the scraped content indicates bot protection triggered.
    Returns True if the content appears to be a block/challenge page.
    """
    if not markdown_content or len(markdown_content.strip()) < 200:
        return True

    matches = BOT_BLOCK_PATTERNS.findall(markdown_content)
    if len(matches) >= 2:
        return True

    if len(markdown_content.strip()) < 500 and len(matches) >= 1:
        return True

    return False


def is_data_insufficient(markdown_content: str) -> bool:
    """
    Check if the scraped markdown contains enough meaningful content
    for a useful AI synthesis. Returns True if data is too thin.
    """
    stripped = markdown_content.strip()

    if len(stripped) < 500:
        return True

    lines = [l.strip() for l in stripped.split("\n") if l.strip()]
    if len(lines) < 10:
        return True

    return False


# ═══════════════════════════════════════════════════════════════
# LAYER 2: G2 / Capterra via Direct Playwright (FREE)
# ═══════════════════════════════════════════════════════════════

def _scrape_url_via_playwright(url: str) -> Optional[str]:
    """Scrape a single URL with Playwright. Returns raw HTML or None."""
    settings = get_settings()

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
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=settings.scraper_timeout)
            page.wait_for_timeout(3000)

            content_html = page.evaluate("""
                () => {
                    let root = document.querySelector('main') || document.body;
                    let clone = root.cloneNode(true);
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
            logger.warning(f"Playwright scrape failed for {url}: {e}")
            return None
        finally:
            browser.close()


def _auto_discover_g2_slug_playwright(tool_name: str) -> Optional[str]:
    """
    Auto-discover the G2 product slug using direct Playwright.
    Returns the slug or None if not found / blocked.
    """
    search_url = f"https://www.g2.com/search?query={quote_plus(tool_name)}"
    logger.info(f"  [G2-Playwright] Discovering slug for '{tool_name}'...")

    raw_html = _scrape_url_via_playwright(search_url)
    if not raw_html:
        return None

    product_matches = re.findall(r'/products/([a-zA-Z0-9_-]+)/reviews', raw_html)
    if product_matches:
        logger.info(f"  [G2-Playwright] Discovered slug: {product_matches[0]}")
        return product_matches[0]

    product_matches = re.findall(r'/products/([a-zA-Z0-9_-]+)', raw_html)
    for slug in product_matches:
        if slug not in ("best", "compare", "categories", "reports"):
            logger.info(f"  [G2-Playwright] Discovered slug: {slug}")
            return slug

    logger.warning(f"  [G2-Playwright] Could not discover slug for '{tool_name}'")
    return None


def scrape_aggregator_sites_playwright(tool_name: str) -> tuple[str, int]:
    """
    LAYER 2: Scrape G2/Capterra via direct Playwright (free).
    Returns (markdown_content, pages_scraped).
    """
    converter = _create_html2text_converter()
    markdown_parts: list[str] = []
    pages_scraped = 0

    # ── G2 ────────────────────────────────────────────────────
    g2_slug = _auto_discover_g2_slug_playwright(tool_name)
    if g2_slug:
        g2_urls = [
            f"https://www.g2.com/products/{g2_slug}/reviews",
            f"https://www.g2.com/products/{g2_slug}/pricing",
            f"https://www.g2.com/products/{g2_slug}/features",
        ]
        for url in g2_urls:
            logger.info(f"  [G2-Playwright] Scraping: {url}")
            raw_html = _scrape_url_via_playwright(url)
            if raw_html:
                md = converter.handle(raw_html)
                if len(md.strip()) > 200 and not is_bot_blocked(md):
                    markdown_parts.append(f"\n\n### SOURCE: G2 ({url}) ###\n\n{md}")
                    pages_scraped += 1

    full_markdown = "\n".join(markdown_parts)
    logger.info(
        f"[G2-Playwright] Extracted {len(full_markdown)} chars "
        f"from {pages_scraped} pages for '{tool_name}'"
    )

    return full_markdown, pages_scraped


# ═══════════════════════════════════════════════════════════════
# LAYER 3: ScrapingBee Proxy (PAID — last resort only)
# ═══════════════════════════════════════════════════════════════

def _scrape_url_via_scrapingbee(url: str, api_key: str, render_js: str = "true") -> Optional[str]:
    """
    Scrape a single URL through ScrapingBee's API with optional JS rendering.
    Returns raw HTML or None on failure.
    """
    params = {
        "api_key": api_key,
        "url": url,
        "render_js": render_js,
        "block_ads": "true",
        "block_resources": "false",
    }

    if render_js == "true":
        params["wait"] = "3000"

    try:
        response = httpx.get(SCRAPINGBEE_API, params=params, timeout=SB_TIMEOUT)

        if response.status_code == 200:
            return response.text
        else:
            logger.warning(
                f"ScrapingBee returned {response.status_code} for {url}: "
                f"{response.text[:200]}"
            )
            return None

    except httpx.TimeoutException:
        logger.warning(f"ScrapingBee timeout for {url}")
        return None
    except Exception as e:
        logger.error(f"ScrapingBee request failed for {url}: {e}")
        return None


def scrape_via_scrapingbee(urls: list[str]) -> tuple[str, int]:
    """
    LAYER 3 (LAST RESORT): Scrape URLs through ScrapingBee's anti-bot proxy.
    Only called when both direct Playwright and G2 aggregators have failed.

    Each JS-rendered request costs ~5 ScrapingBee credits.
    """
    settings = get_settings()
    api_key = settings.scrapingbee_api_key

    if not api_key:
        logger.warning("ScrapingBee API key not configured — skipping final fallback")
        return "", 0

    converter = _create_html2text_converter()
    markdown_parts: list[str] = []
    pages_scraped = 0

    # Scrape original URLs via ScrapingBee as absolute last resort
    all_urls = list(urls)  # original site URLs

    for url in all_urls:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        is_aggregator = any(agg in domain for agg in ["g2.com", "capterra.com"])

        raw_html = None
        used_js = False

        if is_aggregator:
            logger.info(f"  [ScrapingBee-FINAL] Scraping (JS render forced for aggregator): {url}")
            raw_html = _scrape_url_via_scrapingbee(url, api_key, render_js="true")
            used_js = True
        else:
            logger.info(f"  [ScrapingBee-FINAL] Scraping (Static): {url}")
            raw_html = _scrape_url_via_scrapingbee(url, api_key, render_js="false")
            
            # Check if static scrape got blocked or had insufficient data
            if raw_html:
                md = converter.handle(raw_html)
                if is_bot_blocked(md) or is_data_insufficient(md):
                    logger.info(f"  [ScrapingBee-FINAL] Static scrape insufficient/blocked, falling back to JS rendering: {url}")
                    raw_html = _scrape_url_via_scrapingbee(url, api_key, render_js="true")
                    used_js = True
            else:
                logger.info(f"  [ScrapingBee-FINAL] Static scrape failed, falling back to JS rendering: {url}")
                raw_html = _scrape_url_via_scrapingbee(url, api_key, render_js="true")
                used_js = True

        if raw_html:
            md = converter.handle(raw_html)
            if len(md.strip()) > 200 and not is_bot_blocked(md):
                markdown_parts.append(f"\n\n### SOURCE URL: {url} ###\n\n{md}")
                pages_scraped += 1
            else:
                logger.info(f"  [ScrapingBee-FINAL] Skipped (blocked/short even after scrape attempts): {url}")

    full_markdown = "\n".join(markdown_parts)
    logger.info(
        f"[ScrapingBee-FINAL] Extracted {len(full_markdown)} chars "
        f"from {pages_scraped} pages"
    )

    return full_markdown, pages_scraped
