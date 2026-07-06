"""
Cloudy Unicorn Backend — LangGraph Blog Orchestrator
========================================================
AI pipeline for researching and generating blog posts:
  1. Researcher Node — Uses LangChain DuckDuckGo search + Playwright deep-scrape
  2. Writer Node    — Generates MDX blog content via Kimi K2.6 (NVIDIA NIM)
  3. Save Node      — Upserts to Supabase blog_posts table

Uses moonshotai/kimi-k2.6 via NVIDIA NIM for ALL AI tasks.
Completely separate from the SaaS review/comparison pipelines.
"""

import json
import re
import logging
import asyncio
import random
import time
from typing import TypedDict, Optional
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus, urljoin, urlparse

import httpx
import html2text
from playwright.sync_api import sync_playwright
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from langgraph.graph import StateGraph, END

from app.config import get_settings
from app.database import get_supabase_client
from app.prompts.blog_writer import (
    BLOG_WRITER_SYSTEM_PROMPT,
    BLOG_WRITER_USER_PROMPT_TEMPLATE,
    BLOG_TITLE_PROMPT,
)

logger = logging.getLogger(__name__)

# Thread pool for sync Playwright operations
_executor = ThreadPoolExecutor(max_workers=2)

# Stealth configuration for Playwright deep-scraping
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


def extract_json_from_text(text: str) -> dict:
    """
    Extracts a JSON object from text, even if wrapped in markdown code fences,
    or prefixed/suffixed with conversational text.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try searching for a JSON object structure { ... }
    match = re.search(r"(\{[\s\S]*\})", text)
    if match:
        json_str = match.group(1).strip()
        # Clean up any potential markdown fences inside the captured group if they exist
        if json_str.startswith("```json"):
            json_str = json_str[7:].strip()
        if json_str.endswith("```"):
            json_str = json_str[:-3].strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Try removing trailing commas, which are a common LLM mistake
            try:
                cleaned = re.sub(r",\s*([\]}])", r"\1", json_str)
                return json.loads(cleaned)
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to decode JSON: {e}")
    raise ValueError("No JSON block found in text")


# ──────────────────────────────────────────────────────────────
# STATE DEFINITION
# ──────────────────────────────────────────────────────────────

class BlogOrchestratorState(TypedDict):
    """State passed between LangGraph nodes for blog generation."""
    topic: str                      # User-provided topic
    tags: list[str]                 # User-provided or AI-generated tags

    # Research outputs
    research_data: str              # Concatenated markdown from scraped sources
    research_urls: list[str]        # URLs that were scraped
    pages_scraped: int              # Number of pages successfully scraped

    # AI outputs
    title: str                      # AI-generated blog title
    slug: str                       # AI-generated URL slug
    meta_description: str           # AI-generated meta description
    generated_content: str          # MDX content from Writer
    cover_image_url: Optional[str]  # Cover image URL

    # Control flow
    status: str
    error: Optional[str]

    # Output
    post_id: Optional[str]


# ──────────────────────────────────────────────────────────────
# RESEARCH HELPERS
# ──────────────────────────────────────────────────────────────

def _create_html2text_converter() -> html2text.HTML2Text:
    """Configure html2text for blog research extraction."""
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


def _ddg_search(topic: str, max_results: int = 8) -> tuple[list[str], str]:
    """
    Use LangChain's DuckDuckGoSearchResults tool for URL discovery.
    Returns (urls, raw_snippets_text).
    No browser needed — uses the duckduckgo-search Python API directly.
    """
    urls: list[str] = []
    all_snippets: list[str] = []

    wrapper = DuckDuckGoSearchAPIWrapper(
        max_results=max_results,
        region="wt-wt",  # worldwide
        time="m",  # past month for freshness
    )
    search_tool = DuckDuckGoSearchResults(
        api_wrapper=wrapper,
        max_results=max_results,
        output_format="list",
    )

    # Run multiple search queries for breadth
    queries = [
        topic,
        f"{topic} guide tutorial",
        f"{topic} review comparison 2026",
    ]

    for query in queries:
        if len(urls) >= max_results:
            break
        try:
            results = search_tool.invoke(query)
            if isinstance(results, list):
                for r in results:
                    link = r.get("link", "")
                    snippet = r.get("snippet", "")
                    title = r.get("title", "")
                    if link and link not in urls and len(urls) < max_results:
                        urls.append(link)
                    if snippet:
                        all_snippets.append(f"**{title}**: {snippet}")
            logger.info(
                f"  🔍 DDG search '{query[:50]}...' yielded "
                f"{len(results) if isinstance(results, list) else 0} results"
            )
        except Exception as e:
            logger.warning(f"  DDG search failed for '{query[:50]}': {e}")
            continue

    snippets_text = "\n\n".join(all_snippets)
    logger.info(f"🔗 DDG discovered {len(urls)} URLs, {len(snippets_text)} chars of snippets")
    return urls, snippets_text


def _scrape_research_urls(urls: list[str]) -> tuple[str, int]:
    """
    Deep-scrape research URLs to markdown using Playwright.
    Returns (concatenated_markdown, pages_scraped).
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
        )
        page = context.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )

        for url in urls:
            try:
                logger.info(f"  📄 Deep-scraping: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(2000)

                content_html = page.evaluate("""
                    () => {
                        let root = document.querySelector('article')
                            || document.querySelector('main')
                            || document.querySelector('.post-content')
                            || document.querySelector('.article-content')
                            || document.body;
                        let clone = root.cloneNode(true);
                        const removeSelectors = [
                            'nav', 'header', 'footer', 'script', 'style', 'noscript',
                            'svg', 'iframe', '.cookie-banner', '.cookie-consent', '.ad',
                            '.advertisement', '.sidebar', '.comments', '.social-share',
                            '[role="navigation"]', '[role="banner"]', '[role="contentinfo"]'
                        ];
                        removeSelectors.forEach(sel => {
                            clone.querySelectorAll(sel).forEach(el => el.remove());
                        });
                        return clone.innerHTML;
                    }
                """)

                if content_html:
                    md = converter.handle(content_html)
                    if len(md.strip()) > 200:
                        truncated_md = md.strip()[:40000]
                        markdown_parts.append(
                            f"\n\n### SOURCE: {url} ###\n\n{truncated_md}"
                        )
                        pages_scraped += 1
                    else:
                        logger.info(f"  Skipped (too short): {url}")

            except Exception as e:
                logger.warning(f"  Failed to scrape {url}: {e}")
                continue

        browser.close()

    full_markdown = "\n".join(markdown_parts)
    logger.info(
        f"Research scraping complete: {len(full_markdown)} chars "
        f"from {pages_scraped}/{len(urls)} pages"
    )
    return full_markdown, pages_scraped


def _sync_research(topic: str) -> tuple[str, list[str], int]:
    """
    Synchronous research function combining DDG search + Playwright deep-scrape.
    Returns (markdown_data, urls_scraped, pages_count).
    """
    settings = get_settings()
    max_urls = settings.blog_research_max_urls

    # Step 1: Discover URLs via LangChain DuckDuckGo search tool
    urls, snippets = _ddg_search(topic, max_results=max_urls)

    if not urls:
        logger.warning(f"No research URLs found for topic: {topic}")
        # Still return DDG snippets if we got any — they have useful content
        if snippets:
            return f"### SEARCH SNIPPETS ###\n\n{snippets}", [], 0
        return "", [], 0

    # Step 2: Deep-scrape discovered URLs for full article content
    scraped_markdown, pages_scraped = _scrape_research_urls(urls)

    # Combine DDG snippets + deep-scraped content for richer context
    combined = ""
    if snippets:
        combined += f"### SEARCH SNIPPETS ###\n\n{snippets}\n\n"
    if scraped_markdown:
        combined += scraped_markdown

    return combined, urls, pages_scraped


# ──────────────────────────────────────────────────────────────
# KIMI K2.6 LLM HELPER
# ──────────────────────────────────────────────────────────────

def _get_kimi_llm(temperature: float = 0.7, max_tokens: int = 8000) -> ChatOpenAI:
    """
    Create a ChatOpenAI client pointed at moonshotai/kimi-k2.6 via NVIDIA NIM.
    All blog AI tasks use this model exclusively.
    """
    settings = get_settings()
    model_name = settings.blog_writer_model  # "moonshotai/kimi-k2.6"

    llm_kwargs = {
        "model": model_name,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": 300,  # 5 minutes timeout to prevent premature ReadTimeout on large generations
    }

    # Route to NVIDIA NIM (model has a slash → NVIDIA, not OpenAI)
    if settings.nvidia_api_key and "/" in model_name:
        llm_kwargs["api_key"] = settings.nvidia_api_key
        llm_kwargs["base_url"] = "https://integrate.api.nvidia.com/v1"
    else:
        llm_kwargs["api_key"] = settings.openai_api_key

    print(f"🤖 [MODEL USAGE] Invoking Kimi LLM: {model_name} (temp={temperature}, max_tokens={max_tokens})", flush=True)
    logger.info(f"Using blog writer model: '{model_name}' for blog post generation")
    return ChatOpenAI(**llm_kwargs)


# ──────────────────────────────────────────────────────────────
# NODE 1: RESEARCHER
# ──────────────────────────────────────────────────────────────

async def blog_researcher_node(state: BlogOrchestratorState) -> BlogOrchestratorState:
    """
    Researcher Node: Uses LangChain DuckDuckGo search + Playwright deep-scrape.

    1. DuckDuckGoSearchResults tool discovers relevant URLs (API-based, no browser)
    2. Playwright deep-scrapes discovered URLs for full article content
    """
    logger.info(f"📚 Blog Researcher starting for: {state['topic']}")
    print(f"\n📚 [1/3] Researching topic: '{state['topic']}' via DuckDuckGo & Playwright deep-scraping...", flush=True)

    loop = asyncio.get_running_loop()

    try:
        research_data, urls, pages_scraped = await loop.run_in_executor(
            _executor,
            _sync_research,
            state["topic"],
        )

        if not research_data.strip():
            logger.warning("Research returned no data, proceeding with topic only")
            research_data = f"No external research data could be gathered for: {state['topic']}. Write based on your training knowledge."

        logger.info(
            f"📚 Research complete: {len(research_data)} chars from {pages_scraped} pages"
        )

        return {
            **state,
            "research_data": research_data,
            "research_urls": urls,
            "pages_scraped": pages_scraped,
            "status": "writing",
        }

    except Exception as e:
        logger.error(f"Blog Researcher failed: {e}")
        return {
            **state,
            "research_data": f"Research failed: {str(e)}. Write based on your training knowledge about: {state['topic']}",
            "research_urls": [],
            "pages_scraped": 0,
            "status": "writing",
        }


# ──────────────────────────────────────────────────────────────
# NODE 2: WRITER
# ──────────────────────────────────────────────────────────────

async def blog_writer_node(state: BlogOrchestratorState) -> BlogOrchestratorState:
    """
    Writer Node: Generates blog title metadata + full MDX content.

    Uses moonshotai/kimi-k2.6 via NVIDIA NIM for both:
    1. Title/slug/meta generation (low-temp structured output)
    2. Full blog content generation (higher-temp creative writing)
    """
    logger.info(f"✍️  Blog Writer starting for: {state['topic']}")
    print(f"\n✍️ [2/3] Generating blog metadata (Title, Slug, Tags) for: {state['topic']}...", flush=True)

    try:
        # ── Step 1: Generate title, slug, meta description, tags ──────
        title_llm = _get_kimi_llm(temperature=0.3, max_tokens=1000)

        research_excerpt = state["research_data"][:3000]
        title_prompt = BLOG_TITLE_PROMPT.format(
            topic=state["topic"],
            research_excerpt=research_excerpt,
        )

        title_response = await title_llm.ainvoke([
            HumanMessage(content=title_prompt),
        ])

        title_text = title_response.content.strip()
        title_data = extract_json_from_text(title_text)

        title = title_data.get("title", state["topic"])
        slug = title_data.get("slug", re.sub(r"[^a-z0-9]+", "-", state["topic"].lower()).strip("-"))
        meta_description = title_data.get("meta_description", f"Learn about {state['topic']} in this comprehensive guide.")
        ai_tags = title_data.get("tags", [])

        # Merge user-provided tags with AI-generated ones
        all_tags = list(set(state.get("tags", []) + ai_tags))

        logger.info(f"✍️  Generated metadata: title='{title}', slug='{slug}'")
        print(f"✍️ [3/3] Generating full blog post MDX content (~2000 words)...", flush=True)

        # Fetch registered tools from Supabase to dynamically guide LLM between toolSlug and href
        db = get_supabase_client()
        try:
            tools_resp = db.table("tools").select("slug").eq("is_active", True).execute()
            registered_slugs = [t["slug"] for t in tools_resp.data] if tools_resp.data else []
        except Exception as e:
            logger.warning(f"Failed to fetch active tools for prompt context: {e}")
            registered_slugs = []
        registered_tools_str = ", ".join(registered_slugs) if registered_slugs else "None"

        # ── Step 2: Generate full blog content ──────────────────────
        content_llm = _get_kimi_llm(temperature=0.7, max_tokens=8000)

        user_prompt = BLOG_WRITER_USER_PROMPT_TEMPLATE.format(
            topic=state["topic"],
            slug=slug,
            registered_tools=registered_tools_str,
            research_data=state["research_data"][:240000],  # Cap research context at 240k chars
        )

        content_response = await content_llm.ainvoke([
            SystemMessage(content=BLOG_WRITER_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

        generated_content = content_response.content

        logger.info(f"✍️  Blog Writer generated {len(generated_content)} chars of MDX")

        return {
            **state,
            "title": title,
            "slug": slug,
            "meta_description": meta_description,
            "tags": all_tags,
            "generated_content": generated_content,
            "status": "saving",
        }

    except json.JSONDecodeError as e:
        logger.error(f"Title generation JSON parse failed: {e}")
        # Fallback: use topic as title
        fallback_slug = re.sub(r"[^a-z0-9]+", "-", state["topic"].lower()).strip("-")
        return {
            **state,
            "title": state["topic"],
            "slug": fallback_slug,
            "meta_description": f"Learn about {state['topic']} in this comprehensive guide.",
            "status": "failed",
            "error": f"Title generation failed: {str(e)}",
        }

    except Exception as e:
        logger.error(f"Blog Writer failed: {e}")
        return {
            **state,
            "status": "failed",
            "error": f"Writer failed: {str(e)}",
        }


# ──────────────────────────────────────────────────────────────
# NODE 3: SAVE TO DATABASE
# ──────────────────────────────────────────────────────────────

async def blog_save_node(state: BlogOrchestratorState) -> BlogOrchestratorState:
    """
    Save Node: Upserts the generated blog post into the blog_posts table.
    Completely separate from the generated_pages table used for SaaS content.
    """
    db = get_supabase_client()
    print(f"💾 [💾] Upserting generated blog post '{state['title']}' (slug: {state['slug']}) to Supabase...", flush=True)

    schema_markup = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": state["title"],
        "description": state["meta_description"],
        "datePublished": datetime.now(timezone.utc).isoformat(),
        "dateModified": datetime.now(timezone.utc).isoformat(),
        "author": {
            "@type": "Organization",
            "name": "Cloudy Unicorn",
        },
        "publisher": {
            "@type": "Organization",
            "name": "Cloudy Unicorn",
        },
        "keywords": state.get("tags", []),
    }

    if state.get("cover_image_url"):
        schema_markup["image"] = state["cover_image_url"]

    post_data = {
        "slug": state["slug"],
        "title": state["title"],
        "meta_description": state["meta_description"],
        "markdown_content": state["generated_content"],
        "topic": state["topic"],
        "research_data": state.get("research_data", "")[:150000],
        "cover_image_url": state.get("cover_image_url"),
        "schema_markup": schema_markup,
        "tags": state.get("tags", []),
        "published_status": "published",
        "published_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        result = db.table("blog_posts").upsert(
            post_data,
            on_conflict="slug",
        ).execute()

        post_id = result.data[0]["id"] if result.data else None

        logger.info(f"💾 Saved blog post '{state['slug']}' with ID: {post_id}")

        return {
            **state,
            "post_id": post_id,
            "status": "completed",
        }

    except Exception as e:
        logger.error(f"Blog Save failed: {e}")
        return {
            **state,
            "status": "failed",
            "error": f"Save failed: {str(e)}",
        }


# ──────────────────────────────────────────────────────────────
# GRAPH CONSTRUCTION
# ──────────────────────────────────────────────────────────────

def _should_continue_after_writer(state: BlogOrchestratorState) -> str:
    """Route after writer: save if successful, END if failed."""
    if state["status"] == "failed":
        return END
    return "save"


def build_blog_orchestrator_graph() -> StateGraph:
    """Build the LangGraph pipeline: Research → Write → Save."""
    graph = StateGraph(BlogOrchestratorState)

    graph.add_node("researcher", blog_researcher_node)
    graph.add_node("writer", blog_writer_node)
    graph.add_node("save", blog_save_node)

    graph.set_entry_point("researcher")
    graph.add_edge("researcher", "writer")
    graph.add_conditional_edges("writer", _should_continue_after_writer)
    graph.add_edge("save", END)

    return graph.compile()


# ──────────────────────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────────────────────

async def generate_blog_post(topic: str, tags: list[str] | None = None) -> dict:
    """
    Main entry point: Generates a complete blog post from a topic.

    Pipeline: DDG Search → Playwright Scrape → Write (Kimi K2.6) → Save (Supabase)

    Args:
        topic: The blog topic/subject to research and write about
        tags: Optional list of tags for categorization

    Returns:
        dict with post_id, slug, status, and pipeline metadata
    """
    db = get_supabase_client()

    # Log the generation attempt
    log_data = {
        "trigger_type": "manual",
        "action": "generate_blog",
        "status": "running",
        "metadata": {"topic": topic, "tags": tags or []},
    }
    log_result = db.table("generation_logs").insert(log_data).execute()
    log_id = log_result.data[0]["id"] if log_result.data else None

    initial_state: BlogOrchestratorState = {
        "topic": topic,
        "tags": tags or [],
        "research_data": "",
        "research_urls": [],
        "pages_scraped": 0,
        "title": "",
        "slug": "",
        "meta_description": "",
        "generated_content": "",
        "cover_image_url": None,
        "status": "researching",
        "error": None,
        "post_id": None,
    }

    start_time = time.time()

    graph = build_blog_orchestrator_graph()
    final_state = await graph.ainvoke(initial_state)

    duration_ms = int((time.time() - start_time) * 1000)

    # Update generation log
    if log_id:
        db.table("generation_logs").update({
            "status": "completed" if final_state["status"] == "completed" else "failed",
            "error_message": final_state.get("error"),
            "duration_ms": duration_ms,
            "metadata": {
                "topic": topic,
                "slug": final_state.get("slug"),
                "pages_scraped": final_state.get("pages_scraped", 0),
                "research_chars": len(final_state.get("research_data", "")),
                "content_chars": len(final_state.get("generated_content", "")),
            },
        }).eq("id", log_id).execute()

    logger.info(
        f"📝 Blog Pipeline completed: "
        f"topic='{topic[:60]}', status={final_state['status']}, "
        f"slug='{final_state.get('slug')}', duration={duration_ms}ms, "
        f"research={final_state.get('pages_scraped', 0)} pages"
    )

    return {
        "post_id": final_state.get("post_id"),
        "slug": final_state.get("slug"),
        "title": final_state.get("title"),
        "status": final_state["status"],
        "error": final_state.get("error"),
        "duration_ms": duration_ms,
        "pages_researched": final_state.get("pages_scraped", 0),
        "research_urls": final_state.get("research_urls", []),
    }
