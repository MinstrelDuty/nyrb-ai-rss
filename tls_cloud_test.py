import requests
import re
from datetime import datetime, timedelta

def cloud_test_robust_adaptive():
    print("🚀 启动 TLS 终极自适应测试 (健壮正则版)...")
    
    target_shards = ["26", "25"]
    headers = {"Accept": "text/plain", "X-No-Cache": "true"}
    
    # 动态时间窗口
    time_threshold = datetime.now() - timedelta(days=8)
    
    # 🚫 黑名单
    BLACK_LIST = [
        '/author/', '/tag/', '/topics/', '/category/', 
        '/issues/', '/feed/', 'wp-json', 'wp-content',
        '/crossword-quiz/', '/letters-to-the-editor/'
    ]
    
    found_articles = []
    print(f"📡 正在扫描分片，寻找 {time_threshold.strftime('%Y-%m-%d')} 之后的所有更新...")

    for num in target_shards:
        url = f"https://www.the-tls.com/tls_articles-sitemap{num}.xml"
        try:
            resp = requests.get(f"https://r.jina.ai/{url}", headers=headers, timeout=40)
            text = resp.text
            
            # 💡 核心改动：不再依赖 XML 标签，直接抓取 URL 和紧随其后的日期字符串
            # 匹配逻辑：匹配 https://www.the-tls.com/ 后面跟着一串路径，
            # 然后尝试在附近寻找符合 YYYY-MM-DD 格式的日期
            matches = re.findall(r'(https://www.the-tls.com/[^\s<"\'\)]+).*?(\d{4}-\d{2}-\d{2})', text, re.DOTALL)
            
            if not matches:
                print(f"   🔎 分片 {num} 未通过组合匹配找到数据，尝试单独抓取链接...")
                # 备选方案：只抓链接
                only_links = re.findall(r'https://www.the-tls.com/[^\s<"\'\)]+', text)
                print(f"   🔎 分片 {num} 原始文本包含 {len(only_links)} 个链接。")
                # 如果只有链接没有日期，为了全自动，我们可以选择信任最新分片的前 50 条
                continue

            print(f"   🔎 分片 {num} 匹配到 {len(matches)} 组潜在数据")

            for link, lastmod in matches:
                # 校验路径深度
                if len(link.split('/')) <= 4: continue
                # 校验黑名单
                if any(bad in link for bad in BLACK_LIST): continue

                # 校验时间
                try:
                    mod_date = datetime.strptime(lastmod, '%Y-%m-%d')
                    if mod_date >= time_threshold:
                        if not any(a['url'] == link for a in found_articles):
                            found_articles.append({"url": link, "date": lastmod})
                except:
                    continue
                    
        except Exception as e:
            print(f"   ❌ 分片 {num} 访问异常: {e}")

    # 排序
    found_articles.sort(key=lambda x: x['date'], reverse=True)

    print("\n" + "="*60)
    print(f"✅ 自适应扫描完毕！本期共发现 {len(found_articles)} 篇新文章。")
    print("="*60)
    
    for i, item in enumerate(found_articles, 1):
        print(f"{i:02d}. [{item['date']}] {item['url']}")
    print("="*60)

if __name__ == "__main__":
    cloud_test_robust_adaptive()
