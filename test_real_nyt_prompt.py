import os
import sys
import requests

# ==========================================
# ⚙️ 配置区
# ==========================================
# 目标测试文章：Carissa Véliz 的《Prophecy》书评
TARGET_URL = "https://www.nytimes.com/2026/04/29/books/review/prophecy-carissa-veliz.html"
API_URL = "https://api.deepseek.com/v1/chat/completions" # 替换为你的大模型 API 地址

def fetch_real_text_via_jina(url):
    """通过 Jina 提取真实网页纯文本"""
    print(f"🕸️ [阶段一] 正在穿透 NYT 防爬墙获取真实文本...")
    jina_url = f"https://r.jina.ai/{url}"
    headers = {"Accept": "text/plain"}
    
    try:
        response = requests.get(jina_url, headers=headers, timeout=30)
        response.raise_for_status()
        text = response.text
        print(f"✅ 成功获取正文！文本长度: {len(text)} 字符")
        return text
    except Exception as e:
        print(f"❌ [获取失败] 无法提取文章内容: {e}")
        sys.exit(1)

def test_prompt_tuning(article_text):
    """将真实文本送入炼丹炉测试"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ [环境变量错误] 未找到 DEEPSEEK_API_KEY，请先 export 或在系统中设置。")
        sys.exit(1)

    print("\n🔥 [阶段二] 启动 AI 炼丹炉，开始精读分析...")
    
    # 截断超长文本以防 Token 溢出（取前 15000 字符，对书评来说足够了）
    safe_text = article_text[:15000]

    # 经过优化的、专门针对你前端结构的终极 Prompt
    prompt = """
    你是一个极其专业的纽约时报书评（NYT Book Review）分析师。
    请阅读以下英文书评内容，并严格按照指定格式生成一份中文深度精读报告。

    【输出格式要求（极其严格）】：
    你的输出必须分为两部分，中间用分隔符 "=====" 隔开。绝对不要输出任何 markdown 代码块（如 ```html）。

    第一部分（一行数据，用 ||| 分隔）：
    [极具吸引力的中文标题] ||| ✍️ 作者：[提取书评作者] | 🎯 探讨对象：[书名及原作者] ||| [一句话犀利破题，控制在30字内]

    第二部分（HTML 格式的深度正文，直接输出 h3, p, ul 标签，不需要外层 div）：
    <h3>📰 核心脉络</h3>
    <p>[提炼文章的核心观点和论述脉络]</p>
    <h3>🧠 独立点评</h3>
    <p>[给出你对这篇书评的评价或拓展思考]</p>
    <ul>
       <li><strong>金句摘录：</strong>[提取一句原文金句并翻译]</li>
    </ul>

    【以下是待分析的真实书评正文】：
    """ + safe_text

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5 # 适中的温度，兼顾准确性和语言的生动性
    }

    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        
        result = response.json()['choices'][0]['message']['content']
        print("✅ AI 响应成功！\n")
        
        # ================== 结果检验 ==================
        print("=" * 50)
        print("📦 AI 原始输出预览：\n")
        print(result)
        print("=" * 50)
        
        print("\n🪓 [阶段三] 格式容错率与切割检验...")
        if "=====" in result:
            parts = result.split("=====")
            header_meta = parts[0].strip()
            html_body = parts[1].strip()
            
            print("\n👉 [检验一：前端分隔符解析]")
            if header_meta.count("|||") >= 2:
                print(f"  ✅ 成功识别头部数据：\n  {header_meta}")
            else:
                print(f"  ❌ 头部丢失 '|||' 分隔符，前端将会解析失败！提取到的头部：{header_meta}")
                
            print("\n👉 [检验二：HTML 标签纯净度]")
            if html_body.startswith("<h3") or html_body.startswith("<p"):
                 print("  ✅ 正文排版以原生 HTML 标签开头，适合直接注入网页！")
            elif "```html" in html_body:
                 print("  ⚠️ AI 多此一举生成了 Markdown 代码块，你需要进一步用 replace('```html', '') 清洗！")
            else:
                 print("  ⚠️ 正文格式似乎不太对劲，预览前 50 字：")
                 print(f"  {html_body[:50]}...")
                 
        else:
            print("❌ 数据未找到 '=====' 核心分隔符！提示词彻底失败！")

        print("\n🎉 真实场景炼丹测试结束！")

    except requests.exceptions.RequestException as e:
        print(f"❌ [API 请求失败] 请检查网络或 API Key: {e}")
        if hasattr(e, 'response') and e.response is not None:
             print(f"  返回详情: {e.response.text}")

if __name__ == "__main__":
    print("开始执行 NYT 真实网页分析测试...\n")
    # 1. 抓取真实文本
    article_content = fetch_real_text_via_jina(TARGET_URL)
    
    # 2. 喂给 AI
    test_prompt_tuning(article_content)
