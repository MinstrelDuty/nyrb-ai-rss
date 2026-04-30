import requests
import re
from datetime import datetime, timedelta

def cloud_test_category_time_filter():
    print("🚀 启动 TLS 专项测试 (分类路径 + 时间窗口双重验证)...")
    
    # 🎯 目标分片
    sitemap_url = "https://www.the-tls.com/tls_articles-sitemap25.xml"
    jina_url = f"https://r.jina.ai/{sitemap_url}"
    
    # 🏷️ 你观察到的大分类关键词白名单
    # 只有命中这些路径的链接才被认为是“正文文章”
    CATEGORY_WHITELIST = [
        '/arts/', '/history/', '/literature/', '/politics-society/', 
        '/lives/', '/philosophy/', '/science-technology/', '/classics/',
        '/archaeology/', '/religion/', '/law/', '/economics/'
    ]
    
    print(f"📡 正在从分片中提取符合分类特征的最新文章...")
    
    try:
        response = requests.get(jina_url, headers={"Accept": "text/plain"}, timeout=40)
        
        # 设定 8 天的时间窗口（覆盖最新一期）
        time_threshold = datetime.now() - timedelta(days=8)
        
        # 提取链接和日期
        blocks = re.findall(r'<loc>(.*?)</loc>.*?<lastmod>(.*?)</lastmod>', response.text, re.DOTALL)
        
        results = []
        for link, lastmod in blocks:
            # 1. 验证分类：必须命中白名单中的一个大分类
            if not any(cat in link for cat in CATEGORY_WHITELIST):
                continue
            
            # 2. 验证时间：必须在最近 8 天内
            try:
                mod_date = datetime.strptime(lastmod[:10], '%Y-%m-%d')
                if mod_date < time_threshold:
                    continue
            except:
                continue
                
            # 3. 排除杂质
            if any(x in link for x in ['/topics/', '/author/', '/tag/']):
                continue

            results.append({"url": link, "date": lastmod[:10]})

        print("\n" + "="*60)
        print(f"✅ 过滤成功！在本期中精准锁定 {len(results)} 篇分类长文。")
        print("="*60)
        
        for i, item in enumerate(reversed(results), 1):
            print(f"{i:02d}. [{item['date']}] {item['url']}")
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")

if __name__ == "__main__":
    cloud_test_category_time_filter()
