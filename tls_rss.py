import os
import re
import time
import requests
import markdown
from bs4 import BeautifulSoup
from email.utils import formatdate
from openai import OpenAI
import xml.etree.ElementTree as ET

# ==========================================
# 0. 基础配置
# ==========================================
api_key = os.getenv("DEEPSEEK_API_KEY", "").strip(" '\"\n\r\t")
try:
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
except Exception as e:
    print(f"❌ 初始化 DeepSeek 客户端失败: {e}")
    exit(1)

XML_FILE = 'tls_ai_enhanced.xml'
MAX_HISTORY = 50 # 限制在 50 篇，TLS 更新快，保留精品即可

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ==========================================
# 1. 历史数据与目录抓取 (TLS 专用)
# ==========================================

def get_existing_items():
    """解析已有的 XML 文件，避免重复抓取"""
    existing_urls = set()
    existing_items_xml = []
    
    if os.path.exists(XML_FILE):
        try:
            tree = ET.parse(XML_FILE)
            root = tree.getroot()
            for item in root.findall('.//item'):
                link = item.find('link').text if item.find('link') is not None else ""
                if link:
                    existing_urls.add(link)
                # 将原来的整个 <item> 转回字符串保留
                item_xml_str = ET.tostring(item, encoding='unicode')
                existing_items_xml.append(item_xml_str)
            print(f"📂 本地智库中已存在 {len(existing_urls)} 篇 TLS 深度精读。")
        except Exception as e:
            print(f"⚠️ 解析旧 XML 失败 (首次运行或文件损坏)，将重新创建: {e}")
            
    return existing_urls, existing_items_xml

def get_latest_article_urls(existing_urls, max_items=60):
    """【Plan B 终极进化】智能追踪真正的文章分片地图，彻底排除话题和分类页"""
    import re
    import requests
    
    print("🕵️ 启动 Plan B：正在从 Yoast 根目录精准定位真正的文章数据库...")
    urls = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0",
        "Accept": "text/xml,application/xml"
    }
    
    try:
        # 1. 访问总地图索引
        index_url = "https://www.the-tls.com/sitemap_index.xml"
        print(f"📂 正在扫描总指挥部: {index_url}")
        
        response = requests.get(index_url, headers=headers, timeout=20)
        
        # 兜底：如果被拦截，呼叫 Jina 强行读取
        if response.status_code != 200 or "<sitemap" not in response.text:
            print("⚠️ 根目录直连受阻，呼叫 Jina 传送门强制解析...")
            jina_url = f"https://r.jina.ai/{index_url}"
            response = requests.get(jina_url, headers={"Accept": "text/plain"}, timeout=30)
            
        # 2. 提取所有子地图链接
        sub_maps = re.findall(r'<loc>(https://www.the-tls.com/[a-zA-Z0-9\-_]*sitemap[a-zA-Z0-9\-_]*\.xml)</loc>', response.text)
        
        if not sub_maps:
            print("❌ 根地图解析失败，未发现子地图链接。")
            return []

        # 🎯 核心逻辑：精准筛选“文章正文”地图
        # 我们要找包含 article 或 post 的，但绝对不能包含 topic, category, author, tag 等关键词
        target_article_maps = [
            m for m in sub_maps 
            if ('article' in m or 'post' in m) and not any(x in m for x in ['topic', 'category', 'author', 'tag', 'issue'])
        ]
        
        if not target_article_maps:
            print("⚠️ 未找到纯净的文章地图，尝试退而求其次寻找 tls_issues...")
            target_article_maps = [m for m in sub_maps if 'tls_issues' in m]

        if not target_article_maps:
             print("❌ 无法锁定文章地图分片。请检查地图结构。")
             return []

        # 获取最后一份地图（通常是最新的一份）
        target_sitemap = target_article_maps[-1]
        print(f"🎯 成功锁定目标！正在深入底层数据库: {target_sitemap}")
        
        # 3. 抓取选定的子地图
        resp2 = requests.get(target_sitemap, headers=headers, timeout=20)
        if resp2.status_code != 200 or "<loc>" not in resp2.text:
             resp2 = requests.get(f"https://r.jina.ai/{target_sitemap}", headers={"Accept": "text/plain"}, timeout=30)
             
        # 4. 提取具体文章链接并倒序排列（从最新开始抓）
        raw_links = re.findall(r'https://www.the-tls.com/[a-zA-Z0-9\-\/]+', resp2.text)
        raw_links = list(dict.fromkeys(raw_links))
        raw_links.reverse()
        
        for href in raw_links:
            # 二次防御过滤：排除地图里可能残留的非文章长链接
            if len(href.split('/')) > 4:
                if any(x in href for x in ['/issues/', '/categor', '/author', '/tag', '/about', '/buy', '/login', '/subscribe', '/my-account', '/letters', 'wp-content', '.xml', '/topics/']):
                    continue
                    
                if href not in existing_urls and href not in urls:
                    urls.append(href)
                    if len(urls) >= max_items:
                        break
                        
        print(f"✅ 提炼成功！共从底层抽取出 {len(urls)} 篇真正的深度长文。")
        return urls
        
    except Exception as e:
        print(f"❌ Plan B 运行过程中发生不可预知的错误: {e}")
        return []
# ==========================================
# 2. 核心引擎：Jina 空间传送门与 AI 提炼
# ==========================================

def scrape_article_via_jina(url):
    """使用 Jina Reader 暴力击穿反爬防火墙"""
    print(f"🌀 启动 Jina 空间传送门获取正文 -> {url}")
    try:
        jina_url = f"https://r.jina.ai/{url}"
        headers = { "Accept": "text/markdown", "X-No-Cache": "true" }
        
        response = requests.get(jina_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        text = response.text
        
        # 提取标题
        title = "TLS 深度长文"
        first_line = text.split('\n')[0]
        if first_line.startswith('Title: '):
            title = first_line.replace('Title: ', '').strip()
        elif first_line.startswith('# '):
            title = first_line.replace('# ', '').strip()

        # 防御机制：如果连 Jina 都只抓到一点点（意味着需要账号登录才能看）
        if len(text) < 1500 and ("Subscribe" in text or "Log in" in text):
            print("🚨 遭遇后端硬性付费墙拦截，跳过此篇...")
            return None
            
        # 这里提取一张特色图片（TLS 可能提取不到，这里做个兜底）
        # Jina 会把图片变成 markdown 格式：![alt](url)
        image_url = ""
        img_match = re.search(r'!\[.*?\]\((https://.*?\.jpg.*?)\)', text)
        if img_match:
             image_url = img_match.group(1)

        return {"title": title, "url": url, "text": text, "image_url": image_url}
        
    except Exception as e:
        print(f"❌ Jina 抓取失败: {url} - {e}")
        return None

def process_with_ai(article_data):
    """DeepSeek 针对 TLS 的超浓缩精读处理"""
    text = article_data.get("text", "")
    
    if len(text) < 500:
        return "无中文标题", "✍️ 未获取作者与对象", "未获取破题", "<p>文章过短，无法提取摘要。</p>"

    text = text[:80000] 
    
    # 针对 TLS 的超浓缩版提示词
    system_prompt = """你是一位为时间宝贵的精英读者写作的资深主笔。请基于提供的文章撰写精读报告。
【最高指令】：本文篇幅较短，总字数必须极其严苛地控制在 600-700 字左右！语言必须极度凝练、犀利。严禁以“想象一下”等呆板词汇开头。

请务必严格按照以下带有【】的标签格式输出：

【中文标题】
直接写出英文标题的精准且具有吸引力的中文翻译

【作者与对象】
格式必须为：“✍️ 作者：[文章作者名] ｜ 🎯 探讨对象：[评论的具体书名/展览/事件]”

【一句话破题】
用一句极具张力的话（不超过40字），直接点破文章核心。

【正文】
### 📰 核心脉络
（约300字）极其简练地梳理文章逻辑，只保留最核心的冲突或观点。

### 🧠 独立点评
（约200字）简明扼要地指出文章在思想史或艺术界的价值。

### 📚 延伸矩阵
（严禁伪造！只需推荐 2-3 本核心相关或不同观点的真实著作，每本一句话介绍）"""

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"标题：《{article_data['title']}》\n正文：\n{text}"}
                ],
                max_tokens=2000, temperature=0.7
            )
            ai_text = response.choices[0].message.content
            
            # ==========================================
            # 🔪 防御型切割逻辑
            # ==========================================
            zh_title = "未获取中文标题"
            meta_info = "✍️ 未获取作者与对象"
            hook = "未获取破题"
            main_content = ai_text 

            title_match = re.search(r'【中文标题】(.*?)(?=【作者与对象】|【一句话破题】)', ai_text, re.S)
            if title_match:
                zh_title = title_match.group(1).strip()
                main_content = main_content.replace(title_match.group(0), "")

            meta_match = re.search(r'【作者与对象】(.*?)(?=【一句话破题】)', ai_text, re.S)
            if meta_match:
                meta_info = meta_match.group(1).strip()
                main_content = main_content.replace(meta_match.group(0), "")

            hook_match = re.search(r'【一句话破题】(.*?)(?=【正文】|###|$)', ai_text, re.S)
            if hook_match:
                hook = hook_match.group(1).strip()
                main_content = main_content.replace(hook_match.group(0), "")

            main_content = main_content.replace("【正文】", "").strip()
            
            # 转 HTML
            ai_html = markdown.markdown(main_content, extensions=['extra'])
            wrapper = f'<div style="font-size:16px; line-height:1.6; color:#333;">{ai_html}</div>'
            
            if article_data.get("image_url"):
                img = f'<img src="{article_data["image_url"]}" style="width:100%; border-radius:10px; margin-bottom:15px;"/><br>'
                wrapper = img + wrapper
                
            return zh_title, meta_info, hook, wrapper
            
        except Exception as e:
            if '429' in str(e):
                print("⚠️ API 频率限制，沉睡 30 秒...")
                time.sleep(30)
            else:
                print(f"❌ AI 处理错误: {e}")
                return "API错误", "API错误", "API错误", f"<p style='color:red;'>AI 错误: {e}</p>"
                
    return "触发限制", "触发限制", "触发限制", "<p style='color:red;'>跳过此文章摘要。</p>"

# ==========================================
# 3. 主程序装配与打包发布
# ==========================================

def main():
    existing_urls, existing_items_xml = get_existing_items()
    
    # 限制单次运行抓 20 篇，保护 API 和精力
    urls = get_latest_article_urls(existing_urls, max_items=20) 
    
    if not urls: 
        print("🎉 当前期 TLS 无新文章发布。正在休眠...")
        return

    new_items_xml = []
    for url in urls:
        print(f"\n🔥 开始提炼: {url}")
        article_data = scrape_article_via_jina(url)
        
        # 只有在文章数据非空时才动用 AI
        if article_data and article_data["text"] and len(article_data["text"]) > 1500:
            zh_title, meta_info, hook, ai_summary_html = process_with_ai(article_data)
            pub_date = formatdate(localtime=False)
            
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
            time.sleep(15) # 尊贵的喘息时间，防止被 DeepSeek 封锁

    if new_items_xml:
        all_items = (new_items_xml + existing_items_xml)[:MAX_HISTORY]
        
        rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
    <title><![CDATA[TLS 深度精读版]]></title>
    <link>https://github.com/</link>
    <description><![CDATA[泰晤士文学增刊高级摘要]]></description>
    <language>zh-CN</language>
    <pubDate>{formatdate(localtime=False)}</pubDate>
"""
        for item in all_items:
            rss_xml += item
        rss_xml += "\n</channel>\n</rss>"

        with open(XML_FILE, 'w', encoding='utf-8') as f:
            f.write(rss_xml)
            
        print(f"\n✅ 智库更新完毕！本次完美消化了 {len(new_items_xml)} 篇 TLS 文章。")
    else:
        print("\n✅ 运行结束。本次所有探测到的链接均被后端付费墙硬拦截，无新内容入库。")

if __name__ == "__main__":
    main()
