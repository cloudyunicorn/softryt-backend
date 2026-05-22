"""
SoftRYT Backend — Tool Models
================================
Pydantic models for the `tools` table CRUD operations.
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from datetime import datetime
from uuid import UUID


class ToolBase(BaseModel):
    """Shared fields for tool creation and updates."""
    name: str = Field(..., min_length=1, max_length=200, description="Display name of the tool")
    slug: str = Field(..., min_length=1, max_length=100, description="URL-safe identifier")
    website_url: str = Field(..., description="Official website URL")
    pricing_url: Optional[str] = Field(None, description="Direct link to pricing page")
    affiliate_url: Optional[str] = Field(None, description="Affiliate/referral link")
    category: str = Field("general", description="Tool category (e.g., 'project-management')")
    logo_url: Optional[str] = Field(None, description="CDN URL for tool logo")
    description: Optional[str] = Field(None, description="Short one-liner description")


class ToolCreate(ToolBase):
    """Request body for creating a new tool."""
    pass


class ToolUpdate(BaseModel):
    """Request body for updating an existing tool (all fields optional)."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    slug: Optional[str] = Field(None, min_length=1, max_length=100)
    website_url: Optional[str] = None
    pricing_url: Optional[str] = None
    affiliate_url: Optional[str] = None
    category: Optional[str] = None
    logo_url: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class ToolResponse(ToolBase):
    """Response model for a tool (includes DB-generated fields)."""
    id: UUID
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ToolListResponse(BaseModel):
    """Paginated list of tools."""
    tools: list[ToolResponse]
    total: int
