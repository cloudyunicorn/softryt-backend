# SoftRYT Backend — Programmatic SEO & Affiliate Automation Engine

SoftRYT Backend is the core automation and orchestration engine for the SoftRYT programmatic SEO affiliate platform. Powered by FastAPI, it automates the pipeline of scraping SaaS tool data (pricing tiers, features, integrations) and generating high-ranking, fact-checked comparison pages, reviews, and blog posts in MDX format.

The system uses a multi-agent AI design powered by LangChain and LangGraph to write and fact-check generated contents against cached real-world specifications to ensure zero hallucination of product details or prices.

---

## 🚀 Key Features

### 1. Automated Web Scraper
* **Headless Playwright Crawler**: Automatically navigates SaaS pricing and feature pages to extract structured lists of features, price points, integrations, and limits.
* **Smart Fallback**: Seamlessly switches to ScrapingBee API if local anti-bot security (Cloudflare, etc.) blocks the headless browser.
* **Content Hashing**: Hashes scraped data to detect changes, only triggering AI regenerations if the product details or pricing actually changed.

### 2. Multi-Agent AI Generation Pipelines
* **Unbiased Comparisons (Tool A vs Tool B)**: Builds deep-dive comparisons highlighting differences, pricing matrices, pros/cons, and recommended use-cases.
* **Detailed Product Reviews**: Generates long-form review structures based on scraped product specifications.
* **Topical Blog Generation**: Compiles topical blog articles using search integrations (DuckDuckGo/BeautifulSoup) for live context search.
* **Autonomous Fact-Checking**: Employs a LangGraph fact-checking loop. The generated MDX is validated line-by-line against scraped source data. If any pricing, feature, or integration hallucination is found, it automatically restarts the writing loop with targeted rewrite instructions (up to `MAX_RETRIES` times).

### 3. Sync & Security
* **On-Demand ISR Revalidation**: Triggers cache busts on the Next.js frontend via an authenticated webhook (`REVALIDATION_SECRET`) immediately after new pages are generated.
* **API Key Protection**: Secures all write and trigger routes via custom header authentication (`X-API-Key`).
* **Supabase Integration**: Stores scraped structures, generated pages, run telemetry, and system audits directly into Supabase PostgreSQL.

---

## 🛠️ Tech Stack

* **Language**: Python 3.12+
* **Framework**: FastAPI (REST API)
* **Package Manager**: `uv` (Fast package resolver and installer)
* **Web Scraping**: Playwright, ScrapingBee, BeautifulSoup4, html2text
* **Orchestration / LLM**: LangChain, LangGraph, Pydantic Settings
* **AI Models Support**: OpenAI (GPT-4o-mini), DeepSeek (v3), Moonshot AI (Kimi K2.6), Llama 3.3 (via NVIDIA NIM/OpenRouter)
* **Database**: Supabase Python Client

---

## 📂 Project Structure

```
softryt-backend/
├── app/
│   ├── models/            # Pydantic validation schemas
│   ├── routers/           # FastAPI API routes (pages, tools, blog, pipeline)
│   ├── services/          # Core business logic (orchestrators, scraper, scheduler)
│   ├── auth.py            # API key authentication middleware
│   ├── config.py          # Centralized configuration (Pydantic Settings)
│   ├── database.py        # Supabase database client factory
│   └── main.py            # FastAPI application setup & CORS configuration
├── migrations/            # SQL migration scripts for Supabase schema
├── scripts/               # Developer test and seeding utilities
├── main.py                # Server entry point
├── pyproject.toml         # Python project configuration & dependencies
└── uv.lock                # Lockfile for reproducible builds
```

---

## 💻 Local Setup & Installation

### Prerequisites
* Python 3.12+ Installed
* `uv` Package Manager installed (highly recommended: [Install uv](https://github.com/astral-sh/uv))
* A Supabase project initialized

### 1. Clone & Install Dependencies
Navigate to the backend directory and run:
```bash
# Sync virtualenv and dependencies
uv sync

# Install Playwright browser engines
uv run playwright install chromium
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

Review the following fields:
```ini
# Supabase
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_KEY="your-supabase-service-role-or-write-key"

# LLM Providers
OPENAI_API_KEY="sk-proj-..."
NVIDIA_API_KEY="nvapi-..."  # Optional (if using Nvidia NIM endpoints)

# Security & Sync
API_KEY="your-custom-secure-api-key"
REVALIDATION_SECRET="shared-secret-with-frontend"
FRONTEND_URL="http://localhost:3000"

# Generation configuration
WRITER_MODEL="gpt-4o-mini"
FACT_CHECKER_MODEL="gpt-4o-mini"
```

### 3. Setup Database Schema
Execute the SQL scripts inside [migrations/](file:///D:/Dev/Portfolio%20Projects/softryt/softryt-backend/migrations) in your Supabase SQL Editor:
1. `001_create_tables.sql` - Establishes `tools`, `tool_features`, `generated_pages`, and `generation_logs` tables.
2. `002_enable_rls.sql` - Sets up Row-Level Security policies for public reads and authenticated backend writes.
3. `003_seed_viral_tools.sql` - Seeds initial SaaS tools catalog data.
4. `005_create_blog_posts.sql` - Creates the `blog_posts` table for programmatic articles.

### 4. Run the Server
Launch the FastAPI development server:
```bash
uv run python main.py
```
By default, the server runs on [http://localhost:8000](http://localhost:8000). The interactive API docs will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## 🔌 API Reference Summary

> [!IMPORTANT]
> All endpoints except `/health` and `/` require the `X-API-Key` header with the token configured in your `.env` file.

### Pipelines
* **`POST /api/v1/scrape`**: Triggers scraper for a specific tool.
  ```json
  { "tool_id": "UUID", "force": false }
  ```
* **`POST /api/v1/scrape/all`**: Triggers a background scraper run for all tools in the database.
* **`POST /api/v1/pages/generate/comparison`**: Triggers generating/regenerating a comparison page (A vs B).
* **`POST /api/v1/pages/generate/review`**: Triggers generating a review page for a single tool.
* **`POST /api/v1/blog/generate`**: Initiates a topical blog post generation using live search research.

### Tools & Pages Admin
* **`GET /api/v1/tools`**: Fetch all tracked tools.
* **`POST /api/v1/tools`**: Add a new tool to track.
* **`GET /api/v1/pages`**: View generated pages and their tracking metrics (clicks, views).
* **`POST /api/v1/pages/{id}/publish`**: Change a page state from `draft` to `published` (fires ISR revalidation).
