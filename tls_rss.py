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

def get_latest_article_urls(existing_urls, max_items=80):
    """【终极健壮自适应版】对齐测试脚本成功逻辑，实现云端全自动"""
    import re
    import requests
    from datetime import datetime, timedelta

    # 1. 扫描最近的两个分片（确保跨周更新不遗漏）
    target_shards = ["26", "25"]
    headers = {"Accept": "text/plain", "X-No-Cache": "true"}
    
    # 2. 动态时间窗口：只看最近 8 天
    time_threshold = datetime.now() - timedelta(days=8)
    
    # 3. 严苛黑名单：排除掉所有非正文页面
    BLACK_LIST = [
        '/author/', '/tag/', '/topics/', '/category/', 
        '/issues/', '/feed/', 'wp-json', 'wp-content',
        '/crossword-quiz/', '/letters-to-the-editor/', '/highlights/'
    ]
    
    found_articles = []
    print(f"🔄 正在启动终极自适应扫描... 目标窗口: {time_threshold.strftime('%Y-%m-%d')} 至今")

    for num in target_shards:
        url = f"https://www.the-tls.com/tls_articles-sitemap{num}.xml"
        try:
            # 调用 Jina 获取纯文本
            resp = requests.get(f"https://r.jina.ai/{url}", headers=headers, timeout=40)
            text = resp.text
            
            # 💡 核心：健壮模糊匹配 (URL + 后面跟着的日期)
            # 这种写法免疫 XML 标签被 Jina 转换成 Markdown 的情况
            matches = re.findall(r'(https://www.the-tls.com/[^\s<"\'\)]+).*?(\d{4}-\d{2}-\d{2})', text, re.DOTALL)
            
            for link, lastmod in matches:
                # 去除 Jina 可能带上的 Markdown 尾巴 (如 ](url )
                clean_link = link.split(']')[0].split(')')[0]
                
                # 校验：路径层级 > 4
                if len(clean_link.split('/')) <= 4:
                    continue
                
                # 校验：不在黑名单
                if any(bad in clean_link for bad in BLACK_LIST):
                    continue

                # 校验：时间窗口
                try:
                    mod_date = datetime.strptime(lastmod, '%Y-%m-%d')
                    if mod_date >= time_threshold:
                        # 校验：是否已存在于数据库
                        if clean_link not in existing_urls and clean_link not in found_articles:
                            found_articles.append(clean_link)
                except:
                    continue
        except Exception as e:
            print(f"⚠️ 分片 {num} 扫描中断: {e}")

    # 4. 排序：最新发布的排在最前
    # 注意：Sitemap 通常按时间正序，我们取回后 reverse 一下
    found_articles.reverse()
    
    print(f"✅ 扫描完成：本期共精准锁定 {len(found_articles)} 篇待处理新文章。")
    return found_articles[:max_items]
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
    system_prompt = """你是一位为时间宝贵的精英读者写作的资深主笔，专门负责《泰晤士报文学增刊》(The TLS) 的深度转化。请基于提供的文章撰写精读报告。

【最高指令】：本文篇幅较短，总字数必须极其严苛地控制在 600-700 字左右！语言必须极度清晰、凝练、犀利。严禁以“想象一下”等呆板词汇开头。

【自适应处理准则】：
1. 若为 Book Review/Essay：侧重论点冲突与思想深度。
2. 若为 In Brief/NB/Freelance：侧重捕捉其讽刺艺术、短评定论或文坛轶事，保留其特有的机锋。
3. 若为 Poem/Original Poems：侧重意象解读与情感基调。

请务必严格按照以下带有【】的标签格式输出：

【中文标题】
直接写出文章/评论对象最精准且具有文人风骨的中文翻译

【作者与对象】
格式必须为：“✍️ 作者：[文章作者名] ｜ 🎯 探讨对象：[评论的具体书名/展览/事件/栏目主题]”

【一句话破题】
用一句极具张力的话（不超过40字），直接点破文章核心。

【正文】
### 📰 核心脉络
（约300字）极其简练地梳理逻辑。针对长文需提炼核心冲突；针对短评(In Brief)需整合其关键论断；针对专栏(NB)需捕捉其核心机锋。

### 🧠 独立点评
（约200字）简明扼要地指出文章在思想史、艺术界或文学现实中的价值。

### 📚 延伸矩阵
（严禁伪造！只需推荐 2-3 本核心相关或不同观点的真实著作，每本一句话介绍。若是专栏或随笔，可推荐作者的其他代表作）"""
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
    
    # 限制单次运行抓 60 篇，保护 API 和精力
    urls = get_latest_article_urls(existing_urls, max_items=60) 
    
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
