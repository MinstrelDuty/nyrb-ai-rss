# Sheet JSON Publishing Design

## Goal

Publish only reviewed-and-approved Sheet rows through a deterministic pipeline:
Google Sheet CSV -> canonical Markdown -> JSON and RSS -> GitHub Pages.

## Canonical archive

`scripts/import_sheet.py` requires the configured fourteen CSV columns. It
canonicalizes URLs, rejects invalid ISO-8601 `processed_at` values and invalid
keyword JSON, skips `review`, and accepts only `published`. For a URL occurring
more than once, it selects the greatest parsed `processed_at`. The canonical
file name is a stable URL-derived name beneath `data/articles/<source>/`; an
incoming accepted revision overwrites that exact file. Existing canonical files
with the same URL are also removed when their filename differs, preventing a
legacy collision from producing duplicate JSON/RSS records.

Canonical Markdown uses the existing dependency-free frontmatter helpers. The
frontmatter stores the Sheet data, including a JSON-array `keywords` value, and
the body is exactly `body_markdown`. `author_subject` is never persisted.

## Derived artifacts

`build_articles_json.py` reloads canonical Markdown, includes only published
records, deduplicates by canonical URL using newest `processed_at`, sorts by
article date descending, and emits compact structured article objects in
`data/articles.json`. `build_rss.py` uses the same record loader to create the
four existing RSS files. RSS descriptions retain `title_zh|||author_subject|||hook`
only for subscriber compatibility; content:encoded renders Markdown to HTML and
image URLs remain enclosures/media content.

## Web and workflow

The browser fetches one `data/articles.json` document and filters it by source.
It renders Markdown using the existing marked.js dependency, derives the author
and subject line at render time, and passes titles, metadata, keywords, and
plain body text to search. Exported Markdown remains generated in the browser.

`publish.yml` is manual-only. It reads `SHEET_CSV_URL` from a repository secret
or variable, runs import/build/test steps, stages only canonical/archive output,
and commits only when staged content differs. It neither modifies the raw
collector workflow nor introduces automatic scheduling.

## Error handling and tests

Malformed CSV headers, URLs, timestamps, keyword JSON, and unsupported status
values cause the importer to fail clearly; the only permitted statuses are
`review` and `published`. Tests exercise status gating, newest-revision wins,
round-trip canonical Markdown, JSON shape/order, RSS legacy compatibility,
keyword search, and unchanged raw ingestion tests.
