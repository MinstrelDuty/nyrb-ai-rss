# nyrb-ai-rss v2 八来源 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 NYRB、LRB、TLS、NYT、NEWYORKER、ATLANTIC、LARB、PUBLICBOOKS 统一接入无 AI API 的 CSV→Markdown→RSS→GitHub Pages 流水线，同时保留全部历史文章和现有前端行为。

**Architecture:** 七个普通来源由 ChatGPT Scheduled Task 写入公开 Google Sheet，NYT 由本地采集任务保存为 `raw/nyt/*.md` 后由 Scheduled Task 精读；GitHub Actions 只下载 CSV、导入最终 Markdown、构建 8 个 RSS 并提交变化。历史 XML 先迁移为 Markdown，再由同一个 RSS 构建器生成派生 XML。

**Tech Stack:** Python 3.10+、标准库 `csv`/`hashlib`/`urllib`/`xml.etree.ElementTree`、`requests`、`beautifulsoup4`、`markdown`、`markdownify`、pytest、现有原生 JavaScript 前端。

**Spec:** `docs/superpowers/specs/2026-09-01-nyrb-ai-rss-v2-eight-sources-design.md`

## Global Constraints

- 第一批正式来源固定为 `NYRB`、`LRB`、`TLS`、`NYT`、`NEWYORKER`、`ATLANTIC`、`LARB`、`PUBLICBOOKS`。
- 不使用 OpenAI API、DeepSeek API 或任何其他模型 API。
- GitHub Actions 只负责 CSV 导入、归档、RSS 构建、测试和提交。
- `SHEET_CSV_URL` 不硬编码；未配置或下载失败时不得清空归档或生成空 RSS。
- `status != published` 的 Sheet 行不进入正式归档和 RSS。
- canonicalized URL 是唯一去重键；重复记录不得覆盖已有 Markdown。
- 现有 `nyt_ai_enhanced.xml` 未提交修改属于用户工作，任何提交不得包含它。
- 现有 HTML/CSS/JavaScript 框架和 RSS 字段保持兼容，只增加 4 个来源配置。
- 关闭旧 DeepSeek 生产链路前，用户必须完成 Scheduled Task→Google Sheet 无人值守写入验证。

---

### Task 1: 建立 Python 测试基线与通用 URL/归档工具

**Files:**
- Create: `requirements.txt`
- Create: `scripts/__init__.py`
- Create: `scripts/utils.py`
- Create: `tests/test_utils.py`

**Interfaces:**
- `canonicalize_url(url: str) -> str`：去掉 fragment、移除 `utm_*`/`fbclid`/`gclid` 等追踪参数、统一末尾斜杠。
- `stable_article_id(source: str, url: str) -> str`：返回 `<source.lower()>-<sha256(normalized_url)[:12]>`。
- `article_filename(source: str, article_date: str, url: str) -> str`：有合法 ISO 日期时返回 `<date>-<slug>.md`，否则返回 `<source.lower()>-<hash>.md`；slug 冲突由调用方追加稳定 ID。
- `parse_frontmatter(text: str) -> tuple[dict[str, str], str]`：解析本项目生成的简单 YAML frontmatter，返回元数据和正文；不接受缺少闭合 `---` 的输入。
- `render_frontmatter(metadata: dict[str, str], body: str) -> str`：使用 JSON 风格双引号安全输出字符串值，返回以换行结尾的 Markdown。

- [ ] **Step 1: 写失败测试**

```python
def test_canonicalize_url_removes_tracking_and_fragment():
    assert canonicalize_url(
        "https://example.com/article/?utm_source=x&id=7#comments"
    ) == "https://example.com/article?id=7"

def test_stable_id_is_source_prefixed_and_repeatable():
    assert stable_article_id("LRB", "https://example.com/a") == stable_article_id("LRB", "https://example.com/a")
    assert stable_article_id("LRB", "https://example.com/a").startswith("lrb-")

def test_frontmatter_round_trip_preserves_multiline_body():
    text = render_frontmatter({"source": "NYRB", "title_zh": "中文标题"}, "第一行\n第二行")
    metadata, body = parse_frontmatter(text)
    assert metadata["source"] == "NYRB"
    assert body == "第一行\n第二行\n"
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest tests/test_utils.py -q`

Expected: FAIL because `scripts.utils` and its functions do not exist.

- [ ] **Step 3: 实现最小工具**

使用 `urllib.parse.urlsplit/parse_qsl/urlencode/urlunsplit` 完成 URL 规范化；使用 `hashlib.sha256` 生成稳定 ID；使用标准库和受限的 YAML 键值解析实现 frontmatter，不引入数据库或模型依赖。`article_filename` 的 slug 只从 canonical URL 的 path 最后一段生成，不能使用中文标题。

- [ ] **Step 4: 运行通过测试**

Run: `python -m pytest tests/test_utils.py -q`

Expected: PASS，且多行正文、Unicode、引号和追踪参数均有断言覆盖。

- [ ] **Step 5: 提交**

```bash
git add requirements.txt scripts/__init__.py scripts/utils.py tests/test_utils.py
git commit -m "feat: add archive URL and frontmatter utilities"
```

### Task 2: 实现 Google Sheet CSV 导入器

**Files:**
- Create: `tests/fixtures/sample_sheet.csv`
- Create: `scripts/import_sheet.py`
- Create: `tests/test_import_sheet.py`
- Modify: `requirements.txt`

**Interfaces:**
- `REQUIRED_COLUMNS: tuple[str, ...]`：固定为 `source,url,original_title,title_zh,author_subject,hook,body_markdown,processed_at`。
- `ALLOWED_SOURCES: frozenset[str]`：包含 8 个来源。
- `ImportStats`：字段为 `fetched_rows`、`valid_rows`、`new_articles`、`duplicate_rows`、`invalid_rows`。
- `import_rows(rows: Iterable[dict[str, str]], archive_root: Path) -> ImportStats`：逐行验证并写入最终 Markdown，单行失败不影响其他行。
- `fetch_csv(url: str, session: requests.Session | None = None) -> str`：检查 HTTP 状态后返回 CSV 文本；网络失败抛出明确异常。
- `main() -> int`：读取 `SHEET_CSV_URL`，打印统计；无地址时以非零状态退出且不修改归档。

- [ ] **Step 1: 写失败测试和 CSV fixture**

fixture 必须包含：一条合法多行中文 Markdown、一条与第一条 canonical URL 等价的重复行、一条缺少必填字段的行、一条非法 source 行、一条 `partial` 行，以及一条来自 NYT 的合法行。

```python
def test_import_rows_writes_published_article_and_multiline_body(tmp_path):
    rows = load_fixture_rows()
    stats = import_rows(rows, tmp_path / "data" / "articles")
    files = list((tmp_path / "data" / "articles").rglob("*.md"))
    assert stats.new_articles == 2
    assert len(files) == 2
    assert "第一行\n第二行" in files[0].read_text(encoding="utf-8") or "第一行\n第二行" in files[1].read_text(encoding="utf-8")

def test_import_rows_skips_duplicate_invalid_and_partial_rows(tmp_path, caplog):
    stats = import_rows(load_fixture_rows(), tmp_path / "articles")
    assert stats.duplicate_rows == 1
    assert stats.invalid_rows == 2
    assert "partial" in caplog.text

def test_fetch_csv_rejects_http_failure(monkeypatch):
    response = Mock(status_code=503, text="unavailable")
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response)
    with pytest.raises(CsvFetchError):
        fetch_csv("https://example.invalid/feed.csv")
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest tests/test_import_sheet.py -q`

Expected: FAIL because importer interfaces are absent.

- [ ] **Step 3: 实现逐行验证与写入**

使用 `csv.DictReader`，拒绝缺少固定表头的 CSV；去除字段外层空白但不破坏 `body_markdown` 内部换行；校验 source、必填字段、`processed_at`/`article_date` 的 ISO 格式；只接受 `published`。先在内存中决定所有输出路径，再逐个以 `x` 模式创建文件；已存在同 URL 或同 stable ID 时计为 duplicate，不覆盖文件。打印五项统计并将 warning 写入 logging。

- [ ] **Step 4: 运行通过测试**

Run: `python -m pytest tests/test_utils.py tests/test_import_sheet.py -q`

Expected: PASS；fixture 中的多行正文、Unicode、重复、partial、坏行和下载失败全部符合预期。

- [ ] **Step 5: 提交**

```bash
git add scripts/import_sheet.py tests/fixtures/sample_sheet.csv tests/test_import_sheet.py requirements.txt
git commit -m "feat: import published sheet rows into markdown archive"
```

### Task 3: 实现从 Markdown 归档生成 8 个 RSS

**Files:**
- Create: `scripts/build_rss.py`
- Create: `tests/test_build_rss.py`
- Modify: `requirements.txt`

**Interfaces:**
- `FEEDS: dict[str, dict[str, str]]`：8 个 source 到输出文件、标题、描述、站点链接的映射。
- `load_archived_articles(archive_root: Path) -> list[Article]`：扫描 Markdown，读取 frontmatter 和正文，过滤 `status != published`。
- `markdown_to_html(body: str, image_url: str = "") -> str`：使用 `markdown` 的 `extra` 扩展转换正文，并安全地在开头添加图片。
- `build_feed(source: str, articles: Iterable[Article], generated_at: datetime) -> str`：返回包含 RSS 2.0、content 命名空间和兼容 item 字段的 XML 文本。
- `write_feeds(archive_root: Path, output_root: Path) -> dict[str, int]`：先生成并解析全部 XML，全部成功后再原子替换 8 个输出文件。

- [ ] **Step 1: 写失败测试**

```python
def test_build_feed_filters_source_and_status_and_keeps_order(tmp_path):
    write_article(tmp_path, source="NYRB", title_zh="较新", processed_at="2026-09-01T10:00:00+08:00")
    write_article(tmp_path, source="NYRB", title_zh="草稿", status="partial", processed_at="2026-09-01T11:00:00+08:00")
    write_article(tmp_path, source="LRB", title_zh="其他来源", processed_at="2026-09-01T12:00:00+08:00")
    xml = build_feed("NYRB", load_archived_articles(tmp_path), datetime.now(timezone.utc))
    root = ET.fromstring(xml)
    items = root.findall("./channel/item")
    assert [item.findtext("title") for item in items] == ["较新"]

def test_build_feed_preserves_frontend_description_and_cdata_content():
    xml = build_feed("TLS", [article_with_body("中文|||作者与对象|||一句话")], datetime.now(timezone.utc))
    assert "中文|||作者与对象|||一句话" in xml
    assert "content:encoded" in xml
    ET.fromstring(xml)

def test_write_feeds_does_not_replace_outputs_when_a_feed_fails(tmp_path, monkeypatch):
    old = tmp_path / "nyrb_ai_enhanced.xml"
    old.write_text("old", encoding="utf-8")
    monkeypatch.setattr("scripts.build_rss.build_feed", lambda *args: (_ for _ in ()).throw(ValueError("bad")))
    with pytest.raises(ValueError):
        write_feeds(tmp_path / "articles", tmp_path)
    assert old.read_text(encoding="utf-8") == "old"
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest tests/test_build_rss.py -q`

Expected: FAIL because RSS builder interfaces are absent.

- [ ] **Step 3: 实现解析、排序和 XML 输出**

使用 frontmatter 的 `source`、`status` 和 `published_at/article_date/processed_at` 计算发布时间；稳定 guid 使用 `stable_article_id`，不要使用当前时间。description 固定为三段 `title_zh|||author_subject|||hook`；正文 HTML 保留图片和 Markdown 标题。CDATA 内容使用 `]]>` 安全拆分；XML 文本通过 `xml.etree.ElementTree` 预解析验证。

- [ ] **Step 4: 运行通过测试**

Run: `python -m pytest tests/test_utils.py tests/test_import_sheet.py tests/test_build_rss.py -q`

Expected: PASS；8 个来源分别生成，中文、CDATA、排序、过滤和失败保护均通过。

- [ ] **Step 5: 提交**

```bash
git add scripts/build_rss.py tests/test_build_rss.py requirements.txt
git commit -m "feat: build compatible RSS feeds from markdown archives"
```

### Task 4: 迁移现有 NYRB/LRB/TLS/NYT XML 历史文章

**Files:**
- Create: `scripts/migrate_legacy_xml.py`
- Create: `tests/fixtures/legacy_sample.xml`
- Create: `tests/test_migrate_legacy_xml.py`
- Create: `data/articles/nyrb/.gitkeep`
- Create: `data/articles/lrb/.gitkeep`
- Create: `data/articles/tls/.gitkeep`
- Create: `data/articles/nyt/.gitkeep`

**Interfaces:**
- `migrate_feed(xml_path: Path, source: str, archive_root: Path, dry_run: bool = False) -> MigrationStats`。
- `migrate_feeds(feed_paths: dict[str, Path], archive_root: Path, dry_run: bool = False) -> dict[str, MigrationStats]`。
- `MigrationStats`：字段为 `items_seen`、`urls_seen`、`created`、`duplicates`、`invalid`。
- `legacy_item_to_article(item: ET.Element, source: str) -> dict[str, str]`：解析 title/link/guid/pubDate/description/content:encoded，兼容 `|||` 三段描述和旧标签式 Markdown 描述。

- [ ] **Step 1: 写失败测试和最小 XML fixture**

fixture 至少包含一个 `|||` item、一个标签式 description item、一个带图片的 HTML 正文 item，以及一个重复 URL item。

```python
def test_legacy_item_to_article_extracts_pipe_description_and_html():
    article = legacy_item_to_article(first_item(), "NYRB")
    assert article["title_zh"] == "中文标题"
    assert article["author_subject"] == "作者与对象"
    assert article["hook"] == "一句话"
    assert "核心脉络" in article["body_markdown"]

def test_migrate_feeds_is_idempotent_and_preserves_counts(tmp_path):
    paths = {"NYRB": fixture_path()}
    first = migrate_feeds(paths, tmp_path / "articles")
    second = migrate_feeds(paths, tmp_path / "articles")
    assert first["NYRB"].created == 2
    assert second["NYRB"].created == 0
    assert second["NYRB"].duplicates == 2
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest tests/test_migrate_legacy_xml.py -q`

Expected: FAIL because migration interfaces are absent.

- [ ] **Step 3: 实现 XML 到 Markdown 的幂等迁移**

使用 `ElementTree` 读取 XML；用 `markdownify` 将 `content:encoded` HTML 转为 Markdown，无法转换的原始 HTML 保留在正文中；从 pubDate 提取 `published_at` 和可用的 `article_date`；从 description 提取三段字段或旧标签字段。先建立现有 URL 索引，再创建新文件，绝不覆盖同 URL 文件。

- [ ] **Step 4: 对真实四个 XML 做 dry-run 统计**

Run: `python scripts/migrate_legacy_xml.py --dry-run --archive-root data/articles`

Expected: 输出 NYRB/LRB/TLS/NYT 各自 item、URL、可创建、重复和坏项统计；不产生文件，不修改 XML。

- [ ] **Step 5: 执行迁移并验证样本**

Run: `python scripts/migrate_legacy_xml.py --archive-root data/articles`

Expected: 四个来源的归档文件数与迁移统计一致；每个来源随机抽样至少 5 篇，frontmatter 有 URL/title/source，正文非空。

- [ ] **Step 6: 运行迁移测试**

Run: `python -m pytest tests/test_migrate_legacy_xml.py -q`

Expected: PASS，重复执行不新增文件，URL 和 item 统计无意外丢失。

- [ ] **Step 7: 提交迁移工具与历史归档**

提交前确认 `git diff -- nyt_ai_enhanced.xml` 仍显示用户原有修改，暂存时只添加迁移脚本、测试和 `data/articles/`。

```bash
git add scripts/migrate_legacy_xml.py tests/fixtures/legacy_sample.xml tests/test_migrate_legacy_xml.py data/articles
git commit -m "feat: migrate legacy RSS history into canonical archive"
```

### Task 5: 保持前端兼容并增加四个来源

**Files:**
- Modify: `app.js:5-8`
- Modify: `index.html:236-239`
- Create: `tests/frontend-sources.test.js`

**Interfaces:**
- `SOURCES` 保持现有对象结构 `{ id, shortName, name, file }`。
- 新增映射：`newyorker/NEWYORKER/纽约客`、`atlantic/ATLANTIC/大西洋月刊`、`larb/LARB/洛杉矶书评`、`publicbooks/PUBLICBOOKS/Public Books`。

- [ ] **Step 1: 写失败测试**

```javascript
const fs = require('node:fs');
const app = fs.readFileSync('app.js', 'utf8');
const html = fs.readFileSync('index.html', 'utf8');

for (const [id, file, label] of [
  ['newyorker', 'newyorker_ai_enhanced.xml', '纽约客'],
  ['atlantic', 'atlantic_ai_enhanced.xml', '大西洋月刊'],
  ['larb', 'larb_ai_enhanced.xml', '洛杉矶书评'],
  ['publicbooks', 'publicbooks_ai_enhanced.xml', 'Public Books']
]) {
  test(`contains ${id} source in app and navigation`, () => {
    assert.match(app, new RegExp(`id: '${id}'`));
    assert.match(app, new RegExp(`file: '${file}'`));
    assert.match(html, new RegExp(`data-source="${id}"`));
    assert.match(html, new RegExp(label));
  });
}
```

- [ ] **Step 2: 运行失败测试**

Run: `node --test tests/frontend-sources.test.js`

Expected: FAIL because the four new source entries are absent.

- [ ] **Step 3: 修改最小配置**

只在 `SOURCES` 数组和导航按钮中增加四个来源；不改 RSS 解析、搜索、日期分组、下载和 HTML 结构。同步更新页面 meta description 中的来源列表。

- [ ] **Step 4: 运行前端测试与既有测试**

Run: `node --test tests/*.test.js`

Expected: PASS，既有搜索/Markdown 测试和 8 来源静态配置测试全部通过。

- [ ] **Step 5: 提交**

```bash
git add app.js index.html tests/frontend-sources.test.js
git commit -m "feat: expose all eight RSS sources in frontend"
```

### Task 6: 以 fixture 完成完整本地流水线

**Files:**
- Modify: `scripts/import_sheet.py`
- Modify: `scripts/build_rss.py`
- Create: `tests/test_pipeline.py`
- Create: `tests/fixtures/expected_feed_checks.json`

**Interfaces:**
- 测试通过 `import_rows` 写入临时 archive，再通过 `write_feeds` 写入临时输出目录；不访问网络，不使用真实 Google Sheet。

- [ ] **Step 1: 写端到端失败测试**

```python
def test_fixture_pipeline_creates_archive_and_all_eight_valid_feeds(tmp_path):
    archive = tmp_path / "data" / "articles"
    output = tmp_path / "site"
    stats = import_rows(load_fixture_rows(), archive)
    counts = write_feeds(archive, output)
    assert stats.new_articles == 2
    assert counts["NYRB"] == 1
    assert counts["NYT"] == 1
    for filename in EXPECTED_FEED_FILES:
        root = ET.parse(output / filename).getroot()
        assert root.tag == "rss"
```

- [ ] **Step 2: 运行端到端测试**

Run: `python -m pytest tests/test_pipeline.py -q`

Expected: 若接口或 8 feed 映射不完整则 FAIL；修复只允许调整 importer/RSS 实现，不绕过 parser 校验。

- [ ] **Step 3: 补齐安全边界并通过测试**

确认：空 CSV 不产生文件；再次导入返回 `0 new articles`；坏行不阻止好行；RSS 任何一个 feed 失败时 8 个旧输出均不被替换。

- [ ] **Step 4: 运行全套 Python 与 JavaScript 测试**

Run: `python -m pytest -q; node --test tests/*.test.js`

Expected: 全部 PASS。

- [ ] **Step 5: 提交端到端测试**

```bash
git add tests/test_pipeline.py tests/fixtures/expected_feed_checks.json scripts/import_sheet.py scripts/build_rss.py
git commit -m "test: verify sheet archive and rss pipeline end to end"
```

### Task 7: 更新文档与 GitHub Actions，但保留生产切换闸门

**Files:**
- Modify: `.github/workflows/main.yml`
- Modify: `README.md`
- Create: `.github/workflows/v2-validation.yml`
- Modify: `.gitignore`

**Interfaces:**
- workflow 使用 `SHEET_CSV_URL: ${{ vars.SHEET_CSV_URL }}`，不使用 secrets 中的 AI key。
- `v2-validation.yml` 支持 `workflow_dispatch`，运行 fixture/迁移/RSS/XML 校验，不连接真实 Sheet。
- `main.yml` 的正式切换在 Phase 0 通过后执行；切换前不得删除旧脚本或修改生产 DeepSeek 步骤。

- [ ] **Step 1: 写 workflow 静态验收测试**

```python
def test_v2_workflow_has_no_ai_api_dependency():
    text = Path('.github/workflows/v2-validation.yml').read_text(encoding='utf-8')
    assert 'DEEPSEEK_API_KEY' not in text
    assert 'openai' not in text.lower()
    assert 'workflow_dispatch' in text
```

- [ ] **Step 2: 运行静态验收并确认初始失败**

Run: `python -m pytest tests/test_workflow_config.py -q`

Expected: FAIL until the validation workflow exists with the required fields.

- [ ] **Step 3: 添加 v2 validation workflow 和 README 配置说明**

validation workflow 安装 `requirements.txt`，运行 `pytest`、`node --test`，运行 RSS XML parser 校验；README 说明 Sheet 表头、`SHEET_CSV_URL` Repository Variable、NYT raw 输入和 Phase 0 门槛。`.gitignore` 只忽略临时测试输出，不忽略 `data/articles/` 或 `raw/nyt/`。

- [ ] **Step 4: 运行 workflow/文档测试**

Run: `python -m pytest tests/test_workflow_config.py -q`

Expected: PASS，validation workflow 明确不包含 `openai`、`DEEPSEEK_API_KEY`，并保留手动触发入口。

- [ ] **Step 5: 提交非生产验证 workflow 和文档**

```bash
git add .github/workflows/v2-validation.yml README.md .gitignore tests/test_workflow_config.py
git commit -m "docs: document v2 validation workflow and sheet setup"
```

- [ ] **Step 6: 等待外部 Phase 0 验证**

用户在 ChatGPT 中完成：普通对话写测试 Sheet、一次性 Scheduled Task 无人值守追加第二行，并确认不需要人工批准。若失败，保留旧 `main.yml` 生产链路，不执行下一步。

- [ ] **Step 7: Phase 0 通过后切换正式 workflow**

将 `main.yml` 改为 checkout→setup-python→安装最小依赖→`import_sheet.py`→`build_rss.py`→测试/XML 校验→仅变化时提交；调度改为每天多次并保留 `workflow_dispatch`。此时移除 `openai` 安装、`DEEPSEEK_API_KEY` 环境变量和 AI 调用步骤；旧 `nyrb_rss.py`、`lrb_rss.py`、`tls_rss.py` 移入 `legacy/`，不删除历史文件。

- [ ] **Step 8: 切换后验证并提交**

Run: `python -m pytest -q; node --test tests/*.test.js`

Expected: 全部测试通过；`git diff --check` 通过；工作区只保留用户原有 `nyt_ai_enhanced.xml` 修改或已明确处理的迁移产物。

```bash
git add .github/workflows/main.yml legacy README.md
git commit -m "feat: switch production workflow to sheet archive pipeline"
```

### Task 8: 生产前后验收与回归检查

**Files:**
- Create: `scripts/validate_release.py`
- Create: `tests/test_validate_release.py`
- Modify: `README.md`

**Interfaces:**
- `validate_release(repo_root: Path) -> ValidationReport`：检查 8 个 XML 可解析、每个来源只含对应 source、所有 published archive URL 在对应 RSS 中出现、旧来源迁移样本存在、前端 8 个来源配置存在。
- `ValidationReport.ok: bool` 和 `ValidationReport.errors: list[str]`。

- [ ] **Step 1: 写失败测试**

```python
def test_validate_release_reports_missing_feed(tmp_path):
    report = validate_release(tmp_path)
    assert report.ok is False
    assert any('publicbooks_ai_enhanced.xml' in error for error in report.errors)
```

- [ ] **Step 2: 实现只读发布校验器**

校验器不得修改文件；逐个读取 8 个 XML 和 Markdown frontmatter，发现缺失、XML parse error、source 混入、URL 丢失或前端配置缺失时返回错误列表并以非零状态退出。

- [ ] **Step 3: 运行发布前检查**

Run: `python scripts/validate_release.py; git diff --check`

Expected: 8 个 RSS 均可解析、历史迁移和新增 fixture 均通过，且无 whitespace error。

- [ ] **Step 4: 运行最终全套测试**

Run: `python -m pytest -q; node --test tests/*.test.js`

Expected: 全部 PASS。

- [ ] **Step 5: 提交发布校验器**

```bash
git add scripts/validate_release.py tests/test_validate_release.py README.md
git commit -m "test: add eight-source release validation"
```

## Execution Notes

- 每个 Task 完成后先运行该 Task 的专用测试，再运行相关回归测试，然后才提交。
- 迁移真实 XML 前必须保留 Git 可回退点；不得使用 `git reset --hard` 或覆盖用户未提交的 NYT XML。
- 生产 workflow 的 DeepSeek 清理严格位于 Task 7 的 Phase 0 之后；之前只能开发和验证新链路。
- `raw/nyt/` 的本地采集任务不在本计划中实现中文精读或模型调用；本计划只保证 GitHub 归档/RSS 能消费 Scheduled Task 最终写入的 NYT Sheet 行。
