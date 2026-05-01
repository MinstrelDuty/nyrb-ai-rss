import time
import logging
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 填入你刚才找到的两篇测试文章
TEST_URLS = [
    "https://www.nytimes.com/2026/04/24/books/review/podcast-book-club-renovation-kenan-orhan.html",
    "https://www.nytimes.com/2026/04/23/books/hollywood-thriller-books.html"
]

def test_direct_wayback(url):
    """甩掉 Jina，直接请求 Wayback Machine 并自己解析 HTML"""
    logging.info(f"🕵️‍♂️ 启动纯净快照抓取 (无Jina) -> {url}")
    
    # 直接请求档案馆的最新快照
    wayback_url = f"https://web.archive.org/web/2/{url}"
    
    # 伪装成正常的浏览器，以免被档案馆当成恶意爬虫
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(wayback_url, headers=headers, timeout=45)
        response.raise_for_status()
        
        # 使用 BeautifulSoup 像手术刀一样切开网页
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 纽约时报的正文通常都在 <p> 标签里，我们把超过 20 个字的段落全抽出来拼接
        paragraphs = soup.find_all('p')
        text = "\n".join([p.get_text() for p in paragraphs if len(p.get_text()) > 20])
        
        if len(text) >= 800:
            preview = text[:150].replace('\n', ' ')
            logging.info(f"🎉 [实验成功] 完美拿到快照！字数: {len(text)}。")
            logging.info(f"👀 正文预览: {preview}...\n" + "-"*50)
        else:
            logging.error(f"❌ [实验失败] 快照无效或返回文本过短。字数: {len(text)}。")
            logging.error(f"👀 返回内容预览: {text[:200]}...\n" + "-"*50)
            
    except Exception as e:
        logging.error(f"❌ 请求崩溃: {e}")

if __name__ == "__main__":
    logging.info("🚀 开启脱离 Jina 的直连快照实验...\n" + "="*50)
    for target_url in TEST_URLS:
        test_direct_wayback(target_url)
        time.sleep(3) # 停顿一下
