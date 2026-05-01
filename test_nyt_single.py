import os
import sys
import requests
import re
import markdown

# ==========================================
# 🧪 炼丹实验室配置区
# ==========================================
# 你可以在这里换成任何你想测试的 NYT 链接
TARGET_URL = "https://www.nytimes.com/2026/04/30/books/review/new-romance-books.html" 
API_URL = "https://api.deepseek.com/chat/completions" 

def fetch_real_text_via_jina(url):
    print(f"\n🕸️ [抓取阶段] 正在穿透获取真实文本 -> {url}")
    jina_url = f"https://r.jina.ai/{url}"
    headers = {"Accept": "text/plain"}
    try:
        response = requests.get(jina_url, headers=headers, timeout=30)
        response.raise_for_status()
        text = response.text
        print(f"✅ 成功获取！文本长度: {len(text)} 字符。预览: {text[:100].replace('\n', ' ')}...")
        return text
    except Exception as e:
        print(f"❌ [获取失败]: {e}")
        print("💡 提示：如果遇到 403 Forbidden，说明被 NYT 拦截了，请换个链接或晚点再试。")
        sys.exit(1)

def test_single_article(url, article_text):
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ [环境变量错误] 未找到 DEEPSEEK_API_KEY")
        sys.exit(1)

    safe_text = article_text[:80000] # 放宽截断字数，保证长书单能被完整吃下

    # ==========================================
    # 🚦 极速规则引擎：直接通过 URL 最后一段判断体裁
    # ==========================================
    url_slug = url.split('/')[-1].lower() 
    
    if "books" in url_slug:
        print("\n🚦 [路由判定] 命中关键词 'books' -> 走向【📚 书单盘点】炼丹炉！")
        
        system_prompt = """你是一位纽约时报的资深图书编辑。这是一篇新书盘点/推荐书单文章。
【最高指令】：绝不允许自创标签！不要给【】标签加粗！

请严格按照以下格式输出：

【中文标题】
精准且吸引人的中文翻译

【作者与对象】
✍️ 作者：纽约时报编辑部 ｜ 🎯 探讨对象：多本新书盘点

【一句话破题】
用一句极具张力的话（不超过40字），概括这份书单整体的核心主题或时代气息。

【正文】
（从这里开始使用Markdown排版）
### 📚 新书速览矩阵
（🚨 核心指令：请遍历原文，提取出文章中推荐的【每一本书】，绝不遗漏！如果因防爬墙导致无书名可提取，直接说明情况即可。）
- **《[中文书名]》([原书名])** | ✍️ [作者]
  💡 **核心看点**：[用1-2句话精准概括该书的内容、卖点。必须严格基于原文内容，绝不许凭空捏造！]
（重复此列表直到所有推荐书籍提取完毕）
### 🧠 编辑部短评
（约150字。跳出单本书，简单点评这份书单整体反映了当下的出版趋势或关注焦点。）
"""

    else:
        print("\n🚦 [路由判定] 未命中盘点词 -> 走向【📰 深度书评】炼丹炉！")
        
        system_prompt = """你是一位为时间宝贵的精英读者写作的资深主笔。请基于提供的深度文章撰写精读报告。
【最高指令】：总字数严格控制在600字左右！严禁以“想象一下”开头。绝不允许自创标签！不要给【】标签加粗！

请严格按照以下格式输出：

【中文标题】
直接写出英文标题的精准中文翻译

【作者与对象】
✍️ 作者：[文章作者名] ｜ 🎯 探讨对象：[如果是书评，写《书名》及原书作者]

【一句话破题】
用一句极具张力的话（不超过40字），直接点破这篇文章的核心冲突或洞见。

【正文】
（从这里开始使用Markdown排版）
### 📰 核心脉络
（约300字）语言要极具可读性，像讲故事一样梳理文章逻辑，必须精准嵌入2-3个核心细节（如关键史实、概念或人物）。

### 🧠 独立点评
（约200字）必须进行学术史层面的考察。指出文章在思想史或学术界的坐标，它回应了什么争论？延续或挑战了哪种范式？

### 📚 延伸矩阵
（🚨 绝对铁律：推荐的所有书籍必须是【现实中真实存在的出版物】，严禁AI伪造书名或作者！宁可推荐稍微宽泛但真实的经典著作，也绝不能编造！每本书需用1-2句话详实介绍其学术价值）
- **核心相关（1本）**：与文章探讨的具体对象直接相关。
- **相同脉络（1本）**：与作者理论底色相同或同属一个思想谱系。
- **不同观点（1-2本）**：提供截然不同的解释框架或反面视角的著作。"""

    # ==========================================
    # 🔥 启动炼丹炉 (发送 API 请求)
    # ==========================================
    print("🔥 正在向 DeepSeek 注入灵魂，请稍候...")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"原始英文素材：\n{safe_text}"}
        ],
        "temperature": 0.5
    }

    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        result = response.json()['choices'][0]['message']['content']
        
        print("\n" + "=" * 50)
        print("📦 AI 原始输出预览：\n")
        print(result)
        print("=" * 50)
        
        print("\n🪓 [切割检验阶段] 正则化清洗与校验...")
        ai_text_clean = result.replace('**【', '【').replace('】**', '】')
        
        try:
            zh_title = re.search(r'【中文标题】(.*?)【作者与对象】', ai_text_clean, re.S).group(1).strip().replace('\n', ' ')
            meta_info = re.search(r'【作者与对象】(.*?)【一句话破题】', ai_text_clean, re.S).group(1).strip().replace('\n', ' ')
            hook = re.search(r'【一句话破题】(.*?)【正文】', ai_text_clean, re.S).group(1).strip().replace('\n', ' ')
            body_md = re.search(r'【正文】(.*)', ai_text_clean, re.S).group(1).strip()
            
            print("👉 ✅ 成功！四大部件（标题/元数据/破题/正文）完美分离！你的前端页面不会崩溃。")
        except AttributeError:
            print("\n❌ 警告：AI 输出了异常格式，正则引擎未能匹配到完整的 4 个标签！你需要微调提示词。")

        print("\n🎉 炼丹测试结束！")

    except Exception as e:
        print(f"❌ [请求失败] {e}")

if __name__ == "__main__":
    # 填入你要测试的 URL
    test_url = TARGET_URL
    article_content = fetch_real_text_via_jina(test_url)
    test_single_article(test_url, article_content)
