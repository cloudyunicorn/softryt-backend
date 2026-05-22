-- ============================================================
-- SoftRYT — Seed Data: Viral B2B SaaS Tools
-- 003_seed_viral_tools.sql
-- 
-- Seeds the database with popular, high-search-volume SaaS tools
-- across key B2B categories for programmatic comparison pages.
-- ============================================================

-- ──────────────────────────────────────────────────────────────
-- CATEGORY: Project Management
-- ──────────────────────────────────────────────────────────────

INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Notion', 'notion', 'https://www.notion.so', 'https://www.notion.so/pricing', 'project-management', 'All-in-one workspace for notes, docs, wikis, and project management'),
('Coda', 'coda', 'https://coda.io', 'https://coda.io/pricing', 'project-management', 'Doc-powered workspace that blends documents, spreadsheets, and apps'),
('Linear', 'linear', 'https://linear.app', 'https://linear.app/pricing', 'project-management', 'Streamlined issue tracking and project management for software teams'),
('Jira', 'jira', 'https://www.atlassian.com/software/jira', 'https://www.atlassian.com/software/jira/pricing', 'project-management', 'Enterprise-grade agile project management and issue tracking'),
('Asana', 'asana', 'https://asana.com', 'https://asana.com/pricing', 'project-management', 'Work management platform for teams to organize and track projects'),
('Monday.com', 'monday', 'https://monday.com', 'https://monday.com/pricing', 'project-management', 'Visual work OS for teams to manage projects, workflows, and tasks'),
('ClickUp', 'clickup', 'https://clickup.com', 'https://clickup.com/pricing', 'project-management', 'All-in-one productivity platform replacing multiple work tools'),
('Basecamp', 'basecamp', 'https://basecamp.com', 'https://basecamp.com/pricing', 'project-management', 'Simple, opinionated project management and team communication');

-- ──────────────────────────────────────────────────────────────
-- CATEGORY: Design & Collaboration
-- ──────────────────────────────────────────────────────────────

INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Figma', 'figma', 'https://www.figma.com', 'https://www.figma.com/pricing', 'design', 'Collaborative interface design tool for teams'),
('Canva', 'canva', 'https://www.canva.com', 'https://www.canva.com/pricing', 'design', 'Visual design platform for creating graphics, presentations, and content'),
('Framer', 'framer', 'https://www.framer.com', 'https://www.framer.com/pricing', 'design', 'No-code website builder with design-to-production workflow'),
('Webflow', 'webflow', 'https://webflow.com', 'https://webflow.com/pricing', 'design', 'Visual web development platform with CMS and hosting');

-- ──────────────────────────────────────────────────────────────
-- CATEGORY: Developer Tools & Infrastructure
-- ──────────────────────────────────────────────────────────────

INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Vercel', 'vercel', 'https://vercel.com', 'https://vercel.com/pricing', 'dev-tools', 'Frontend cloud platform for deploying web applications'),
('Netlify', 'netlify', 'https://www.netlify.com', 'https://www.netlify.com/pricing', 'dev-tools', 'Web development platform with serverless backend services'),
('Railway', 'railway', 'https://railway.app', 'https://railway.app/pricing', 'dev-tools', 'Infrastructure platform for deploying apps and databases instantly'),
('Render', 'render', 'https://render.com', 'https://render.com/pricing', 'dev-tools', 'Unified cloud platform to build and run apps and websites'),
('Supabase', 'supabase', 'https://supabase.com', 'https://supabase.com/pricing', 'dev-tools', 'Open-source Firebase alternative with Postgres, auth, and storage'),
('Firebase', 'firebase', 'https://firebase.google.com', 'https://firebase.google.com/pricing', 'dev-tools', 'Google platform for building mobile and web applications'),
('PlanetScale', 'planetscale', 'https://planetscale.com', 'https://planetscale.com/pricing', 'dev-tools', 'Serverless MySQL platform with branching and unlimited scale'),
('Neon', 'neon', 'https://neon.tech', 'https://neon.tech/pricing', 'dev-tools', 'Serverless Postgres with autoscaling and branching');

-- ──────────────────────────────────────────────────────────────
-- CATEGORY: AI & Automation
-- ──────────────────────────────────────────────────────────────

INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Cursor', 'cursor', 'https://cursor.sh', 'https://cursor.sh/pricing', 'ai-tools', 'AI-powered code editor built on VS Code with intelligent completions'),
('GitHub Copilot', 'github-copilot', 'https://github.com/features/copilot', 'https://github.com/features/copilot#pricing', 'ai-tools', 'AI pair programmer that suggests code completions in your IDE'),
('Replit', 'replit', 'https://replit.com', 'https://replit.com/pricing', 'ai-tools', 'Browser-based IDE with AI coding assistant and instant deployment'),
('v0', 'v0', 'https://v0.dev', 'https://v0.dev/pricing', 'ai-tools', 'AI-powered UI generation tool by Vercel for React components'),
('Bolt', 'bolt', 'https://bolt.new', 'https://bolt.new', 'ai-tools', 'AI-powered full-stack web development in the browser'),
('Lovable', 'lovable', 'https://lovable.dev', 'https://lovable.dev/pricing', 'ai-tools', 'AI software engineer that builds production-ready web apps');

-- ──────────────────────────────────────────────────────────────
-- CATEGORY: Communication & Collaboration
-- ──────────────────────────────────────────────────────────────

INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Slack', 'slack', 'https://slack.com', 'https://slack.com/pricing', 'communication', 'Business messaging platform for team communication and workflows'),
('Discord', 'discord', 'https://discord.com', 'https://discord.com/nitro', 'communication', 'Community platform for voice, video, and text communication'),
('Loom', 'loom', 'https://www.loom.com', 'https://www.loom.com/pricing', 'communication', 'Async video messaging platform for workplace communication'),
('Zoom', 'zoom', 'https://zoom.us', 'https://zoom.us/pricing', 'communication', 'Video conferencing and virtual meeting platform');

-- ──────────────────────────────────────────────────────────────
-- CATEGORY: Analytics & Marketing
-- ──────────────────────────────────────────────────────────────

INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('PostHog', 'posthog', 'https://posthog.com', 'https://posthog.com/pricing', 'analytics', 'Open-source product analytics, session replay, and feature flags'),
('Mixpanel', 'mixpanel', 'https://mixpanel.com', 'https://mixpanel.com/pricing', 'analytics', 'Product analytics platform for user behavior tracking and insights'),
('Amplitude', 'amplitude', 'https://amplitude.com', 'https://amplitude.com/pricing', 'analytics', 'Digital analytics platform for understanding user journeys'),
('Plausible', 'plausible', 'https://plausible.io', 'https://plausible.io/#pricing', 'analytics', 'Lightweight, privacy-focused web analytics alternative to Google Analytics');

-- ──────────────────────────────────────────────────────────────
-- CATEGORY: CMS & Content
-- ──────────────────────────────────────────────────────────────

INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Contentful', 'contentful', 'https://www.contentful.com', 'https://www.contentful.com/pricing', 'cms', 'Headless CMS for building digital experiences across channels'),
('Sanity', 'sanity', 'https://www.sanity.io', 'https://www.sanity.io/pricing', 'cms', 'Composable content cloud with real-time collaboration and customization'),
('Strapi', 'strapi', 'https://strapi.io', 'https://strapi.io/pricing', 'cms', 'Open-source headless CMS for building APIs without writing code');

-- ──────────────────────────────────────────────────────────────
-- CATEGORY: Email & Marketing Automation
-- ──────────────────────────────────────────────────────────────

INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Resend', 'resend', 'https://resend.com', 'https://resend.com/pricing', 'email', 'Modern email API for developers with React Email templates'),
('SendGrid', 'sendgrid', 'https://sendgrid.com', 'https://sendgrid.com/pricing', 'email', 'Cloud-based email delivery platform for transactional and marketing emails'),
('Mailchimp', 'mailchimp', 'https://mailchimp.com', 'https://mailchimp.com/pricing', 'email', 'All-in-one marketing platform with email, automation, and analytics'),
('ConvertKit', 'convertkit', 'https://convertkit.com', 'https://convertkit.com/pricing', 'email', 'Creator-focused email marketing platform with automation');
