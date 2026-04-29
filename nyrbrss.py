import os
import time
import logging
import markdown
import requests
import re  # 🚀 新增：用于精准读取旧档案的正规表达式引擎
from bs4 import BeautifulSoup
from email.utils import formatdate
from openai import OpenAI

# ==========================================
# 0. 初始化
# ==========================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

api_key = os.getenv("DEEPSEEK_API_KEY", "").strip(" '\"\n\r\t")
if len(api_key) == 0:
    logging.error("❌ 致命错误：秘钥为空！")

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Referer": "https://www.google.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

# 🚀 历史设定：你想在这个网页上保留多少篇历史文章？
MAX_HISTORY = 150 
XML_FILE = 'nyrb_ai_enhanced.xml'

# ==========================================
# 1. 记忆读取与网页抓取
# ==========================================

# 🧠 核心新功能：读取旧的 XML 档案，提取已有的文章和链接
def get_existing_items():
    existing_urls = set()
    existing_items_xml = []
    
    if os.path.exists(XML_FILE):
        try:
            with open(XML_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 使用正则极其安全地把每一篇旧文章完整的切下来
            item_blocks = re.findall(r'<item>.*?</item>', content, re.DOTALL)
            for block in item_blocks:
                existing_items_xml.append(block)
                # 记住这篇文章的链接，用于一会“查重”
                link_match = re.search(r'<link>(.*?)</link>', block)
                if link_match:
                    existing_urls.add(link_match.group(1).strip())
                    
            logging.info(f"📂 成功读取本地记忆：发现了 {len(existing_items_xml)} 篇历史文章。")
        except Exception as e:
            logging.warning(f"⚠️ 读取历史记录失败，将创建全新档案: {e}")
            
    return existing_urls, existing_items_xml

def get_latest_article_urls(max_items=8):
    urls = []
    try:
        response = requests.get("https://www.nybooks.com/", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if ('/articles/' in href or '/online/' in href) and href not in urls:
                urls.append(href)
                if len(urls) >= max_items:
                    break
    except Exception as e:
        logging.error(f"抓取链接失败: {e}")
    return urls

def scrape_article(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        title_tag = soup.find('h1')
        title = title_tag.text.strip() if title_tag else "未知标题"
        
        image_url = ""
        img_tag = soup.find('meta', property='og:image')
        if img_tag:
            image_url = img_tag['content']
            
        paragraphs = soup.find_all('p')
        text = "\n".join([p.text.strip() for p in paragraphs if p.text.strip()])
        return {"title": title, "url": url, "text": text, "image_url": image_url}
    except Exception as e:
        return None

# ==========================================
# 2. AI 深入处理
# ==========================================
def process_with_ai(article_data):
    text = article_data.get("text", "")
    if len(text) < 500:
        return "<p>文章过短，无法总结。</p>"

    text = text[:15000] 

    system_prompt = """你是一位专业的书评人。请直接输出以下内容的Markdown排版，绝对不要包含“好的”、“我已经阅读”等废话：
1. 📰 **核心摘要**：详细概括。
2. 💡 **AI 评述**：深度分析视角。
3. 📚 **扩展阅读**：推荐2-3本书。"""

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"标题：《{article_data['title']}》\n正文：\n{text}"}
                ],
                max_tokens=4000, 
                temperature=0.7
            )
            ai_markdown = response.choices[0].message.content
            ai_html = markdown.markdown(ai_markdown, extensions=['extra'])
            
            wrapper = f'<div style="font-size:16px; line-height:1.6; color:#333;">{ai_html}</div>'
            if article_data.get("image_url"):
                img = f'<img src="{article_data["image_url"]}" style="width:100%; border-radius:10px;"/><br>'
                return img + wrapper
            return wrapper
        except Exception as e:
            if '429' in str(e) or 'RateLimit' in str(e):
                time.sleep(30)
            else:
                return f"<p style='color:red;'>AI 错误: {e}</p>"
    return "<p style='color:red;'>触发限制，跳过此文章摘要。</p>"

# ==========================================
# 3. 智能查重与拼装
# ==========================================
def main():
    if len(api_key) == 0:
        return
        
    # 1. 唤醒记忆：读取旧文章列表
    existing_urls, existing_items_xml = get_existing_items()
    
    # 2. 去看世界：抓取最新的 8 篇链接
    urls = get_latest_article_urls(max_items=8) 
    if not urls:
        return

    new_items_xml = []
    
    for url in urls:
        # 🚀 智能查重拦截：如果这篇以前翻译过了，直接跳过！省钱省力！
        if url in existing_urls:
            logging.info(f"⏭️ 这篇历史已存在，无需重新翻译，跳过: {url}")
            continue

        logging.info(f"✨ 发现新文章，正在抓取并处理: {url}")
        article_data = scrape_article(url)
        if article_data and article_data["text"]:
            ai_summary_html = process_with_ai(article_data)
            pub_date = formatdate(localtime=False)
            
            item_xml = f"""
    <item>
        <title><![CDATA[{article_data["title"]}]]></title>
        <link>{url}</link>
        <guid isPermaLink="false">{url}</guid>
        <pubDate>{pub_date}</pubDate>
        <description><![CDATA[这只是个引子，请点开查看完整的排版长文！]]></description>
        <content:encoded><![CDATA[{ai_summary_html}]]></content:encoded>
    </item>"""
            new_items_xml.append(item_xml)
            time.sleep(20) # 只有处理了新文章，才需要休息

    # 3. 新老交替：把新鲜出炉的文章放在最前面，旧文章跟在后面
    all_items = new_items_xml + existing_items_xml
    
    # 4. 保持身材：最多只保留最近的 50 篇（也就是 MAX_HISTORY 的设定），防止文件撑爆
    all_items = all_items[:MAX_HISTORY]

    # 5. 组装全新的 XML 外壳
    rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
    <title><![CDATA[纽约书评 - AI 深度精读版]]></title>
    <link>https://www.nybooks.com/</link>
    <description><![CDATA[由 DeepSeek 自动抓取并提供中文深度总结]]></description>
    <language>zh-CN</language>
    <pubDate>{formatdate(localtime=False)}</pubDate>
"""
    for item in all_items:
        rss_xml += item
        
    rss_xml += "\n</channel>\n</rss>"

    with open('nyrb_ai_enhanced.xml', 'w', encoding='utf-8') as f:
        f.write(rss_xml)
        
    logging.info(f"✅ 更新完毕！本次新增 {len(new_items_xml)} 篇文章，当前你的网站上共有 {len(all_items)} 篇历史沉淀。")

if __name__ == "__main__":
    main()
