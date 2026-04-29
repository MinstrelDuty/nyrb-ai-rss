import os
import time
import logging
import markdown
import requests
import re
from bs4 import BeautifulSoup
from email.utils import formatdate
from openai import OpenAI

# ==========================================
# 0. 初始化与最强伪装
# ==========================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

api_key = os.getenv("DEEPSEEK_API_KEY", "").strip(" '\"\n\r\t")
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Referer": "https://www.google.com/",
    "X-Forwarded-For": "66.249.66.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

XML_FILE = 'nyrb_ai_enhanced.xml'
MAX_HISTORY = 150 

# ==========================================
# 1. 记忆读取与智能链接嗅探
# ==========================================
def get_existing_items():
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
            pass
    return existing_urls, existing_items_xml

def get_latest_article_urls(existing_urls, max_items=10):
    urls = []
    try:
        # 🎯 极客技巧：访问这个固定网址，服务器会自动把我们带到“最新一期”的专属页面！
        target_url = "https://www.nybooks.com/current-issue/" 
        logging.info(f"正在扫描纽约书评最新一期目录: {target_url}")
        
        response = requests.get(target_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            
            # 🚀 NYRB 正则匹配：锁定形如 /articles/2026/05/14/文章标题/ 的链接
            if re.match(r'^/articles/\d{4}/\d{2}/\d{2}/[^/]+/?', href):
                # 如果已经是完整链接就不拼了，如果只是路径就拼上主域名
                full_url = f"https://www.nybooks.com{href}" if href.startswith('/') else href
                
                # 🧠 核心排队逻辑：不在本次列表，也不在历史记忆里
                if full_url not in urls and full_url not in existing_urls:
                    urls.append(full_url)
                    # 抓满 10 篇停止，剩下的等下一次 Actions 运行
                    if len(urls) >= max_items:
                        break
    except Exception as e:
        logging.error(f"抓取链接失败: {e}")
    
    logging.info(f"队列计算完毕，NYRB 本次共有 {len(urls)} 篇新文章需要处理。")
    return urls

# ==========================================
# 2. 正文抓取与 AI 处理
# ==========================================
def scrape_article(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        title_tag = soup.find('h1')
        title = title_tag.text.strip() if title_tag else "NYRB 精选文章"
        
        image_url = ""
        img_tag = soup.find('meta', property='og:image')
        if img_tag:
            image_url = img_tag['content']
            
        paragraphs = soup.find_all('p')
        text = "\n".join([p.text.strip() for p in paragraphs if p.text.strip()])
        return {"title": title, "url": url, "text": text, "image_url": image_url}
    except Exception as e:
        return None

def process_with_ai(article_data):
    text = article_data.get("text", "")
    if len(text) < 500:
        return "<p>文章内容过短，可能遭遇了防抓取拦截。</p>"

    text = text[:15000] 
    
    # 🚀 “说人话”降维打击提示词
    system_prompt = """你是一位深受欢迎的专栏作家，极其擅长把晦涩的学术文章讲得通俗易懂、引人入胜。
请直接输出以下内容的Markdown排版（绝对不要包含“好的”等废话开场白）：
1. 📰 **核心摘要**：用像讲故事一样的大白话，生动地概括文章核心。多用短句，拒绝枯燥的学术术语和长篇大论的从句！
2. 💡 **深度透视**：用犀利、接地气（但不掉书袋）的视角，为读者一针见血地解析这篇文章探讨了什么现实痛点。
3. 📚 **延伸解渴**：通俗推荐2-3本相关的优质好书（必须附带一两句极其吸引人的推荐理由）。"""

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"标题：《{article_data['title']}》\n正文：\n{text}"}
                ],
                max_tokens=4000, temperature=0.7
            )
            ai_markdown = response.choices[0].message.content
            ai_html = markdown.markdown(ai_markdown, extensions=['extra'])
            
            wrapper = f'<div style="font-size:16px; line-height:1.6; color:#333;">{ai_html}</div>'
            if article_data.get("image_url"):
                img = f'<img src="{article_data["image_url"]}" style="width:100%; border-radius:10px;"/><br>'
                return img + wrapper
            return wrapper
        except Exception as e:
            if '429' in str(e):
                time.sleep(30)
            else:
                return f"<p style='color:red;'>AI 错误: {e}</p>"
    return "<p style='color:red;'>触发限制，跳过此文章摘要。</p>"

# ==========================================
# 3. 主程序装配
# ==========================================
def main():
    if len(api_key) == 0: return
    
    # 1. 唤醒记忆
    existing_urls, existing_items_xml = get_existing_items()
    
    # 2. 寻找新猎物（传入现有记忆，每次抓 10 篇）
    urls = get_latest_article_urls(existing_urls, max_items=10) 
    
    if not urls: 
        logging.info("🎉 当前期所有文章已全部处理完毕，正在等待 NYRB 发布新一期...")
        return

    new_items_xml = []
    for url in urls:
        logging.info(f"✨ 正在处理本期新文章: {url}")
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
        <description><![CDATA[纽约书评深度精读已生成！]]></description>
        <content:encoded><![CDATA[{ai_summary_html}]]></content:encoded>
    </item>"""
            new_items_xml.append(item_xml)
            time.sleep(20)

    # 组装 XML 保存
    all_items = (new_items_xml + existing_items_xml)[:MAX_HISTORY]
    
    rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
    <title><![CDATA[纽约书评 (NYRB) - AI 深度精读版]]></title>
    <link>https://www.nybooks.com/</link>
    <description><![CDATA[自动排队处理最新一期内容，拒绝废话，生动解析]]></description>
    <language>zh-CN</language>
    <pubDate>{formatdate(localtime=False)}</pubDate>
"""
    for item in all_items: rss_xml += item
    rss_xml += "\n</channel>\n</rss>"

    with open(XML_FILE, 'w', encoding='utf-8') as f:
        f.write(rss_xml)
        
    logging.info(f"✅ NYRB 更新完毕！本次完美消化了 {len(new_items_xml)} 篇文章。")

if __name__ == "__main__":
    main()
