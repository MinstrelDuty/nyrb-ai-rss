import os
import sys
import requests
import re
import markdown

# ==========================================
# 🎯 靶场配置区
# ==========================================
# 测试书单类：https://www.nytimes.com/2026/04/29/books/new-books-may.html
# 测试深度书评：https://www.nytimes.com/2026/04/29/books/review/prophecy-carissa-veliz.html
TARGET_URL = "https://www.nytimes.com/2026/04/29/books/new-books-may.html" 
API_URL = "https://api.deepseek.com/chat/completions" 

def fetch_real_text_via_jina(url):
    print(f"\n🕸️ [阶段一] 获取真实文本 -> {url}")
    jina_url = f"https://r.jina.ai/{url}"
    headers = {"Accept": "text/plain"}
    try:
        response = requests.get(jina_url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"❌ [获取失败]: {e}")
        sys.exit(1)

def call_deepseek(prompt, temperature=0.6):
    """通用的 API 调用包装函数"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature
    }
    response = requests.post(API_URL, json=payload, headers=headers, timeout=120)
    response.raise_for_status()
    return response.json()['choices'][0]['message']['content'].strip()

def detect_article_type(title, text):
    """🚦 智能路由器：只用标题和前 1000 字，极速判断体裁"""
    print("🚦 [阶段二] 启动 AI 路由分诊台，正在判断文章体裁...")
    
    router_prompt = f"""
    判断以下文章的体裁。只允许输出 "REVIEW" 或 "LIST" 两个词之一，不要有任何标点或废话。
    - 如果它主要是在深入评论一本书、一部电影、或者是一篇独立散文，输出 "REVIEW"
    - 如果它是一份包含多本书的新书盘点、推荐书单（如：x月份新书、本周精选x本），输出 "LIST"
    
    标题：{title}
    开头截取：{text[:1000]}
    """
    try:
        result = call_deepseek(router_prompt, temperature=0.1) # 低温度，保证输出稳定
        # 容错：如果 AI 没听话多输出了字，只要包含 LIST 就判定为 LIST
        if "LIST" in result.upper():
            return "LIST"
        return "REVIEW"
    except Exception as e:
        print(f"⚠️ 路由判断失败，默认回退到 REVIEW 模式: {e}")
        return "REVIEW"

def test_single_article(url, article_text):
    safe_text = article_text[:20000] 
    
    # 用 URL 最后一段做个临时标题给路由用
    fallback_title = url.split('/')[-1].replace('.html', '').replace('-', ' ').title()
    
    # 1. 🚦 先进行路由判断
    article_type = detect_article_type(fallback_title, safe_text)
    print(f"✅ AI 判定结果：【{article_type}】模式")

    # 2. 🧠 根据路由结果，装载专属的提示词
    print(f"\n🔥 [阶段三] 启动【{article_type}】专属炼丹炉...")
    
    if article_type == "LIST":
        # ==================================================
        # 📚 专属提示词 A：盘点书单生成器
        # ==================================================
        final_prompt = """你是一位纽约时报的资深图书编辑。这是一篇新书盘点/推荐书单文章。
请严格按照以下【】标签格式输出报告。绝不允许自创标签！不要给标签加粗！

【中文标题】
精准且具有吸引力的中文翻译

【作者与对象】
✍️ 作者：纽约时报编辑部 ｜ 🎯 探讨对象：多本新书盘点

【一句话破题】
用一句极具张力的话（不超过40字），概括这份书单整体的时代气息或核心主题。

【正文】
（从这里开始使用Markdown排版）
### 📚 新书速览矩阵
（请遍历并提取出原文提到的书目，简明扼要地概括每本书的核心看点。不要写废话长篇大论。）
- **《[中文书名]》([原书名])** | ✍️ [作者]
  💡 **核心看点**：[用1-2句话精准概括该书的内容、卖点。严格基于原文，绝不捏造！]
- **《[中文书名]》([原书名])** | ✍️ [作者]
  💡 **核心看点**：[同上]
（依此类推，列出文章中的书目）

### 🧠 编辑部短评
（约150字。跳出单本书，简单点评这份书单整体反映了当下怎样的出版趋势、时代情绪或知识界关注的焦点。）

【以下是待分析的书单正文】：
""" + safe_text

    else:
        # ==================================================
        # 📰 专属提示词 B：深度学术书评生成器 (你之前的满级提示词)
        # ==================================================
        final_prompt = """你是一位为时间宝贵的精英读者写作的资深主笔。请基于提供的文章撰写精读报告。
【最高指令】：总字数严格控制在600字左右！严禁以“想象一下”等呆板词汇开头。绝不允许自创标签！不要给标签加粗！
（🔔 特别注意：如果检测到本文是一首诗歌、短篇小说或极短篇随笔，请自动将“独立点评”和“脉络梳理”调整为【文学赏析与意境解读】风格。）

请务必严格按照以下带有【】的标签格式输出，不要有任何偏差：

【中文标题】
直接写出英文标题的精准且具有吸引力的中文翻译

【作者与对象】
✍️ 作者：[文章作者名] ｜ 🎯 探讨对象：[如果是书评，写《书名》及原书作者；如果是独立随笔，写“独立随笔”]

【一句话破题】
用一句极具张力的话（不超过40字），直接点破这篇文章的核心冲突或洞见

【正文】
（从这里开始使用Markdown排版）
### 📰 核心脉络
（约300字）语言要极具可读性，像讲故事一样梳理文章逻辑，必须精准嵌入2-3个核心细节。

### 🧠 独立点评
（约200字）必须进行学术史层面的考察。指出文章在思想史或学术界的坐标。

### 📚 延伸矩阵
（🚨 绝对铁律：推荐的所有书籍必须是【现实中真实存在的出版物】！每本书用1-2句话详实介绍其学术价值）
- **核心相关（1本）**：与文章探讨的具体对象直接相关。
- **相同脉络（1本）**：与作者理论底色相同或同属一个思想谱系。
- **不同观点（1-2本）**：提供截然不同的解释框架或反面视角的著作。

【以下是待分析的深度书评正文】：
""" + safe_text

    # 3. 🚀 发送最终请求
    try:
        result = call_deepseek(final_prompt, temperature=0.6)
        
        print("\n" + "=" * 50)
        print("📦 AI 原始输出预览：\n")
        print(result)
        print("=" * 50)
        
        # 4. 🪓 通用的正则切割检验
        print("\n🪓 [阶段四] 正则化清洗与切割检验...")
        ai_text_clean = result.replace('**【', '【').replace('】**', '】')
        try:
            zh_title = re.search(r'【中文标题】(.*?)【作者与对象】', ai_text_clean, re.S).group(1).strip().replace('\n', ' ')
            meta_info = re.search(r'【作者与对象】(.*?)【一句话破题】', ai_text_clean, re.S).group(1).strip().replace('\n', ' ')
            hook = re.search(r'【一句话破题】(.*?)【正文】', ai_text_clean, re.S).group(1).strip().replace('\n', ' ')
            body_md = re.search(r'【正文】(.*)', ai_text_clean, re.S).group(1).strip()
            
            print("👉 [检验一：标签提取状态] ✅ 成功！四大部件完美分离。")
        except AttributeError:
            print("\n❌ [提取失败] 触发降级机制：将暴力刮除标签并提取全文...")

        print("\n🎉 单篇极限测试结束！")
    except Exception as e:
        print(f"❌ [请求失败] {e}")

if __name__ == "__main__":
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("❌ [环境变量错误] 未找到 DEEPSEEK_API_KEY")
        sys.exit(1)
        
    article_content = fetch_real_text_via_jina(TARGET_URL)
    test_single_article(TARGET_URL, article_content)
