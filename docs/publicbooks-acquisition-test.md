# Public Books — Reviews acquisition test

Research date: 2026-09-15. This test used anonymous HTTPS requests only. No
login, subscription cookie, paywall workaround, CAPTCHA, proxy scraping
service, or access-control bypass was used.

## Result

**Classification: C — local and cloud acquisition are not stable enough to
implement.**

Public Books exposes useful public discovery metadata, but its full article
HTML is guarded by user-agent-sensitive access control. A normal Python
Requests identity (the natural implementation and an Actions-like probe) and
a normal Chrome identity receive HTTP 403 for the category and article pages.
A generic `Mozilla/5.0` identity happens to receive HTTP 200, but relying on
that difference would be selecting a user-agent to evade the site's bot
policy, which is explicitly out of scope.

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

## Decision

No `publicbooks_rss.py`, local crawler, raw files, workflow, or production
configuration was added. The RSS and sitemap endpoints are worth keeping as
future discovery references, but they do not provide complete正文, and using a
UA selected to get around the article-page block would violate the acquisition
constraints.

Public Books should be reconsidered only if it publishes a stable full-content
feed/API or changes the access policy so that an ordinary GitHub Actions
Requests client can retrieve article HTML without special handling.
