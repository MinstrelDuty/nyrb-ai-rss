# Public Books — Reviews acquisition test

Research date: 2026-09-15. Initial research used anonymous HTTPS requests
only. After explicit approval to reuse the existing TLS pattern, the branch
now also contains a **manual-test-only** collector that asks Jina Reader for
the Reviews index and article Markdown. It is not wired into `main.yml` or any
scheduled workflow.

## Result

**Status: manual cloud validation pending.**

Public Books exposes useful public discovery metadata, but direct access is
currently guarded. On the latest local retest, the RSS feed, Reviews feed and
sitemap all returned an `sgcaptcha` HTML response (HTTP 202), rather than
their public XML. This is why a normal feed-only collector is not sufficient.
The new collector deliberately follows TLS: direct RSS is preferred when it
is valid XML; otherwise Jina Reader renders the official Reviews page and
each resulting article. The collector rejects CAPTCHA, login/subscription,
preview, ellipsis-ended and too-short responses before writing raw Markdown.

## Public entry points

| Entry | Anonymous result | What it provides | Assessment |
| --- | --- | --- | --- |
| `/feed/` | HTTP 200 | Recent posts, title, link, date, author, categories, excerpt | Best current discovery feed; filter items whose category contains `Reviews` |
| `/category/reviews/feed/` | HTTP 200 | Review links and metadata | Stable format, but the current snapshot lagged behind the general feed (latest observed item: 2026-08-18) |
| `/sitemap_index.xml` → `post-sitemap*.xml` | HTTP 200 | Canonical URLs and `lastmod`; current `post-sitemap4.xml` held the newest 12 posts | Good URL discovery, but no section/category classification or body |
| `/category/reviews/` | 403 with default Requests; 200 only with generic UA | Current review listing and pagination | Not a stable cloud entry point |
| Article HTML | 403 with default Requests/Chrome; 200 only with generic UA | Complete-looking HTML and JSON-LD metadata when accessible | Not safe to automate under the no-bypass requirement |

The article JSON-LD is useful when the page is accessible: it contains
`headline`, `author`, `datePublished`, `articleSection: ["Reviews"]`,
`wordCount`, and `thumbnailUrl`. It does not contain `articleBody`, so it
cannot replace the guarded HTML body.

## Three recent sample comparison

Samples were selected from the current Reviews listing/general feed:

1. `Rachel Cusk’s Diminishing Returns` — 2026-09-14
2. `If on a Winter’s Night a Reader…` — 2026-09-10
3. `My Job Is to Fulfill Your Infantile Desire` — 2026-09-08

The local “accessible” probe used the generic `Mozilla/5.0` response only to
measure what is behind the gate. The Actions-like probe used the default
Python Requests identity (`python-requests/2.32.0`), with no special UA.

| Sample | Local status / body | Local first/last | Actions-like status / body | Metadata |
| --- | --- | --- | --- | --- |
| Rachel Cusk | 200 / 14,944 chars / 26 paragraphs | Starts with the review opening; ends with the commissioned-byline sentence | 403 / 0 chars | JSON-LD author Morgan Barry; published 2026-09-14; wordCount 2,499; image present |
| Winter’s Night | 200 / 19,017 chars / 30 paragraphs | Starts with the reading argument; ends with the final Calvino note and return markers | 403 / 0 chars | JSON-LD author Megan Cummins; published 2026-09-10; wordCount 3,123; image present |
| Infantile Desire | 200 / 13,848 chars / 23 paragraphs | Starts with the Hu Anyan discussion; ends with the collective-action conclusion | 403 / 0 chars | JSON-LD author Megan Cummins; published 2026-09-08; wordCount 2,284; image present |

For the three 200 responses, the `.entry-content` text length is consistent
with the JSON-LD word count (roughly 2,284–3,123 words), and the final
paragraphs are present rather than an ellipsis or “Continue reading” preview.
That completeness is real only for the UA-dependent 200 response; it is not a
deployable anonymous contract.

The same pattern was observed across the entry points: `/feed/` and the
sitemap are accessible without a special UA, while category/article HTML is
not. Chrome-like requests returned the site's 403 page (about 75 KB), and
default Requests article responses returned a short 403 body.

## Current implementation and decision gate

This branch now adds `publicbooks_rss.py` and the manual-only
`.github/workflows/publicbooks-test.yml`. They use the existing raw archive
format, canonical URL de-duplication and strict incomplete-body rejection.
They do not modify the six existing collectors, Work/Sheet/publishing/web
layers, or any cron workflow.

The local runtime cannot currently connect to `r.jina.ai` (TLS EOF), so it
cannot serve as a full-body validation environment. The workflow is the
decision gate: Public Books can be classified as **A** only if GitHub Actions
retrieves complete bodies for current Reviews samples and the collector writes
valid raw Markdown. If the same request fails or returns previews, the code
remains an unmerged experiment and the source remains **C**.
