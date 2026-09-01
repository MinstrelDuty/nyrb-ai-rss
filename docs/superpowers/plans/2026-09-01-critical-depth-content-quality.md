# Critical-Depth Content Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the article-generation contract so Chinese book-review introductions are evidence-based, type-aware, critically useful, and safe to publish through the existing Google Sheet → Markdown → RSS pipeline.

**Architecture:** Keep ChatGPT Scheduled Task responsible for reading source material, building an internal evidence card, and writing the final Sheet row. Keep GitHub Actions mechanical: validate CSV, preserve optional quality metadata, archive published rows, and build RSS. A manual ChatGPT experiment with fixed NYT samples is a gate before changing production prompts or removing the DeepSeek workflow.

**Tech Stack:** Markdown prompt artifacts, Google Sheet CSV schema, Python `csv`/frontmatter importer, pytest, existing RSS builder, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-01-critical-depth-content-quality-design.md`

## Global Constraints

- Do not call OpenAI, DeepSeek, or any other model API from GitHub Actions.
- Do not remove the production DeepSeek workflow until the user confirms the Phase 0 Scheduled Task → Google Sheet test succeeds.
- Preserve the existing required Sheet columns and accept old rows without the new optional quality columns.
- Publish only rows with `status=published`; rows with `status=review` must not enter Markdown or RSS.
- Do not publish guessed author, title, date, or recommendation metadata.
- Do not silently overwrite an existing archive article with the same canonical URL.

---

### Task 1: Create the critical-depth prompt and manual evaluation pack

**Files:**
- Create: `docs/prompts/critical-depth-v1.md`
- Create: `docs/evals/critical-depth-nyt-eval.md`
- Modify: none

**Interfaces:**
- Consumes: the article title and full source text supplied to a ChatGPT Scheduled Task.
- Produces: one Sheet-compatible row with the existing fields plus optional `article_type`, `source_thesis`, `evidence_notes`, `critical_context`, `counterpoint`, `confidence`, and `verification_note`.

- [ ] **Step 1: Write the prompt artifact**

Create a copy-pasteable prompt with these exact output requirements:

```text
你是一位严谨的文学与文化评论主笔。你的任务不是把文章写长，而是让每个判断都能回到原文。

先在内部完成证据卡，再输出最终结果。不要输出证据卡的推理过程，只输出下列字段。

一、文章类型：从 book_review、book_list、essay、obituary、poetry、film_art、news_commentary、other 中选择一个。
二、中文标题：准确翻译，不添加原题没有的判断。
三、作者与对象：只填写原文明确或已核验的信息；无法确认时写“原文未明确”。
四、一句话破题：40-60 个汉字，指出核心冲突或判断，不要重复文章主题。
五、原文核心论点：用一两句话复述作者实际提出的判断，不把你的联想伪装成原文观点。
六、证据：列出 2-4 个原文明确出现的细节、例证、概念或叙事转折。
七、批评性分析：说明论点使用的框架，以及它与何种具体传统或争论有关；没有充分依据时不要罗列理论名词。
八、张力与限度：指出盲点、反例、证据边界或原文没有展开的另一种解释；没有依据时写“原文未展开”。
九、延伸阅读：只推荐能够确认真实存在且与本文有明确关系的作品；无法确认就省略。
十、置信度：high、medium 或 low。作者、书名、日期或推荐书目无法确认时必须降低置信度。

最终正文必须使用以下 Markdown 标题：
### 📰 核心脉络
### 🧠 批评性分析
### ⚖️ 张力与限度
### 📚 延伸阅读

事实、原文观点和你的分析要分开。不得编造书名、作者、出版信息、机构、引文或学术争论。出现关键事实冲突时，将 status 写为 review，并在 verification_note 说明冲突。
```

- [ ] **Step 2: Write the fixed NYT evaluation set**

Create an evaluation sheet containing six fixed cases from the current NYT archive: a single-book review, a book list, a cultural essay, an obituary, a short review, and one special-format item. Record each case by source URL and local XML item position so the same inputs can be rerun.

- [ ] **Step 3: Write the scoring rubric**

Score each output from 0 to 2 on: clear thesis, source-grounded evidence, concrete critical analysis, explicit limits, factual reliability, and type fit. Require an average of at least 9/12 and a factual-reliability score of 2 on every sample.

- [ ] **Step 4: Run the prompt manually in ordinary ChatGPT**

Paste the prompt and one fixed NYT article at a time. Save the six outputs outside the repository or in the evaluation document, record scores, and mark every unsupported factual claim. Do not use these outputs in production yet.

- [ ] **Step 5: Commit the prompt and evaluation pack**

```bash
git add docs/prompts/critical-depth-v1.md docs/evals/critical-depth-nyt-eval.md
git commit -m "docs: add critical-depth prompt evaluation pack"
```

**Gate:** Do not start Task 2 until the six-sample evaluation meets the rubric or the user approves a revised prompt after reviewing the failures.

### Task 2: Preserve quality metadata and enforce the publish gate in the importer

**Files:**
- Modify: `scripts/import_sheet.py`
- Test: `tests/test_import_sheet.py`
- Modify: `tests/fixtures/sample_sheet.csv`

**Interfaces:**
- Consumes: the current required columns and optional quality columns from `csv.DictReader`.
- Produces: Markdown frontmatter containing the optional quality metadata; `status=review` rows are skipped; published rows containing prohibited public placeholders are rejected.

- [ ] **Step 1: Write failing importer tests**

Add tests that assert:

```python
def make_row(**overrides):
    row = {
        "source": "NYT",
        "url": "https://example.com/nyt/quality",
        "original_title": "Quality",
        "title_zh": "质量测试",
        "author_subject": "作者与对象",
        "hook": "核心判断",
        "body_markdown": "### 🧠 批评性分析\n具体分析",
        "article_date": "2026-09-01",
        "processed_at": "2026-09-01T00:00:00+00:00",
        "status": "published",
        "article_type": "book_review",
        "confidence": "high",
        "verification_note": "",
    }
    row.update(overrides)
    return row

def test_import_preserves_optional_quality_metadata(tmp_path):
    stats = import_rows([{
        "source": "NYT",
        "url": "https://example.com/nyt/quality",
        "original_title": "Quality",
        "title_zh": "质量测试",
        "author_subject": "作者与对象",
        "hook": "核心判断",
        "body_markdown": "### 🧠 批评性分析\n具体分析",
        "article_date": "2026-09-01",
        "processed_at": "2026-09-01T00:00:00+00:00",
        "status": "published",
        "article_type": "book_review",
        "confidence": "high",
        "verification_note": "",
    }], tmp_path / "articles")
    text = next((tmp_path / "articles").rglob("*.md")).read_text(encoding="utf-8")
    assert "article_type: book_review" in text
    assert "confidence: high" in text
    assert stats.new_articles == 1

def test_import_skips_review_rows(tmp_path):
    stats = import_rows([make_row(status="review")], tmp_path / "articles")
    assert stats.new_articles == 0

def test_import_rejects_published_guess_placeholder(tmp_path):
    row = make_row(body_markdown="根据常见书目推断，作者可能是某人。")
    stats = import_rows([row], tmp_path / "articles")
    assert stats.new_articles == 0
    assert stats.invalid_rows == 1
```

- [ ] **Step 2: Run the importer tests and verify the expected failures**

Run: `python -m pytest tests/test_import_sheet.py -q`

Expected: failures because quality columns are not currently preserved, review rows are handled only incidentally, and published placeholder text is not rejected.

- [ ] **Step 3: Implement the minimal importer changes**

Extend `OPTIONAL_COLUMNS` with:

```python
("article_date", "image_url", "status", "article_type", "source_thesis",
 "evidence_notes", "critical_context", "counterpoint", "confidence",
 "verification_note")
```

Preserve these values in `_render_article`. Normalize empty `confidence` to `medium` for backward-compatible old rows. Before writing a `published` row, reject only these public placeholder patterns: `根据常见书目推断`, `未获取中文标题`, `未获取作者与对象`, and `未获取破题`. Keep `status=review` as a skip, not an invalid row.

- [ ] **Step 4: Run the importer tests and the full Python suite**

Run: `python -m pytest tests/test_import_sheet.py -q`

Expected: all importer tests pass.

Run: `python -m pytest -q`

Expected: all existing tests plus the new tests pass.

- [ ] **Step 5: Commit the importer gate**

```bash
git add scripts/import_sheet.py tests/test_import_sheet.py tests/fixtures/sample_sheet.csv
git commit -m "feat: preserve review quality metadata in archive import"
```

### Task 3: Make the quality gate visible in archive and release validation

**Files:**
- Modify: `scripts/build_rss.py`
- Modify: `scripts/validate_release.py`
- Test: `tests/test_build_rss.py`
- Test: `tests/test_validate_release.py`

**Interfaces:**
- Consumes: published Markdown frontmatter and body generated by the importer.
- Produces: RSS containing only published articles and release errors for published rows with invalid quality metadata or public placeholders.

- [ ] **Step 1: Write failing release tests**

Add cases proving that a `review` archive file is absent from the RSS and that a published file containing a prohibited placeholder causes `validate_release()` to return `ok=False` with the file path in `errors`.

- [ ] **Step 2: Run the focused tests and verify red**

Run: `python -m pytest tests/test_build_rss.py tests/test_validate_release.py -q`

Expected: the new invalid-quality case fails because release validation currently checks links and frontend configuration only.

- [ ] **Step 3: Implement the minimal validation**

In `validate_release()`, inspect every Markdown file loaded from `data/articles` and report the exact path when a published article contains a prohibited placeholder or has `status=review` but is included in a feed. Keep the existing archive URL and eight-feed checks unchanged.

- [ ] **Step 4: Run focused and full tests**

Run: `python -m pytest tests/test_build_rss.py tests/test_validate_release.py -q`

Expected: all focused tests pass.

Run: `python -m pytest -q`

Expected: the complete Python suite passes.

- [ ] **Step 5: Commit release validation**

```bash
git add scripts/build_rss.py scripts/validate_release.py tests/test_build_rss.py tests/test_validate_release.py
git commit -m "test: enforce critical-depth release quality gate"
```

### Task 4: Document Scheduled Task rollout and Phase 0 production switch

**Files:**
- Modify: `README.md`
- Modify: `.github/workflows/v2-validation.yml`
- Create: `.github/workflows/main.yml` replacement only after Phase 0 approval
- Test: `tests/test_workflow_config.py`

**Interfaces:**
- Consumes: the approved prompt, public Google Sheet CSV URL, and optional NYT `raw/nyt` input.
- Produces: a documented production workflow that imports the Sheet, archives published content, builds all eight RSS feeds, and does not call any AI API.

- [ ] **Step 1: Add tests for the post-Phase-0 workflow contract**

After Phase 0 is confirmed, assert that the production workflow references `scripts/import_sheet.py` and `scripts/build_rss.py`, grants only `contents: write`, contains no `DEEPSEEK_API_KEY`, and lists all eight RSS outputs. Before that confirmation, keep these assertions in a separate review note and leave the active production workflow unchanged.

- [ ] **Step 2: Run the workflow tests and keep the production workflow unchanged before Phase 0**

Run: `python -m pytest tests/test_workflow_config.py -q`

Expected before Phase 0: the active workflow tests remain green and `.github/workflows/main.yml` is unchanged; the post-switch assertions are not activated until the gate is passed.

- [ ] **Step 3: After the user confirms Phase 0, replace the production steps**

Use the approved prompt in the Scheduled Task, configure the public Sheet CSV URL secret, run `python scripts/import_sheet.py --csv-url "$SHEET_CSV_URL"`, run `python scripts/build_rss.py`, archive Markdown changes, and commit all eight XML files. Remove the DeepSeek environment variable and old AI-generation commands only in this step.

- [ ] **Step 4: Run the full release verification**

Run: `python -m pytest -q`

Run: `node --test tests\\*.test.js`

Run the release validator against a temporary build directory and confirm all eight feeds parse and match the Markdown archive.

- [ ] **Step 5: Commit and update the existing Pull Request**

```bash
git add README.md .github/workflows/main.yml .github/workflows/v2-validation.yml tests/test_workflow_config.py
git commit -m "feat: switch production feed generation to scheduled sheet import"
git push
```

Do not merge the Pull Request until the release checks and the user’s live Scheduled Task test are both confirmed.

