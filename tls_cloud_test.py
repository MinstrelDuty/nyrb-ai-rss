import requests
import re

def cloud_test_sitemap_extraction():
    print("🚀 启动 TLS 云端环境专项测试 (Sitemap 暴力渗透版)...")
    
    # 🎯 目标：锁定你之前日志中出现过的 25、26 号文章分片
    # 2026年4月/5月的文章极大概率就在这两个分片中
    sitemap_urls = [
        "https://www.the-tls.com/tls_articles-sitemap26.xml",
        "https://www.the-tls.com/tls_articles-sitemap25.xml"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0",
        "Accept": "text/plain" # 💡 关键：只要求返回纯文本，不渲染
    }
    
    all_found_urls = []

    for target in sitemap_urls:
        print(f"\n📡 正在渗透分片: {target}")
        # 通过 Jina 仅仅作为代理读取 XML 文本
        jina_proxy_url = f"https://r.jina.ai/{target}"
        
        try:
            response = requests.get(jina_proxy_url, headers=headers, timeout=40)
            response.raise_for_status()
            
            # 🔪 核心杀招：直接用正则从 XML 文本中抠出文章链接
            # 匹配 https://www.the-tls.com/ 后面跟着一系列字母数字和斜杠的字符串
            matches = re.findall(r'https://www.the-tls.com/[a-zA-Z0-9\-\/]+', response.text)
            
            # 去重
            matches = list(dict.fromkeys(matches))
            
            # 过滤掉非文章链接
            filtered = []
            for href in matches:
                if len(href.split('/')) > 4:
                    if any(x in href for x in ['/issues/', '/categor', '/author', '/tag', '/topics/', 'wp-content']):
                        continue
                    filtered.append(href)
            
            print(f"✅ 成功从该分片提取到 {len(filtered)} 个链接！")
            all_found_urls.extend(filtered)
            
        except Exception as e:
            print(f"❌ 渗透失败: {e}")

    # 展示结果
    print("\n" + "="*60)
    print(f"📊 总计抓取到 {len(all_found_urls)} 篇唯一文章链接。")
    print("="*60)
    
    # 打印前 50 篇供核对
    for i, url in enumerate(all_found_urls[:50], 1):
        print(f"{i:02d}. {url}")
    print("="*60)

if __name__ == "__main__":
    cloud_test_sitemap_extraction()
