-- ============================================================
-- SoftRYT — Database Schema Migration
-- 001_create_tables.sql
-- 
-- Creates the core tables for the programmatic SEO platform:
--   1. tools          — Base SaaS tool information
--   2. tool_features  — Raw scraped pricing/feature data
--   3. generated_pages — AI-generated SEO content (MDX)
--   4. generation_logs — Pipeline audit trail
-- ============================================================

-- ──────────────────────────────────────────────────────────────
-- ENUMS
-- ──────────────────────────────────────────────────────────────

-- Page types supported by the content generator
CREATE TYPE page_type_enum AS ENUM ('comparison', 'review', 'alternative');

-- Publication workflow states
CREATE TYPE publish_status_enum AS ENUM ('draft', 'published', 'archived');

-- Generation pipeline trigger sources
CREATE TYPE trigger_type_enum AS ENUM ('manual', 'cron', 'webhook');

-- Generation pipeline status
CREATE TYPE generation_status_enum AS ENUM ('pending', 'running', 'completed', 'failed');


-- ──────────────────────────────────────────────────────────────
-- TABLE 1: tools
-- Stores base information about each SaaS tool we track.
-- ──────────────────────────────────────────────────────────────

CREATE TABLE tools (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    slug            TEXT NOT NULL UNIQUE,               -- URL-safe identifier (e.g., "notion")
    website_url     TEXT NOT NULL,
    pricing_url     TEXT,                                -- Direct link to pricing page for scraping
    affiliate_url   TEXT,                                -- Affiliate/referral link for monetization
    category        TEXT NOT NULL DEFAULT 'general',     -- e.g., "project-management", "design", "dev-tools"
    logo_url        TEXT,                                -- CDN URL for the tool's logo
    description     TEXT,                                -- Short one-liner description
    is_active       BOOLEAN NOT NULL DEFAULT true,       -- Toggle to disable scraping/generation
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Fast lookups by slug (used in affiliate redirects and page generation)
CREATE INDEX idx_tools_slug ON tools(slug);
-- Filter by category for category landing pages
CREATE INDEX idx_tools_category ON tools(category);


-- ──────────────────────────────────────────────────────────────
-- TABLE 2: tool_features
-- Stores raw scraped data from each tool's pricing/feature pages.
-- This is the "source of truth" that the AI references.
-- ──────────────────────────────────────────────────────────────

CREATE TABLE tool_features (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_id         UUID NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    
    -- Structured scraped data stored as JSONB for flexibility
    -- pricing_tiers example: [{"name": "Free", "price": "$0/mo", "features": ["5 users", "1GB storage"]}]
    pricing_tiers   JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    -- key_features example: ["Real-time collaboration", "API access", "SSO"]
    key_features    JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    -- Integrations, platform support, etc.
    integrations    JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    -- Raw text dump from scraping (used for AI context)
    raw_content     TEXT,
    
    -- SHA-256 hash of the scraped content to detect changes on re-scrape
    content_hash    TEXT,
    
    -- Tracks when this data was last refreshed
    last_scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Each tool should only have one active feature record
    CONSTRAINT unique_tool_features UNIQUE (tool_id)
);

-- FK index for joins
CREATE INDEX idx_tool_features_tool_id ON tool_features(tool_id);


-- ──────────────────────────────────────────────────────────────
-- TABLE 3: generated_pages
-- Stores AI-generated SEO content (MDX format).
-- Each row is a publishable page on the frontend.
-- ──────────────────────────────────────────────────────────────

CREATE TABLE generated_pages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug                TEXT NOT NULL UNIQUE,                    -- URL path (e.g., "notion-vs-coda")
    page_type           page_type_enum NOT NULL DEFAULT 'comparison',
    
    -- References to the tools being compared/reviewed
    tool_a_id           UUID REFERENCES tools(id) ON DELETE SET NULL,
    tool_b_id           UUID REFERENCES tools(id) ON DELETE SET NULL,
    
    -- SEO metadata
    title               TEXT NOT NULL,                           -- H1 / <title> tag
    meta_description    TEXT NOT NULL,                           -- <meta name="description">
    
    -- The main content body in MDX format
    markdown_content    TEXT NOT NULL,
    
    -- Structured data for JSON-LD schema markup
    schema_markup       JSONB DEFAULT '{}'::jsonb,
    
    -- Publication workflow
    published_status    publish_status_enum NOT NULL DEFAULT 'draft',
    published_at        TIMESTAMPTZ,                             -- When first published
    
    -- Tracking
    view_count          INTEGER NOT NULL DEFAULT 0,
    click_count         INTEGER NOT NULL DEFAULT 0,              -- Affiliate link clicks
    
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Prevent duplicate comparisons (A vs B = B vs A handled at app level)
    CONSTRAINT unique_comparison UNIQUE (tool_a_id, tool_b_id)
);

-- Primary query path: slug lookups for page rendering
CREATE INDEX idx_generated_pages_slug ON generated_pages(slug);
-- Filter by status for public listing
CREATE INDEX idx_generated_pages_status ON generated_pages(published_status);
-- FK indexes for joins
CREATE INDEX idx_generated_pages_tool_a ON generated_pages(tool_a_id);
CREATE INDEX idx_generated_pages_tool_b ON generated_pages(tool_b_id);


-- ──────────────────────────────────────────────────────────────
-- TABLE 4: generation_logs
-- Audit trail for the AI generation pipeline.
-- Tracks every scrape and generation attempt.
-- ──────────────────────────────────────────────────────────────

CREATE TABLE generation_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id         UUID REFERENCES generated_pages(id) ON DELETE SET NULL,
    tool_id         UUID REFERENCES tools(id) ON DELETE SET NULL,
    
    trigger_type    trigger_type_enum NOT NULL DEFAULT 'manual',
    action          TEXT NOT NULL,                       -- e.g., "scrape", "generate", "fact-check"
    status          generation_status_enum NOT NULL DEFAULT 'pending',
    
    -- Error details if the pipeline failed
    error_message   TEXT,
    
    -- Performance tracking
    duration_ms     INTEGER,
    
    -- Additional metadata (model used, token count, etc.)
    metadata        JSONB DEFAULT '{}'::jsonb,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Query logs by page or tool
CREATE INDEX idx_generation_logs_page_id ON generation_logs(page_id);
CREATE INDEX idx_generation_logs_tool_id ON generation_logs(tool_id);
CREATE INDEX idx_generation_logs_status ON generation_logs(status);


-- ──────────────────────────────────────────────────────────────
-- AUTO-UPDATE TRIGGERS
-- Automatically set `updated_at` on row modification.
-- ──────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_tools_updated_at
    BEFORE UPDATE ON tools
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tool_features_updated_at
    BEFORE UPDATE ON tool_features
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_generated_pages_updated_at
    BEFORE UPDATE ON generated_pages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
