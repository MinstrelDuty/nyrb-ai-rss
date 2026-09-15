import json
from pathlib import Path

import atlantic_books
import newyorker_rss
import publicbooks_rss
from scripts.raw_utils import save_raw_article
from scripts.utils import parse_frontmatter


def _long_text(prefix: str = "A complete paragraph") -> str:
    return (prefix + " carries concrete evidence and a sustained argument. ") * 30


def test_newyorker_section_is_strictly_scoped_and_deduplicated():
    html = """
    <script type="application/ld+json">
      {"@type":"ItemList","itemListElement":[
        {"@type":"ListItem","position":1,"url":"https://www.newyorker.com/books/under-review/book-review"},
        {"@type":"ListItem","position":2,"url":"https://www.newyorker.com/best-books-2026"},
        {"@type":"ListItem","position":3,"url":"https://www.newyorker.com/books/under-review/book-review"}
      ]}
    </script>
    """
    assert newyorker_rss.parse_section_urls(
        html, {"https://www.newyorker.com/books/under-review/already"}
    ) == ["https://www.newyorker.com/books/under-review/book-review"]


def test_newyorker_article_jsonld_extracts_metadata_and_rejects_locked_or_truncated():
    body = _long_text()
    html = f"""
    <script type="application/ld+json">{{
      "@type":"NewsArticle", "headline":"A Review", "articleSection":"Under Review",
      "author":[{{"name":"Example Author"}}], "datePublished":"2026-09-10T10:00:00-04:00",
      "image":["https://example.com/cover.jpg"], "isAccessibleForFree":true,
      "articleBody":{json.dumps(body)}
    }}</script>
    """
    article = newyorker_rss.parse_article_html(
        html, "https://www.newyorker.com/books/under-review/a-review?utm_source=test"
    )
    assert article is not None
    assert article["title"] == "A Review"
    assert article["author"] == "Example Author"
    assert article["article_date"] == "2026-09-10"
    assert article["url"] == "https://www.newyorker.com/books/under-review/a-review"
    assert article["image_url"] == "https://example.com/cover.jpg"

    locked = html.replace('"isAccessibleForFree":true', '"isAccessibleForFree":false')
    assert newyorker_rss.parse_article_html(locked, "https://www.newyorker.com/books/under-review/a-review") is None
    truncated = html.replace(body, body + "…")
    assert newyorker_rss.parse_article_html(truncated, "https://www.newyorker.com/books/under-review/a-review") is None


def test_atlantic_atom_feed_extracts_complete_books_entry_and_skips_short_other_channel():
    body = _long_text("The review")
    escaped = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    xml = f"""<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
      <entry>
        <title>Book Review</title><author><name>Atlantic Writer</name></author>
        <published>2026-09-11T12:00:00Z</published>
        <link rel="alternate" href="https://www.theatlantic.com/books/book-review/?utm_source=feed"/>
        <media:content url="https://example.com/atlantic.jpg"/>
        <content type="html">&lt;p&gt;{escaped}&lt;/p&gt;</content>
      </entry>
      <entry>
        <title>Newsletter</title><link rel="alternate" href="https://www.theatlantic.com/newsletters/short/"/>
        <content type="html">&lt;p&gt;Too short&lt;/p&gt;</content>
      </entry>
    </feed>"""
    entries = atlantic_books.parse_feed_entries(xml, set())
    assert len(entries) == 1
    article = entries[0]
    assert article["url"] == "https://www.theatlantic.com/books/book-review"
    assert article["author"] == "Atlantic Writer"
    assert article["article_date"] == "2026-09-11"
    assert article["image_url"] == "https://example.com/atlantic.jpg"
    assert "The review" in article["text"]


def test_atlantic_feed_rejects_preview_markers_and_ellipsis():
    body = _long_text("A preview") + " Continue reading"
    escaped = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    xml = f"""<feed xmlns="http://www.w3.org/2005/Atom"><entry>
      <title>Preview</title><link rel="alternate" href="https://www.theatlantic.com/books/preview/"/>
      <content type="html">&lt;p&gt;{escaped}&lt;/p&gt;</content>
    </entry></feed>"""
    assert atlantic_books.parse_feed_entries(xml, set()) == []


def test_new_sources_use_raw_paths_and_cross_run_canonical_dedup(tmp_path: Path):
    article = {
        "source": "NEWYORKER",
        "title": "Under Review",
        "author": "Author",
        "url": "https://www.newyorker.com/books/under-review/review?utm_medium=email",
        "article_date": "2026-09-10",
        "image_url": "",
        "text": _long_text(),
    }
    first = save_raw_article(article, tmp_path / "raw", captured_at="2026-09-12T00:00:00Z")
    second = save_raw_article(
        {**article, "url": article["url"].replace("?utm_medium=email", "#comments")},
        tmp_path / "raw",
        captured_at="2026-09-12T00:01:00Z",
    )
    assert first is not None
    assert first.parent.name == "newyorker"
    assert second is None
    metadata, body = parse_frontmatter(first.read_text(encoding="utf-8"))
    assert metadata["source"] == "NEWYORKER"
    assert metadata["status"] == "raw"
    assert body.startswith("# 正文\n\n")


def test_publicbooks_feed_discovers_only_new_reviews_and_canonicalizes_urls():
    xml = """<?xml version="1.0"?>
    <rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>
      <item><title>Review</title><link>https://www.publicbooks.org/review/?utm_source=feed</link>
        <dc:creator>Reviewer</dc:creator><pubDate>Sun, 14 Sep 2026 15:00:00 +0000</pubDate>
        <category>Reviews</category></item>
      <item><title>Essay</title><link>https://www.publicbooks.org/essay/</link>
        <category>Essays</category></item>
      <item><title>Already saved</title><link>https://www.publicbooks.org/already/</link>
        <category>Reviews</category></item>
    </channel></rss>"""

    entries = publicbooks_rss.parse_review_feed(
        xml, {"https://www.publicbooks.org/already/"}
    )

    assert entries == [{
        "title": "Review",
        "author": "Reviewer",
        "url": "https://www.publicbooks.org/review",
        "article_date": "2026-09-14",
        "image_url": "",
    }]


def test_publicbooks_retries_captcha_response_before_falling_back_to_jina(monkeypatch):
    xml = """<rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><item>
      <title>Recovered Review</title><link>https://www.publicbooks.org/recovered/</link>
      <dc:creator>Reviewer</dc:creator><pubDate>Sun, 14 Sep 2026 15:00:00 +0000</pubDate>
      <category>Reviews</category>
    </item></channel></rss>"""
    calls = []

    class Response:
        def __init__(self, status_code, text, content_type):
            self.status_code = status_code
            self.text = text
            self.headers = {"content-type": content_type}

        def raise_for_status(self):
            return None

    def fake_get(url, **_kwargs):
        calls.append(url)
        if len(calls) == 1:
            return Response(202, "<html>sgcaptcha</html>", "text/html")
        return Response(200, xml, "application/rss+xml")

    monkeypatch.setattr(publicbooks_rss.requests, "get", fake_get)
    monkeypatch.setattr(publicbooks_rss.time, "sleep", lambda _seconds: None)

    articles = publicbooks_rss.get_latest_reviews(set())

    assert [article["url"] for article in articles] == ["https://www.publicbooks.org/recovered"]
    assert calls == [publicbooks_rss.FEED_URL, publicbooks_rss.FEED_URL]


def test_publicbooks_skips_run_when_rss_remains_captcha_blocked(monkeypatch):
    calls = []

    class Response:
        status_code = 202
        text = "<html>sgcaptcha</html>"
        headers = {"content-type": "text/html"}

    def fake_get(url, **_kwargs):
        calls.append(url)
        return Response()

    monkeypatch.setattr(publicbooks_rss.requests, "get", fake_get)
    monkeypatch.setattr(publicbooks_rss.time, "sleep", lambda _seconds: None)

    assert publicbooks_rss.get_latest_reviews(set()) == []
    assert calls == [publicbooks_rss.FEED_URL] * publicbooks_rss.FEED_ATTEMPTS


def test_publicbooks_jina_parser_extracts_complete_review_and_rejects_captcha_or_preview():
    body = _long_text("The review argues")
    text = f"""Title: A Public Books Review
URL Source: https://www.publicbooks.org/a-review/
Published Time: 2026-09-14T15:00:00+00:00
Author: Reviewer Name
Markdown Content:
# A Public Books Review

![Cover](https://example.com/cover.jpg)

{body}

The review ends with a complete sentence.
"""

    article = publicbooks_rss.parse_jina_article(
        text, "https://www.publicbooks.org/a-review/?utm_source=feed"
    )

    assert article is not None
    assert article["source"] == "PUBLICBOOKS"
    assert article["title"] == "A Public Books Review"
    assert article["author"] == "Reviewer Name"
    assert article["url"] == "https://www.publicbooks.org/a-review"
    assert article["article_date"] == "2026-09-14"
    assert article["image_url"] == "https://example.com/cover.jpg"
    assert article["text"].rstrip().endswith("complete sentence.")

    assert publicbooks_rss.parse_jina_article(
        "Title: Blocked\nMarkdown Content:\nsgcaptcha: verify you are human",
        "https://www.publicbooks.org/blocked/",
    ) is None
    assert publicbooks_rss.parse_jina_article(
        text.replace("The review ends with a complete sentence.", "Continue reading…"),
        "https://www.publicbooks.org/a-review/",
    ) is None
