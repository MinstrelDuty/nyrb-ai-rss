import requests
import re

def cloud_test_rss_brute_force():
    print("🚀 启动 TLS 云端环境专项测试 (RSS 暴力正则版)...")
    
    # 🎯 目标：TLS 官方 RSS
    rss_url = "https://www.the-tls.com/feed"
    jina_url = f"https://r.jina.ai/{rss_url}"
    
    # 💡 强制要求 Jina 只搬运纯文本，不要做任何多余的渲染
    headers = {
        "Accept": "text/plain", 
        "X-No-Cache": "true"
    }
    
    print(f"📡 正在通过 Jina 代理强力抽取 RSS 文本: {rss_url}")
    
    try:
        response = requests.get(jina_url, headers=headers, timeout=40)
        response.raise_for_status()
        
        # 🧪 打印前 500 个字符看看抓到了什么（调试用）
        print(f"📄 成功获取数据，前 500 字符预览: \n{response.text[:500]}...")
        
        # 🔪 核心杀招：直接用正则匹配 <link> 标签中的内容或所有 TLS 长链接
        # 这种方法免疫所有解析器的标签变异
        links = re.findall(r'https://www.the-tls.com/[a-zA-Z0-9\-\/]+', response.text)
        
        # 去重并保持顺序
        unique_links = []
        for l in links:
            if l not in unique_links:
                unique_links.append(l)
        
        # 🎯 精准过滤
        urls = []
        for link in unique_links:
            # TLS 文章链接通常层级较深（大于 4 个斜杠）
            if len(link.split('/')) > 4:
                # 排除 RSS 常见的干扰项
                if any(x in link for x in ['/issues/', '/category/', '/author/', '/tag/', '/topics/', 'wp-content', '.xml']):
                    continue
                urls.append(link)

        print("\n" + "="*60)
        print(f"✅ 暴力提取成功！自动锁定 {len(urls)} 篇最新文章链接。")
        print("="*60)
        
        if urls:
            for i, url in enumerate(urls[:50], 1):
                print(f"{i:02d}. {url}")
            print(f"\n💡 结论：RSS 路径通畅，可以实现全自动按期抓取。")
        else:
            print("❌ 警告：依然没抓到链接。请检查预览文字，看看是不是返回了防火墙拦截页。")
        print("="*60)

    except Exception as e:
        print(f"❌ 云端测试异常: {e}")

if __name__ == "__main__":
    cloud_test_rss_brute_force()
