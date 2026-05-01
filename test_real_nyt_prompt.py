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
   prompt = """你是一位为时间宝贵的精英读者写作的资深主笔。请基于提供的文章撰写精读报告。
【最高指令】：总字数严格控制在600字左右！严禁以“想象一下”等呆板词汇开头。
（🔔 特别注意：如果检测到本文是一首诗歌、短篇小说或极短篇随笔，请自动将“独立点评”和“脉络梳理”调整为【文学赏析与意境解读】风格，延伸阅读可推荐相关的诗集或文学评论。）

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
（约300）语言要极具可读性，像讲故事一样梳理文章逻辑，必须精准嵌入2-3个核心细节（如关键史实、概念或人物）。

### 🧠 独立点评
（约200字）必须进行学术史层面的考察。指出文章在思想史或学术界的坐标，它回应了什么争论？延续或挑战了哪种范式？

### 📚 延伸矩阵
（🚨 绝对铁律：推荐的所有书籍必须是【现实中真实存在的出版物】，严禁AI伪造书名或作者！宁可推荐稍微宽泛但真实的经典著作，也绝不能编造！每本书需用1-2句话详实介绍其学术价值）
- **核心相关（1本）**：与文章探讨的具体对象直接相关。
- **相同脉络（1本）**：与作者理论底色相同或同属一个思想谱系。
- **不同观点（1-2本）**：提供截然不同的解释框架或反面视角的著作。"""


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
