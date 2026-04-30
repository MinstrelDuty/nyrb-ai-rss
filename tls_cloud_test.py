import requests
from bs4 import BeautifulSoup

def cloud_test_current_issue_extraction():
    print("🚀 启动 TLS 云端环境专项测试 (按期刊目录精准版)...")
    
    # 🎯 目标：锁定最新一期目录页
    target_url = "https://www.the-tls.com/issues/current-issue/" 
    jina_url = f"https://r.jina.ai/{target_url}"
    
    # 🚀 配置：要求 Jina 返回 HTML，并强制等待目录元素渲染
    headers = {
        "Accept": "text/html",
        "X-No-Cache": "true",
        "X-Return-Format": "html",
        "X-Wait-For-Selector": ".tls-card-headline" 
    }
    
    print(f"📡 正在通过 Jina 调取渲染后的目录页: {target_url}")
    try:
        # 设置 60 秒超时，因为云端渲染 JS 比较耗时
        response = requests.get(jina_url, headers=headers, timeout=60)
        response.raise_for_status()
        
        # 使用 BeautifulSoup 解析
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 🕵️ 精准定位：只寻找 class 包含 tls-card-headline 的链接
        # 这就是你提供的源码中文章标题的特征
        article_links = soup.find_all('a', class_=lambda c: c and 'tls-card-headline' in c)
        
        urls = []
        for a in article_links:
            href = a.get('href', '')
            if href.startswith('/'):
                href = "https://www.the-tls.com" + href
            
            # 过滤掉分类、话题等干扰链接
            if "the-tls.com" in href and len(href.split('/')) > 4:
                if any(x in href for x in ['/issues/', '/category/', '/author/', '/tag/', '/topics/']):
                    continue
                if href not in urls:
                    urls.append(href)

        # 📊 输出结果
        print("\n" + "="*60)
        print(f"🎯 目录解析完毕！在本期中精准锁定 {len(urls)} 篇文章。")
        print("="*60)
        
        if len(urls) > 0:
            for i, url in enumerate(urls, 1):
                print(f"{i:02d}. {url}")
        else:
            print("❌ 依然抓到 0 篇。这说明 Jina 在云端被 TLS 防火墙挡住了 JS 渲染。")
        print("="*60)

    except Exception as e:
        print(f"❌ 云端测试发生致命错误: {e}")

if __name__ == "__main__":
    cloud_test_current_issue_extraction()
