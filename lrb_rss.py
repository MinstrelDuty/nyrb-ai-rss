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

XML_FILE = 'lrb_ai_enhanced.xml'
# 🚀 必须调高！保证它能记住过去几个月的文章，防止重复抓取
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
        # 🎯 直接访问 LRB 的“当前期”总目录
        target_url = "https://www.lrb.co.uk/the-paper" 
        logging.info(f"正在扫描最新一期目录: {target_url}")
        
        response = requests.get(target_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            
            # 🚀 终极正则匹配：精准锁定 v48/n07/作者/标题 这种格式的文章
            # 这就意味着，不管是 v48 还是 v49，n07 还是 n08，只要是文章链接它就能认出来！
            if re.match(r'^/the-paper/v\d+/n\d+/[^/]+/.+', href):
                full_url = f"https://www.lrb.co.uk{href}"
                
                # 🧠 核心排队逻辑：只有当这篇文章既不在本次待抓列表，也不在历史记忆里时，才加入列表！
                if full_url not in urls and full_url not in existing_urls:
                    urls.append(full_url)
                    # 抓满 10 篇就停止扫描，剩下的留给下一次运行！
                    if len(urls) >= max_items:
                        break
    except Exception as e:
        logging.error(f"抓取链接失败: {e}")
    
    logging.info(f"队列计算完毕，本次共有 {len(urls)} 篇新文章需要处理。")
    return urls

# ==========================================
# ==========================================
# ==========================================
# 2. 正文抓取与 AI 处理
# ==========================================
def scrape_article(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        title_tag = soup.find('h1')
        title = title_tag.text.strip() if title_tag else "精选文章"
        
        image_url = ""
        img_tag = soup.find('meta', property='og:image')
        if img_tag:
            image_url = img_tag['content']
            
        # 🚀 包含之前为你加上的“诗歌与短文”兼容补丁
        paragraphs = soup.find_all(['p', 'pre', 'blockquote', 'div'], class_=re.compile(r'poem|stanza|text|body|content', re.I))
        
        text_blocks = []
        for p in paragraphs:
            text_blocks.append(p.get_text(separator=' ', strip=True))
            
        text = "\n".join([t for t in text_blocks if len(t) > 5])
        
        # 兜底策略：如果上面抓不到，直接去主体里扒纯文本
        if len(text) < 100:
            article_body = soup.find('article') or soup.find('main')
            if article_body:
                text = article_body.get_text(separator='\n', strip=True)

        return {"title": title, "url": url, "text": text, "image_url": image_url}
    except Exception as e:
        logging.error(f"抓取正文失败: {e}")
        return None

def process_with_ai(article_data):
    text = article_data.get("text", "")
    
    # 🚀 门槛降到极低，保护诗歌和短文不被误杀
    if len(text) < 100:
        return "无中文标题", "未获取破题", "<p>文章内容过短，或者遇到了极其特殊的排版无法抓取。</p>"

    # 🚀 彻底解锁字数封印！保留 80000 字符，生吞万字长文
    text = text[:80000] 
    
    # 🚀 提示词终极进化：强制 AI 加上结构标签，方便程序精准切割！
    system_prompt = """你是一位为时间宝贵的精英读者写作的资深主笔。请基于提供的文章撰写精读报告。
【最高指令】：总字数严格控制在 800-1000 字左右！严禁以“想象一下”等呆板词汇开头。

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
（300-400字）语言要极具可读性，像讲故事一样梳理文章逻辑，必须精准嵌入2-3个核心细节（如关键史实、概念或人物）。

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
                    {"role": "user", "content": f"标题：《{article_data['title']}》\n正文：\n{text}"}
                ],
                max_tokens=4000, temperature=0.7
            )
            ai_text = response.choices[0].message.content
            
            zh_title = "未获取中文标题"
            hook = "未获取破题"
            main_content = ai_text
            
            # 🔪 核心切割逻辑：把 AI 生成的三大块内容安全拆开
            if "【中文标题】" in ai_text and "【一句话破题】" in ai_text and "【正文】" in ai_text:
                try:
                    zh_title = ai_text.split("【中文标题】")[1].split("【一句话破题】")[0].strip()
                    hook = ai_text.split("【一句话破题】")[1].split("【正文】")[0].strip()
                    main_content = ai_text.split("【正文】")[1].strip()
                except Exception:
                    pass
            
            ai_html = markdown.markdown(main_content, extensions=['extra'])
            wrapper = f'<div style="font-size:16px; line-height:1.6; color:#333;">{ai_html}</div>'
            
            if article_data.get("image_url"):
                img = f'<img src="{article_data["image_url"]}" style="width:100%; border-radius:10px;"/><br>'
                wrapper = img + wrapper
                
            return zh_title, hook, wrapper
            
        except Exception as e:
            if '429' in str(e):
                time.sleep(30)
            else:
                return "API错误", "API错误", f"<p style='color:red;'>AI 错误: {e}</p>"
    return "触发限制", "触发限制", "<p style='color:red;'>跳过此文章摘要。</p>"

# ==========================================
# 3. 主程序装配
# ==========================================
def main():
    if len(api_key) == 0: return
    
    existing_urls, existing_items_xml = get_existing_items()
    urls = get_latest_article_urls(existing_urls, max_items=10) 
    
    if not urls: 
        logging.info("🎉 当前期所有文章已全部处理完毕，正在等待发布新一期...")
        return

    new_items_xml = []
    for url in urls:
        logging.info(f"✨ 正在处理本期新文章: {url}")
        article_data = scrape_article(url)
        if article_data and article_data["text"]:
            # 📦 接收切分好的三个零件
            zh_title, hook, ai_summary_html = process_with_ai(article_data)
            pub_date = formatdate(localtime=False)
            
            # 🚀 我们把提取出来的 中文标题 和 破题，用 "|||" 拼起来，悄悄塞进 description 标签里
            item_xml = f"""
    <item>
        <title><![CDATA[{article_data["title"]}]]></title>
        <link>{url}</link>
        <guid isPermaLink="false">{url}</guid>
        <pubDate>{pub_date}</pubDate>
        <description><![CDATA[{zh_title}|||{hook}]]></description>
        <content:encoded><![CDATA[{ai_summary_html}]]></content:encoded>
    </item>"""
            new_items_xml.append(item_xml)
            time.sleep(20)

    all_items = (new_items_xml + existing_items_xml)[:MAX_HISTORY]
    
    rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
    <title><![CDATA[AI 深度精读版]]></title>
    <link>https://github.com/</link>
    <description><![CDATA[高端学术精读杂志]]></description>
    <language>zh-CN</language>
    <pubDate>{formatdate(localtime=False)}</pubDate>
"""
    for item in all_items: rss_xml += item
    rss_xml += "\n</channel>\n</rss>"

    with open(XML_FILE, 'w', encoding='utf-8') as f:
        f.write(rss_xml)
        
    logging.info(f"✅ 更新完毕！本次完美消化了 {len(new_items_xml)} 篇文章。")

if __name__ == "__main__":
    main()
