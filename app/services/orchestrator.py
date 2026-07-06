"""
SoftRYT Backend — LangGraph AI Orchestrator
==============================================
Stateful AI pipeline using LangGraph with two nodes:
  1. Writer Node (GPT-4o-mini) — Generates MDX comparison content
  2. Fact-Checker Node (GPT-4o-mini) — Validates content accuracy

The graph follows this flow:
  START → Writer → Fact-Checker → (pass) → Save → END
                                → (fail) → Writer (retry, max 2)

Uses LangGraph StateGraph for deterministic, auditable workflow execution.
"""

import json
import logging
from typing import TypedDict, Annotated, Optional
from uuid import UUID
from datetime import datetime, timezone

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END

from app.config import get_settings
from app.database import get_supabase_client
from app.prompts.writer import WRITER_SYSTEM_PROMPT, WRITER_USER_PROMPT_TEMPLATE
from app.prompts.fact_checker import FACT_CHECKER_SYSTEM_PROMPT, FACT_CHECKER_USER_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# STATE DEFINITION
# The shared state that flows through all graph nodes
# ──────────────────────────────────────────────────────────────

class OrchestratorState(TypedDict):
    """State passed between LangGraph nodes."""
    # Input data
    tool_a: dict              # Tool A info + scraped features
    tool_b: dict              # Tool B info + scraped features
    slug: str                 # Generated page slug

    # AI outputs
    generated_content: str    # MDX content from Writer
    fact_check_result: dict   # JSON result from Fact-Checker

    # Control flow
    retry_count: int          # Number of Writer retries
    max_retries: int          # Max retries before giving up
    corrections: str          # Fact-checker corrections for retry
    status: str               # "pending", "completed", "failed"
    error: Optional[str]      # Error message if failed

    # Output
    page_id: Optional[str]    # UUID of the saved page


# ──────────────────────────────────────────────────────────────
# NODE 1: WRITER
# Uses GPT-4o-mini to generate MDX comparison content
# ──────────────────────────────────────────────────────────────

async def writer_node(state: OrchestratorState) -> OrchestratorState:
    """
    Writer Node: Generates a complete MDX comparison article.
    
    On first run, uses the raw scraped data.
    On retries, includes the fact-checker's corrections as additional instructions.
    """
    settings = get_settings()
    llm_kwargs = {
        "model": settings.writer_model,
        "temperature": 0.7,
        "max_tokens": 8000,
        "timeout": 300,
    }
    
    # Route to NVIDIA NIM if model name contains a slash (e.g. "meta/llama-3.3", "openai/gpt-oss-120b")
    # Plain model names (e.g. "gpt-4o-mini") route to OpenAI directly
    if settings.nvidia_api_key and "/" in settings.writer_model:
        llm_kwargs["api_key"] = settings.nvidia_api_key
        llm_kwargs["base_url"] = "https://integrate.api.nvidia.com/v1"
    else:
        llm_kwargs["api_key"] = settings.openai_api_key

    print(f"🤖 [MODEL USAGE] Invoking Comparison Writer LLM: {settings.writer_model}", flush=True)
    logger.info(f"Using comparison writer model: '{settings.writer_model}' for tool comparison generation")
    llm = ChatOpenAI(**llm_kwargs)

    tool_a = state["tool_a"]
    tool_b = state["tool_b"]

    # Build the user prompt with all scraped data
    user_prompt = WRITER_USER_PROMPT_TEMPLATE.format(
        tool_a_name=tool_a["name"],
        tool_a_url=tool_a.get("website_url", ""),
        tool_a_category=tool_a.get("category", ""),
        tool_a_description=tool_a.get("description", ""),
        tool_a_pricing=json.dumps(tool_a.get("pricing_tiers", []), indent=2),
        tool_a_features=json.dumps(tool_a.get("key_features", []), indent=2),
        tool_a_raw_content=(tool_a.get("raw_content", "") or "")[:50000],
        tool_b_name=tool_b["name"],
        tool_b_url=tool_b.get("website_url", ""),
        tool_b_category=tool_b.get("category", ""),
        tool_b_description=tool_b.get("description", ""),
        tool_b_pricing=json.dumps(tool_b.get("pricing_tiers", []), indent=2),
        tool_b_features=json.dumps(tool_b.get("key_features", []), indent=2),
        tool_b_raw_content=(tool_b.get("raw_content", "") or "")[:50000],
        slug=state["slug"],
        tool_a_slug=tool_a.get("slug", ""),
        tool_b_slug=tool_b.get("slug", ""),
    )

    # If this is a retry, append the fact-checker's corrections
    if state.get("corrections"):
        user_prompt += f"\n\n## CORRECTIONS FROM FACT-CHECKER (MUST FIX):\n{state['corrections']}"
        logger.info(f"Writer retry #{state['retry_count']} with corrections")

    messages = [
        SystemMessage(content=WRITER_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    try:
        response = await llm.ainvoke(messages)
        generated_content = response.content

        logger.info(f"Writer generated {len(generated_content)} chars of MDX content")

        return {
            **state,
            "generated_content": generated_content,
            "status": "fact_checking",
        }

    except Exception as e:
        logger.error(f"Writer node failed: {e}")
        return {
            **state,
            "status": "failed",
            "error": f"Writer failed: {str(e)}",
        }


# ──────────────────────────────────────────────────────────────
# NODE 2: FACT-CHECKER
# Uses GPT-4o-mini to validate content against scraped data
# ──────────────────────────────────────────────────────────────

async def fact_checker_node(state: OrchestratorState) -> OrchestratorState:
    """
    Fact-Checker Node: Reviews generated MDX against raw scraped data.
    
    Returns a structured JSON result with:
    - passed: bool
    - confidence_score: float
    - issues: list of found problems
    - corrections: instructions for the writer if failed
    """
    settings = get_settings()
    llm_kwargs = {
        "model": settings.fact_checker_model,
        "temperature": 0.1,  # Low temperature for precise fact-checking
        "max_tokens": 4000,
        "timeout": 300,
    }

    # Route to NVIDIA NIM if model name contains a slash
    if settings.nvidia_api_key and "/" in settings.fact_checker_model:
        llm_kwargs["api_key"] = settings.nvidia_api_key
        llm_kwargs["base_url"] = "https://integrate.api.nvidia.com/v1"
    else:
        llm_kwargs["api_key"] = settings.openai_api_key

    print(f"🤖 [MODEL USAGE] Invoking Comparison Fact-Checker LLM: {settings.fact_checker_model}", flush=True)
    logger.info(f"Using comparison fact-checker model: '{settings.fact_checker_model}' for tool comparison validation")
    llm = ChatOpenAI(**llm_kwargs)

    tool_a = state["tool_a"]
    tool_b = state["tool_b"]

    user_prompt = FACT_CHECKER_USER_PROMPT_TEMPLATE.format(
        generated_content=state["generated_content"][:40000],
        tool_a_name=tool_a["name"],
        tool_a_pricing=json.dumps(tool_a.get("pricing_tiers", []), indent=2),
        tool_a_features=json.dumps(tool_a.get("key_features", []), indent=2),
        tool_a_comprehensive=json.dumps(tool_a.get("comprehensive_data", {}), indent=2)[:5000],
        tool_b_name=tool_b["name"],
        tool_b_pricing=json.dumps(tool_b.get("pricing_tiers", []), indent=2),
        tool_b_features=json.dumps(tool_b.get("key_features", []), indent=2),
        tool_b_comprehensive=json.dumps(tool_b.get("comprehensive_data", {}), indent=2)[:5000],
    )

    messages = [
        SystemMessage(content=FACT_CHECKER_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    try:
        response = await llm.ainvoke(messages)
        
        # Parse the JSON response from the fact-checker
        result_text = response.content.strip()
        # Handle potential markdown code fences around JSON
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()

        fact_check_result = json.loads(result_text)

        passed = fact_check_result.get("passed", False)
        confidence = fact_check_result.get("confidence_score", 0)
        issues = fact_check_result.get("issues", [])
        corrections = fact_check_result.get("corrections", "")

        logger.info(
            f"Fact-check: passed={passed}, confidence={confidence}, "
            f"issues={len(issues)}, retry={state['retry_count']}/{state['max_retries']}"
        )

        if passed:
            return {
                **state,
                "fact_check_result": fact_check_result,
                "status": "passed",
                "corrections": "",
            }
        else:
            return {
                **state,
                "fact_check_result": fact_check_result,
                "status": "failed_check",
                "corrections": corrections,
                "retry_count": state["retry_count"] + 1,
            }

    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Fact-checker node failed: {e}")
        # On parse failure, pass the content through (assume OK)
        return {
            **state,
            "fact_check_result": {"passed": True, "confidence_score": 0.5, "issues": [], "corrections": ""},
            "status": "passed",
            "corrections": "",
        }


# ──────────────────────────────────────────────────────────────
# NODE 3: SAVE TO DATABASE
# Upserts the validated content into `generated_pages`
# ──────────────────────────────────────────────────────────────

async def save_node(state: OrchestratorState) -> OrchestratorState:
    """
    Save Node: Upserts the generated and validated MDX content
    into the `generated_pages` Supabase table.
    """
    db = get_supabase_client()
    tool_a = state["tool_a"]
    tool_b = state["tool_b"]

    # Generate SEO metadata
    title = f"{tool_a['name']} vs {tool_b['name']}: Complete Comparison ({datetime.now().year})"
    meta_description = (
        f"In-depth comparison of {tool_a['name']} and {tool_b['name']}. "
        f"Compare pricing, features, pros & cons to find the best "
        f"{tool_a.get('category', 'tool')} for your team."
    )

    # Build JSON-LD schema markup
    schema_markup = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": meta_description,
        "datePublished": datetime.now(timezone.utc).isoformat(),
        "dateModified": datetime.now(timezone.utc).isoformat(),
        "author": {
            "@type": "Organization",
            "name": "Cloudy Unicorn",
        },
        "about": [
            {"@type": "SoftwareApplication", "name": tool_a["name"]},
            {"@type": "SoftwareApplication", "name": tool_b["name"]},
        ],
    }

    page_data = {
        "slug": state["slug"],
        "page_type": "comparison",
        "tool_a_id": str(tool_a["id"]),
        "tool_b_id": str(tool_b["id"]),
        "title": title,
        "meta_description": meta_description,
        "markdown_content": state["generated_content"],
        "schema_markup": schema_markup,
        "published_status": "published",
        "published_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        result = db.table("generated_pages").upsert(
            page_data,
            on_conflict="slug",
        ).execute()

        page_id = result.data[0]["id"] if result.data else None

        logger.info(f"Saved page '{state['slug']}' with ID: {page_id}")

        return {
            **state,
            "page_id": page_id,
            "status": "completed",
        }

    except Exception as e:
        logger.error(f"Save node failed: {e}")
        return {
            **state,
            "status": "failed",
            "error": f"Save failed: {str(e)}",
        }


# ──────────────────────────────────────────────────────────────
# ROUTING LOGIC
# Decides whether to retry or save based on fact-check result
# ──────────────────────────────────────────────────────────────

def should_retry_or_save(state: OrchestratorState) -> str:
    """
    Conditional edge: routes to either 'writer' (retry) or 'save' (accept).
    
    Routes to 'save' if:
      - Fact-check passed
      - Max retries exceeded (accept imperfect content)
    
    Routes to 'writer' if:
      - Fact-check failed AND retries remaining
    """
    if state["status"] == "passed":
        return "save"
    elif state["status"] == "failed":
        return END
    elif state["retry_count"] >= state["max_retries"]:
        logger.warning(f"Max retries ({state['max_retries']}) reached. Saving imperfect content.")
        return "save"
    else:
        return "writer"


# ──────────────────────────────────────────────────────────────
# GRAPH CONSTRUCTION
# Builds the LangGraph StateGraph with conditional edges
# ──────────────────────────────────────────────────────────────

def build_orchestrator_graph() -> StateGraph:
    """
    Constructs the LangGraph workflow:
    
    START → writer → fact_checker → (conditional) → save → END
                                                   → writer (retry)
    """
    graph = StateGraph(OrchestratorState)

    # Add nodes
    graph.add_node("writer", writer_node)
    graph.add_node("fact_checker", fact_checker_node)
    graph.add_node("save", save_node)

    # Set entry point
    graph.set_entry_point("writer")

    # Add edges
    graph.add_edge("writer", "fact_checker")
    graph.add_conditional_edges("fact_checker", should_retry_or_save)
    graph.add_edge("save", END)

    return graph.compile()


# ──────────────────────────────────────────────────────────────
# PUBLIC API
# Entry point for the pipeline, called by API routes
# ──────────────────────────────────────────────────────────────

async def generate_comparison(tool_a_id: UUID, tool_b_id: UUID) -> dict:
    """
    Main entry point: generates a comparison page for two tools.
    
    Steps:
    1. Fetch tool info and scraped features from DB
    2. Build initial state
    3. Execute the LangGraph pipeline
    4. Return the final state with page_id and status
    
    Args:
        tool_a_id: UUID of the first tool
        tool_b_id: UUID of the second tool
    
    Returns:
        dict with page_id, slug, status, and any errors
    """
    db = get_supabase_client()
    settings = get_settings()

    # Fetch tool info
    tool_a_result = db.table("tools").select("*").eq("id", str(tool_a_id)).single().execute()
    tool_b_result = db.table("tools").select("*").eq("id", str(tool_b_id)).single().execute()

    if not tool_a_result.data or not tool_b_result.data:
        raise ValueError("One or both tools not found")

    tool_a = tool_a_result.data
    tool_b = tool_b_result.data

    # Save original tool IDs before merging (features data has its own 'id' that would overwrite)
    tool_a_uuid = tool_a["id"]
    tool_b_uuid = tool_b["id"]

    # Fetch scraped features (if available)
    features_a = db.table("tool_features").select("*").eq("tool_id", str(tool_a_id)).maybe_single().execute()
    features_b = db.table("tool_features").select("*").eq("tool_id", str(tool_b_id)).maybe_single().execute()

    # Merge tool info with features
    if features_a and features_a.data:
        tool_a.update(features_a.data)
    if features_b and features_b.data:
        tool_b.update(features_b.data)

    # Restore the original tool IDs (features merge may have overwritten 'id')
    tool_a["id"] = tool_a_uuid
    tool_b["id"] = tool_b_uuid

    # Generate the URL slug (alphabetically sorted for consistency)
    sorted_names = sorted([tool_a["slug"], tool_b["slug"]])
    slug = f"{sorted_names[0]}-vs-{sorted_names[1]}"

    # Log the generation attempt
    log_data = {
        "trigger_type": "manual",
        "action": "generate",
        "status": "running",
        "metadata": {"tool_a": tool_a["name"], "tool_b": tool_b["name"], "slug": slug},
    }
    log_result = db.table("generation_logs").insert(log_data).execute()
    log_id = log_result.data[0]["id"] if log_result.data else None

    # Build initial state for the graph
    initial_state: OrchestratorState = {
        "tool_a": tool_a,
        "tool_b": tool_b,
        "slug": slug,
        "generated_content": "",
        "fact_check_result": {},
        "retry_count": 0,
        "max_retries": settings.max_retries,
        "corrections": "",
        "status": "pending",
        "error": None,
        "page_id": None,
    }

    # Execute the LangGraph pipeline
    import time
    start_time = time.time()

    graph = build_orchestrator_graph()
    final_state = await graph.ainvoke(initial_state)

    duration_ms = int((time.time() - start_time) * 1000)

    # Update the generation log
    if log_id:
        db.table("generation_logs").update({
            "status": "completed" if final_state["status"] == "completed" else "failed",
            "page_id": final_state.get("page_id"),
            "error_message": final_state.get("error"),
            "duration_ms": duration_ms,
        }).eq("id", log_id).execute()

    logger.info(
        f"Pipeline completed for {slug}: "
        f"status={final_state['status']}, "
        f"duration={duration_ms}ms, "
        f"retries={final_state['retry_count']}"
    )

    return {
        "page_id": final_state.get("page_id"),
        "slug": slug,
        "status": final_state["status"],
        "error": final_state.get("error"),
        "duration_ms": duration_ms,
        "retries": final_state["retry_count"],
    }
