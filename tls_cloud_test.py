import requests
import re
from datetime import datetime, timedelta

def cloud_test_dynamic_full_auto():
    print("🚀 启动 TLS 终极全自动测试 (动态分片扫描)...")
    
    # 1. 先抓索引页，找到当前最大的分片编号
    index_url = "https://www.the-tls.com/sitemap_index.xml"
    headers = {"Accept": "text/plain", "X-No-Cache": "true"}
    
    try:
        print("📡 正在检索最新数据库索引...")
        index_resp = requests.get(f"https://r.jina.ai/{index_url}", headers=headers, timeout=30)
        # 找出所有 tls_articles-sitemapXX.xml
        all_shards = re.findall(r'tls_articles-sitemap(\d+)\.xml', index_resp.text)
        if not all_shards:
            print("❌ 未能获取分片列表，尝试手动降级扫描...")
            target_shards = ["26", "25"]
        else:
            # 取最大的两个分片，确保覆盖跨周更新
            latest_shard = max(map(int, all_shards))
            target_shards = [str(latest_shard), str(latest_shard - 1)]
        
        print(f"📂 锁定最新分片: {target_shards}")

        # 2. 扫描选定的分片
        CATEGORY_WHITELIST = ['/arts/', '/history/', '/literature/', '/politics-society/', '/lives/', '/philosophy/', '/science-technology/']
        final_articles = []
        
        for shard_num in target_shards:
            shard_url = f"https://www.the-tls.com/tls_articles-sitemap{shard_num}.xml"
            print(f"🔍 正在渗透分片 {shard_num}...")
            resp = requests.get(f"https://r.jina.ai/{shard_url}", headers=headers, timeout=30)
            
            # 暴力提取所有符合分类且路径够深的链接
            links = re.findall(r'<loc>(https://www.the-tls.com/[a-zA-Z0-9\-\/]+)</loc>', resp.text)
            
            for l in links:
                if any(cat in l for cat in CATEGORY_WHITELIST) and len(l.split('/')) > 4:
                    if not any(x in l for x in ['/author/', '/tag/', '/topics/']):
                        if l not in final_articles:
                            final_articles.append(l)

        # 3. 结果展示（模拟最新一期）
        # 我们不设时间门禁，直接取最新的 50 篇
        print("\n" + "="*60)
        print(f"✅ 扫描完毕！从最新数据库中提取到 {len(final_articles)} 篇候选文章。")
        print("="*60)
        
        # 这里的 reverse 是因为 Sitemap 通常旧的在前，新的在后
        final_articles.reverse()
        for i, url in enumerate(final_articles[:55], 1):
            print(f"{i:02d}. {url}")
            
    except Exception as e:
        print(f"❌ 运行异常: {e}")

if __name__ == "__main__":
    cloud_test_dynamic_full_auto()
