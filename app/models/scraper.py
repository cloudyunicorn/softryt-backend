"""
SoftRYT Backend — Scraper Models
====================================
Pydantic models for structuring scraped data from SaaS pricing pages.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class PricingTier(BaseModel):
    """A single pricing plan/tier scraped from a tool's pricing page."""
    name: str = Field(..., description="Plan name (e.g., 'Free', 'Pro', 'Enterprise')")
    price: str = Field(..., description="Price string (e.g., '$10/mo', 'Custom', 'Free')")
    billing_period: Optional[str] = Field(None, description="Billing cycle (e.g., 'monthly', 'yearly')")
    features: list[str] = Field(default_factory=list, description="List of features included in this tier")
    is_popular: bool = Field(False, description="Whether this is the highlighted/recommended plan")
    cta_text: Optional[str] = Field(None, description="Call-to-action button text")


class ScrapedToolData(BaseModel):
    """Complete scraped data for a single tool."""
    tool_id: UUID
    tool_name: str
    pricing_tiers: list[PricingTier] = Field(default_factory=list)
    key_features: list[str] = Field(default_factory=list)
    integrations: list[str] = Field(default_factory=list)
    raw_content: Optional[str] = Field(None, description="Raw text content from the page")
    content_hash: Optional[str] = Field(None, description="SHA-256 hash for change detection")


class ScrapeRequest(BaseModel):
    """Request body for triggering a scrape."""
    tool_id: UUID = Field(..., description="ID of the tool to scrape")
    force: bool = Field(False, description="Force re-scrape even if data is fresh")


class ScrapeResponse(BaseModel):
    """Response for a scrape operation."""
    tool_id: UUID
    tool_name: str
    status: str = "completed"
    changed: bool = False  # Whether content changed since last scrape
    pricing_tiers_count: int = 0
    features_count: int = 0
    message: str = "Scrape completed successfully"


class ToolFeaturesResponse(BaseModel):
    """Response model for tool_features table data."""
    id: UUID
    tool_id: UUID
    pricing_tiers: list[dict]
    key_features: list[str]
    integrations: list[str]
    raw_content: Optional[str] = None
    content_hash: Optional[str] = None
    last_scraped_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
