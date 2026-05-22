"""
SoftRYT Backend — Page Models
================================
Pydantic models for the `generated_pages` table.
These represent AI-generated SEO content.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID


# Type aliases matching the PostgreSQL enums
PageType = Literal["comparison", "review", "alternative"]
PublishStatus = Literal["draft", "published", "archived"]


class PageBase(BaseModel):
    """Shared fields for page creation."""
    slug: str = Field(..., min_length=1, max_length=300, description="URL path for the page")
    page_type: PageType = Field("comparison", description="Type of generated page")
    title: str = Field(..., min_length=1, max_length=200, description="H1 / title tag")
    meta_description: str = Field(..., min_length=1, max_length=320, description="Meta description for SEO")
    markdown_content: str = Field(..., description="Full MDX content body")


class PageCreate(PageBase):
    """Request body for creating a new generated page."""
    tool_a_id: Optional[UUID] = Field(None, description="First tool ID (for comparisons)")
    tool_b_id: Optional[UUID] = Field(None, description="Second tool ID (for comparisons)")
    schema_markup: Optional[dict] = Field(None, description="JSON-LD structured data")
    published_status: PublishStatus = "draft"


class PageUpdate(BaseModel):
    """Request body for updating an existing page (all fields optional)."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    meta_description: Optional[str] = Field(None, min_length=1, max_length=320)
    markdown_content: Optional[str] = None
    schema_markup: Optional[dict] = None
    published_status: Optional[PublishStatus] = None


class PageResponse(PageBase):
    """Response model for a generated page."""
    id: UUID
    tool_a_id: Optional[UUID] = None
    tool_b_id: Optional[UUID] = None
    schema_markup: Optional[dict] = None
    published_status: PublishStatus = "draft"
    published_at: Optional[datetime] = None
    view_count: int = 0
    click_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PageListResponse(BaseModel):
    """Paginated list of generated pages."""
    pages: list[PageResponse]
    total: int


class PageSlugResponse(BaseModel):
    """Minimal response for sitemap/slug listing."""
    slug: str
    updated_at: datetime
    page_type: PageType


class ComparisonRequest(BaseModel):
    """Request body for generating a comparison page."""
    tool_a_id: UUID = Field(..., description="First tool to compare")
    tool_b_id: UUID = Field(..., description="Second tool to compare")
    force_regenerate: bool = Field(False, description="Force regeneration even if page exists")


class ComparisonResponse(BaseModel):
    """Response for a comparison generation request."""
    page_id: UUID
    slug: str
    status: str = "completed"
    message: str = "Comparison page generated successfully"


class ReviewRequest(BaseModel):
    """Request body for generating a review page."""
    tool_id: UUID = Field(..., description="Tool to review")
    force_regenerate: bool = Field(False, description="Force regeneration even if page exists")


class ReviewResponse(BaseModel):
    """Response for a review generation request."""
    page_id: UUID
    slug: str
    status: str = "completed"
    message: str = "Review page generated successfully"


class BulkReviewRequest(BaseModel):
    category: str | None = None
    force_regenerate: bool = False
