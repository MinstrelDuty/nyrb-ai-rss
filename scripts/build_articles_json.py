"""Build the GitHub Pages article payload from canonical Markdown."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from scripts.publishing import load_articles
except ModuleNotFoundError:  # Supports direct script execution from the repository root.
    from publishing import load_articles


JSON_FIELDS = (
    "source", "url", "original_title", "author", "article_date", "image_url",
    "title_zh", "subject", "hook", "keywords", "body_markdown", "processed_at",
)


def build_articles_json(
    articles_root: Path = Path("data/articles"), output_path: Path = Path("data/articles.json")
) -> list[dict[str, Any]]:
    records = load_articles(articles_root)
    records.sort(key=lambda article: (article["article_date"], article["processed_at"], article["url"]), reverse=True)
    payload = [{field: article[field] for field in JSON_FIELDS} for article in records]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--articles-root", type=Path, default=Path("data/articles"))
    parser.add_argument("--output", type=Path, default=Path("data/articles.json"))
    args = parser.parse_args()
    print(f"Built {len(build_articles_json(args.articles_root, args.output))} article JSON record(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
