import os
import sys
import requests
import re
import markdown

# ==========================================
# 🎯 靶场配置区 (在这里换上你想测试的任意 NYT 链接)
# ==========================================
TARGET_URL = "https://www.nytimes.com/2026/04/29/books/review/japanese-gothic-kylie-lee-baker.html" # 默认测试这篇容易翻车的书单
API_URL = "https://api.deepseek.com/chat/completions" 

def fetch_real_text_via_jina(url):
    print(f"\n🕸️ [阶段一] 正在穿透 NYT 防爬墙获取真实文本 -> {url}")
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

def test_single_article(article_text):
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ [环境变量错误] 未找到 DEEPSEEK_API_KEY，请检查设置。")
        sys.exit(1)

    print("\n🔥 [阶段二] 启动 AI 炼丹炉，开始压力测试...")
    safe_text = article_text[:15000] # 截断保护

    # 👇 融入了“终极警告”的满级提示词
    prompt = """你是一位为时间宝贵的精英读者写作的资深主笔。请基于提供的文章撰写精读报告。
【最高指令】：总字数控制在800字以内！严禁以“想象一下”等呆板词汇开头。绝不允许给【】标签加上Markdown的加粗星号！

（🚨 核心逻辑：动态体裁适配）
请在阅读原文后，先判断文章体裁，再决定【正文】内部的结构安排。

▶️ 【体裁A：常规深度书评 / 独立随笔】（默认）
【正文】内部结构必须为：
### 📰 核心脉络
（像讲故事一样梳理文章逻辑，精准嵌入2-3个核心细节）
### 🧠 独立点评
（指出文章在学术界或思想史的坐标）
### 📚 延伸矩阵
（推荐3本真实存在的相关著作并简评，严禁伪造）

▶️ 【体裁B：多本书单 / 新书盘点】（如“5月新书”、“本周精选8本”）
【正文】内部结构请彻底抛弃脉络与延伸，直接变更为：
### 📚 精选新书速览
（如果原书单超过10本，请为你认为最具价值的 6-8 本书撰写简介即可，切勿超时长篇大论）
- **《[中文书名]》([原书名])** | ✍️ [作者]
  💡 **核心看点**：[用2-3句话精准概括该书的内容、卖点或编辑的推荐理由。必须严格基于原文内容，绝不许凭空捏造情节！]
（重复此列表直到精选结束）
### 🧠 综合短评
（约150字。跳出单本书，简单点评这份书单整体反映了当下怎样的出版趋势或时代情绪。）


👇 请务必严格按照以下带有【】的标签格式输出，不要有任何偏差：

【中文标题】
精准且具有吸引力的中文翻译

【作者与对象】
格式：“✍️ 作者：[作者名] ｜ 🎯 探讨对象：[如果是书评写《书名》；如果是书单写“多本新书盘点”]”

【一句话破题】
用一句极具张力的话（不超过40字），直接点破这篇文章或这份书单的核心看点。

【正文】
（从这里开始使用Markdown排版。请严格根据上述的【动态体裁适配】决定这里面的小标题和内容！）

【以下是待分析的真实文章正文】：
""" + safe_text

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.6
    }

    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        
        result = response.json()['choices'][0]['message']['content']
        
        print("\n" + "=" * 50)
        print("📦 AI 原始输出预览 (未切割前)：\n")
        print(result)
        print("=" * 50)
        
        print("\n🪓 [阶段三] 正则化清洗与切割检验...")
        
        # 提前清洗 AI 可能擅自加上的 Markdown 加粗星号，防止正则失效
        ai_text_clean = result.replace('**【', '【').replace('】**', '】')
        
        try:
            zh_title = re.search(r'【中文标题】(.*?)【作者与对象】', ai_text_clean, re.S).group(1).strip().replace('\n', ' ')
            meta_info = re.search(r'【作者与对象】(.*?)【一句话破题】', ai_text_clean, re.S).group(1).strip().replace('\n', ' ')
            hook = re.search(r'【一句话破题】(.*?)【正文】', ai_text_clean, re.S).group(1).strip().replace('\n', ' ')
            body_md = re.search(r'【正文】(.*)', ai_text_clean, re.S).group(1).strip()
            
            print("\n👉 [检验一：标签提取状态] ✅ 成功！")
            print(f"  📌 标题: {zh_title}")
            print(f"  📌 元信息: {meta_info}")
            print(f"  📌 破题: {hook}")
            
            # 测试 Markdown 转 HTML
            html_body = markdown.markdown(body_md, extensions=['extra'])
            print("\n👉 [检验二：Markdown 渲染] ✅ 成功！")
            print(f"  📝 正文 HTML 前 100 字符预览: \n  {html_body[:100]}...")

        except AttributeError:
            print("\n❌ [提取失败] AI 输出了异常格式，正则引擎未能匹配到完整的 4 个标签！")
            print("⚠️ 触发降级机制：将暴力刮除标签并提取全文...")
            
            zh_title = "智能解析遇到偏差"
            meta_info = "✍️ 详见正文 ｜ 🎯 综合探讨"
            hook = "核心洞见提取失败，请直接阅读深度正文。"
            body_md = re.sub(r'【.*?】', '', ai_text_clean).strip()
            print(f"  📝 降级提取后的正文预览: \n  {body_md[:100]}...")

        print("\n🎉 单篇极限测试结束！")

    except Exception as e:
        print(f"❌ [API 请求失败] {e}")

if __name__ == "__main__":
    article_content = fetch_real_text_via_jina(TARGET_URL)
    test_single_article(article_content)
