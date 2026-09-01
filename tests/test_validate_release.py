from pathlib import Path

from scripts.build_rss import write_feeds
from scripts.import_sheet import import_rows
from scripts.validate_release import validate_release


def test_validate_release_reports_missing_feed(tmp_path):
    (tmp_path / "app.js").write_text("", encoding="utf-8")
    (tmp_path / "index.html").write_text("", encoding="utf-8")

    report = validate_release(tmp_path)

    assert report.ok is False
    assert any("publicbooks_ai_enhanced.xml" in error for error in report.errors)


def test_validate_release_accepts_fixture_archive_and_eight_feeds(tmp_path):
    root = tmp_path
    archive = root / "data" / "articles"
    rows = [
        {
            "source": "NYRB",
            "url": "https://example.com/nyrb/article",
            "original_title": "Original",
            "title_zh": "中文标题",
            "author_subject": "作者与对象",
            "hook": "一句话",
            "body_markdown": "### 核心脉络\n\n正文",
            "article_date": "2026-09-01",
            "processed_at": "2026-09-01T00:00:00+00:00",
            "image_url": "",
            "status": "published",
        }
    ]
    import_rows(rows, archive)
    write_feeds(archive, root)
    (root / "app.js").write_text(
        "id: 'nyrb' file: 'nyrb_ai_enhanced.xml' id: 'lrb' file: 'lrb_ai_enhanced.xml' "
        "id: 'tls' file: 'tls_ai_enhanced.xml' id: 'nyt' file: 'nyt_ai_enhanced.xml' "
        "id: 'newyorker' file: 'newyorker_ai_enhanced.xml' "
        "id: 'atlantic' file: 'atlantic_ai_enhanced.xml' "
        "id: 'larb' file: 'larb_ai_enhanced.xml' id: 'publicbooks' file: 'publicbooks_ai_enhanced.xml'",
        encoding="utf-8",
    )
    (root / "index.html").write_text(
        'data-source="nyrb" data-source="lrb" data-source="tls" data-source="nyt" '
        'data-source="newyorker" data-source="atlantic" '
        'data-source="larb" data-source="publicbooks"',
        encoding="utf-8",
    )

    report = validate_release(root)

    assert report.ok is True
    assert report.errors == []
