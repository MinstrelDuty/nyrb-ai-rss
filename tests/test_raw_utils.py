from pathlib import Path

from scripts.raw_utils import (
    get_existing_urls,
    save_raw_article,
)
from scripts.utils import parse_frontmatter, render_frontmatter


def _article(url: str, title: str = "A Difficult / Title") -> dict[str, str]:
    return {
        "source": "LRB",
        "title": title,
        "author": "Example Author",
        "url": url,
        "article_date": "2026-09-10",
        "image_url": "https://example.com/image.jpg",
        "text": ("First paragraph with enough real article text to be accepted. " * 2)
        + "\n\n"
        + ("Last paragraph remains part of the article body. " * 2),
    }


def test_existing_urls_unions_canonical_raw_and_legacy_urls(tmp_path: Path):
    raw_root = tmp_path / "raw"
    raw_file = raw_root / "lrb" / "existing.md"
    raw_file.parent.mkdir(parents=True)
    raw_file.write_text(
        render_frontmatter(
            {"url": "https://example.com/raw/?utm_source=newsletter#comments"},
            "body",
        ),
        encoding="utf-8",
    )
    xml_file = tmp_path / "lrb.xml"
    xml_file.write_text(
        "<?xml version=\"1.0\"?><rss><channel><item>"
        "<link>https://example.com/legacy/</link>"
        "</item></channel></rss>",
        encoding="utf-8",
    )

    assert get_existing_urls(raw_root, xml_file) == {
        "https://example.com/raw",
        "https://example.com/legacy",
    }


def test_save_raw_article_writes_required_frontmatter_and_clean_filename(tmp_path: Path):
    raw_root = tmp_path / "raw"
    target = save_raw_article(
        _article("https://www.lrb.co.uk/the-paper/v48/n18/example/a-difficult-title"),
        raw_root,
        captured_at="2026-09-12T04:34:56Z",
    )

    assert target == raw_root / "lrb" / "2026-09-10-a-difficult-title.md"
    metadata, body = parse_frontmatter(target.read_text(encoding="utf-8"))
    assert metadata == {
        "source": "LRB",
        "title": "A Difficult / Title",
        "author": "Example Author",
        "url": "https://www.lrb.co.uk/the-paper/v48/n18/example/a-difficult-title",
        "article_date": "2026-09-10",
        "captured_at": "2026-09-12T04:34:56Z",
        "image_url": "https://example.com/image.jpg",
        "status": "raw",
    }
    assert body.startswith("# 正文\n\nFirst paragraph")
    assert body.rstrip().endswith("article body.")


def test_save_raw_article_skips_a_url_already_present_in_any_raw_source(tmp_path: Path):
    raw_root = tmp_path / "raw"
    article = _article("https://example.com/same/?utm_medium=email")
    first = save_raw_article(article, raw_root, captured_at="2026-09-12T00:00:00Z")
    duplicate = _article("https://example.com/same#fragment", title="Renamed")

    second = save_raw_article(
        duplicate,
        raw_root,
        captured_at="2026-09-12T01:00:00Z",
    )

    assert first is not None
    assert second is None
    assert len(list(raw_root.rglob("*.md"))) == 1


def test_save_raw_article_never_overwrites_a_same_day_same_title_collision(tmp_path: Path):
    raw_root = tmp_path / "raw"
    first = save_raw_article(
        _article("https://example.com/one", title="Same Title"),
        raw_root,
        captured_at="2026-09-12T00:00:00Z",
    )
    second = save_raw_article(
        _article("https://example.com/two", title="Same Title"),
        raw_root,
        captured_at="2026-09-12T00:01:00Z",
    )

    assert first.name == "2026-09-10-same-title.md"
    assert second != first
    assert second.stem.startswith("2026-09-10-same-title-")
    assert first.read_text(encoding="utf-8") != second.read_text(encoding="utf-8")


def test_save_raw_article_rejects_body_under_minimum_without_creating_a_file(tmp_path: Path):
    raw_root = tmp_path / "raw"
    article = _article("https://example.com/too-short")
    article["text"] = "Too short"

    assert save_raw_article(article, raw_root) is None
    assert not list(raw_root.rglob("*.md"))
