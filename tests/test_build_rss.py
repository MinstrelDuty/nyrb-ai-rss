from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from scripts.build_rss import (
    FEEDS,
    build_feed,
    load_archived_articles,
    markdown_to_html,
    write_feeds,
)


def write_article(root, *, source, title_zh, url, status="published", processed_at):
    path = root / source.lower() / f"{title_zh}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"source: {source}\n"
        f"url: {url}\n"
        f"title_zh: {title_zh}\n"
        "original_title: Original title\n"
        "author_subject: 作者与对象\n"
        "hook: 一句话破题\n"
        f"processed_at: {processed_at}\n"
        f"status: {status}\n"
        "---\n\n"
        "### 核心脉络\n\n正文 <b>内容</b>\n",
        encoding="utf-8",
    )
    return path


def test_build_feed_filters_source_and_status_and_keeps_order(tmp_path):
    archive = tmp_path / "articles"
    write_article(
        archive,
        source="NYRB",
        title_zh="较新",
        url="https://example.com/nyrb/new",
        processed_at="2026-09-01T10:00:00+08:00",
    )
    write_article(
        archive,
        source="NYRB",
        title_zh="草稿",
        url="https://example.com/nyrb/draft",
        status="partial",
        processed_at="2026-09-01T11:00:00+08:00",
    )
    write_article(
        archive,
        source="LRB",
        title_zh="其他来源",
        url="https://example.com/lrb/other",
        processed_at="2026-09-01T12:00:00+08:00",
    )

    xml = build_feed("NYRB", load_archived_articles(archive), datetime.now(timezone.utc))
    root = ET.fromstring(xml)
    items = root.findall("./channel/item")

    assert [item.findtext("title") for item in items] == ["Original title"]
    assert items[0].findtext("description") == "较新|||作者与对象|||一句话破题"


def test_build_feed_preserves_compatibility_fields_and_cdata_content():
    article = {
        "source": "TLS",
        "url": "https://example.com/tls/body?a=1&b=2",
        "title_zh": "中文标题",
        "original_title": "Original & title",
        "author_subject": "作者与对象",
        "hook": "一句话",
        "body_markdown": "### 核心脉络\n\n含有 ]]> 和 <b>标签</b>",
        "processed_at": "2026-09-01T00:00:00+00:00",
        "status": "published",
        "image_url": "https://example.com/image.jpg?a=1&b=2",
    }

    xml = build_feed("TLS", [article], datetime.now(timezone.utc))
    root = ET.fromstring(xml)
    item = root.find("./channel/item")

    assert item.findtext("title") == "Original & title"
    assert item.findtext("link") == "https://example.com/tls/body?a=1&b=2"
    assert item.findtext("description") == "中文标题|||作者与对象|||一句话"
    assert "content:encoded" in xml
    assert "<![CDATA[" in xml
    assert "]]><" not in xml.replace("]]><![CDATA[", "")
    assert ET.tostring(root, encoding="unicode")


def test_markdown_to_html_adds_escaped_image_url():
    rendered = markdown_to_html("正文", "https://example.com/image.jpg?a=1&b=2")
    assert rendered.startswith('<img src="https://example.com/image.jpg?a=1&amp;b=2"')
    assert "<p>正文</p>" in rendered


def test_write_feeds_does_not_replace_outputs_when_a_feed_fails(tmp_path, monkeypatch):
    output = tmp_path / "site"
    output.mkdir()
    old = output / "nyrb_ai_enhanced.xml"
    old.write_text("old", encoding="utf-8")

    def fail(*args, **kwargs):
        raise ValueError("bad feed")

    monkeypatch.setattr("scripts.build_rss.build_feed", fail)
    with pytest.raises(ValueError, match="bad feed"):
        write_feeds(tmp_path / "articles", output)
    assert old.read_text(encoding="utf-8") == "old"


def test_feed_mapping_contains_all_eight_sources():
    assert set(FEEDS) == {
        "NYRB",
        "LRB",
        "TLS",
        "NYT",
        "NEWYORKER",
        "ATLANTIC",
        "LARB",
        "PUBLICBOOKS",
    }
