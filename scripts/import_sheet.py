"""Import approved rows from a published Google Sheet CSV URL."""

from __future__ import annotations

import os
from pathlib import Path

import requests

try:
    from scripts.publishing import import_csv_text
except ModuleNotFoundError:  # Supports direct script execution from the repository root.
    from publishing import import_csv_text


def import_sheet(csv_url: str, articles_root: Path = Path("data/articles")) -> list[Path]:
    response = requests.get(csv_url, timeout=30)
    response.raise_for_status()
    return import_csv_text(response.text, articles_root)


def main() -> int:
    csv_url = os.environ.get("SHEET_CSV_URL", "").strip()
    if not csv_url:
        raise SystemExit("SHEET_CSV_URL is required")
    written = import_sheet(csv_url)
    print(f"Imported {len(written)} published article(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
