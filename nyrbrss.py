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
            
            # 🚀 修复点 1：把 match 换成 search，不论开头是 http 还是 / 都能认出来！
            if re.search(r'/articles/\d{4}/\d{2}/\d{2}/', href):
                
                # 🚀 修复点 2：智能拼接完整网址
                if href.startswith('/'):
                    full_url = f"https://www.nybooks.com{href}"
                elif href.startswith('http'):
                    full_url = href
                else:
                    continue
                
                # 顺手砍掉链接尾部可能带有的评论锚点（防重复抓取）
                full_url = full_url.split('#')[0]
                
                # 🧠 核心排队逻辑
                if full_url not in urls and full_url not in existing_urls:
                    urls.append(full_url)
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
    

# 🚀 提示词 5.0：独立批判与全景式阅读矩阵
    system_prompt = """你是一位为精英读者写作的资深思想评论员。请基于提供的文章正文，撰写一份深度精读报告。
输出要求（Markdown格式，严禁“好的”等废话，严禁以“想象一下”或“设想”开头）：

1. 📰 **内容精要（准确且富有细节）**：
   - 拒绝笼统概括，必须包含文章中的 2-3 个核心细节（如具体的历史事件、核心人物名、或作者提出的关键概念/引语）。
   - 语感要专业且流畅，像高质量的深度报道。

2. 🧠 **批判与脉络（深度透视）**：
   - **思想点评**：一针见血地评价本文内容的质量与立意。它的视角有何独特之处？论证是否扎实？是否存在刻意回避的盲区、偏见或逻辑局限？
   - **学术对话**：指出这篇文章在思想史或特定研究领域的“坐标”。它在挑战哪种传统共识？作者在与哪位学者、哪种思潮进行显性辩论或隐秘呼应？

3. 📚 **延伸阅读（全景式书单）**：
   - 推荐 4-5 本真实存在的优质著作，为读者构建一个立体的知识矩阵。请按以下三个维度进行分类推荐：
     * 🎯 **核心辐射（1-2本）**：与本文讨论的具体历史背景、核心人物或直接主题最紧密相关的经典著作。
     * 🤝 **同向深化（1-2本）**：与本文作者处于同一研究脉络、理论框架，或能进一步补充、支撑本文观点的著作。
     * ⚔️ **反向争锋（1本）**：提出截然相反观点、采用完全不同视角，或能对本文及其代表的思潮进行有力反驳的著作。
   - 要求：每本书必须给出书名、作者，并用一两句话精准点明它在这个阅读矩阵中的独特价值。"""

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
    
    # 2. 寻找新猎物
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
