import pytest

import lrb_rss
import nyrb_rss
import tls_rss


LONG_FIRST = "The first paragraph contains the opening argument and concrete evidence. " * 2
LONG_LAST = "The final paragraph closes the essay without unrelated site furniture. " * 2


def test_nyrb_html_parser_extracts_metadata_and_excludes_page_furniture():
    html = f"""
    <html><head>
      <meta property="og:title" content="Wishing It So | Jenny Turner" />
      <meta name="author" content="Jenny Turner" />
      <meta property="og:image" content="https://example.com/nyrb.jpg" />
    </head><body><main><article><h1>Wishing It So</h1>
      <div class="article-main-content"><p>{LONG_FIRST}</p><blockquote>A necessary quotation.</blockquote><p>{LONG_LAST}</p></div>
      <aside><p>Subscribe to our newsletter and related articles.</p></aside>
      <footer><p>Copyright and privacy policy.</p></footer>
    </article></main></body></html>
    """

    article = nyrb_rss.parse_article_html(html, "https://www.nybooks.com/articles/2026/09/24/wishing-it-so/")

    assert article["title"] == "Wishing It So"
    assert article["author"] == "Jenny Turner"
    assert article["article_date"] == "2026-09-24"
    assert article["image_url"] == "https://example.com/nyrb.jpg"
    assert LONG_FIRST.strip() in article["text"]
    assert "A necessary quotation." in article["text"]
    assert article["text"].rstrip().endswith(LONG_LAST.strip())
    assert "Subscribe" not in article["text"]
    assert article["paragraph_count"] == 3


def test_lrb_html_parser_keeps_poetry_lines_and_excludes_footer():
    html = f"""
    <html><head>
      <meta property="og:title" content="Colin Burrow — Good Weird or Bad Weird: Uses of Criticism" />
      <meta name="author" content="Colin Burrow" />
      <meta property="article:published_time" content="2026-09-10" />
    </head><body><article><h1>Good Weird or Bad Weird</h1>
      <div class="article-body"><p>{LONG_FIRST}</p><pre>Line one\nLine two</pre><p>{LONG_LAST}</p></div>
      <footer><p>LRB subscriptions and cookie settings.</p></footer>
    </article></body></html>
    """

    article = lrb_rss.parse_article_html(html, "https://www.lrb.co.uk/the-paper/v48/n18/colin-burrow/good-weird-or-bad-weird")

    assert article["title"] == "Good Weird or Bad Weird"
    assert article["author"] == "Colin Burrow"
    assert article["article_date"] == "2026-09-10"
    assert "Line one\nLine two" in article["text"]
    assert article["text"].rstrip().endswith(LONG_LAST.strip())
    assert "cookie settings" not in article["text"]
    assert article["paragraph_count"] == 3


@pytest.mark.parametrize("crawler", [nyrb_rss, lrb_rss])
def test_html_parser_removes_nested_subscription_furniture_without_crashing(crawler):
    html = f"""
    <html><head><meta property="og:title" content="Nested Furniture" /></head>
    <body><article>
      <p>{LONG_FIRST}</p>
      <div class="subscription-promo"><p>Subscribe now.</p></div>
      <p>{LONG_LAST}</p>
    </article></body></html>
    """

    article = crawler.parse_article_html(html, "https://example.com/article")

    assert "Subscribe now" not in article["text"]
    assert article["text"].rstrip().endswith(LONG_LAST.strip())


def test_tls_jina_parser_preserves_markdown_body_and_metadata():
    text = f"""Title: On not sitting down in the National Gallery
URL Source: https://www.the-tls.com/arts/visual-arts/on-not-sitting-down
Published Time: Thu, 10 Sep 2026 08:00:00 GMT
Markdown Content:
# On not sitting down in the National Gallery

By Laura Freeman

{LONG_FIRST}

> A quoted observation.

{LONG_LAST}
"""

    article = tls_rss.parse_jina_article(text, "https://www.the-tls.com/arts/visual-arts/on-not-sitting-down")

    assert article["title"] == "On not sitting down in the National Gallery"
    assert article["author"] == "Laura Freeman"
    assert article["article_date"] == "2026-09-10"
    assert article["text"].startswith("# On not sitting down")
    assert "> A quoted observation." in article["text"]
    assert "URL Source:" not in article["text"]
    assert article["paragraph_count"] == 4


def test_tls_jina_parser_rejects_a_short_paywall_response():
    text = "Title: Locked\nMarkdown Content:\nSubscribe or Log in to continue reading."

    assert tls_rss.parse_jina_article(text, "https://www.the-tls.com/locked") is None


def test_tls_jina_parser_rejects_a_long_preview_ending_in_ellipsis():
    text = f"""Title: Discussing ancient DNA
URL Source: https://www.the-tls.com/regular-features/mary-beard-a-dons-life/discussing-ancient-dna-blog-post
Markdown Content:
{LONG_FIRST}

Part of the problem, of course, is that we probably put too much emphasis on individual high-profile cases, rather than more general patterns.…
"""

    assert tls_rss.parse_jina_article(
        text,
        "https://www.the-tls.com/regular-features/mary-beard-a-dons-life/discussing-ancient-dna-blog-post",
    ) is None


def test_tls_jina_parser_accepts_complete_body_after_stripping_tls_footer():
    text = f"""Title: Jamaican Forget-Me-Not
URL Source: https://www.the-tls.com/literature/original-poems-literature/jamaican-forget-me-not-hannah-lowe
Markdown Content:
# Jamaican Forget-Me-Not

{LONG_FIRST}

The poem closes with a deliberate image and a period.

[Terms & Conditions](https://www.the-tls.com/terms-conditions)

Copyright © The Times Literary Supplement Limited 2026.

![Image 3](https://pixel.wp.com/g.gif?v=ext)
"""

    article = tls_rss.parse_jina_article(
        text,
        "https://www.the-tls.com/literature/original-poems-literature/jamaican-forget-me-not-hannah-lowe",
    )

    assert article is not None
    assert article["text"].rstrip().endswith("period.")
    assert "Terms & Conditions" not in article["text"]
    assert "Copyright" not in article["text"]


def test_tls_jina_parser_drops_navigation_when_reader_omits_content_marker():
    text = f"""Title: Discussing ancient DNA
URL Source: https://www.the-tls.com/regular-features/mary-beard-a-dons-life/discussing-ancient-dna-blog-post
[](https://www.the-tls.com/)

[Current Issue](https://www.the-tls.com/issues/current-issue)

# Discussing ancient DNA

{LONG_FIRST}

{LONG_LAST}
"""

    article = tls_rss.parse_jina_article(text, "https://www.the-tls.com/regular-features/mary-beard-a-dons-life/discussing-ancient-dna-blog-post")

    assert article["text"].startswith("# Discussing ancient DNA")
    assert "Current Issue" not in article["text"]
