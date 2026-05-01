import os
import re
import time
import logging
import requests
import markdown
import xml.etree.ElementTree as ET
from email.utils import formatdate
from openai import OpenAI

# ==========================================
# 0. 基础配置
# ==========================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 从 GitHub Secrets 中读取 API Key
api_key = os.getenv("DEEPSEEK_API_KEY", "").strip(" '\"\n\r\t")
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

XML_FILE = 'nyt_ai_enhanced.xml'
MAX_HISTORY = 150
NYT_RSS_URL = "https://rss.nytimes.com/services/xml/rss/nyt/Books/Review.xml"

# 基础请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

# ==========================================
# 1. 历史数据读取与 RSS 最新链接抓取
# ==========================================

def get_existing_items():
    """读取已生成的 XML 以防重复抓取和扣费"""
    existing_urls = set()
    existing_items_xml = []
    if os.path.exists(XML_FILE):
        try:
            with open(XML_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
            item_blocks = re.findall(r'<item>.*?</item>', content, re.DOTALL)
            for block in item_blocks:
                existing_items_xml.append(block)
                link_match = re.search(r'<link>(.*?)</link>', block)
                if link_match:
                    existing_urls.add(link_match.group(1).strip())
        except Exception as e:
            logging.error(f"读取历史 XML 失败: {e}")
    return existing_urls, existing_items_xml


def get_latest_article_urls(existing_urls, max_items=30):
    """抓取纽约时报书评的官方 RSS 并在源头清洗链接"""
    urls = []
    try:
        logging.info(f"正在扫描 NYT 官方 RSS 目录: {NYT_RSS_URL}")
        response = requests.get(NYT_RSS_URL, headers=HEADERS, timeout=20)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        for item in root.findall('.//item'):
            link = item.find('link').text
            if not link:
                continue
                
            # 清理 NYT 链接的追踪后缀，保持链接纯净，防止防重机制失效
            clean_link = link.split('?')[0]
            
            if clean_link not in urls and clean_link not in existing_urls:
                urls.append(clean_link)
                if len(urls) >= max_items:
                    break
    except Exception as e:
        logging.error(f"抓取 NYT RSS 链接失败: {e}")

    logging.info(f"RSS 扫描完毕，本次共有 {len(urls)} 篇纯新文章需要处理。")
    return urls

# ==========================================
# 2. 核心引擎：Jina 穿透抓取与 AI 满级深度处理
# ==========================================

def scrape_article(url):
    """通过 Jina API 穿透 NYT 网页结构，提取纯净正文"""
    logging.info(f"🌀 启动 Jina 提取正文 -> {url}")
    try:
        jina_url = f"https://r.jina.ai/{url}"
        headers = {"Accept": "text/plain"}
        response = requests.get(jina_url, headers=headers, timeout=40)
        response.raise_for_status()
        text = response.text
        
        # Jina 提取的是纯文本，我们用 URL 最后一段作为临时原版标题
        fallback_title = url.split('/')[-1].replace('.html', '').replace('-', ' ').title()
        
        return {"title": fallback_title, "url": url, "text": text, "image_url": ""}
    except Exception as e:
        logging.error(f"抓取正文失败: {url} - {e}")
        return None

def process_with_ai(article_data):
    """调用满级提示词，并使用正则精确切割前端需要的结构化数据"""
    text = article_data.get("text", "")

    if len(text) < 100:
        return "无中文标题", "✍️ 未获取作者与对象", "未获取破题", "<p>文章内容过短或 Jina 提取失败。</p>"

    # 截断超长文本
    text = text[:80000]

    system_prompt = """你是一位为时间宝贵的精英读者写作的资深主笔。请基于提供的文章撰写精读报告。
【最高指令】：总字数严格控制在600字左右！严禁以“想象一下”等呆板词汇开头。
（🔔 特别注意：如果检测到本文是一首诗歌、短篇小说或极短篇随笔，请自动将“独立点评”和“脉络梳理”调整为【文学赏析与意境解读】风格，延伸阅读可推荐相关的诗集或文学评论。）

请务必严格按照以下带有【】的标签格式输出，不要有任何偏差：

【中文标题】
直接写出英文标题的精准且具有吸引力的中文翻译

【作者与对象】
格式必须为：“✍️ 作者：[文章作者名] ｜ 🎯 探讨对象：[如果是书评，写《书名》及原书作者；如果是展览/电影/政治事件，写明具体名称；如果是独立随笔，写“独立随笔”]”

【一句话破题】
用一句极具张力的话（不超过40字），直接点破这篇文章的核心冲突或洞见

【正文】
（从这里开始使用Markdown排版）
### 📰 核心脉络
（约300）语言要极具可读性，像讲故事一样梳理文章逻辑，必须精准嵌入2-3个核心细节（如关键史实、概念或人物）。

### 🧠 独立点评
（约200字）必须进行学术史层面的考察。指出文章在思想史或学术界的坐标，它回应了什么争论？延续或挑战了哪种范式？

### 📚 延伸矩阵
（🚨 绝对铁律：推荐的所有书籍必须是【现实中真实存在的出版物】，严禁AI伪造书名或作者！宁可推荐稍微宽泛但真实的经典著作，也绝不能编造！每本书需用1-2句话详实介绍其学术价值）
- **核心相关（1本）**：与文章探讨的具体对象直接相关。
- **相同脉络（1本）**：与作者理论底色相同或同属一个思想谱系。
- **不同观点（1-2本）**：提供截然不同的解释框架或反面视角的著作。"""

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"原始英文素材（参考标题：{article_data['title']}）：\n{text}"}
                ],
                max_tokens=4000, temperature=0.6
            )
            ai_text = response.choices[0].message.content

            # ==========================================
            # 🔪 基于【标签】的正则截取引擎
            # ==========================================
            try:
                zh_title = re.search(r'【中文标题】(.*?)【作者与对象】', ai_text, re.S).group(1).strip().replace('\n', ' ')
                meta_info = re.search(r'【作者与对象】(.*?)【一句话破题】', ai_text, re.S).group(1).strip().replace('\n', ' ')
                hook = re.search(r'【一句话破题】(.*?)【正文】', ai_text, re.S).group(1).strip().replace('\n', ' ')
                body_md = re.search(r'【正文】(.*)', ai_text, re.S).group(1).strip()
            except AttributeError:
                # 容错降级：如果 AI 抽风没有输出标准标签
                logging.warning("AI 输出未完全遵循标签格式，触发降级解析...")
                zh_title = "智能解析遇到偏差"
                meta_info = "✍️ 作者信息待确认 ｜ 🎯 探讨对象待确认"
                hook = "核心洞见提取失败，请直接阅读正文。"
                body_md = ai_text.replace("【中文标题】", "").replace("【作者与对象】", "").replace("【一句话破题】", "").replace("【正文】", "")

            # 使用 markdown 库转成 HTML，装入 div
            ai_html = markdown.markdown(body_md, extensions=['extra'])
            wrapper = f'<div style="font-size:16px; line-height:1.6; color:#333;">{ai_html}</div>'

            return zh_title, meta_info, hook, wrapper

        except Exception as e:
            if '429' in str(e):
                logging.warning("API 频率限制，沉睡 30 秒...")
                time.sleep(30)
            else:
                logging.error(f"AI 处理错误: {e}")
                return "API错误", "API错误", "API错误", f"<p style='color:red;'>AI 错误: {e}</p>"

    return "触发限制", "触发限制", "触发限制", "<p style='color:red;'>跳过此文章摘要。</p>"


# ==========================================
# 3. 主程序装配与打包发布
# ==========================================

def main():
    if not api_key:
        logging.error("未找到 DEEPSEEK_API_KEY 环境变量！")
        return

    existing_urls, existing_items_xml = get_existing_items()

    # NYT 单次处理篇数建议控制在 30 篇左右，保护 API
    urls = get_latest_article_urls(existing_urls, max_items=30)

    if not urls:
        logging.info("🎉 当前期 NYT 所有文章已处理完毕或无更新。本次未消耗 AI Token。")
        return

    new_items_xml = []
    for url in urls:
        logging.info(f"✨ 正在处理 NYT 新文章: {url}")
        article_data = scrape_article(url)

        if article_data and article_data["text"]:
            zh_title, meta_info, hook, ai_summary_html = process_with_ai(article_data)
            pub_date = formatdate(localtime=False)

            # 将四个核心部件拼装成 XML Item，完美适配前端解析格式
            item_xml = f"""
    <item>
        <title><![CDATA[{article_data["title"]}]]></title>
        <link>{url}</link>
        <guid isPermaLink="false">{url}</guid>
        <pubDate>{pub_date}</pubDate>
        <description><![CDATA[{zh_title}|||{meta_info}|||{hook}]]></description>
        <content:encoded><![CDATA[{ai_summary_html}]]></content:encoded>
    </item>"""
            new_items_xml.append(item_xml)
            time.sleep(15)  # 尊贵的喘息时间，防止并发过高

    all_items = (new_items_xml + existing_items_xml)[:MAX_HISTORY]

    rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
    <title><![CDATA[纽约时报书评 - AI 深度精读版]]></title>
    <link>https://www.nytimes.com/section/books/review</link>
    <description><![CDATA[高端学术精读杂志 - NYT 专区]]></description>
    <language>zh-CN</language>
    <pubDate>{formatdate(localtime=False)}</pubDate>
"""
    for item in all_items:
        rss_xml += item
    rss_xml += "\n</channel>\n</rss>"

    with open(XML_FILE, 'w', encoding='utf-8') as f:
        f.write(rss_xml)

    logging.info(f"✅ NYT 更新完毕！本次完美消化了 {len(new_items_xml)} 篇文章。")

if __name__ == "__main__":
    main()
