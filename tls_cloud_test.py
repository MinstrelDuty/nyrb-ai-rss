import requests
import re
from datetime import datetime, timedelta

def cloud_test_adaptive_scanning():
    print("🚀 启动 TLS 终极自适应测试 (黑名单过滤 + 动态时间窗)...")
    
    # 🎯 扫描最近的两个分片
    target_shards = ["26", "25"]
    headers = {"Accept": "text/plain", "X-No-Cache": "true"}
    
    # 🗓️ 动态时间窗口：锁定最近 8 天（确保覆盖一整期且允许少量重叠）
    time_threshold = datetime.now() - timedelta(days=8)
    
    # 🚫 黑名单：排除所有非文章路径
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
            # 1. 抓取 XML 文本
            resp = requests.get(f"https://r.jina.ai/{url}", headers=headers, timeout=40)
            
            # 2. 暴力提取链接与日期块
            blocks = re.findall(r'<loc>(.*?)</loc>.*?<lastmod>(.*?)</lastmod>', resp.text, re.DOTALL)
            print(f"   🔎 分片 {num} 原始数据含 {len(blocks)} 条记录")

            for link, lastmod in blocks:
                # 🟢 校验 A: 路径层级必须 > 4 (排除首页和频道页)
                if len(link.split('/')) <= 4:
                    continue
                
                # 🟢 校验 B: 不在黑名单内
                if any(bad in link for bad in BLACK_LIST):
                    continue

                # 🟢 校验 C: 时间门禁
                try:
                    # 解析 2026-04-30 这种格式
                    mod_date = datetime.strptime(lastmod[:10], '%Y-%m-%d')
                    if mod_date >= time_threshold:
                        if link not in found_articles:
                            found_articles.append({"url": link, "date": lastmod[:10]})
                except:
                    continue
                    
        except Exception as e:
            print(f"   ❌ 分片 {num} 访问异常: {e}")

    # 3. 排序：最新的排在最前
    found_articles.sort(key=lambda x: x['date'], reverse=True)

    print("\n" + "="*60)
    print(f"✅ 自适应扫描完毕！本期共发现 {len(found_articles)} 篇新文章。")
    print("="*60)
    
    if found_articles:
        for i, item in enumerate(found_articles, 1):
            print(f"{i:02d}. [{item['date']}] {item['url']}")
    else:
        print("⚠️ 未发现新文章。可能本周尚未发布，或需检查更高编号的分片。")
    print("="*60)

if __name__ == "__main__":
    cloud_test_adaptive_scanning()
