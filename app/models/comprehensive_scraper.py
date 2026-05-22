"""
SoftRYT Backend — Comprehensive Scraper Models
===================================================
Enterprise-grade Pydantic schemas for the deep-crawl data extraction pipeline.

ComprehensiveToolData forces the LLM to act as a Principal Solutions Architect,
extracting hard technical facts — not marketing fluff — from multi-page scrapes.
"""

from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID


# ── Output Schema ─────────────────────────────────────────────

class PricingTierDetail(BaseModel):
    """A single pricing tier with granular detail."""
    tier_name: str = Field(..., description="Exact plan name (e.g., 'Team', 'Business', 'Enterprise')")
    price: str = Field(..., description="Exact price string (e.g., '$49/mo per seat', 'Custom', 'Free')")
    billing_period: Optional[str] = Field(None, description="Billing cycle (monthly, annual, usage-based)")
    seat_minimum: Optional[str] = Field(None, description="Minimum seats if applicable")
    limitations: list[str] = Field(default_factory=list, description="Hard limits (storage caps, API rate limits, user caps)")
    included_features: list[str] = Field(default_factory=list, description="Features included in this tier")


class ComprehensiveToolData(BaseModel):
    """
    Enterprise-grade structured extraction from a SaaS tool's entire web presence.
    
    This schema forces the LLM to evaluate the tool as a Principal Solutions Architect
    would — focusing on hard technical capabilities, constraints, and architecture,
    not marketing copy.
    """
    technical_summary: str = Field(
        ...,
        description=(
            "Deep architectural overview: what the tool does at a systems level, "
            "its core value proposition, target persona, and key differentiators. "
            "2-4 sentences of dense, technical prose."
        ),
    )
    core_capabilities: list[str] = Field(
        default_factory=list,
        description=(
            "Exhaustive list of primary features and capabilities. "
            "Be specific and technical (e.g., 'Real-time collaborative editing with OT/CRDT', "
            "not 'Easy collaboration')."
        ),
    )
    advanced_features: list[str] = Field(
        default_factory=list,
        description=(
            "Niche, enterprise, or power-user features that differentiate this tool. "
            "Edge cases, advanced workflows, white-labeling, custom domains, audit logs, etc."
        ),
    )
    developer_experience: list[str] = Field(
        default_factory=list,
        description=(
            "API availability and quality, SDKs, CLI tools, webhooks, "
            "documentation quality, open-source components, plugin/extension systems."
        ),
    )
    integration_ecosystem: list[str] = Field(
        default_factory=list,
        description=(
            "All supported third-party integrations and platforms. "
            "Include specific names (e.g., 'Slack', 'Jira', 'Salesforce', 'Zapier')."
        ),
    )
    pricing_architecture: list[PricingTierDetail] = Field(
        default_factory=list,
        description="All pricing tiers with exact pricing, limitations, and included features.",
    )
    compliance_and_security: list[str] = Field(
        default_factory=list,
        description=(
            "Security certifications and compliance: SOC 2 Type II, GDPR, HIPAA, "
            "ISO 27001, SSO/SAML, SCIM, data residency, encryption at rest/in transit, etc."
        ),
    )


# ── Request / Response ────────────────────────────────────────

class ComprehensiveScrapeRequest(BaseModel):
    """Request body for the comprehensive deep-scrape endpoint."""
    tool_id: UUID = Field(..., description="ID of the tool in the `tools` table")
    base_url: str = Field(..., description="Root URL of the tool's website (e.g., https://posthog.com)")


class ComprehensiveScrapeResponse(BaseModel):
    """Response body after a comprehensive scrape completes."""
    tool_id: UUID
    tool_name: str
    status: str = "completed"
    urls_discovered: int = 0
    urls_scraped: int = 0
    markdown_chars: int = 0
    data: Optional[ComprehensiveToolData] = None
    message: str = "Comprehensive scrape completed successfully"
