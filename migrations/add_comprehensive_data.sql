-- Migration: Add comprehensive_data JSONB column to tool_features
-- Run this in your Supabase SQL Editor
-- ================================================================

ALTER TABLE tool_features
ADD COLUMN IF NOT EXISTS comprehensive_data JSONB DEFAULT NULL;

COMMENT ON COLUMN tool_features.comprehensive_data IS 
  'Enterprise-grade structured data from the deep-crawl pipeline. Contains technical_summary, core_capabilities, advanced_features, developer_experience, integration_ecosystem, pricing_architecture, compliance_and_security.';
