import os
import time  # <--- 新增这行，用于控制程序暂停
import logging
import warnings
warnings.filterwarnings("ignore")
import requests
import feedparser
import markdown
import re
from bs4 import BeautifulSoup
import google.generativeai as genai
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone

# ==========================================
# 1. 配置与初始化
# ==========================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 【🔑 请把下面的中文替换成你的真实 API Key】
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")



genai.configure(api_key=GEMINI_API_KEY)
# 【修复点 1】：改用 -latest 后缀，兼容性最强
# 方案 A (最稳定的基础模型，绝对不会 404)：
model = genai.GenerativeModel('gemini-2.5-flash')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Referer": "https://www.google.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}


# ==========================================
# 2. 内容抓取 (强攻首页提取)
# ==========================================
def get_latest_article_urls(max_items=8):
    homepage_url = "https://www.nybooks.com/"
    logging.info(f"由于官方 RSS 为空，改为直接从主页 {homepage_url} 提取最新文章链接...")

    NORMAL_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    try:
        response = requests.get(homepage_url, headers=NORMAL_HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        urls = []

        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if href.startswith('https://www.nybooks.com/articles/') or href.startswith(
                    'https://www.nybooks.com/online/'):
                clean_url = href.split('#')[0].split('?')[0]
                if clean_url not in urls:
                    urls.append(clean_url)
            elif href.startswith('/articles/') or href.startswith('/online/'):
                clean_url = "https://www.nybooks.com" + href.split('#')[0].split('?')[0]
                if clean_url not in urls:
                    urls.append(clean_url)

        valid_urls = [u for u in urls if len(u.split('/')) > 5]

        if not valid_urls:
            logging.error("从首页提取文章链接失败。")
            return []

        final_urls = valid_urls[:max_items]
        logging.info(f"🎉 成功从主页提取到 {len(final_urls)} 篇文章链接！")
        return final_urls

    except Exception as e:
        logging.error(f"抓取主页文章列表失败: {e}")
        return []


def scrape_article(url):
    logging.info(f"正在抓取文章: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        title_tag = soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else "未知标题"

        author_tag = soup.find(class_=lambda c: c and 'author' in c.lower())
        author = author_tag.get_text(strip=True) if author_tag else "未知作者"

        date_meta = soup.find('meta', property='article:published_time')
        # 【修复点 2】：强制使用 UTC 时区，修复 feedgen 报错
        pub_date = date_meta['content'] if date_meta else datetime.now(timezone.utc).isoformat()
        # 兜底检查：如果抓取到的时间字符串没有时区标记 (+ 或 Z)，强制补全
        if '+' not in pub_date and not pub_date.endswith('Z'):
            pub_date += '+00:00'

        image_meta = soup.find('meta', property='og:image')
        image_url = image_meta['content'] if image_meta else None

        article_body = soup.find('article') or soup.find('div', class_='article-content')
        paragraphs = article_body.find_all('p') if article_body else soup.find_all('p')

        text_content = "\n\n".join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20])

        if not text_content:
            logging.warning(f"未能提取到正文内容: {url}")

        return {
            "title": title,
            "url": url,
            "author": author,
            "pub_date": pub_date,
            "image_url": image_url,
            "text": text_content
        }
    except Exception as e:
        logging.error(f"抓取/解析页面失败 {url}: {e}")
        return None


# ==========================================
# 3. AI 深入处理 (优化输出格式)
# ==========================================
def process_with_ai(article_data):
    text = article_data.get("text", "")
    if len(text) < 500:
        return "<p>文章内容过短，无法生成 AI 总结。</p>"

    # 限制单篇文章字数，防止单篇直接超载
    text = text[:30000] 

    system_prompt = """你是一位博学多识的书评人。请阅读文章并以 Markdown 格式返回：
1. 📰 **核心摘要**：300字概括。
2. 💡 **AI 评述**：深度分析视角。
3. 📚 **扩展阅读**：推荐2-3本书。
请全部使用中文，多用 Emoji 和粗体。"""

    full_prompt = f"{system_prompt}\n\n文章标题：《{article_data['title']}》\n正文：\n{text}"
    
    # 🚀 核心改造：最多允许失败重试 3 次
    max_retries = 3
    for attempt in range(max_retries):
        logging.info(f"🤖 正在处理: {article_data['title']} (第 {attempt + 1} 次尝试)")
        try:
            response = model.generate_content(full_prompt)
            ai_markdown = response.text
            ai_html = markdown.markdown(ai_markdown, extensions=['extra'])
            
            wrapper = f'<div style="font-size:16px; line-height:1.6; color:#333;">{ai_html}</div>'
            
            if article_data.get("image_url"):
                img = f'<img src="{article_data["image_url"]}" style="width:100%; border-radius:10px;"/><br>'
                return img + wrapper
            return wrapper
            
        except Exception as e:
            error_msg = str(e)
            if '429' in error_msg or 'Quota' in error_msg:
                wait_time = 60  # 遇到限流，强制深呼吸 60 秒
                logging.warning(f"⚠️ 触发 API 限流 (429)，代码休眠 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                logging.error(f"❌ AI 处理发生严重错误: {e}")
                return f"<p style='color:red;'>AI 处理期间发生未知错误: {e}</p>"
                
    return "<p style='color:red;'>⚠️ 经过多次等待和重试，依然触发 API 限制，跳过此文章摘要。</p>"


# ==========================================
# 4. RSS 生成 (双重注入防止截断)
# ==========================================
def generate_rss(items, output_file="nyrb_ai_enhanced.xml"):
    fg = FeedGenerator()
    fg.title('NYRB AI 增强版')
    fg.link(href='https://www.nybooks.com/', rel='alternate')
    fg.description('纽约书评 AI 自动总结')
    fg.language('zh-cn')

    for item in items:
        fe = fg.add_entry()
        fe.title(item['title'])
        fe.link(href=item['url'])
        fe.author({'name': item['author']})
        fe.pubDate(item['pub_date'])

        # 【关键】同时填充这两个字段，彻底解决截断问题
        fe.description(item['ai_html_content'])
        fe.content(item['ai_html_content'], type='html')

    fg.rss_file(output_file)
    logging.info(f"✅ RSS 已生成: {output_file}")


# ==========================================
#5.主程序入口(调整频率)
# ==========================================
def main():

    print("🚀 启动全自动抓取...")
    urls = get_latest_article_urls(max_items=8)

    processed_items = []
    for i, url in enumerate(urls):
        data = scrape_article(url)
        if data:
            ai_content = process_with_ai(data)
            data['ai_html_content'] = ai_content
            processed_items.append(data)

            if i < len(urls) - 1:
                logging.info("⏳ 休息 30 秒保护配额...")
                time.sleep(30)

    if processed_items:
        generate_rss(processed_items)


if __name__ == "__main__":
    main()
