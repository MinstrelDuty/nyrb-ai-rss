import os
import time
import logging
import markdown
from feedgen.feed import FeedGenerator
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai

# ==========================================
# 0. 日志配置与 API 终极验证 (彻底消灭 Header 报错)
# ==========================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 获取秘钥，并用最严厉的方式剥离所有隐藏的空格、换行和引号
api_key = os.getenv("GEMINI_API_KEY", "").strip(" '\"\n\r\t")

logging.info(f"🔑 当前获取到的 API 秘钥长度为: {len(api_key)}")
if len(api_key) == 0:
    logging.error("❌ 致命错误：代码根本没有拿到秘钥！GitHub Secrets 传递失败！")
    exit(1)

# 初始化 Gemini
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.0-flash')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# ==========================================
# 1. 网页抓取逻辑 (保持你原有的逻辑)
# ==========================================
def get_latest_article_urls(max_items=4):
    """从纽约书评主页抓取最新文章链接 (为防限流，这里限制抓取数量)"""
    urls = []
    try:
        response = requests.get("https://www.nybooks.com/", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/articles/' in href or '/online/' in href:
                if href.startswith('/'):
                    href = 'https://www.nybooks.com' + href
                if href not in urls:
                    urls.append(href)
            if len(urls) >= max_items:
                break
        logging.info(f"🎉 成功提取到 {len(urls)} 篇文章链接。")
    except Exception as e:
        logging.error(f"抓取链接失败: {e}")
    return urls

def fetch_article_content(url):
    """抓取单篇文章的正文内容"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        title_tag = soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else "未知标题"
        
        # 寻找文章正文的容器 (根据实际网页结构可能需要微调)
        content_div = soup.find('div', class_='article-body') or soup.find('article')
        text = ""
        if content_div:
            paragraphs = content_div.find_all('p')
            text = "\n\n".join([p.get_text(strip=True) for p in paragraphs])
            
        img_tag = soup.find('meta', property='og:image')
        image_url = img_tag['content'] if img_tag else ""
        
        return {"title": title, "text": text, "url": url, "image_url": image_url}
    except Exception as e:
        logging.error(f"抓取文章内容失败 {url}: {e}")
        return None

# ==========================================
# 2. AI 深入处理 (自带防爆截断与防 429 重试)
# ==========================================
def process_with_ai(article_data):
    text = article_data.get("text", "")
    if len(text) < 500:
        return "<p>文章内容过短，无法生成 AI 总结。</p>"

    # 🚀 极其关键：只取前 8000 个字符，彻底防止瞬间字数超载！
    text = text[:8000] 

    system_prompt = """你是一位博学多识的书评人。请阅读文章并以 Markdown 格式返回：
1. 📰 **核心摘要**：300字概括。
2. 💡 **AI 评述**：深度分析视角。
3. 📚 **扩展阅读**：推荐2-3本书。
请全部使用中文，多用 Emoji 和粗体。"""

    full_prompt = f"{system_prompt}\n\n文章标题：《{article_data['title']}》\n正文：\n{text}"
    
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
                wait_time = 60
                logging.warning(f"⚠️ 触发 API 限流 (429)，代码休眠 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                logging.error(f"❌ AI 处理发生严重错误: {e}")
                return f"<p style='color:red;'>AI 处理期间发生未知错误: {e}</p>"
                
    return "<p style='color:red;'>⚠️ 经过多次等待和重试，依然触发 API 限制，跳过此文章摘要。</p>"

# ==========================================
# 3. 主程序与 RSS 生成
# ==========================================
def main():
    urls = get_latest_article_urls(max_items=4)
    if not urls:
        return

    fg = FeedGenerator()
    fg.title('纽约书评 (NYRB) - AI 深度增强版')
    fg.link(href='https://www.nybooks.com/', rel='alternate')
    fg.description('全自动抓取并由 Gemini 2.0 提供深度中文总结的阅读源。')
    fg.language('zh-cn')

    for i, url in enumerate(urls):
        logging.info(f"正在抓取: {url}")
        article_data = fetch_article_content(url)
        if not article_data or not article_data['text']:
            continue
            
        ai_summary_html = process_with_ai(article_data)
        
        fe = fg.add_entry()
        fe.id(url)
        fe.title(article_data['title'])
        fe.link(href=url)
        fe.content(ai_summary_html, type='html')
        
        # 强制深呼吸，保护每日配额
        if i < len(urls) - 1:
            logging.info("⏳ 休息 45 秒，保护 API 配额...")
            time.sleep(45)

    fg.rss_file('nyrb_ai_enhanced.xml')
    logging.info("✅ RSS XML 文件生成成功！")

if __name__ == "__main__":
    main()
