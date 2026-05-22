-- ============================================================
-- Cloudy Unicorn — Blog Posts Table
-- 005_create_blog_posts.sql
--
-- Stores AI-generated blog content, completely separate from
-- the SaaS comparison/review content in generated_pages.
-- ============================================================

CREATE TABLE blog_posts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug                TEXT NOT NULL UNIQUE,                    -- URL path (e.g., "best-ai-tools-2026")
    title               TEXT NOT NULL,                           -- Blog post title / H1
    meta_description    TEXT NOT NULL,                           -- SEO meta description
    markdown_content    TEXT NOT NULL,                           -- Full MDX blog body
    topic               TEXT NOT NULL,                           -- Original topic/prompt provided
    research_data       TEXT,                                    -- Raw scraped research markdown
    cover_image_url     TEXT,                                    -- URL to AI-generated cover image
    schema_markup       JSONB DEFAULT '{}'::jsonb,               -- JSON-LD structured data
    tags                TEXT[] DEFAULT '{}',                     -- Tag array for categorization

    -- Publication workflow
    published_status    publish_status_enum NOT NULL DEFAULT 'draft',
    published_at        TIMESTAMPTZ,

    -- Tracking
    view_count          INTEGER NOT NULL DEFAULT 0,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Primary query path: slug lookups
CREATE INDEX idx_blog_posts_slug ON blog_posts(slug);
-- Filter by status for public listing
CREATE INDEX idx_blog_posts_status ON blog_posts(published_status);
-- Tag-based filtering
CREATE INDEX idx_blog_posts_tags ON blog_posts USING GIN(tags);

-- Auto-update updated_at
CREATE TRIGGER update_blog_posts_updated_at
    BEFORE UPDATE ON blog_posts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ──────────────────────────────────────────────────────────────
-- ROW LEVEL SECURITY
-- Same pattern as generated_pages: public read for published,
-- full anon access for backend (uses publishable key).
-- ──────────────────────────────────────────────────────────────

ALTER TABLE blog_posts ENABLE ROW LEVEL SECURITY;

-- Public users can only see published blog posts
CREATE POLICY "blog_posts_public_read" ON blog_posts
    FOR SELECT
    TO anon, authenticated
    USING (published_status = 'published');

-- Allow anon to read/write (backend uses publishable key)
CREATE POLICY "blog_posts_anon_full_access" ON blog_posts
    FOR ALL
    TO anon, authenticated
    USING (true)
    WITH CHECK (true);
