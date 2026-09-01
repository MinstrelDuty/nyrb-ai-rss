# nyrb-ai-rss v2：八来源归档与发布设计

## 1. 目标与边界

本次改造将日常内容生产与机械发布拆开：ChatGPT Scheduled Task 负责发现、阅读、核验和写入 Google Sheet；GitHub Actions 只负责读取公开 CSV、验证、去重、生成 Markdown 归档与 RSS，并继续通过 GitHub Pages 提供网页。

第一批正式来源为：`NYRB`、`LRB`、`TLS`、`NYT`、`NEWYORKER`、`ATLANTIC`、`LARB`、`PUBLICBOOKS`。

本项目不使用 OpenAI API、DeepSeek API 或其他模型 API；不引入数据库、服务端、登录、前端框架重写或新的托管平台。现有网页外观和 RSS 兼容格式优先保留。

## 2. 数据流

七个普通来源由 Scheduled Task 直接发现和处理：

```text
NYRB / LRB / TLS / NEWYORKER / ATLANTIC / LARB / PUBLICBOOKS
        ↓
ChatGPT Scheduled Task
        ↓
Google Sheet → Published CSV
```

NYT 只在正文采集层采用不同方案：

```text
NYT Book Review
        ↓
本地浏览器或本地采集任务（只采集用户有权访问的正文）
        ↓
raw/nyt/*.md → GitHub
        ↓
ChatGPT Scheduled Task 读取 raw 正文并写入同一 Google Sheet
```

之后所有来源统一进入：

```text
Published CSV
        ↓
scripts/import_sheet.py
        ↓
data/articles/<source>/*.md
        ↓
scripts/build_rss.py
        ↓
8 个 RSS XML → GitHub Pages
```

NYT 的 raw 文件是输入缓存和原始采集档案，不是最终发布归档；不在 raw 阶段生成中文精读。

## 3. 目录与组件

```text
scripts/
  utils.py
  import_sheet.py
  build_rss.py
  migrate_legacy_xml.py

raw/
  nyt/

data/
  articles/
    nyrb/
    lrb/
    tls/
    nyt/
    newyorker/
    atlantic/
    larb/
    publicbooks/

tests/
  fixtures/sample_sheet.csv
  test_import_sheet.py
  test_build_rss.py
  test_migrate_legacy_xml.py
```

`import_sheet.py`、`build_rss.py` 和迁移脚本必须是可独立运行、可测试的纯机械工具，不导入任何模型客户端。

现有 `index.html`、`app.js`、`web-core.js` 继续保留。前端只需在来源配置和导航中增加四个来源时，不得重写现有前端结构。

## 4. Sheet 数据协议

Sheet 第一行为固定字段：

```text
source,url,original_title,title_zh,author_subject,hook,body_markdown,article_date,processed_at,image_url,status
```

必填字段为 `source`、`url`、`original_title`、`title_zh`、`author_subject`、`hook`、`body_markdown`、`processed_at`。`article_date`、`image_url`、`status` 可选；缺省 `status` 按 `published` 处理。

允许的 `source` 只有：

```text
NYRB LRB TLS NYT NEWYORKER ATLANTIC LARB PUBLICBOOKS
```

只有 `status=published` 的记录进入正式 RSS 和最终归档。`partial`、`error` 或其他非 published 记录记录 warning 并跳过，不覆盖已有文章。

CSV 必须使用 Python 标准 `csv` 模块解析，正确支持多行 Markdown、引号、Unicode 和空字段。

## 5. URL、归档与稳定身份

URL 规范化由 `utils.py` 统一完成：去掉 fragment，移除明确的追踪参数，保留影响文章身份的 query 参数，统一末尾斜杠规则。规范化后的 URL 是唯一去重键。

稳定 ID 为：

```text
<source lowercase>-sha256(normalized_url)[:12]
```

新文章优先使用：

```text
YYYY-MM-DD-<url-slug>.md
```

日期优先取合法的 `article_date`；缺失时不伪造文章日期，改用 `<source>-<hash>.md`。如同一日期和 slug 冲突，以稳定 ID 补充文件名，不能覆盖已有文件。

每篇最终 Markdown 至少包含 YAML frontmatter：

```yaml
---
id: "lrb-<stable-id>"
source: "LRB"
url: "https://..."
original_title: "..."
title_zh: "..."
author_subject: "..."
hook: "..."
article_date: "YYYY-MM-DD"
processed_at: "ISO-8601"
image_url: "https://..."
status: "published"
---
```

迁移历史 XML 时可额外保存 `published_at`，以保留旧 RSS 原始发布时间和排序；新 Sheet 记录没有该字段时，RSS 时间优先使用 `article_date`，其次使用 `processed_at`。

重复 URL 默认跳过，不覆盖历史 AI 内容，不实现 `force_update` 或复杂版本管理。

## 6. CSV 导入器

`import_sheet.py` 的职责：

1. 从命令行参数或 `SHEET_CSV_URL` 读取 CSV 地址。
2. 检查 HTTP 状态和下载内容。
3. 解析并验证表头、字段、source、状态和时间格式。
4. 扫描已有 Markdown frontmatter 建立 URL 索引。
5. 对合法、published 且未出现过的行创建 Markdown。
6. 对坏行记录 warning 后继续处理其他行。
7. 输出 fetched rows、valid rows、new articles、duplicate rows、invalid rows。

下载失败、空地址或 CSV 无法解析时必须失败或安全跳过，绝不能清空 `data/`、删除旧 XML 或写出空 RSS。写文件采用临时文件或先完整生成后替换，避免单条异常留下半篇归档。

脚本禁止调用 AI、修改 Google Sheet 或猜测缺失内容。缺少必要字段的记录必须跳过。

## 7. RSS 构建器

`build_rss.py` 从全部最终 Markdown 归档生成：

```text
nyrb_ai_enhanced.xml
lrb_ai_enhanced.xml
tls_ai_enhanced.xml
nyt_ai_enhanced.xml
newyorker_ai_enhanced.xml
atlantic_ai_enhanced.xml
larb_ai_enhanced.xml
publicbooks_ai_enhanced.xml
```

每个来源只包含相同 source 的 `published` 文章，按 RSS 发布时间倒序。每个 item 保留前端和订阅器需要的：

```xml
<title>
<link>
<guid isPermaLink="false">
<pubDate>
<description>
<content:encoded>
```

`description` 继续使用：

```text
中文标题|||作者与对象|||一句话破题
```

`content:encoded` 由 Markdown 转 HTML，并可在开头保留 `image_url` 图片。XML 文本和 CDATA 必须使用安全转义，特别处理 `]]>`，禁止因中文、引号、& 或 Markdown 内容导致 XML 无法解析。

RSS 只是派生输出，不再作为历史数据库。构建失败时不应覆盖现有正常 XML。

## 8. 历史迁移

第一阶段迁移现有 NYRB、LRB、TLS、NYT XML；NEWYORKER、ATLANTIC、LARB、PUBLICBOOKS 从 v2 启用后开始积累。

`migrate_legacy_xml.py` 先读取 XML、统计 item 数和 URL 数，再把每个 item 转成最终 Markdown。旧的 description 兼容两种形态：现有 `|||` 三段式，以及带 `【中文标题】`、`【作者与对象】`、`【一句话破题】`、`【正文】` 标签的旧格式。正文 HTML 转 Markdown 时应尽量保留标题、段落、列表、链接和图片；无法安全转换的原始 HTML 可存入正文，不得静默丢失。

迁移前保留原 XML 备份或由 Git 历史提供可回退版本。迁移后验证每个来源的 item 数、URL 集合、最旧/最新样本、中文标题和正文可显示性。迁移脚本必须幂等，不能覆盖已有同 URL 归档。

当前未提交的 `nyt_ai_enhanced.xml` 用户修改属于已有工作，迁移和实现时必须保留，不能用旧版本覆盖。

## 9. GitHub Actions 与切换策略

workflow 使用 `actions/checkout`、`actions/setup-python` 和最小依赖；不安装 `openai`，不读取 `DEEPSEEK_API_KEY`，保留 `workflow_dispatch`，并改为每天多次轻量运行。

推荐步骤：

```text
checkout
→ setup-python
→ 安装 requests、markdown、pytest 等最小依赖
→ import_sheet.py
→ build_rss.py
→ pytest 与 XML 校验
→ 仅在有变化时提交 data/、raw/（如纳入）和 8 个 XML
```

`SHEET_CSV_URL` 使用 GitHub Repository Variable 或其他不含私人账号信息的配置，不硬编码。未配置时 workflow 必须明确失败或安全跳过，不能生成空 RSS。

只有在本地 fixture、历史迁移、测试 Sheet 和 GitHub Pages 兼容性均验证后，且用户完成 Phase 0：确认 Scheduled Task 可以无人值守写入测试 Sheet，才能删除生产 workflow 中的 DeepSeek 步骤。旧脚本在此之前保留在 `legacy/` 或原位置，不直接删除。

## 10. 前端兼容

现有前端已支持 NYRB、LRB、TLS、NYT 的 RSS 解析、搜索、日期分组和 Markdown 下载。只增加 NEWYORKER、ATLANTIC、LARB、PUBLICBOOKS 的来源配置、显示名和导航，不引入新框架。

RSS 字段保持兼容后，现有文章展开、全文搜索、单来源下载和全部归档下载行为不改变。前端改动应补充来源数量和 XML 解析回归测试，但不作为后台重构的前置依赖。

## 11. 测试与验收

测试至少覆盖：

- CSV 正常行、中文、多行 Markdown、引号和 Unicode；
- 缺失必填字段、非法 source、非 published、空 CSV、下载失败；
- canonical URL 去重和已归档跳过；
- 八来源分离、稳定 guid、排序、CDATA、中文标题和 Markdown→HTML；
- XML 可由标准 parser 解析；
- 历史 XML 迁移的 item/URL 数量和每来源至少五篇抽样；
- 无新增文章时不改变归档和 XML；
- 构建失败时不清空或覆盖旧产物；
- 前端能加载八个 XML，搜索和下载行为保持可用。

最终切换前必须满足：八来源均可进入统一归档；NYT raw→Scheduled Task→Sheet→archive 链路可用；Google Sheet 写入测试无需人工批准；GitHub Actions 不包含任何 AI API；历史文章仍可访问；八个 RSS 和 GitHub Pages 均正常。

