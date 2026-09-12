"""Small, dependency-free helpers shared by the archive tools."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit


_TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref"}


def canonicalize_url(url: str) -> str:
    """Return a stable URL suitable for article identity and deduplication."""

    value = str(url or "").strip()
    if not value:
        raise ValueError("URL must not be empty")

    parts = urlsplit(value)
    if not parts.scheme or not parts.netloc:
        raise ValueError(f"URL must be absolute: {url!r}")

    query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_PARAMS and not key.lower().startswith("utm_")
    ]
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def stable_article_id(source: str, url: str) -> str:
    normalized = canonicalize_url(url)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    source_key = str(source or "").strip().lower()
    if not source_key:
        raise ValueError("source must not be empty")
    return f"{source_key}-{digest}"


def _url_slug(url: str) -> str:
    path = urlsplit(canonicalize_url(url)).path
    raw_slug = unquote(path.rstrip("/").rsplit("/", 1)[-1])
    slug = re.sub(r"[^\w-]+", "-", raw_slug, flags=re.UNICODE)
    return re.sub(r"-+", "-", slug).strip("-_")


def article_filename(source: str, article_date: str, url: str) -> str:
    source_key = str(source or "").strip().lower()
    stable_suffix = stable_article_id(source, url).split("-", 1)[1]
    slug = _url_slug(url)
    try:
        date.fromisoformat(str(article_date or ""))
        valid_date = bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(article_date)))
    except ValueError:
        valid_date = False

    if valid_date and slug:
        return f"{article_date}-{slug}.md"
    return f"{source_key}-{stable_suffix}.md"


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    normalized = str(text).replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        raise ValueError("frontmatter must start with ---")
    closing = normalized.find("\n---\n", 4)
    if closing == -1:
        raise ValueError("frontmatter is not closed")

    metadata: dict[str, str] = {}
    header = normalized[4:closing]
    for line in header.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*):(?:[ \t]*(.*))?", line)
        if not match:
            raise ValueError(f"invalid frontmatter line: {line!r}")
        key, raw_value = match.groups()
        raw_value = raw_value or ""
        if raw_value.startswith('"'):
            try:
                metadata[key] = str(json.loads(raw_value))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid quoted frontmatter value for {key}") from exc
        else:
            metadata[key] = raw_value

    body = normalized[closing + len("\n---\n") :]
    if body and not body.endswith("\n"):
        body += "\n"
    return metadata, body


def render_frontmatter(metadata: dict[str, str], body: str) -> str:
    lines = ["---"]
    for key, value in metadata.items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", str(key)):
            raise ValueError(f"invalid frontmatter key: {key!r}")
        lines.append(f"{key}: {json.dumps(str(value or ""), ensure_ascii=False)}")
    lines.extend(["---", ""])
    content = str(body or "").replace("\r\n", "\n")
    if content and not content.endswith("\n"):
        content += "\n"
    return "\n".join(lines) + content
