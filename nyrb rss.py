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
model = genai.GenerativeModel('models/gemini-flash-latest')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Referer": "https://www.google.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}


# ==========================================
# 2. 内容抓取 (强攻首页提取)
# ==========================================
def get_latest_article_urls(max_items=10):
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
# 3. AI 深入处理 (精装排版版)
# ==========================================
def process_with_ai(article_data):
    text = article_data.get("text", "")
    if len(text) < 500:
        logging.warning(f"文章过短，可能未成功绕过付费墙，跳过 AI 处理: {article_data['title']}")
        return "<p>文章内容过短或未成功绕过付费墙，无法生成 AI 总结。</p>"

    text = text[:50000]

    # 🚀 颜值升级版 Prompt：强制 AI 使用 Emoji、粗体和无序列表
    system_prompt = """你是一位博学多识的书评人和学术编辑。
请阅读用户提供的长篇文章，并以 **高颜值的 Markdown 格式** 返回以下三个板块（请全部使用中文输出）：

> 💡 **排版强制要求**：请务必多使用 Emoji 图标 🎨、对核心人名/书名使用 **粗体** 强调、并使用区块引用（>）来突出金句，让文章在手机屏幕上极具视觉吸引力！

### 📰 一、 核心摘要 (Summary)
[用大约300字精准、生动地概括文章的核心论点和主要脉络]

### 🧠 二、 深度评述 (Commentary)
[对文章进行批判性思考。请分条列出你的独到见解，分析其深度、独特视角或潜在的局限性]

### 📚 三、 扩展阅读 (Further Reading)
[推荐 2-3 本相关书籍或深度报道。格式必须为：
* 📖 **《书名》** - 作者：[一句简短犀利的推荐理由]]
"""

    full_prompt = f"{system_prompt}\n\n---\n文章标题：《{article_data['title']}》\n作者：{article_data['author']}\n\n文章正文：\n{text}"

    logging.info(f"🤖 正在调用 Gemini 处理文章: {article_data['title']} (字数: {len(text)})")
    try:
        response = model.generate_content(full_prompt)
        ai_markdown = response.text

        # 将 Markdown 转换为 HTML
        ai_html = markdown.markdown(ai_markdown, extensions=['extra'])

        # 🎨 外观升级：给生成的 HTML 加上基础排版样式
        wrapper_start = '<div style="font-family: system-ui, -apple-system, sans-serif; line-height: 1.7; color: #333; font-size: 16px;">'
        wrapper_end = '</div><br><hr style="border: 0; border-top: 1px solid #eee;"><p style="text-align:center; color:#999; font-size:12px;">✨ <em>Generated by Gemini AI</em> ✨</p>'

        # 优化封面图样式：圆角 + 柔和阴影
        if article_data.get("image_url"):
            img_html = f'<img src="{article_data["image_url"]}" alt="封面图" style="max-width:100%; height:auto; border-radius:12px; margin-bottom:20px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); display:block; margin-left:auto; margin-right:auto;"/><br/>'
            ai_html = wrapper_start + img_html + ai_html + wrapper_end
        else:
            ai_html = wrapper_start + ai_html + wrapper_end

        return ai_html
    except Exception as e:
        logging.error(f"Gemini 处理失败 {article_data['title']}: {e}")
        return f"<p>AI 处理期间发生错误: {e}</p>"


# ==========================================
# 4. RSS 生成 (修复全文截断版)
# ==========================================
def generate_rss(items, output_file="nyrb_ai_enhanced.xml"):
    logging.info("正在生成最终的 RSS 文件...")
    fg = FeedGenerator()
    fg.title('The New York Review of Books - AI 增强版')
    fg.link(href='https://www.nybooks.com/', rel='alternate')
    fg.description('纽约书评 AI 增强版：包含全文核心摘要、AI 批判性评述与扩展阅读。')
    fg.language('zh-cn')

    for item in items:
        fe = fg.add_entry()
        fe.title(item['title'])
        fe.link(href=item['url'])
        fe.author({'name': item['author']})
        fe.pubDate(item['pub_date'])

        # 将 AI 内容作为摘要 (兼容老式阅读器)
        fe.description(item['ai_html_content'])

        # 🚀 【新增这一行】：将 AI 内容声明为“完整正文”
        fe.content(content=item['ai_html_content'], type='html')

    try:
        fg.rss_file(output_file)
        logging.info(f"✅ RSS 文件成功生成！保存在当前目录: {os.path.abspath(output_file)}")
    except Exception as e:
        logging.error(f"RSS 生成失败: {e}")


# ==========================================
# 5. 主程序入口
# ==========================================
def main():
    print("🚀 启动 NYRB AI RSS 生成器...\n")
    urls = get_latest_article_urls(max_items=10)

    processed_items = []
    for i, url in enumerate(urls):
        article_data = scrape_article(url)
        if not article_data:
            continue

        ai_html = process_with_ai(article_data)
        article_data['ai_html_content'] = ai_html
        processed_items.append(article_data)

        # ⏳ 核心补丁：处理完一篇后，强制暂停 30 秒，保护免费 API 额度
        if i < len(urls) - 1:  # 最后一篇处理完就不用等了
            logging.info("⏳ 为避免触发 API 免费频率限制，程序休息 30 秒...")
            time.sleep(30)

    if processed_items:
        generate_rss(processed_items)
    else:
        logging.warning("没有成功处理任何文章，未能生成 RSS。")


if __name__ == "__main__":
    main()