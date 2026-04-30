import requests
from bs4 import BeautifulSoup
import time
import os

def cloud_test_tls_extraction():
    print("🚀 启动 TLS 云端环境专项测试 (Current Issue 强攻版)...")
    
    # 🎯 目标：直接狙击目录页
    target_url = "https://www.the-tls.com/issues/current-issue/" 
    jina_url = f"https://r.jina.ai/{target_url}"
    
    # 🚀 模拟云端高强度配置
    headers = {
        "Accept": "text/html",
        "X-No-Cache": "true",
        "X-Wait-For-Selector": ".tls-card-headline", # 核心：必须等到标题渲染出来
        "X-Return-Format": "html"
    }
    
    print(f"📡 正在通过 Jina 调取渲染后的 HTML: {target_url}")
    try:
        # 增加超时时间，云端渲染可能较慢
        response = requests.get(jina_url, headers=headers, timeout=60)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 精准定位文章链接 (基于你提供的源码特征)
        print("🕵️ 开始扫描 tls-card-headline 元素...")
        article_links = soup.find_all('a', class_=lambda c: c and 'tls-card-headline' in c)
        
        urls = []
        for a in article_links:
            href = a.get('href', '')
            if href.startswith('/'):
                href = "https://www.the-tls.com" + href
            
            # 排除非文章链接
            if "/authors/" in href or "/categories/" in href or "/topics/" in href:
                continue
                
            if href not in urls:
                urls.append(href)

        print(f"\n✅ 成功！在云端环境下共提取到 {len(urls)} 篇唯一文章链接。")
        print("-" * 60)
        for i, url in enumerate(urls[:50], 1): # 展示前50篇
            print(f"{i:02d}. {url}")
        print("-" * 60)

        # 抽样测试第一篇的正文抓取能力
        if urls:
            print(f"\n🧪 抽样测试第一篇正文抓取: {urls[0]}")
            test_headers = {"Accept": "text/markdown", "X-No-Cache": "true"}
            test_resp = requests.get(f"https://r.jina.ai/{urls[0]}", headers=test_headers, timeout=30)
            print(f"📄 抓取结果字数: {len(test_resp.text)} 字符")
            if len(test_resp.text) > 2000:
                print("🎉 测试通过：正文内容丰富，反爬已击穿！")
            else:
                print("⚠️ 警告：正文字数过少，可能仍被防火墙拦截。")

    except Exception as e:
        print(f"❌ 云端测试发生错误: {e}")

if __name__ == "__main__":
    cloud_test_tls_extraction()
