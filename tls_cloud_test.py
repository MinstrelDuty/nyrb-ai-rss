import requests
import re

def cloud_test_final_diagnostic():
    print("🚀 启动 TLS 极致容错测试 (全匹配模式)...")
    
    # 既然 25/24 没东西，我们扩大范围，强制扫描 25 和 26
    # 因为 2026 年的文章大概率就在这两个分片
    target_shards = ["26", "25"]
    
    headers = {"Accept": "text/plain", "X-No-Cache": "true"}
    CATEGORY_KEYWORDS = ['/arts/', '/history/', '/literature/', '/politics-society/', '/lives/', '/philosophy/']
    
    all_found_urls = []

    for num in target_shards:
        url = f"https://www.the-tls.com/tls_articles-sitemap{num}.xml"
        print(f"📡 正在探测分片 {num}: {url}")
        try:
            resp = requests.get(f"https://r.jina.ai/{url}", headers=headers, timeout=40)
            
            # 🧪 诊断：先看看有没有拿到任何链接
            # 不管是不是文章，只要是 https 链接都先抓出来
            raw_links = re.findall(r'https://[a-zA-Z0-9\.\-\/_]+', resp.text)
            print(f"   📊 原始文本发现 {len(raw_links)} 个潜在链接。")
            
            for link in raw_links:
                # 排除 XML 自身标签干扰
                if '.xml' in link or 'sitemaps.org' in link:
                    continue
                
                # 核心逻辑：包含 tls 且 命中分类关键词
                if "the-tls.com" in link and any(cat in link for cat in CATEGORY_KEYWORDS):
                    if link not in all_found_urls:
                        all_found_urls.append(link)
                        
        except Exception as e:
            print(f"   ❌ 分片 {num} 请求失败: {e}")

    print("\n" + "="*60)
    print(f"🎯 最终过滤战果：{len(all_found_urls)} 篇分类文章")
    print("="*60)
    
    # 倒序显示（通常最新的在 XML 底部，所以 reverse）
    all_found_urls.reverse()
    for i, l in enumerate(all_found_urls[:55], 1):
        print(f"{i:02d}. {l}")

if __name__ == "__main__":
    cloud_test_final_diagnostic()
