from pathlib import Path
from xml.etree import ElementTree as ET

from scripts.migrate_legacy_xml import (
    legacy_item_to_article,
    migrate_feeds,
)


FIXTURE = Path(__file__).parent / "fixtures" / "legacy_sample.xml"


def first_item():
    return ET.parse(FIXTURE).getroot().find("./channel/item")


def test_legacy_item_to_article_extracts_pipe_description_and_html():
    article = legacy_item_to_article(first_item(), "NYRB")

    assert article["title_zh"] == "中文标题"
    assert article["author_subject"] == "作者与对象"
    assert article["hook"] == "一句话"
    assert "核心脉络" in article["body_markdown"]
    assert article["image_url"] == "https://example.com/first.jpg"
    assert article["article_date"] == "2026-09-01"


def test_legacy_item_to_article_extracts_tagged_description():
    item = ET.parse(FIXTURE).getroot().find("./channel/item[2]")
    article = legacy_item_to_article(item, "NYRB")

    assert article["title_zh"] == "第二中文标题"
    assert article["author_subject"] == "作者乙与对象乙"
    assert article["hook"] == "第二句话"
    assert "第二段正文" in article["body_markdown"]


def test_migrate_feeds_is_idempotent_and_counts_duplicate_url(tmp_path):
    first = migrate_feeds({"NYRB": FIXTURE}, tmp_path / "articles")
    second = migrate_feeds({"NYRB": FIXTURE}, tmp_path / "articles")

    assert first["NYRB"].items_seen == 3
    assert first["NYRB"].created == 2
    assert first["NYRB"].duplicates == 1
    assert second["NYRB"].created == 0
    assert second["NYRB"].duplicates == 3
