import os
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# ==========================================
# ⚙️ 调试区：你只需要修改这里的两个变量
# ==========================================

# 1. 测试对象：填入一篇你想用来做“小白鼠”的文章链接
TEST_URL = "https://www.lrb.co.uk/the-paper/v48/n08/william-davies/easy-to-join-easy-to-leave"

# 2. 提示词试验场：在这里随意修改、打磨你的 Prompt
TEST_PROMPT = """你是一位为时间宝贵的精英读者写作的资深主笔。请基于提供的文章撰写精读报告。
【最高指令】：总字数必须严格控制在 800-1000 字左右！语言必须极度凝练、通俗、犀利。

请严格按以下结构和字数限制输出（使用Markdown格式）：
1. 🎯 一句话破题（绝不超过 40 字）
2. 📰 核心脉络（控制在 300-400 字）
3. 🧠 独立点评（控制在 200 字左右）
4. 📚 延伸矩阵（3-4 本即可，每本一句话推荐理由）"""

# ==========================================
# 🚀 以下是底层引擎，无需修改
# ==========================================
print("正在启动提示词沙盒测试...")

api_key = os.getenv("DEEPSEEK_API_KEY", "").strip(" '\"\n\r\t")
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Referer": "https://www.google.com/",
    "X-Forwarded-For": "66.249.66.1"
}

def scrape_single_article(url):
    print(f"📥 正在抓取测试文章: {url}")
    response = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    title_tag = soup.find('h1')
    title = title_tag.text.strip() if title_tag else "测试文章"
    
    paragraphs = soup.find_all('p')
    text = "\n".join([p.text.strip() for p in paragraphs if p.text.strip()])
    return title, text[:15000]

def run_test():
    title, text = scrape_single_article(TEST_URL)
    if len(text) < 500:
        print("❌ 抓取失败或文章太短，请更换测试链接。")
        return

    print("🧠 正在请求 DeepSeek 进行 AI 处理 (预计需要 10-20 秒)...")
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": TEST_PROMPT},
                {"role": "user", "content": f"标题：《{title}》\n正文：\n{text}"}
            ],
            temperature=0.7
        )
        result = response.choices[0].message.content
        
        # 将结果写入本地 Markdown 文件
        output_filename = "test_result.md"
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(f"# 调试结果：{title}\n\n")
            f.write(result)
            
        print(f"\n✅ 测试完成！结果已保存到当前目录下的【{output_filename}】文件。")
        print("👇 预览输出前 300 个字符：")
        print("-" * 50)
        print(result[:300] + "......")
        print("-" * 50)
        
    except Exception as e:
        print(f"❌ API 请求失败: {e}")

if __name__ == "__main__":
    if not api_key:
        print("⚠️ 请先设置 DEEPSEEK_API_KEY 环境变量！")
    else:
        run_test()
