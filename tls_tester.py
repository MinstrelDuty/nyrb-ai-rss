import os
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import cloudscraper # 🚀 引入破壁神器

# ==========================================
# 0. 炼丹炉配置 (云端环境)
# ==========================================
# GitHub Actions 会自动注入这个环境变量
api_key = os.getenv("DEEPSEEK_API_KEY", "").strip(" '\"\n\r\t")

# 初始化 OpenAI 客户端
try:
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
except Exception as e:
    print(f"❌ 初始化 DeepSeek 客户端失败: {e}")
    exit(1)

# 【重要】：每次测试前，请在这里换上你想测试的 TLS 文章链接
TEST_URL = "https://www.the-tls.com/arts/visual-arts/tracey-emin-second-life-tate-modern-london-review-sophie-oliver"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.google.com/"
}

# ==========================================
# ==========================================
# 1. 探针：使用 CloudScraper 潜入 TLS
# ==========================================
def scrape_tls_article(url):
    print(f"🕵️ 正在潜入 TLS 抓取文章 (启动 CloudScraper 伪装): {url}")
    try:
        # 🚀 实例化破壁机，伪装成最新的 Windows Chrome 浏览器
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        
        # 使用 scraper 替代原先的 requests
        response = scraper.get(url, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 获取标题
        title_tag = soup.find('h1')
        title = title_tag.text.strip() if title_tag else "未获取标题"
        
        # TLS 的正文通常藏在特定的段落类名中，或者直接抓 <p>
        paragraphs = soup.find_all('p')
        text_blocks = [p.get_text(separator=' ', strip=True) for p in paragraphs]
        text = "\n".join([t for t in text_blocks if len(t) > 30])
        
        print("\n" + "="*50)
        print(f"📊 【云端抓取报告】")
        print(f"网页返回状态码: {response.status_code}")
        print(f"英文原标题: {title}")
        print(f"抓取到的总字符数: {len(text)} 字符")
        print("="*50 + "\n")
        
        # 拦截刚才那个好笑的“真人验证”警告
        if "Help us verify real visitors" in title or "potentially automated" in text:
            print("🚨 警报：CloudScraper 伪装失效，依然被 TLS 防火墙拦截！")
            return None
            
        if len(text) < 1500:
            print("⚠️ 警告：可能撞上了付费墙（Paywall）！下面是抓取到的部分原文：\n")
            print(text[:500] + "......\n")
        else:
            print("✅ 成功突破防火墙！下面是部分原文展示：\n")
            print(text[:500] + "......\n")
            
        return {"title": title, "url": url, "text": text}
        
    except Exception as e:
        print(f"❌ 抓取失败: {e}")
        return None

# ==========================================
# 2. 炼丹：AI 浓缩提取测试
# ==========================================
def test_ai_prompt(article_data):
    if not article_data or len(article_data["text"]) < 100:
        print("❌ 文本太短，无法进行 AI 炼丹。")
        return
        
    text = article_data["text"][:80000] 
    
    # 🚀 针对 TLS 特制的【超浓缩版】提示词
    system_prompt = """你是一位为时间宝贵的精英读者写作的资深主笔。请基于提供的文章撰写精读报告。
【最高指令】：本文篇幅较短，总字数必须极其严苛地控制在 400-600 字左右！语言必须极度凝练、犀利。严禁以“想象一下”等呆板词汇开头。

请务必严格按照以下带有【】的标签格式输出：

【中文标题】
直接写出英文标题的精准且具有吸引力的中文翻译

【作者与对象】
格式必须为：“✍️ 作者：[文章作者名] ｜ 🎯 探讨对象：[评论的具体书名/对象]”

【一句话破题】
用一句极具张力的话（不超过40字），直接点破文章核心。

【正文】
### 📰 核心脉络
（150-200字）极其简练地梳理文章逻辑，只保留最核心的冲突或观点。

### 🧠 独立点评
（约100字）简明扼要地指出文章在思想史或学术界的价值。

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
    print("🚀 启动 GitHub 云端炼丹炉...")
    data = scrape_tls_article(TEST_URL)
    test_ai_prompt(data)
