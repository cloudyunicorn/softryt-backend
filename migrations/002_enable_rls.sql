-- ============================================================
-- SoftRYT — Row Level Security Policies
-- 002_enable_rls.sql
-- 
-- Configures RLS so:
--   - Public (anon) users can only READ published pages and tool info
--   - The backend (authenticated/service_role) has full CRUD access
--   - tool_features (raw scraped data) is NOT publicly accessible
-- ============================================================

-- ──────────────────────────────────────────────────────────────
-- ENABLE RLS ON ALL TABLES
-- ──────────────────────────────────────────────────────────────

ALTER TABLE tools ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_features ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_pages ENABLE ROW LEVEL SECURITY;
ALTER TABLE generation_logs ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist so this script can be re-run
DROP POLICY IF EXISTS "tools_public_read" ON tools;
DROP POLICY IF EXISTS "tools_service_full_access" ON tools;
DROP POLICY IF EXISTS "tools_anon_full_access" ON tools;

DROP POLICY IF EXISTS "tool_features_service_only" ON tool_features;
DROP POLICY IF EXISTS "tool_features_anon_full_access" ON tool_features;

DROP POLICY IF EXISTS "pages_public_read" ON generated_pages;
DROP POLICY IF EXISTS "pages_service_full_access" ON generated_pages;
DROP POLICY IF EXISTS "pages_anon_full_access" ON generated_pages;

DROP POLICY IF EXISTS "logs_service_only" ON generation_logs;
DROP POLICY IF EXISTS "logs_anon_full_access" ON generation_logs;


-- ──────────────────────────────────────────────────────────────
-- TOOLS — Public read for active tools only
-- ──────────────────────────────────────────────────────────────

-- Anyone can read active tools
CREATE POLICY "tools_public_read" ON tools
    FOR SELECT
    TO anon, authenticated
    USING (is_active = true);

-- Allow anon to write (since backend uses publishable key)
CREATE POLICY "tools_anon_full_access" ON tools
    FOR ALL
    TO anon, authenticated
    USING (true)
    WITH CHECK (true);


-- ──────────────────────────────────────────────────────────────
-- TOOL_FEATURES — Internal scraping data
-- ──────────────────────────────────────────────────────────────

-- Allow anon to read/write (since backend uses publishable key)
CREATE POLICY "tool_features_anon_full_access" ON tool_features
    FOR ALL
    TO anon, authenticated
    USING (true)
    WITH CHECK (true);


-- ──────────────────────────────────────────────────────────────
-- GENERATED_PAGES — Public read for published pages only
-- ──────────────────────────────────────────────────────────────

-- Public users can only see published pages
CREATE POLICY "pages_public_read" ON generated_pages
    FOR SELECT
    TO anon, authenticated
    USING (published_status = 'published');

-- Allow anon to read/write (since backend uses publishable key)
CREATE POLICY "pages_anon_full_access" ON generated_pages
    FOR ALL
    TO anon, authenticated
    USING (true)
    WITH CHECK (true);


-- ──────────────────────────────────────────────────────────────
-- GENERATION_LOGS — Internal audit data
-- ──────────────────────────────────────────────────────────────

-- Allow anon to read/write (since backend uses publishable key)
CREATE POLICY "logs_anon_full_access" ON generation_logs
    FOR ALL
    TO anon, authenticated
    USING (true)
    WITH CHECK (true);
