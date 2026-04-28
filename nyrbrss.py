import os
import time
import logging
import markdown
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from openai import OpenAI  # 👈 换成了兼容的 OpenAI 库

# ==========================================
# 0. 日志配置与 DeepSeek 初始化
# ==========================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 强力清洗秘钥首尾的空格、换行！
api_key = os.getenv("DEEPSEEK_API_KEY", "").strip(" '\"\n\r\t")

logging.info(f"🔑 当前获取到的 API 秘钥长度为: {len(api_key)} 字符")
if len(api_key) == 0:
    logging.error("❌ 致命错误：秘钥为空！请检查 GitHub 的 DEEPSEEK_API_KEY 配置！")

# 🚀 狸猫换太子：用 OpenAI 的库，连上 DeepSeek 的服务器！
client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)

# 网页抓取伪装头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Referer": "https://www.google.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

# ==========================================
# 1. 抓取最新文章链接
# ==========================================
def get_latest_article_urls(max_items=8):
    logging.info("正在从 NYRB 主页提取最新文章链接...")
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
        logging.info(f"🎉 成功提取到 {len(urls)} 篇文章链接！")
    except Exception as e:
        logging.error(f"抓取链接失败: {e}")
    return urls

# ==========================================
# 2. 提取单篇文章正文
# ==========================================
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
        logging.error(f"提取文章正文失败 {url}: {e}")
        return None

# ==========================================
# 3. AI 深入处理 (DeepSeek 版本)
# ==========================================
def process_with_ai(article_data):
    text = article_data.get("text", "")
    if len(text) < 500:
        return "<p>文章内容过短，无法生成 AI 总结。</p>"

    # DeepSeek 能力强，放宽到 15000 字符
    text = text[:15000] 

    system_prompt = """你是一位博学多识的书评人。请阅读文章并以 Markdown 格式返回：
1. 📰 **核心摘要**：300字概括。
2. 💡 **AI 评述**：深度分析视角。
3. 📚 **扩展阅读**：推荐2-3本书。
请全部使用中文，多用 Emoji 和粗体。"""

    max_retries = 3
    for attempt in range(max_retries):
        logging.info(f"🤖 正在处理: {article_data['title']} (第 {attempt + 1} 次尝试)")
        try:
            # 🚀 调用 DeepSeek 模型
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"文章标题：《{article_data['title']}》\n正文：\n{text}"}
                ]
            )
            ai_markdown = response.choices[0].message.content
            ai_html = markdown.markdown(ai_markdown, extensions=['extra'])
            
            wrapper = f'<div style="font-size:16px; line-height:1.6; color:#333;">{ai_html}</div>'
            
            if article_data.get("image_url"):
                img = f'<img src="{article_data["image_url"]}" style="width:100%; border-radius:10px;"/><br>'
                return img + wrapper
            return wrapper
            
        except Exception as e:
            error_msg = str(e)
            if '429' in error_msg or 'RateLimit' in error_msg:
                wait_time = 30
                logging.warning(f"⚠️ 触发限流，休眠 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                logging.error(f"❌ AI 处理发生错误: {e}")
                return f"<p style='color:red;'>AI 处理期间发生未知错误: {e}</p>"
                
    return "<p style='color:red;'>⚠️ 经过多次重试依然触发限制，跳过此文章摘要。</p>"

# ==========================================
# ==========================================
# 4. 主函数：生成 RSS
# ==========================================
def main():
    if len(api_key) == 0:
        logging.error("⛔ 秘钥为空，程序强行终止！")
        return

    # 这里已经帮你改成了 8 篇
    urls = get_latest_article_urls(max_items=8) 
    if not urls:
        return

    fg = FeedGenerator()
    fg.title("纽约书评 - AI 深度精读版 (DeepSeek)")
    fg.link(href="https://www.nybooks.com/", rel="alternate")
    fg.description("由 DeepSeek 自动抓取并提供中文深度总结的 NYRB 订阅源")
    fg.language("zh-CN")

    for i, url in enumerate(urls):
        logging.info(f"正在抓取文章: {url}")
        article_data = scrape_article(url)
        
        if article_data and article_data["text"]:
            ai_summary_html = process_with_ai(article_data)
            
            fe = fg.add_entry()
            fe.title(article_data["title"])
            fe.link(href=url)
            
            # ✅ 完美的 RSS 全文支持
            fe.description("AI 深度精读已生成，请点击展开查看完整内容。")
            fe.content(content=ai_summary_html, type='html')
            
            if i < len(urls) - 1:
                logging.info("⏳ 休息 20 秒保护配额...")
                time.sleep(20)

    # 这两行已经完美缩进对齐
    fg.rss_file('nyrb_ai_enhanced.xml', pretty=True)
    logging.info("✅ RSS 文件 nyrb_ai_enhanced.xml 生成完毕！")

if __name__ == "__main__":
    main()
