import csv
import io
import json
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from scripts.build_articles_json import build_articles_json
from scripts.build_rss import build_rss
from scripts.publishing import REQUIRED_COLUMNS, import_csv_text, load_articles, published_records_from_csv
from scripts.utils import render_frontmatter


def _csv(rows: list[dict[str, str]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=REQUIRED_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _row(**overrides: str) -> dict[str, str]:
    row = {
        "source": "LRB",
        "url": "https://www.lrb.co.uk/the-paper/v48/n18/colin-burrow/good-weird?utm_source=queue",
        "raw_path": "raw/lrb/2026-09-10-good-weird-or-bad-weird.md",
        "original_title": "Good Weird or Bad Weird",
        "author": "Colin Burrow",
        "article_date": "2026-09-10",
        "image_url": "https://example.com/burrow.jpg",
        "title_zh": "好怪还是坏怪",
        "subject": "文学批评中的细读",
        "hook": "批评的怪异性需要被重新理解。",
        "keywords": '["close reading", "criticism"]',
        "body_markdown": "# 正文\n\n这是一篇经过人工审校的正文。",
        "processed_at": "2026-09-14T09:00:00Z",
        "status": "published",
    }
    row.update(overrides)
    return row


def test_import_skips_review_and_overwrites_same_url_with_newest_published_revision(tmp_path: Path):
    root = tmp_path / "data" / "articles"
    first_csv = _csv(
        [
            _row(status="review", url="https://example.com/review", title_zh="不得发布"),
            _row(body_markdown="旧正文", processed_at="2026-09-14T09:00:00Z"),
        ]
    )
    second_csv = _csv(
        [
            _row(
                title_zh="新版好怪还是坏怪",
                keywords='["close reading", "revision"]',
                body_markdown="# 新版正文\n\n修订后的内容。",
                processed_at="2026-09-14T10:00:00Z",
            ),
        ]
    )

    first_written = import_csv_text(first_csv, root)
    written = import_csv_text(second_csv, root)

    assert written == first_written
    assert len(written) == 1
    assert written[0].parent == root / "lrb"
    assert len(list(root.rglob("*.md"))) == 1
    articles = load_articles(root)
    assert articles == [
        {
            "source": "lrb",
            "url": "https://www.lrb.co.uk/the-paper/v48/n18/colin-burrow/good-weird",
            "raw_path": "raw/lrb/2026-09-10-good-weird-or-bad-weird.md",
            "original_title": "Good Weird or Bad Weird",
            "author": "Colin Burrow",
            "article_date": "2026-09-10",
            "image_url": "https://example.com/burrow.jpg",
            "title_zh": "新版好怪还是坏怪",
            "subject": "文学批评中的细读",
            "hook": "批评的怪异性需要被重新理解。",
            "keywords": ["close reading", "revision"],
            "body_markdown": "# 新版正文\n\n修订后的内容。\n",
            "processed_at": "2026-09-14T10:00:00Z",
            "status": "published",
        }
    ]


def test_builders_emit_structured_json_and_legacy_compatible_rss(tmp_path: Path):
    articles_root = tmp_path / "data" / "articles"
    import_csv_text(_csv([_row()]), articles_root)
    json_path = tmp_path / "data" / "articles.json"

    build_articles_json(articles_root, json_path)
    build_rss(articles_root, tmp_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload == [
        {
            "source": "lrb",
            "url": "https://www.lrb.co.uk/the-paper/v48/n18/colin-burrow/good-weird",
            "original_title": "Good Weird or Bad Weird",
            "author": "Colin Burrow",
            "article_date": "2026-09-10",
            "image_url": "https://example.com/burrow.jpg",
            "title_zh": "好怪还是坏怪",
            "subject": "文学批评中的细读",
            "hook": "批评的怪异性需要被重新理解。",
            "keywords": ["close reading", "criticism"],
            "body_markdown": "# 正文\n\n这是一篇经过人工审校的正文。\n",
            "processed_at": "2026-09-14T09:00:00Z",
        }
    ]
    rss = ET.parse(tmp_path / "lrb_ai_enhanced.xml").getroot()
    item = rss.find("./channel/item")
    assert item is not None
    assert item.findtext("title") == "Good Weird or Bad Weird"
    assert item.findtext("description") == "好怪还是坏怪|||✍️ 作者：Colin Burrow ｜ 🎯 探讨对象：文学批评中的细读|||批评的怪异性需要被重新理解。"
    content = item.find("{http://purl.org/rss/1.0/modules/content/}encoded")
    assert content is not None
    assert "<h1>正文</h1>" in (content.text or "")
    assert "https://example.com/burrow.jpg" in (content.text or "")


def test_json_builder_ignores_a_nonpublished_canonical_file(tmp_path: Path):
    articles_root = tmp_path / "data" / "articles"
    import_csv_text(_csv([_row()]), articles_root)
    review = _row(status="review", url="https://example.com/not-published")
    review_path = articles_root / "lrb" / "review.md"
    review_path.write_text(
        render_frontmatter(
            {key: value for key, value in review.items() if key != "body_markdown"},
            review["body_markdown"],
        ),
        encoding="utf-8",
    )

    payload = build_articles_json(articles_root, tmp_path / "data" / "articles.json")

    assert [article["url"] for article in payload] == [
        "https://www.lrb.co.uk/the-paper/v48/n18/colin-burrow/good-weird"
    ]


def test_repeating_the_same_sheet_produces_identical_published_artifacts(tmp_path: Path):
    articles_root = tmp_path / "data" / "articles"
    csv_text = _csv([_row()])
    json_path = tmp_path / "data" / "articles.json"

    import_csv_text(csv_text, articles_root)
    build_articles_json(articles_root, json_path)
    build_rss(articles_root, tmp_path)
    first = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}

    import_csv_text(csv_text, articles_root)
    build_articles_json(articles_root, json_path)
    build_rss(articles_root, tmp_path)
    second = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}

    assert second == first


def test_import_accepts_the_utf8_bom_used_by_some_csv_exports():
    records = published_records_from_csv("\ufeff" + _csv([_row()]))

    assert records[0]["source"] == "lrb"


def test_builder_scripts_run_directly_from_the_repository_root():
    repo_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [sys.executable, "scripts/build_articles_json.py", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_articles_json_is_sorted_by_article_date_descending(tmp_path: Path):
    articles_root = tmp_path / "data" / "articles"
    import_csv_text(
        _csv(
            [
                _row(url="https://example.com/older", article_date="2026-09-01"),
                _row(url="https://example.com/newer", article_date="2026-09-11"),
            ]
        ),
        articles_root,
    )

    payload = build_articles_json(articles_root, tmp_path / "data" / "articles.json")

    assert [article["url"] for article in payload] == [
        "https://example.com/newer",
        "https://example.com/older",
    ]
