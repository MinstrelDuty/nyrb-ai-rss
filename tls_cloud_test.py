import requests
from bs4 import BeautifulSoup

def cloud_test_rss_extraction():
    print("🚀 启动 TLS 云端环境专项测试 (全自动 RSS 订阅源版)...")
    
    # 🎯 目标：TLS 官方 RSS
    rss_url = "https://www.the-tls.com/feed"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/xml"
    }
    
    print(f"📡 正在尝试读取 RSS 订阅源: {rss_url}")
    
    try:
        # 第一步：尝试直接请求
        print("尝试 1: 直连 RSS 源...")
        response = requests.get(rss_url, headers=headers, timeout=20)
        
        # 第二步：如果直连失败（比如返回 403 或 404），改用 Jina 代理
        if response.status_code != 200 or not response.text.strip():
            print(f"⚠️ 直连失败 (状态码: {response.status_code})，尝试通过 Jina 代理读取...")
            jina_url = f"https://r.jina.ai/{rss_url}"
            # 💡 强制使用纯文本模式，绕过 JS 渲染
            response = requests.get(jina_url, headers={"Accept": "text/plain"}, timeout=30)
        
        # 解析 XML
        # 注意：这里我们使用 'html.parser' 或 'xml' (如果安装了 lxml) 
        # 为了兼容性，先用 'html.parser' 演示
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # RSS 规范中链接通常在 <link> 标签内，嵌套在 <item> 中
        items = soup.find_all('item')
        
        urls = []
        for item in items:
            # 提取 link 标签的内容
            link = item.find('link').next_sibling.strip() if item.find('link') else ""
            if not link:
                # 有些 RSS 格式 link 标签直接包含文本
                link = item.link.text if item.link else ""
            
            if link and "the-tls.com" in link:
                # 基础过滤：排除掉非文章的链接
                if any(x in link for x in ['/issues/', '/category/', '/author/', '/tag/', '/topics/']):
                    continue
                if link not in urls:
                    urls.append(link)

        print("\n" + "="*60)
        print(f"✅ RSS 测试完毕！自动发现 {len(urls)} 篇最新文章链接。")
        print("="*60)
        
        if urls:
            for i, url in enumerate(urls[:50], 1): # 展示前 50 篇
                print(f"{i:02d}. {url}")
        else:
            print("❌ 警告：虽然读取了数据，但未发现有效文章链接。可能是解析规则需微调。")
        print("="*60)

    except Exception as e:
        print(f"❌ 云端测试发生异常: {e}")

if __name__ == "__main__":
    cloud_test_rss_extraction()
