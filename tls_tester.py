import os
import requests
from openai import OpenAI

# ==========================================
# 0. 炼丹炉配置 (云端环境)
# ==========================================
api_key = os.getenv("DEEPSEEK_API_KEY", "").strip(" '\"\n\r\t")

try:
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
except Exception as e:
    print(f"❌ 初始化 DeepSeek 客户端失败: {e}")
    exit(1)

# 测试链接（你刚才的链接）
TEST_URL = "https://www.the-tls.com/arts/visual-arts/tracey-emin-second-life-tate-modern-london-review-sophie-oliver"

# ==========================================
# 1. 探针：祭出 Jina Reader 空间传送门
# ==========================================
def scrape_tls_article(url):
    print(f"🕵️ 启动终极武器：Jina Reader 代理抓取 -> {url}")
    try:
        # 🚀 魔法就在这里：只需要在原链接前面加上 https://r.jina.ai/
        jina_url = f"https://r.jina.ai/{url}"
        
        headers = {
            # 告诉 Jina，我们不要 HTML，请直接给我干净的 Markdown
            "Accept": "text/markdown", 
            # 绕过缓存，强制获取最新
            "X-No-Cache": "true" 
        }
        
        # 把超时时间设长一点，因为云端浏览器渲染需要时间
        response = requests.get(jina_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        text = response.text
        
        # 尝试从 Markdown 中提取标题（Jina 通常会把标题设为一级标题 #）
        title = "TLS 深度长文"
        first_line = text.split('\n')[0]
        if first_line.startswith('Title: '):
            title = first_line.replace('Title: ', '').strip()
        elif first_line.startswith('# '):
            title = first_line.replace('# ', '').strip()

        print("\n" + "="*50)
        print(f"📊 【终极武器抓取报告】")
        print(f"网页返回状态码: {response.status_code}")
        print(f"推测原标题: {title}")
        print(f"抓取到的总字符数: {len(text)} 字符")
        print("="*50 + "\n")
        
        # 拦截判断
        if len(text) < 1500:
            print("⚠️ 警告：字数过少，可能撞上了真·付费墙（Paywall）！\n")
            print("部分原文：\n" + text[:500] + "......\n")
            if "Subscribe" in text or "Log in" in text:
                print("🚨 确认撞上 TLS 商业付费墙！无法读取后半部分。")
        else:
            print("✅ 成功击穿所有防御机制！下面是极其纯净的 Markdown 原文：\n")
            print(text[:500] + "\n......(此处省略数千字)......\n")
            
        return {"title": title, "url": url, "text": text}
        
    except Exception as e:
        print(f"❌ 抓取失败: {e}")
        return None

# ==========================================
# 2. 炼丹：AI 浓缩提取测试 (保持不变)
# ==========================================
def test_ai_prompt(article_data):
    if not article_data or len(article_data["text"]) < 500:
        print("❌ 文本太短或被墙，无法进行 AI 炼丹。")
        return
        
    text = article_data["text"][:80000] 
    
    system_prompt = """你是一位为时间宝贵的精英读者写作的资深主笔。请基于提供的文章撰写精读报告。
【最高指令】：本文篇幅较短，总字数必须极其严苛地控制在 400-600 字左右！语言必须极度凝练、犀利。严禁以“想象一下”等呆板词汇开头。

请务必严格按照以下带有【】的标签格式输出：

【中文标题】
直接写出英文标题的精准且具有吸引力的中文翻译

【作者与对象】
格式必须为：“✍️ 作者：[文章作者名] ｜ 🎯 探讨对象：[评论的具体书名/展览/事件]”

【一句话破题】
用一句极具张力的话（不超过40字），直接点破文章核心。

【正文】
### 📰 核心脉络
（150-200字）极其简练地梳理文章逻辑，只保留最核心的冲突或观点。

### 🧠 独立点评
（约100字）简明扼要地指出文章在思想史或艺术界的价值。

### 📚 延伸矩阵
（严禁伪造！只需推荐 1-2 本核心相关或不同观点的真实著作，每本一句话介绍）"""

    print("🔥 正在将文章投入 DeepSeek 炼丹炉 (云端版)...\n")
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"标题：《{article_data['title']}》\n正文：\n{text}"}
            ],
            max_tokens=2000, temperature=0.7
        )
        print("\n✨ 【AI 提炼结果】 ✨\n")
        print(response.choices[0].message.content)
        
    except Exception as e:
        print(f"❌ AI 请求失败: {e}")

if __name__ == "__main__":
    print("🚀 启动 GitHub 云端炼丹炉 (究极降维版)...")
    data = scrape_tls_article(TEST_URL)
    test_ai_prompt(data)
