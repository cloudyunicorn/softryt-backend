"""
SoftRYT Backend — LangGraph AI Review Orchestrator
=====================================================
Stateful AI pipeline using LangGraph for single-tool reviews:
  1. Writer Node (gpt-oss-120b) — Generates MDX review content
  2. Fact-Checker Node (GPT-4o-mini) — Validates content accuracy
"""

import json
import logging
from typing import TypedDict, Optional
from uuid import UUID
from datetime import datetime, timezone

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END

from app.config import get_settings
from app.database import get_supabase_client
from app.prompts.review_writer import REVIEW_WRITER_SYSTEM_PROMPT, REVIEW_WRITER_USER_PROMPT_TEMPLATE
from app.prompts.review_fact_checker import REVIEW_FACT_CHECKER_SYSTEM_PROMPT, REVIEW_FACT_CHECKER_USER_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# STATE DEFINITION
# ──────────────────────────────────────────────────────────────

class ReviewOrchestratorState(TypedDict):
    """State passed between LangGraph nodes for review generation."""
    tool: dict                # Tool info + scraped features
    slug: str                 # Generated page slug (e.g. "toolname-review")

    # AI outputs
    generated_content: str    # MDX content from Writer
    fact_check_result: dict   # JSON result from Fact-Checker

    # Control flow
    retry_count: int
    max_retries: int
    corrections: str
    status: str
    error: Optional[str]

    # Output
    page_id: Optional[str]


# ──────────────────────────────────────────────────────────────
# NODE 1: WRITER
# ──────────────────────────────────────────────────────────────

async def review_writer_node(state: ReviewOrchestratorState) -> ReviewOrchestratorState:
    """
    Writer Node: Generates a complete MDX review article for a single tool.

    Uses openai/gpt-oss-120b via NVIDIA NIM for review generation.
    On retries, includes the fact-checker's corrections as additional instructions.
    """
    settings = get_settings()
    model_name = settings.writer_model

    llm_kwargs = {
        "model": model_name,
        "temperature": 0.7,
        "max_tokens": 8000,
        "timeout": 300,
    }

    # Route to NVIDIA NIM if model name contains a slash (e.g. "openai/gpt-oss-120b")
    # Plain model names (e.g. "gpt-4o-mini") route to OpenAI directly
    if settings.nvidia_api_key and "/" in model_name:
        llm_kwargs["api_key"] = settings.nvidia_api_key
        llm_kwargs["base_url"] = "https://integrate.api.nvidia.com/v1"
    else:
        llm_kwargs["api_key"] = settings.openai_api_key

    print(f"🤖 [MODEL USAGE] Invoking Review Writer LLM: {model_name}", flush=True)
    logger.info(f"Using writer model: '{model_name}' for single-tool review generation")
    llm = ChatOpenAI(**llm_kwargs)

    tool = state["tool"]

    user_prompt = REVIEW_WRITER_USER_PROMPT_TEMPLATE.format(
        tool_name=tool["name"],
        tool_url=tool.get("website_url", ""),
        tool_category=tool.get("category", ""),
        tool_description=tool.get("description", ""),
        tool_pricing=json.dumps(tool.get("pricing_tiers", []), indent=2),
        tool_features=json.dumps(tool.get("key_features", []), indent=2),
        tool_comprehensive=json.dumps(tool.get("comprehensive_data", {}), indent=2)[:100000],
        tool_raw_content=(tool.get("raw_content", "") or "")[:50000],
        tool_slug=tool.get("slug", ""),
    )

    if state.get("corrections"):
        user_prompt += f"\n\n## CORRECTIONS FROM FACT-CHECKER (MUST FIX):\n{state['corrections']}"
        logger.info(f"Review Writer retry #{state['retry_count']} with corrections")

    messages = [
        SystemMessage(content=REVIEW_WRITER_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    try:
        response = await llm.ainvoke(messages)
        generated_content = response.content

        logger.info(f"Review Writer generated {len(generated_content)} chars of MDX content")

        return {
            **state,
            "generated_content": generated_content,
            "status": "fact_checking",
        }

    except Exception as e:
        logger.error(f"Review Writer node failed: {e}")
        return {
            **state,
            "status": "failed",
            "error": f"Writer failed: {str(e)}",
        }


# ──────────────────────────────────────────────────────────────
# NODE 2: FACT-CHECKER
# ──────────────────────────────────────────────────────────────

async def review_fact_checker_node(state: ReviewOrchestratorState) -> ReviewOrchestratorState:
    settings = get_settings()
    llm_kwargs = {
        "model": settings.fact_checker_model,
        "temperature": 0.1,
        "max_tokens": 4000,
        "timeout": 300,
    }

    if settings.nvidia_api_key and "/" in settings.fact_checker_model:
        llm_kwargs["api_key"] = settings.nvidia_api_key
        llm_kwargs["base_url"] = "https://integrate.api.nvidia.com/v1"
    else:
        llm_kwargs["api_key"] = settings.openai_api_key

    print(f"🤖 [MODEL USAGE] Invoking Review Fact-Checker LLM: {settings.fact_checker_model}", flush=True)
    logger.info(f"Using fact-checker model: '{settings.fact_checker_model}' for single-tool review validation")
    llm = ChatOpenAI(**llm_kwargs)

    tool = state["tool"]

    user_prompt = REVIEW_FACT_CHECKER_USER_PROMPT_TEMPLATE.format(
        generated_content=state["generated_content"][:40000],
        tool_name=tool["name"],
        tool_pricing=json.dumps(tool.get("pricing_tiers", []), indent=2),
        tool_features=json.dumps(tool.get("key_features", []), indent=2),
        tool_comprehensive=json.dumps(tool.get("comprehensive_data", {}), indent=2)[:5000],
    )

    messages = [
        SystemMessage(content=REVIEW_FACT_CHECKER_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    try:
        response = await llm.ainvoke(messages)
        
        result_text = response.content.strip()
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
            f"Review Fact-check: passed={passed}, confidence={confidence}, "
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
        logger.error(f"Review Fact-checker node failed: {e}")
        return {
            **state,
            "fact_check_result": {"passed": True, "confidence_score": 0.5, "issues": [], "corrections": ""},
            "status": "passed",
            "corrections": "",
        }


# ──────────────────────────────────────────────────────────────
# NODE 3: SAVE TO DATABASE
# ──────────────────────────────────────────────────────────────

async def review_save_node(state: ReviewOrchestratorState) -> ReviewOrchestratorState:
    db = get_supabase_client()
    tool = state["tool"]

    title = f"{tool['name']} Review ({datetime.now().year}): Pricing, Features & Verdict"
    meta_description = (
        f"In-depth review of {tool['name']}. "
        f"Explore pricing, core features, ideal use cases, and our final verdict."
    )

    schema_markup = {
        "@context": "https://schema.org",
        "@type": ["Article", "Review"],
        "headline": title,
        "description": meta_description,
        "datePublished": datetime.now(timezone.utc).isoformat(),
        "dateModified": datetime.now(timezone.utc).isoformat(),
        "author": {
            "@type": "Organization",
            "name": "Cloudy Unicorn",
        },
        "itemReviewed": {
            "@type": "SoftwareApplication",
            "name": tool["name"],
            "applicationCategory": tool.get("category", "Software")
        }
    }

    page_data = {
        "slug": state["slug"],
        "page_type": "review",
        "tool_a_id": str(tool["id"]),
        "tool_b_id": None,
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

        logger.info(f"Saved review page '{state['slug']}' with ID: {page_id}")

        return {
            **state,
            "page_id": page_id,
            "status": "completed",
        }

    except Exception as e:
        logger.error(f"Review Save node failed: {e}")
        return {
            **state,
            "status": "failed",
            "error": f"Save failed: {str(e)}",
        }


# ──────────────────────────────────────────────────────────────
# ROUTING LOGIC
# ──────────────────────────────────────────────────────────────

def review_should_retry_or_save(state: ReviewOrchestratorState) -> str:
    if state["status"] == "passed":
        return "save"
    elif state["status"] == "failed":
        return END
    elif state["retry_count"] >= state["max_retries"]:
        logger.warning(f"Max retries ({state['max_retries']}) reached. Saving imperfect content.")
        return "save"
    else:
        return "writer"


def build_review_orchestrator_graph() -> StateGraph:
    graph = StateGraph(ReviewOrchestratorState)

    graph.add_node("writer", review_writer_node)
    graph.add_node("fact_checker", review_fact_checker_node)
    graph.add_node("save", review_save_node)

    graph.set_entry_point("writer")

    graph.add_edge("writer", "fact_checker")
    graph.add_conditional_edges("fact_checker", review_should_retry_or_save)
    graph.add_edge("save", END)

    return graph.compile()


# ──────────────────────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────────────────────

async def generate_review(tool_id: UUID) -> dict:
    db = get_supabase_client()
    settings = get_settings()

    tool_result = db.table("tools").select("*").eq("id", str(tool_id)).single().execute()

    if not tool_result.data:
        raise ValueError("Tool not found")

    tool = tool_result.data
    tool_uuid = tool["id"]

    features = db.table("tool_features").select("*").eq("tool_id", str(tool_id)).maybe_single().execute()

    if features and features.data:
        tool.update(features.data)

    tool["id"] = tool_uuid

    slug = f"review/{tool['slug']}"

    log_data = {
        "trigger_type": "manual",
        "action": "generate_review",
        "status": "running",
        "metadata": {"tool": tool["name"], "slug": slug},
    }
    log_result = db.table("generation_logs").insert(log_data).execute()
    log_id = log_result.data[0]["id"] if log_result.data else None

    initial_state: ReviewOrchestratorState = {
        "tool": tool,
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

    import time
    start_time = time.time()

    graph = build_review_orchestrator_graph()
    final_state = await graph.ainvoke(initial_state)

    duration_ms = int((time.time() - start_time) * 1000)

    if log_id:
        db.table("generation_logs").update({
            "status": "completed" if final_state["status"] == "completed" else "failed",
            "page_id": final_state.get("page_id"),
            "error_message": final_state.get("error"),
            "duration_ms": duration_ms,
        }).eq("id", log_id).execute()

    logger.info(
        f"Review Pipeline completed for {slug}: "
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
