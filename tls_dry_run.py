import requests
import re
import time

def test_tls_full_issue_scrape():
    print("🚀 启动 TLS 零 Token 干跑测试 (Dry Run)...\n")
    
    # ==========================================
    # 阶段 1：测试目录页抓取与链接过滤
    # ==========================================
    target_url = "https://www.the-tls.com/issues/current-issue/" 
    jina_url = f"https://r.jina.ai/{target_url}"
    urls = []
    
    print(f"🕵️ [阶段1] 使用 Jina 传送门强行解析目录 -> {target_url}")
    try:
        headers = {
            "Accept": "text/markdown",
            "X-No-Cache": "true"
        }
        response = requests.get(jina_url, headers=headers, timeout=30)
        response.raise_for_status()
        text = response.text
        
        # 正则提取
        link_pattern = re.compile(r'\[.*?\]\((https?://.*?|/.*?)\)')
        matches = link_pattern.findall(text)
        
        for href in matches:
            if href.startswith('/'):
                href = "https://www.the-tls.com" + href
            href = href.strip(")'\"")
                
            if href.startswith('https://www.the-tls.com/') and len(href.split('/')) > 4:
                # 我们昨天优化的终极词根过滤网
                if any(x in href for x in ['/issues/', '/categor', '/author', '/tag', '/about', '/buy', '/login', '/subscribe', '/my-account', '/letters']):
                    continue
                    
                if href not in urls:
                    urls.append(href)
        
        print(f"\n🎯 目录解析完毕！共锁定 {len(urls)} 篇纯净文章链接。")
        print("-" * 50)
        for i, u in enumerate(urls, 1):
            print(f"{i:02d}. {u}")
        print("-" * 50 + "\n")
        
    except Exception as e:
        print(f"❌ 目录抓取失败: {e}")
        return

    # ==========================================
    # 阶段 2：抽样测试正文抓取 (验证是否被墙)
    # ==========================================
    if not urls:
        print("⚠️ 没有抓到任何链接，测试终止。")
        return

    test_count = min(3, len(urls)) # 只测前 3 篇，节约时间
    print(f"🕵️ [阶段2] 抽取前 {test_count} 篇文章进行正文抓取测试 (不调用 AI)...\n")
    
    for i in range(test_count):
        test_url = urls[i]
        print(f"📄 测试 {i+1}: {test_url}")
        try:
            art_jina_url = f"https://r.jina.ai/{test_url}"
            resp = requests.get(art_jina_url, headers=headers, timeout=30)
            resp.raise_for_status()
            
            content_length = len(resp.text)
            
            if content_length < 1500:
                print(f"   ⚠️ 警告：只抓到 {content_length} 字符，大概率撞上了付费墙！")
            else:
                print(f"   ✅ 成功：抓取到 {content_length} 字符，反爬虫已被击穿！")
                
            time.sleep(3) # 对 Jina 稍微温柔一点
            
        except Exception as e:
            print(f"   ❌ 抓取正文失败: {e}")

    print("\n🎉 干跑测试结束！请核对上面的链接列表是否全部是真正的文章。")

if __name__ == "__main__":
    test_tls_full_issue_scrape()
