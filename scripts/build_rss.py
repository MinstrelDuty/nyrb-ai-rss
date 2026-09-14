"""Build legacy-compatible RSS feeds from canonical article Markdown."""

from __future__ import annotations

import argparse
import html
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

import markdown
from bs4 import BeautifulSoup

try:
    from scripts.publishing import SUPPORTED_SOURCES, load_articles
except ModuleNotFoundError:  # Supports direct script execution from the repository root.
    from publishing import SUPPORTED_SOURCES, load_articles


CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
ET.register_namespace("content", CONTENT_NS)


def author_subject(article: dict[str, Any]) -> str:
    return f"✍️ 作者：{article['author']} ｜ 🎯 探讨对象：{article['subject']}"


def _rss_date(article: dict[str, Any]) -> str:
    article_date = article["article_date"] or article["processed_at"][:10]
    if len(article_date) == 10:
        return format_datetime(datetime.fromisoformat(article_date).replace(tzinfo=timezone.utc))
    return format_datetime(datetime.fromisoformat(article["processed_at"].replace("Z", "+00:00")))


def _body_html(article: dict[str, Any]) -> str:
    body_html = markdown.markdown(html.escape(article["body_markdown"]), extensions=["extra"])
    image_url = _safe_image_url(article["image_url"])
    if image_url:
        image = f'<img src="{image_url}" alt="" style="width:100%; border-radius:10px;"/>'
        body_html = f"{image}\n{body_html}"
    return _sanitize_html(body_html)


def _safe_image_url(value: str) -> str:
    image_url = str(value or "").strip()
    parsed = urlsplit(image_url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    return html.escape(image_url, quote=True)


def _safe_content_url(value: str) -> bool:
    url = str(value or "").strip()
    parsed = urlsplit(url)
    if parsed.scheme:
        return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)
    return url.startswith(("/", "./", "../", "#", "?")) and not url.startswith("//")


def _sanitize_html(value: str) -> str:
    allowed_tags = {
        "a", "blockquote", "br", "code", "del", "em", "h1", "h2", "h3", "h4", "h5", "h6",
        "hr", "img", "li", "ol", "p", "pre", "strong", "table", "tbody", "td", "th", "thead", "tr", "ul",
    }
    allowed_attributes = {"a": {"href", "title"}, "img": {"alt", "src", "title"}}
    soup = BeautifulSoup(value, "html.parser")
    for tag in soup.find_all(True):
        if tag.name not in allowed_tags:
            tag.unwrap()
            continue
        for attribute in list(tag.attrs):
            if attribute not in allowed_attributes.get(tag.name, set()):
                del tag.attrs[attribute]
                continue
            if attribute in {"href", "src"} and not _safe_content_url(str(tag.attrs[attribute])):
                del tag.attrs[attribute]
    return str(soup)


def _feed_xml(source: str, articles: list[dict[str, Any]]) -> bytes:
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = f"{source.upper()} AI 深度精读版"
    ET.SubElement(channel, "link").text = "https://minstrelduty.github.io/nyrb-ai-rss/"
    ET.SubElement(channel, "description").text = "高端学术精读杂志"
    ET.SubElement(channel, "language").text = "zh-CN"
    for article in articles:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = article["original_title"] or article["title_zh"]
        ET.SubElement(item, "link").text = article["url"]
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = article["url"]
        ET.SubElement(item, "pubDate").text = _rss_date(article)
        ET.SubElement(item, "description").text = "|||".join(
            (article["title_zh"], author_subject(article), article["hook"])
        )
        ET.SubElement(item, f"{{{CONTENT_NS}}}encoded").text = _body_html(article)
    ET.indent(rss, space="  ")
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)


def build_rss(
    articles_root: Path = Path("data/articles"), output_root: Path = Path(".")
) -> dict[str, Path]:
    records = load_articles(articles_root)
    output_dir = Path(output_root)
    outputs: dict[str, Path] = {}
    for source in sorted(SUPPORTED_SOURCES):
        source_articles = [article for article in records if article["source"] == source]
        source_articles.sort(key=lambda article: (article["article_date"], article["processed_at"], article["url"]), reverse=True)
        output = output_dir / f"{source}_ai_enhanced.xml"
        output.write_bytes(_feed_xml(source, source_articles) + b"\n")
        outputs[source] = output
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--articles-root", type=Path, default=Path("data/articles"))
    parser.add_argument("--output-root", type=Path, default=Path("."))
    args = parser.parse_args()
    print(f"Built {len(build_rss(args.articles_root, args.output_root))} RSS feed(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
