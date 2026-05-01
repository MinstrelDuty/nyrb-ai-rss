import time
import logging
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 👇 把你从 4月21日 或 4月26日 快照里找出来的文章链接贴在这里
TEST_URLS = [
    "https://www.nytimes.com/2026/04/24/books/review/podcast-book-club-renovation-kenan-orhan.html", # 替换成真实链接 1
    "https://www.nytimes.com/2026/04/23/books/hollywood-thriller-books.html"   # 替换成真实链接 2
]

def test_wayback_machine_bypass(url):
    """纯粹测试路线2：直接向 Wayback Machine 索要历史快照正文"""
    logging.info(f"🕵️‍♂️ 启动实验：尝试从 Wayback Machine 提取 -> {url}")
    
    try:
        # 构造时光机穿透链接
        wayback_url = f"https://web.archive.org/web/2/{url}"
        jina_wayback = f"https://r.jina.ai/{wayback_url}"
        
        logging.info(f"🔗 实际请求地址: {jina_wayback}")
        
        response = requests.get(jina_wayback, headers={"Accept": "text/plain"}, timeout=50)
        text = response.text
        
        if len(text) >= 800 and "Wayback Machine has not archived that URL" not in text:
            preview = text[:150].replace('\n', ' ')
            logging.info(f"🎉 [实验成功] 完美拿到快照！字数: {len(text)}。")
            logging.info(f"👀 正文预览: {preview}...\n" + "-"*50)
        else:
            logging.error(f"❌ [实验失败] 快照无效或返回文本过短。字数: {len(text)}。")
            logging.error(f"👀 返回内容: {text[:200]}...\n" + "-"*50)
            
    except Exception as e:
        logging.error(f"❌ 请求崩溃: {e}")

if __name__ == "__main__":
    logging.info("🚀 开启 Wayback Machine 时光机穿透实验...\n" + "="*50)
    for target_url in TEST_URLS:
        test_wayback_machine_bypass(target_url)
        time.sleep(3) # 停顿3秒防封锁
