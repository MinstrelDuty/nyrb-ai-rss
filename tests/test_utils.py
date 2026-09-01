import pytest

from scripts.utils import (
    article_filename,
    canonicalize_url,
    parse_frontmatter,
    render_frontmatter,
    stable_article_id,
)


def test_canonicalize_url_removes_tracking_and_fragment():
    assert canonicalize_url(
        "https://example.com/article/?utm_source=x&id=7#comments"
    ) == "https://example.com/article?id=7"


def test_canonicalize_url_keeps_meaningful_query_parameters():
    assert canonicalize_url("https://example.com/a/?page=2&fbclid=tracking") == (
        "https://example.com/a?page=2"
    )


def test_stable_id_is_source_prefixed_and_repeatable():
    first = stable_article_id("LRB", "https://example.com/a")
    assert first == stable_article_id("LRB", "https://example.com/a")
    assert first.startswith("lrb-")
    assert len(first) == len("lrb-") + 12


def test_article_filename_uses_url_slug_and_fallback_hash():
    assert article_filename("LRB", "2026-09-01", "https://example.com/a-title") == (
        "2026-09-01-a-title.md"
    )
    assert article_filename("LRB", "", "https://example.com/a-title") == (
        "lrb-" + stable_article_id("LRB", "https://example.com/a-title").split("-", 1)[1] + ".md"
    )


def test_frontmatter_round_trip_preserves_multiline_body_and_quotes():
    text = render_frontmatter(
        {"source": "NYRB", "title_zh": '含 "引号" 的中文标题'},
        "第一行\n第二行",
    )
    metadata, body = parse_frontmatter(text)
    assert metadata["source"] == "NYRB"
    assert metadata["title_zh"] == '含 "引号" 的中文标题'
    assert body == "第一行\n第二行\n"


def test_parse_frontmatter_rejects_unclosed_header():
    with pytest.raises(ValueError, match="frontmatter"):
        parse_frontmatter("---\nsource: NYRB\n正文")
