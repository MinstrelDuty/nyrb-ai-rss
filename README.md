# nyrb-ai-rss
书评深度集萃 https://minstrelduty.github.io/nyrb-ai-rss/

## v2 数据链路

v2 支持 NYRB、LRB、TLS、NYT、NEWYORKER、ATLANTIC、LARB、PUBLICBOOKS 八个来源。

七个普通来源由 ChatGPT Scheduled Task 阅读、核验并写入 Google Sheet；NYT Book Review 由本地采集任务保存到 `raw/nyt/`，再由 Scheduled Task 读取并写入同一张 Sheet。GitHub Actions 不负责阅读文章，也不调用任何 AI API，只处理已发布 CSV、Markdown 归档和 RSS。

## 本地验证

安装 Python 依赖后运行：

```bash
python -m pip install -r requirements.txt
python -m pytest -q
node --test "tests/*.test.js"
```

历史归档位于 `data/articles/<source>/`，每篇文章使用 YAML frontmatter 保存来源、原文 URL、标题、状态和处理时间。RSS XML 是由归档生成的派生文件，不再作为数据库。

## Google Sheet 配置

正式 Sheet 的第一行固定为：

```text
source,url,original_title,title_zh,author_subject,hook,body_markdown,article_date,processed_at,image_url,status
```

将发布到 Web 的 CSV 地址保存为 GitHub Repository Variable：`SHEET_CSV_URL`。CSV 不能包含密钥或私人信息。`status` 不是 `published` 的记录不会进入正式归档和 RSS；重复 canonical URL 会被跳过。

## NYT 采集边界

`raw/nyt/` 只保存用户本来有权访问的 NYT Book Review 正文和原始元数据。本地采集层不生成中文精读；正文不足时不使用搜索摘要补全。正文进入 GitHub 后，由 Scheduled Task 负责精读并写入 Google Sheet。

## 切换生产链路

在普通 ChatGPT 对话和一次性 Scheduled Task 都成功无人值守写入测试 Sheet、且不要求人工批准前，不关闭旧生产流水线。确认 Phase 0 通过后，才将正式 workflow 切换到 `scripts/import_sheet.py` → `scripts/build_rss.py`，并删除旧 DeepSeek/API 依赖。项目不需要大模型 API key。
