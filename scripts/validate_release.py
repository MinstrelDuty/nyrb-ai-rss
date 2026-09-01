"""Read-only validation for the eight-source RSS release."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from .build_rss import FEEDS, load_archived_articles
    from .utils import canonicalize_url
except ImportError:  # direct invocation: python scripts/validate_release.py
    from build_rss import FEEDS, load_archived_articles
    from utils import canonicalize_url


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    errors: list[str]


def validate_release(repo_root: Path) -> ValidationReport:
    root = Path(repo_root)
    errors: list[str] = []
    articles = load_archived_articles(root / "data" / "articles")
    archive_urls: dict[str, set[str]] = {source: set() for source in FEEDS}
    for article in articles:
        archive_urls[article.source].add(canonicalize_url(article.url))

    app_path = root / "app.js"
    index_path = root / "index.html"
    app_text = app_path.read_text(encoding="utf-8") if app_path.exists() else ""
    index_text = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    if not app_path.exists():
        errors.append("app.js is missing")
    if not index_path.exists():
        errors.append("index.html is missing")

    for source, config in FEEDS.items():
        source_id = source.lower()
        if f"id: '{source_id}'" not in app_text or f"file: '{config['file']}'" not in app_text:
            errors.append(f"frontend app.js is missing {source} source configuration")
        if f'data-source="{source_id}"' not in index_text:
            errors.append(f"frontend index.html is missing {source} navigation")

        feed_path = root / config["file"]
        if not feed_path.exists():
            errors.append(f"{config['file']} is missing")
            continue
        try:
            rss_root = ET.parse(feed_path).getroot()
        except ET.ParseError as exc:
            errors.append(f"{config['file']} is not valid XML: {exc}")
            continue

        feed_urls: set[str] = set()
        for item in rss_root.findall("./channel/item"):
            link = (item.findtext("link") or "").strip()
            guid = (item.findtext("guid") or "").strip()
            if not link:
                errors.append(f"{config['file']} contains an item without link")
                continue
            try:
                normalized = canonicalize_url(link)
            except ValueError as exc:
                errors.append(f"{config['file']} contains invalid link: {exc}")
                continue
            feed_urls.add(normalized)
            if not guid.startswith(f"{source_id}-"):
                errors.append(f"{config['file']} contains an item with mixed source guid")
            if normalized not in archive_urls[source]:
                errors.append(f"{config['file']} contains URL not in {source} archive: {normalized}")

        missing_urls = archive_urls[source] - feed_urls
        for url in sorted(missing_urls):
            errors.append(f"{config['file']} is missing archived URL: {url}")

    return ValidationReport(ok=not errors, errors=errors)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    report = validate_release(args.repo_root)
    if report.ok:
        print("release validation passed")
        return 0
    for error in report.errors:
        print(f"ERROR: {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
