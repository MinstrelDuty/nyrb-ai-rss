import requests
import re

def cloud_test_final_bomb():
    print("🚀 启动 TLS 终极渗透测试 (高级浏览器指纹模拟)...")
    
    # 回归目录页，因为这是你“按期抓取”的唯一源头
    target_url = "https://www.the-tls.com/issues/current-issue/"
    jina_url = f"https://r.jina.ai/{target_url}"
    
    # 🛰️ 这里的 headers 是关键：模拟极高真实度的请求
    headers = {
        "Accept": "text/html",
        "X-No-Cache": "true",
        "X-Return-Format": "html",
        "X-Wait-For-Selector": ".tls-card-headline", # 必须等到标题加载
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1" # 模拟手机 Safari，防御通常较弱
    }
    
    print(f"📡 正在尝试击穿 CloudFront 防御层: {target_url}")
    
    try:
        # 设置更长的超时，等待 Jina 模拟指纹
        response = requests.get(jina_url, headers=headers, timeout=60)
        
        # 看看这次返回的是 403 还是真正的 HTML
        if "403 ERROR" in response.text or "Request blocked" in response.text:
            print("❌ 依然被 403 拦截。云端 IP 已被封锁。")
            return
            
        print(f"📄 数据预览: {response.text[:300]}...")
        
        # 提取链接
        links = re.findall(r'https://www.the-tls.com/[a-zA-Z0-9\-\/]+', response.text)
        urls = []
        for l in list(dict.fromkeys(links)):
            if len(l.split('/')) > 4 and not any(x in l for x in ['/issues/', '/category/', '/author/', '/tag/', '/topics/']):
                urls.append(l)

        print(f"\n✅ 击穿成功！锁定 {len(urls)} 篇文章链接。")
        for i, url in enumerate(urls[:50], 1):
            print(f"{i:02d}. {url}")

    except Exception as e:
        print(f"❌ 测试异常: {e}")

if __name__ == "__main__":
    cloud_test_final_bomb()
