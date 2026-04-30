import requests
import re

def cloud_test_final_victory():
    print("🚀 启动 TLS 终极渗透测试 (强制等待 JS 渲染版)...")
    
    target_url = "https://www.the-tls.com/issues/current-issue/"
    jina_url = f"https://r.jina.ai/{target_url}"
    
    headers = {
        "Accept": "text/html",
        "X-No-Cache": "true",
        "X-Return-Format": "html",
        # 🎯 核心：强制 Jina 等待这个特定的 class 出现，最多等 20 秒
        "X-Wait-For-Selector": ".tls-card-headline", 
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    }
    
    print(f"📡 正在等待 JS 渲染并解析目录: {target_url}")
    
    try:
        # 增加超时到 90 秒，给 JS 渲染留足时间
        response = requests.get(jina_url, headers=headers, timeout=90)
        
        # 检查是否包含核心 class
        if "tls-card-headline" not in response.text:
            print("⚠️ 警告：虽然击穿了防火墙，但 JS 渲染似乎未产生文章内容。")
            print(f"数据长度: {len(response.text)} 字符")
            # 看看返回的到底是啥，有没有可能是数据结构变了
        
        # 提取链接：我们只提取带有具体路径的文章链接
        links = re.findall(r'https://www.the-tls.com/[a-zA-Z0-9\-\/]+', response.text)
        
        urls = []
        for l in list(dict.fromkeys(links)):
            # 文章链接特征：层级深，且不含 wp-json, content 等开发路径
            if len(l.split('/')) > 4:
                if not any(x in l for x in ['/issues/', '/category/', '/author/', '/tag/', '/topics/', 'wp-', 'feed', 'oembed']):
                    urls.append(l)

        print("\n" + "="*60)
        print(f"✅ 最终战果：在云端成功锁定 {len(urls)} 篇文章链接！")
        print("="*60)
        
        if urls:
            for i, url in enumerate(urls[:60], 1):
                print(f"{i:02d}. {url}")
        else:
            print("❌ 解析失败：HTML 中未发现符合正则的文章链接。")
        print("="*60)

    except Exception as e:
        print(f"❌ 运行异常: {e}")

if __name__ == "__main__":
    cloud_test_final_victory()
