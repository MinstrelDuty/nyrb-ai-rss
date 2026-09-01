"""Build the eight public RSS feeds from the canonical Markdown archive."""

from __future__ import annotations

import argparse
import html
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path
from typing import Iterable, Mapping

import markdown

try:
    from .utils import canonicalize_url, parse_frontmatter, stable_article_id
except ImportError:  # direct invocation: python scripts/build_rss.py
    from utils import canonicalize_url, parse_frontmatter, stable_article_id


CONTENT_NAMESPACE = "http://purl.org/rss/1.0/modules/content/"
logger = logging.getLogger(__name__)

FEEDS = {
    "NYRB": {
        "file": "nyrb_ai_enhanced.xml",
        "title": "纽约书评深度精读版",
        "description": "New York Review of Books 中文精读归档",
        "link": "https://www.nybooks.com/",
    },
    "LRB": {
        "file": "lrb_ai_enhanced.xml",
        "title": "伦敦书评深度精读版",
        "description": "London Review of Books 中文精读归档",
        "link": "https://www.lrb.co.uk/",
    },
    "TLS": {
        "file": "tls_ai_enhanced.xml",
        "title": "TLS 深度精读版",
        "description": "Times Literary Supplement 中文精读归档",
        "link": "https://www.the-tls.com/",
    },
    "NYT": {
        "file": "nyt_ai_enhanced.xml",
        "title": "纽约时报书评深度精读版",
        "description": "New York Times Book Review 中文精读归档",
        "link": "https://www.nytimes.com/section/books/review",
    },
    "NEWYORKER": {
        "file": "newyorker_ai_enhanced.xml",
        "title": "纽约客书评深度精读版",
        "description": "The New Yorker Books / Under Review 中文精读归档",
        "link": "https://www.newyorker.com/magazine/books",
    },
    "ATLANTIC": {
        "file": "atlantic_ai_enhanced.xml",
        "title": "大西洋月刊书评深度精读版",
        "description": "The Atlantic Books 中文精读归档",
        "link": "https://www.theatlantic.com/books/",
    },
    "LARB": {
        "file": "larb_ai_enhanced.xml",
        "title": "洛杉矶书评深度精读版",
        "description": "Los Angeles Review of Books 中文精读归档",
        "link": "https://lareviewofbooks.org/",
    },
    "PUBLICBOOKS": {
        "file": "publicbooks_ai_enhanced.xml",
        "title": "Public Books 深度精读版",
        "description": "Public Books Reviews 中文精读归档",
        "link": "https://www.publicbooks.org/",
    },
}


@dataclass(frozen=True)
class ArchiveArticle:
    source: str
    url: str
    original_title: str
    title_zh: str
    author_subject: str
    hook: str
    body_markdown: str
    article_date: str = ""
    processed_at: str = ""
    image_url: str = ""
    status: str = "published"
    published_at: str = ""
    path: Path | None = None


def _coerce_article(value: ArchiveArticle | Mapping[str, str]) -> ArchiveArticle:
    if isinstance(value, ArchiveArticle):
        return value
    return ArchiveArticle(
        source=str(value.get("source", "")),
        url=str(value.get("url", "")),
        original_title=str(value.get("original_title", "")),
        title_zh=str(value.get("title_zh", "")),
        author_subject=str(value.get("author_subject", "")),
        hook=str(value.get("hook", "")),
        body_markdown=str(value.get("body_markdown", "")),
        article_date=str(value.get("article_date", "")),
        processed_at=str(value.get("processed_at", "")),
        image_url=str(value.get("image_url", "")),
        status=str(value.get("status", "published")),
        published_at=str(value.get("published_at", "")),
    )


def load_archived_articles(archive_root: Path) -> list[ArchiveArticle]:
    articles: list[ArchiveArticle] = []
    root = Path(archive_root)
    if not root.exists():
        return articles
    for path in sorted(root.rglob("*.md")):
        try:
            metadata, body = parse_frontmatter(path.read_text(encoding="utf-8"))
            source = metadata.get("source", "").upper()
            if source not in FEEDS or metadata.get("status", "published").lower() != "published":
                continue
            articles.append(
                ArchiveArticle(
                    source=source,
                    url=canonicalize_url(metadata["url"]),
                    original_title=metadata.get("original_title", ""),
                    title_zh=metadata.get("title_zh", ""),
                    author_subject=metadata.get("author_subject", ""),
                    hook=metadata.get("hook", ""),
                    body_markdown=body,
                    article_date=metadata.get("article_date", ""),
                    processed_at=metadata.get("processed_at", ""),
                    image_url=metadata.get("image_url", ""),
                    status="published",
                    published_at=metadata.get("published_at", ""),
                    path=path,
                )
            )
        except (OSError, KeyError, ValueError) as exc:
            logger.warning("skipping invalid archive file %s: %s", path, exc)
    return articles


def markdown_to_html(body: str, image_url: str = "") -> str:
    rendered = markdown.markdown(str(body or ""), extensions=["extra"])
    if image_url:
        safe_url = html.escape(str(image_url), quote=True)
        rendered = (
            f'<img src="{safe_url}" style="width:100%; border-radius:10px;"/><br>\n'
            + rendered
        )
    return rendered


def _article_datetime(article: ArchiveArticle) -> datetime:
    for value in (article.published_at, article.article_date, article.processed_at):
        if not value:
            continue
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            try:
                if len(value) == 10:
                    parsed = datetime.combine(date.fromisoformat(value), time.min)
                else:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return datetime.min.replace(tzinfo=timezone.utc)


def _cdata(value: str) -> str:
    return f"<![CDATA[{str(value or '').replace(']]>', ']]]]><![CDATA[')}]]>"


def _text(value: str) -> str:
    return html.escape(str(value or ""), quote=True)


def build_feed(
    source: str,
    articles: Iterable[ArchiveArticle | Mapping[str, str]],
    generated_at: datetime,
) -> str:
    source_key = str(source).upper()
    if source_key not in FEEDS:
        raise ValueError(f"unknown feed source: {source}")
    feed = FEEDS[source_key]
    prepared = [
        _coerce_article(article)
        for article in articles
        if _coerce_article(article).source.upper() == source_key
        and _coerce_article(article).status.lower() == "published"
    ]
    prepared.sort(key=lambda article: (_article_datetime(article), article.url), reverse=True)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    generated_text = format_datetime(generated_at.astimezone(timezone.utc))

    chunks = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<rss version="2.0" xmlns:content="{CONTENT_NAMESPACE}">',
        "<channel>",
        f"<title>{_text(feed['title'])}</title>",
        f"<link>{_text(feed['link'])}</link>",
        f"<description>{_text(feed['description'])}</description>",
        "<language>zh-CN</language>",
        f"<lastBuildDate>{_text(generated_text)}</lastBuildDate>",
    ]
    for article in prepared:
        description = f"{article.title_zh}|||{article.author_subject}|||{article.hook}"
        body_html = markdown_to_html(article.body_markdown, article.image_url)
        chunks.extend(
            [
                "<item>",
                f"<title>{_text(article.original_title)}</title>",
                f"<link>{_text(article.url)}</link>",
                f'<guid isPermaLink="false">{_text(stable_article_id(source_key, article.url))}</guid>',
                f"<pubDate>{_text(format_datetime(_article_datetime(article)))}</pubDate>",
                f"<description>{_text(description)}</description>",
                f"<content:encoded>{_cdata(body_html)}\n</content:encoded>",
                "</item>",
            ]
        )
    chunks.extend(["</channel>", "</rss>", ""])
    return "\n".join(chunks)


def write_feeds(archive_root: Path, output_root: Path) -> dict[str, int]:
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    articles = load_archived_articles(Path(archive_root))
    generated_at = datetime.now(timezone.utc)
    rendered: dict[str, str] = {}
    counts: dict[str, int] = {}
    for source, config in FEEDS.items():
        xml = build_feed(source, articles, generated_at)
        from xml.etree import ElementTree as ET

        ET.fromstring(xml)
        rendered[config["file"]] = xml
        counts[source] = sum(1 for article in articles if article.source == source)

    temporary_paths: list[Path] = []
    try:
        for filename, xml in rendered.items():
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n", dir=output_root, delete=False
            ) as handle:
                handle.write(xml)
                temporary_paths.append(Path(handle.name))
        for temporary, filename in zip(temporary_paths, rendered):
            os.replace(temporary, output_root / filename)
    finally:
        for temporary in temporary_paths:
            if temporary.exists():
                temporary.unlink()
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, default=Path("data/articles"))
    parser.add_argument("--output-root", type=Path, default=Path("."))
    args = parser.parse_args()
    counts = write_feeds(args.archive_root, args.output_root)
    for source, count in counts.items():
        print(f"{source}: {count} articles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
