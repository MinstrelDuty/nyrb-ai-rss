# Obsidian Export and Full-Text Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add current/all-source full-text search, issue Markdown downloads, and current/all-source Obsidian ZIP archives.

**Architecture:** Keep the site build-free. Put deterministic search and Markdown helpers in `web-core.js`, DOM/XML/download orchestration in `app.js`, and markup/styles plus pinned CDN dependencies in `index.html`. Normalize every feed item once and share the cached article model between rendering, searching, and exporting.

**Tech Stack:** Vanilla JavaScript, Node built-in test runner, Turndown 7.2.0, JSZip 3.10.1, Marked, GitHub Pages.

---

## Files

- Create `web-core.js`: pure filename, YAML, search, and Markdown functions; UMD export for browser and Node.
- Create `tests/web-core.test.js`: behavior tests run with `node --test`.
- Create `app.js`: source cache, XML normalization, rendering, search, and downloads.
- Modify `index.html`: controls, responsive styles, pinned scripts, and app entrypoint.

### Task 1: Test and implement search utilities

- [ ] Create `tests/web-core.test.js` with fixtures for NYRB and LRB articles.
- [ ] Add failing assertions that Chinese正文、English title（case-insensitive）and author fields match; an empty query returns all articles.
- [ ] Add a failing assertion that `sanitizeFilename('A:B/C*D?E', 10)` returns `A-B-C-D-E`.
- [ ] Run `node --test tests/web-core.test.js`; expect failure because `web-core.js` is missing.
- [ ] Create `web-core.js` with UMD exports, `normalizeText`, `searchArticles`, and `sanitizeFilename`.
- [ ] Run `node --test tests/web-core.test.js`; expect all search/filename tests to pass.
- [ ] Commit with `git commit -m "feat: add testable article search core"`.

Required API:

```js
searchArticles(articles, query) // checks titleZh, titleEn, metaInfo, hook, contentText
sanitizeFilename(value, maxLength = 80) // replaces Windows-invalid/control chars
```

### Task 2: Test and implement Obsidian Markdown

- [ ] Add failing tests for `yamlString`, `buildArticleMarkdown`, and `buildIssueMarkdown`.
- [ ] Assert frontmatter contains quoted `title`, `original_title`, `source`, `published`, `original_url`, and YAML list tags `书评` plus source ID.
- [ ] Assert an article note contains Chinese heading, metadata, body Markdown, and original link.
- [ ] Assert issue Markdown contains the publication/date heading and numbered article sections without repeated frontmatter.
- [ ] Run tests; expect the three helpers to be undefined.
- [ ] Implement the helpers and export them from `web-core.js`.
- [ ] Run tests; expect all tests to pass.
- [ ] Commit with `git commit -m "feat: generate Obsidian-ready markdown"`.

Required call shape:

```js
buildArticleMarkdown(article, bodyMarkdown)
buildIssueMarkdown(sourceName, isoDate, [{ ...article, bodyMarkdown }])
```

### Task 3: Normalize feeds and add search UI

- [ ] Modify `index.html` to add a search input, `当前刊物/全部四刊` scope switch, result count, current archive button, and all archive button.
- [ ] Pin CDN scripts to Turndown 7.2.0, Marked 15.0.12, and JSZip 3.10.1; load `web-core.js` then `app.js`.
- [ ] Create `app.js` with `SOURCES` entries for NYRB/LRB/TLS/NYT and a `feedCache` Map.
- [ ] Implement `loadSource(source)` so each XML is fetched once and normalized to `{sourceId, sourceName, titleZh, titleEn, metaInfo, hook, contentHtml, contentText, link, publishedAt, publishedDate}`.
- [ ] Implement `loadAllSources()` with `Promise.allSettled`, returning successful articles plus named errors.
- [ ] Move existing rendering into `renderIssueGroups`; preserve tabs, expansion, content, and original links.
- [ ] Implement 180 ms debounced search. Current scope searches the active cache; all scope loads/caches four feeds. Non-empty queries render flat cards with source/date badges and escaped snippets; clearing restores issue groups.
- [ ] Change issue buttons from HTML to `.md` labels and stable ISO-date attributes.
- [ ] Add responsive styles so controls wrap below 640 px without horizontal scrolling.
- [ ] Run `node --check app.js` and `node --test tests/web-core.test.js`; expect clean success.
- [ ] Commit with `git commit -m "feat: add current and cross-publication search"`.

### Task 4: Add Markdown and ZIP downloads

- [ ] In `app.js`, initialize one Turndown service using ATX headings and fenced code blocks.
- [ ] Implement `downloadBlob` with UTF-8 BOM for standalone `.md` and timely Blob URL revocation.
- [ ] Implement delegated issue download: select current-source articles by ISO date, convert HTML to Markdown, call `buildIssueMarkdown`, and download a sanitized `.md` filename.
- [ ] Implement `withBusyButton` so download buttons disable, show `正在整理…`, and restore in `finally`.
- [ ] Implement `buildArchive(sourceResults)`: create `书评深度集萃/{SOURCE}/{YYYY-MM-DD}/{NN}-{title}.md`, one article per note.
- [ ] Add ZIP-root `README.md` with generation time, per-source counts, total count, and any partial-load errors.
- [ ] Wire current archive to the active source and all archive to `loadAllSources`. If all sources fail, show an error and do not download.
- [ ] Name files `书评深度集萃-{SOURCE}-归档-YYYY-MM-DD.zip` and `书评深度集萃-全部归档-YYYY-MM-DD.zip`.
- [ ] Run syntax and unit tests; expect success.
- [ ] Commit with `git commit -m "feat: export issue and archive markdown"`.

### Task 5: Browser and archive verification

- [ ] Start `python -m http.server 8765 --bind 127.0.0.1` in the worktree.
- [ ] In the in-app Browser verify URL/title, meaningful DOM, no overlay, clean relevant console, and desktop screenshot.
- [ ] Search current publication, verify count and current-only source badges; clear and confirm grouped issues return.
- [ ] Search all publications, verify multi-source badges, descending dates, and an explicit no-results state.
- [ ] Trigger issue Markdown, current ZIP, and all ZIP downloads. Inspect files outside the repository for folder structure, note count, YAML, README, and source links.
- [ ] Repeat layout checks at a mobile viewport; verify search, scope, archive buttons, tabs, and cards wrap without clipping.
- [ ] Run `node --test tests/web-core.test.js`, `node --check web-core.js`, and `node --check app.js`; expect all clean.
- [ ] Commit any QA-only corrections with `git commit -m "fix: polish archive and search interactions"`.

## Acceptance mapping

- Current/all search: Task 3 and Task 5.
- Per-issue Markdown: Task 4 and Task 5.
- Current/all ZIP archives: Task 4 and Task 5.
- Obsidian YAML and one-note-per-article layout: Task 2, Task 4, and Task 5.
- Partial feed failure, busy states, pinned dependencies, and mobile layout: Task 3 through Task 5.
