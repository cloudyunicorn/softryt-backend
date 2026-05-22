-- ============================================================
-- SoftRYT — Full Database Reset & Tool Seeding Script
-- ============================================================
-- This script:
--   1. Deletes all generated pages, tool features, and tools
--   2. Inserts 71 tools across 18 categories of direct competitors
--
-- Run this in the Supabase SQL Editor (Dashboard → SQL Editor → New Query)
-- ============================================================

-- Step 1: Clean slate — delete everything (order matters for FK constraints)
DELETE FROM generated_pages;
DELETE FROM generation_logs;
DELETE FROM tool_features;
DELETE FROM tools;

-- Step 2: Insert all tools

-- ── 1. WORKSPACE-DOCS ─────────────────────────────────────────
INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Notion',       'notion',       'https://notion.so',                                  'https://notion.so/pricing',                                  'workspace-docs', 'All-in-one workspace for docs, wikis, and project tracking'),
('Coda',         'coda',         'https://coda.io',                                    'https://coda.io/pricing',                                    'workspace-docs', 'Interactive docs that work like apps with formulas and automation'),
('Obsidian',     'obsidian',     'https://obsidian.md',                                'https://obsidian.md/pricing',                                'workspace-docs', 'Markdown-first knowledge base with local-first privacy'),
('Confluence',   'confluence',   'https://www.atlassian.com/software/confluence',       'https://www.atlassian.com/software/confluence/pricing',       'workspace-docs', 'Enterprise wiki and documentation platform by Atlassian');

-- ── 2. PROJECT-MANAGEMENT ─────────────────────────────────────
INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Asana',        'asana',        'https://asana.com',                                  'https://asana.com/pricing',                                  'project-management', 'Work management platform for team task tracking and workflows'),
('Monday.com',   'monday',       'https://monday.com',                                 'https://monday.com/pricing',                                 'project-management', 'Visual Work OS for project management and team collaboration'),
('ClickUp',      'clickup',      'https://clickup.com',                                'https://clickup.com/pricing',                                'project-management', 'All-in-one productivity platform with customizable project views'),
('Trello',       'trello',       'https://trello.com',                                 'https://trello.com/pricing',                                 'project-management', 'Kanban-style project management with boards, lists, and cards'),
('Wrike',        'wrike',        'https://www.wrike.com',                              'https://www.wrike.com/pricing',                              'project-management', 'Enterprise work management with resource planning and proofing');

-- ── 3. ISSUE-TRACKING ─────────────────────────────────────────
INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Jira',         'jira',         'https://www.atlassian.com/software/jira',             'https://www.atlassian.com/software/jira/pricing',             'issue-tracking', 'Industry-standard issue tracker for agile software development'),
('Linear',       'linear',       'https://linear.app',                                  'https://linear.app/pricing',                                  'issue-tracking', 'Streamlined issue tracking built for modern software teams'),
('GitHub Issues', 'github-issues', 'https://github.com',                                'https://github.com/pricing',                                  'issue-tracking', 'Built-in issue tracking integrated with GitHub repositories'),
('Shortcut',     'shortcut',     'https://shortcut.com',                                'https://shortcut.com/pricing',                                'issue-tracking', 'Project management for software teams with epics and iterations');

-- ── 4. DESIGN-TOOL ────────────────────────────────────────────
INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Figma',        'figma',        'https://www.figma.com',                               'https://www.figma.com/pricing',                               'design-tool', 'Collaborative UI/UX design and prototyping platform'),
('Canva',        'canva',        'https://www.canva.com',                               'https://www.canva.com/pricing',                               'design-tool', 'Visual design platform for graphics, presentations, and social media'),
('Adobe XD',     'adobe-xd',     'https://www.adobe.com/products/xd.html',              'https://www.adobe.com/creativecloud/plans.html',              'design-tool', 'UI/UX design tool from the Adobe Creative Cloud suite'),
('Sketch',       'sketch',       'https://www.sketch.com',                              'https://www.sketch.com/pricing',                              'design-tool', 'macOS-native vector design tool for UI/UX professionals');

-- ── 5. WEBSITE-BUILDER ────────────────────────────────────────
INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Webflow',      'webflow',      'https://webflow.com',                                 'https://webflow.com/pricing',                                 'website-builder', 'Visual web development platform with CMS and hosting'),
('Framer',       'framer',       'https://www.framer.com',                              'https://www.framer.com/pricing',                              'website-builder', 'Design-to-production website builder with animations'),
('Wix',          'wix',          'https://www.wix.com',                                 'https://www.wix.com/upgrade/website',                         'website-builder', 'AI-powered website builder for businesses and portfolios'),
('Squarespace',  'squarespace',  'https://www.squarespace.com',                         'https://www.squarespace.com/pricing',                         'website-builder', 'All-in-one website builder with designer-quality templates');

-- ── 6. HEADLESS-CMS ───────────────────────────────────────────
INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Sanity',       'sanity',       'https://www.sanity.io',                               'https://www.sanity.io/pricing',                               'headless-cms', 'Composable content cloud with real-time collaboration'),
('Strapi',       'strapi',       'https://strapi.io',                                   'https://strapi.io/pricing',                                   'headless-cms', 'Open-source headless CMS for building APIs'),
('Contentful',   'contentful',   'https://www.contentful.com',                          'https://www.contentful.com/pricing',                          'headless-cms', 'Enterprise headless CMS with structured content modeling'),
('Hygraph',      'hygraph',      'https://hygraph.com',                                 'https://hygraph.com/pricing',                                 'headless-cms', 'GraphQL-native headless CMS formerly known as GraphCMS');

-- ── 7. BLOGGING-PLATFORM ──────────────────────────────────────
INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Ghost',        'ghost',        'https://ghost.org',                                   'https://ghost.org/pricing',                                   'blogging-platform', 'Open-source publishing platform for blogs and newsletters'),
('WordPress',    'wordpress',    'https://wordpress.com',                               'https://wordpress.com/pricing',                               'blogging-platform', 'The worlds most popular CMS for websites and blogs'),
('Substack',     'substack',     'https://substack.com',                                'https://substack.com',                                        'blogging-platform', 'Newsletter and subscription publishing platform for writers'),
('Hashnode',     'hashnode',     'https://hashnode.com',                                'https://hashnode.com/pricing',                                'blogging-platform', 'Developer-focused blogging platform with custom domains');

-- ── 8. BACKEND-AS-A-SERVICE ───────────────────────────────────
INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Supabase',     'supabase',     'https://supabase.com',                                'https://supabase.com/pricing',                                'backend-as-a-service', 'Open-source Firebase alternative with Postgres, auth, and storage'),
('Firebase',     'firebase',     'https://firebase.google.com',                         'https://firebase.google.com/pricing',                         'backend-as-a-service', 'Google mobile and web app platform with NoSQL and real-time sync'),
('Appwrite',     'appwrite',     'https://appwrite.io',                                 'https://appwrite.io/pricing',                                 'backend-as-a-service', 'Open-source BaaS with auth, database, storage, and functions'),
('AWS Amplify',  'aws-amplify',  'https://aws.amazon.com/amplify',                      'https://aws.amazon.com/amplify/pricing',                      'backend-as-a-service', 'AWS full-stack cloud platform for web and mobile apps');

-- ── 9. SERVERLESS-DATABASE ────────────────────────────────────
INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Neon',         'neon',         'https://neon.tech',                                   'https://neon.tech/pricing',                                   'serverless-database', 'Serverless Postgres with branching and scale-to-zero'),
('PlanetScale',  'planetscale',  'https://planetscale.com',                             'https://planetscale.com/pricing',                             'serverless-database', 'Serverless MySQL platform powered by Vitess'),
('Turso',        'turso',        'https://turso.tech',                                  'https://turso.tech/pricing',                                  'serverless-database', 'Edge-native SQLite database for globally distributed apps'),
('CockroachDB',  'cockroachdb',  'https://www.cockroachlabs.com',                       'https://www.cockroachlabs.com/pricing',                       'serverless-database', 'Distributed SQL database built for cloud-native resilience');

-- ── 10. DEPLOYMENT-PLATFORM ───────────────────────────────────
INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Vercel',       'vercel',       'https://vercel.com',                                  'https://vercel.com/pricing',                                  'deployment-platform', 'Frontend cloud platform for deploying web applications'),
('Netlify',      'netlify',      'https://www.netlify.com',                             'https://www.netlify.com/pricing',                             'deployment-platform', 'Web development platform for building and deploying sites'),
('Cloudflare Pages', 'cloudflare-pages', 'https://pages.cloudflare.com',               'https://www.cloudflare.com/plans',                            'deployment-platform', 'JAMstack deployment platform with edge computing'),
('Railway',      'railway',      'https://railway.com',                                 'https://railway.com/pricing',                                 'deployment-platform', 'Infrastructure platform for deploying full-stack applications');

-- ── 11. AI-CODING ─────────────────────────────────────────────
INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Cursor',       'cursor',       'https://www.cursor.com',                              'https://www.cursor.com/pricing',                              'ai-coding', 'AI-native code editor built as a fork of VS Code'),
('GitHub Copilot', 'github-copilot', 'https://github.com/features/copilot',            'https://github.com/features/copilot#pricing',                'ai-coding', 'AI pair programmer that suggests code in your IDE'),
('Windsurf',     'windsurf',     'https://windsurf.com',                                'https://windsurf.com/pricing',                                'ai-coding', 'AI-powered IDE with deep codebase understanding'),
('Replit',       'replit',       'https://replit.com',                                  'https://replit.com/pricing',                                  'ai-coding', 'Browser-based IDE with AI coding assistant and instant deployment');

-- ── 12. AI-APP-BUILDER (No-Code AI Dev Tools) ─────────────────
INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('v0',           'v0',           'https://v0.dev',                                      'https://v0.dev/pricing',                                      'ai-app-builder', 'AI-powered UI generation tool by Vercel for React components'),
('Lovable',      'lovable',      'https://lovable.dev',                                 'https://lovable.dev/pricing',                                 'ai-app-builder', 'AI-powered full-stack app builder from prompt to deployed product'),
('Bolt',         'bolt',         'https://bolt.new',                                    'https://bolt.new/pricing',                                    'ai-app-builder', 'Browser-based AI app builder with full-stack WebContainer IDE'),
('Create',       'create-xyz',   'https://www.create.xyz',                              'https://www.create.xyz/pricing',                              'ai-app-builder', 'AI tool for generating and deploying web apps from prompts'),
('Tempo',        'tempo',        'https://www.tempo.new',                               'https://www.tempo.new/pricing',                               'ai-app-builder', 'AI-powered React app builder with visual editor and code export');

-- ── 13. AI-CHAT ───────────────────────────────────────────────
INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('ChatGPT',      'chatgpt',      'https://chat.openai.com',                             'https://openai.com/chatgpt/pricing',                          'ai-chat', 'OpenAI conversational AI assistant for work and creativity'),
('Claude',       'claude',       'https://claude.ai',                                   'https://claude.ai/pricing',                                   'ai-chat', 'Anthropic AI assistant focused on safety and helpfulness'),
('Gemini',       'gemini',       'https://gemini.google.com',                           'https://ai.google.dev/pricing',                               'ai-chat', 'Google multimodal AI assistant integrated with Workspace'),
('Perplexity',   'perplexity',   'https://www.perplexity.ai',                           'https://www.perplexity.ai/pro',                               'ai-chat', 'AI-powered search engine with real-time cited answers');

-- ── 14. TEAM-CHAT ─────────────────────────────────────────────
INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Slack',        'slack',        'https://slack.com',                                   'https://slack.com/pricing',                                   'team-chat', 'Business messaging platform for team communication and workflows'),
('Microsoft Teams', 'microsoft-teams', 'https://www.microsoft.com/en-us/microsoft-teams', 'https://www.microsoft.com/en-us/microsoft-teams/compare-microsoft-teams-options', 'team-chat', 'Unified communication platform with chat, calls, and meetings'),
('Discord',      'discord',      'https://discord.com',                                 'https://discord.com/nitro',                                   'team-chat', 'Community and team chat platform with voice, video, and text'),
('Google Chat',  'google-chat',  'https://workspace.google.com',                        'https://workspace.google.com/pricing',                        'team-chat', 'Team messaging integrated with Google Workspace');

-- ── 15. VIDEO-CONFERENCING ────────────────────────────────────
INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Zoom',         'zoom',         'https://zoom.us',                                     'https://zoom.us/pricing',                                     'video-conferencing', 'Video conferencing and virtual meeting platform'),
('Google Meet',  'google-meet',  'https://meet.google.com',                             'https://workspace.google.com/pricing',                        'video-conferencing', 'Google video conferencing solution for teams'),
('Webex',        'webex',        'https://www.webex.com',                               'https://www.webex.com/pricing',                               'video-conferencing', 'Cisco enterprise video conferencing and collaboration platform'),
('Loom',         'loom',         'https://www.loom.com',                                'https://www.loom.com/pricing',                                'video-conferencing', 'Async video messaging platform for team communication');

-- ── 16. TRANSACTIONAL-EMAIL ───────────────────────────────────
INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Resend',       'resend',       'https://resend.com',                                  'https://resend.com/pricing',                                  'transactional-email', 'Modern email API for developers with React Email templates'),
('SendGrid',     'sendgrid',     'https://sendgrid.com',                                'https://sendgrid.com/pricing',                                'transactional-email', 'Cloud-based email delivery for transactional and marketing emails'),
('Postmark',     'postmark',     'https://postmarkapp.com',                             'https://postmarkapp.com/pricing',                             'transactional-email', 'Transactional email service with industry-leading deliverability'),
('Amazon SES',   'amazon-ses',   'https://aws.amazon.com/ses',                          'https://aws.amazon.com/ses/pricing',                          'transactional-email', 'AWS scalable low-cost email sending service');

-- ── 17. EMAIL-MARKETING ───────────────────────────────────────
INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Mailchimp',    'mailchimp',    'https://mailchimp.com',                               'https://mailchimp.com/pricing',                               'email-marketing', 'All-in-one marketing platform for email campaigns and automation'),
('ConvertKit',   'convertkit',   'https://convertkit.com',                              'https://convertkit.com/pricing',                              'email-marketing', 'Creator-focused email marketing with automation'),
('Beehiiv',      'beehiiv',      'https://www.beehiiv.com',                             'https://www.beehiiv.com/pricing',                             'email-marketing', 'Newsletter platform with growth tools and monetization'),
('Brevo',        'brevo',        'https://www.brevo.com',                               'https://www.brevo.com/pricing',                               'email-marketing', 'All-in-one marketing platform formerly known as Sendinblue');

-- ── 18. PRODUCT-ANALYTICS ─────────────────────────────────────
INSERT INTO tools (name, slug, website_url, pricing_url, category, description) VALUES
('Mixpanel',     'mixpanel',     'https://mixpanel.com',                                'https://mixpanel.com/pricing',                                'product-analytics', 'Product analytics for tracking user interactions and funnels'),
('Amplitude',    'amplitude',    'https://amplitude.com',                               'https://amplitude.com/pricing',                               'product-analytics', 'Digital analytics platform for product intelligence'),
('PostHog',      'posthog',      'https://posthog.com',                                 'https://posthog.com/pricing',                                 'product-analytics', 'Open-source product analytics with session replay and feature flags'),
('Heap',         'heap',         'https://www.heap.io',                                 'https://www.heap.io/pricing',                                 'product-analytics', 'Auto-capture product analytics for complete user journey tracking');


-- ============================================================
-- VERIFICATION QUERIES
-- ============================================================

-- Check total tools
SELECT COUNT(*) AS total_tools FROM tools;

-- Check tools per category
SELECT category, COUNT(*) AS tool_count
FROM tools
GROUP BY category
ORDER BY category;
