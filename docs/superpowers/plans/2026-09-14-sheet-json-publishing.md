# Sheet JSON Publishing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create deterministic Sheet-to-canonical-Markdown publishing for the website and legacy RSS feeds.

**Architecture:** A Python publication module owns validation, canonical persistence and readback. Three small CLI scripts use that module to import CSV and derive JSON/RSS. The browser consumes JSON directly and keeps Markdown-to-HTML rendering client-side.

**Tech Stack:** Python standard library, Beautiful Soup/markdownify already in requirements, browser JavaScript, GitHub Actions, pytest, Node assert.

**Spec:** `docs/superpowers/specs/2026-09-14-sheet-json-publishing-design.md`

## Global Constraints

- Start from `feature/raw-article-ingestion` commit `fac1fe0eadb0d627f1f2301474a870296d54b897` on branch `feature/sheet-json-publishing`.
- Do not change raw crawlers or `.github/workflows/main.yml`.
- Publish exactly the four existing sources and only rows with `status: published`.
- Use `SHEET_CSV_URL`; no AI APIs, database, cron, new framework, or source expansion.

---

### Task 1: Canonical publication model and Sheet importer

**Files:**
- Create: `scripts/publishing.py`, `scripts/import_sheet.py`, `tests/test_publishing.py`
- Modify: `scripts/utils.py`

**Interfaces:**
- Produces `import_sheet(csv_url, articles_root) -> list[pathlib.Path]`, `load_articles(root) -> list[dict]`, and `render_article(record) -> str`.

- [ ] **Step 1: Write failing tests** for review exclusion, published persistence, keyword list decoding, newest same-URL revision selection, and frontmatter/body round-trip.
- [ ] **Step 2: Run** `pytest tests/test_publishing.py -q`; expected failure: publication module does not exist.
- [ ] **Step 3: Implement** CSV download/validation, stable URL-based paths, overwrite-on-revision and typed frontmatter parsing.
- [ ] **Step 4: Run** `pytest tests/test_publishing.py -q`; expected success.

### Task 2: JSON and legacy RSS builders

**Files:**
- Create: `scripts/build_articles_json.py`, `scripts/build_rss.py`
- Modify: `tests/test_publishing.py`

**Interfaces:**
- Consumes `load_articles(root)`.
- Produces `build_articles_json(root, output)` and `build_rss(root, output_root)`.

- [ ] **Step 1: Write failing tests** that build files from canonical Markdown and assert JSON fields/order plus legacy RSS `|||` description and HTML body.
- [ ] **Step 2: Run** `pytest tests/test_publishing.py -q`; expected failure: builder import missing.
- [ ] **Step 3: Implement** deterministic JSON/RSS serialization using only published canonical records.
- [ ] **Step 4: Run** `pytest tests/test_publishing.py -q`; expected success.

### Task 3: Browser JSON reader and keyword search

**Files:**
- Modify: `app.js`, `web-core.js`
- Create: `tests/web-core.test.js`

**Interfaces:**
- Browser receives article records with `original_title`, `body_markdown`, `keywords`, and structured author/subject fields.

- [ ] **Step 1: Write a failing Node assertion** that `searchArticles` finds an article through `keywords`.
- [ ] **Step 2: Run** `node --test tests/web-core.test.js`; expected failure: keywords are excluded.
- [ ] **Step 3: Implement** `data/articles.json` loading, source filtering, dynamic author/subject display, Markdown rendering, and direct Markdown export.
- [ ] **Step 4: Run** `node --test tests/web-core.test.js`; expected success.

### Task 4: Manual publishing workflow and end-to-end verification

**Files:**
- Create: `.github/workflows/publish.yml`
- Modify: `tests/test_raw_workflow.py`

**Interfaces:**
- Workflow reads `SHEET_CSV_URL`, stages publication output only, and does no empty commit.

- [ ] **Step 1: Write a failing test** that exercises generated builders against test inputs and asserts an idempotent second run.
- [ ] **Step 2: Run** `pytest -q`; expected failure until all implementation exists.
- [ ] **Step 3: Add workflow** with `workflow_dispatch`, Python setup, requirements, import/build/tests, and `git diff --cached --quiet` guard.
- [ ] **Step 4: Run** `pytest -q`, `node --test tests/web-core.test.js`, `python -m compileall .`, and `git diff --check`; expected success.
