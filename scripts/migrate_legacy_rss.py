"""One-time migration of legacy enriched RSS items to canonical Markdown."""
from __future__ import annotations

import argparse, json, re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup
from markdownify import markdownify

try:
    from scripts.publishing import load_articles, write_canonical_articles
    from scripts.utils import canonicalize_url
except ModuleNotFoundError:
    from publishing import load_articles, write_canonical_articles
    from utils import canonicalize_url

CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"

def parse_legacy_description(value: str):
    parts = value.split("|||", 2)
    if len(parts) != 3:
        raise ValueError("missing legacy ||| description")
    match = re.fullmatch(r"✍️\s*作者：\s*(.*?)\s*｜\s*🎯\s*探讨对象：\s*(.*)", parts[1].strip())
    if not match:
        raise ValueError("invalid author_subject")
    return parts[0].strip(), match.group(1).strip(), match.group(2).strip(), parts[2].strip()

def html_to_markdown(value: str):
    soup = BeautifulSoup(value or "", "html.parser")
    image = soup.find("img")
    image_url = str(image.get("src", "")).strip() if image else ""
    for tag in soup.find_all(["img", "script", "style"]): tag.decompose()
    return markdownify(str(soup), heading_style="ATX").strip() + "\n", image_url

def _nyt_description(value: str):
    title = re.search(r"^#\s*(?:【中文标题】\s*)?(.+)$", value, re.M)
    author = re.search(r"作者[：:]\s*(.*?)\s*｜", value)
    subject = re.search(r"探讨对象[：:]\s*(.+?)(?=\n\s*#|$)", value, re.S)
    hook = re.search(r"(?:【一句话破题】|【一句话点评】|一句话破题|一句话点评)\s*\n+(.+?)(?=\n\s*##|$)", value, re.S)
    body = re.search(r"(?:【正文】|##\s*【?正文】?)\s*(.*)$", value, re.S)
    if not all((title, author, subject, hook, body)):
        raise ValueError("incomplete NYT legacy description")
    return title.group(1).strip(), author.group(1).strip(), subject.group(1).strip(), hook.group(1).strip(), body.group(1).strip()+"\n"

def _date(value: str) -> str:
    try: return parsedate_to_datetime(value).date().isoformat()
    except Exception: return ""

def migrate_legacy_feeds(feeds: dict[str, Path], articles_root: Path, *, processed_at: str):
    existing = {article["url"]: article for article in load_articles(articles_root)}
    records, report = [], {"migrated":0,"skipped_existing":0,"skipped_invalid":0,"errors":[]}
    seen=set()
    for source, path in feeds.items():
        for item in ET.parse(path).findall("./channel/item"):
            try:
                url=canonicalize_url(item.findtext("link", ""))
                if url in seen:
                    report["skipped_existing"] += 1; continue
                seen.add(url)
                current = existing.get(url)
                # Only an article whose data demonstrably matches a prior
                # migration may be rewritten to backfill provenance. Sheet
                # canonical records always win over old RSS data.
                if current is not None and not (
                    current.get("raw_path") == ""
                    and current.get("keywords") == []
                    and current.get("source") == source
                    and current.get("original_title") == item.findtext("title", "").strip()
                ):
                    report["skipped_existing"] += 1; continue
                description=item.findtext("description", "") or ""
                if "|||" in description:
                    title_zh, author, subject, hook=parse_legacy_description(description)
                    body, image_url=html_to_markdown(item.findtext(CONTENT, "") or "")
                    if not body.strip(): raise ValueError("missing content:encoded")
                elif source == "nyt":
                    title_zh, author, subject, hook, body=_nyt_description(description); image_url=""
                else: raise ValueError("unsupported legacy format")
                records.append({"source":source,"url":url,"raw_path":"","original_title":item.findtext("title", "").strip(),"author":author,"article_date":_date(item.findtext("pubDate", "")),"image_url":image_url,"title_zh":title_zh,"subject":subject,"hook":hook,"keywords":[],"body_markdown":body,"processed_at":current.get("processed_at", processed_at) if current else processed_at,"status":"published","legacy_migrated":True,"migration_source":"legacy_rss"})
            except Exception as exc:
                report["skipped_invalid"] += 1; report["errors"].append({"source":source,"url":item.findtext("link", ""),"reason":str(exc)})
    write_canonical_articles(records, articles_root)
    report["migrated"]=len(records)
    return report

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--articles-root",type=Path,default=Path("data/articles")); parser.add_argument("--report",type=Path,default=Path("data/legacy-migration-report.json")); args=parser.parse_args()
    now=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
    feeds={s:Path(f"{s}_ai_enhanced.xml") for s in ("nyrb","lrb","tls","nyt")}
    report=migrate_legacy_feeds(feeds,args.articles_root,processed_at=now)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__": main()
