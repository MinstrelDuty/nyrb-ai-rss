# Source expansion 1 research

Research date: 2026-09-15. The checks below use anonymous HTTPS requests with a normal browser user-agent through the same network path available to GitHub Actions. No login, subscription cookie, CAPTCHA bypass, proxy scraping service, or paywall workaround was used.

## Summary

| Source | Stable discovery | Full text | Actions suitability | Decision |
| --- | --- | --- | --- | --- |
| The New Yorker — Under Review | Section HTML + Schema.org `ItemList` | Article Schema.org `NewsArticle.articleBody` | 200; `isAccessibleForFree=true` on tested article | **可自动抓取** |
| The Atlantic — Books | Official Atom feed `/feed/books/` | Atom `content` contains the full article HTML | 200; use the official feed only because article pages declare `isAccessibleForFree=false` | **可自动抓取**（仅官方 feed） |
| Public Books — Reviews | Category page, WordPress feed, sitemap candidates | Not testable from Actions-like anonymous requests | All tested endpoints returned 403 | **不适合云端自动抓取** |

## The New Yorker — Under Review

-栏目入口：<https://www.newyorker.com/books/under-review>
- RSS：The New Yorker publishes broad feeds, including <https://www.newyorker.com/feed/culture/rss>, but no feed limited to `Under Review` was found. The culture feed is therefore not used for discovery.
- Discovery: the section page is HTTP 200 and contains a Schema.org `ItemList`. Only URLs beginning with `/books/under-review/` are accepted; this excludes unrelated links that the page also exposes (for example, “Best Books” and Front Row links).
- Article metadata: article pages expose Schema.org `NewsArticle` JSON-LD with `headline`, `author`, `datePublished`, `image`, `articleSection`, `isAccessibleForFree`, and `articleBody`.
- Completeness: the tested article `Can You Write a Memoir in the Third Person?` returned HTTP 200, `isAccessibleForFree=true`, an `articleBody` of about 10k characters, and a normal closing paragraph. The crawler rejects missing/short bodies, non-free articles, subscribe/sign-in/continue-reading markers, and ellipsis-ended previews.
- Recommended mechanism: section JSON-LD for discovery, then article JSON-LD for metadata and body. This is more narrowly scoped and less fragile than the broad RSS feed.
- Implemented in this branch: `newyorker_rss.py`, with tests for scope filtering, JSON-LD parsing, completeness rejection, canonical URLs, and deduplication.

## The Atlantic — Books

-栏目入口：<https://www.theatlantic.com/books/>
- Official feed: <https://www.theatlantic.com/feed/books/> is an Atom feed and returned HTTP 200. It exposed 25 current entries in the research run, including title, author, publication/update time, canonical link, `media:content` image, and HTML `content`.
- Article page: the tested page returned HTTP 200 and rendered full text in this environment, but its JSON-LD explicitly declares `isAccessibleForFree=false`. The crawler does not use the article page and does not attempt to bypass that access state.
- Feed body: the official Atom `content` field contained complete HTML for tested book reviews (for example, 9.5k and 13.4k extracted text characters). Feed entries with very short bodies, subscription markers, `Continue reading`, or suspicious ellipsis endings are rejected.
- Scope: the feed is the Books channel, but it contains some recommendations, fiction, poetry, and newsletter items. The crawler accepts only long entries that are clearly in the Books channel and uses a conservative minimum body length; it skips short poetry/newsletter previews.
- Recommended mechanism: official Atom feed only. Do not fall back to direct article HTML.
- Implemented in this branch: `atlantic_books.py`, with tests for Atom discovery, metadata/image extraction, completeness rejection, canonical URLs, and deduplication.

## Public Books — Reviews

-栏目入口：<https://www.publicbooks.org/category/reviews/>
- Candidate feeds checked: `/feed/`, `/category/reviews/feed/`, and `/reviews/feed/`.
- Candidate sitemap checked: `/sitemap_index.xml`.
- Result: the endpoint behavior is user-agent dependent. A generic `Mozilla/5.0` request returned HTTP 200 for the category, Reviews RSS feed, and sitemap, and a sampled article exposed normal HTML with 27 article paragraphs. The normal Chrome-like user-agent used by the other collectors, Python Requests' default identity, and the project compatibility identity returned HTTP 403 (the same WAF block page) for those endpoints.
- This is an access-control/bot-protection signal, not a stable public contract. Making the collector work would require choosing a UA specifically to evade that policy, which is outside the allowed scope. Therefore the article body cannot be considered reliably available to an anonymous GitHub Actions runner, even though a browser-oriented probe sometimes succeeds.
- No crawler is implemented, and no workaround is attempted. Conclusion: **不适合云端自动抓取** until Public Books provides an Actions-accessible official feed/API or changes the access policy.

## GitHub Actions test workflow

`.github/workflows/source-expansion-test.yml` is manual-only (`workflow_dispatch`) and runs the verified New Yorker and Atlantic collectors. Public Books is intentionally not called. The existing `main.yml`, publish workflow, Work/Sheet schema, web code, RSS builder, and NYT collector are unchanged.
