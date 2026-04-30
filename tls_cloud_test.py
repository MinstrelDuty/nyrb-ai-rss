import requests
import re
from datetime import datetime, timedelta

def cloud_test_smart_time_filter():
    print("🚀 启动 TLS 云端环境专项测试 (智能时间过滤版)...")
    
    # 🎯 目标：锁定你之前测试成功过的文章分片
    sitemap_url = "https://www.the-tls.com/tls_articles-sitemap25.xml"
    jina_url = f"https://r.jina.ai/{sitemap_url}"
    
    headers = {
        "Accept": "text/plain",
        "X-No-Cache": "true"
    }
    
    print(f"📡 正在通过 Jina 提取 XML 数据库并进行时间比对: {sitemap_url}")
    
    try:
        response = requests.get(jina_url, headers=headers, timeout=40)
        response.raise_for_status()
        
        # 🕰️ 定义“本周”的时间窗口（例如过去 7 天）
        # 考虑到 TLS 每周五更新，设为 8 天可以稳稳覆盖一整期
        time_window_days = 8
        time_threshold = datetime.now() - timedelta(days=time_window_days)
        print(f"📅 过滤阈值：只保留 {time_threshold.strftime('%Y-%m-%d')} 之后发布的文章")

        # 🔪 核心提取逻辑：匹配 <loc>链接</loc> 和紧随其后的 <lastmod>日期</lastmod>
        # re.DOTALL 允许跨行匹配
        blocks = re.findall(r'<loc>(https://www.the-tls.com/[a-zA-Z0-9\-\/]+)</loc>\s*<lastmod>(.*?)</lastmod>', response.text, re.DOTALL)
        
        results = []
        for link, lastmod in blocks:
            # 1. 基础路径过滤
            if any(x in link for x in ['/issues/', '/category/', '/author/', '/tag/', '/topics/', 'wp-content']):
                continue
                
            # 2. 时间过滤
            try:
                # lastmod 格式通常为 2026-04-30T10:00:00+00:00，取前 10 位
                mod_date = datetime.strptime(lastmod[:10], '%Y-%m-%d')
                if mod_date >= time_threshold:
                    results.append({"url": link, "date": lastmod[:10]})
            except Exception:
                continue

        # 🎯 结果展示
        print("\n" + "="*60)
        print(f"✅ 智能过滤成功！在最近 {time_window_days} 天内共锁定 {len(results)} 篇本期文章。")
        print("="*60)
        
        if results:
            # 倒序排列，最新的在前
            results.reverse()
            for i, item in enumerate(results[:60], 1):
                print(f"{i:02d}. [{item['date']}] {item['url']}")
            
            print(f"\n💡 结论：该方案可以完美实现云端全自动“按期”抓取。")
        else:
            print("❌ 未发现最近 8 天内更新的文章。可能是本周尚未更新，或需要检查分片编号。")
            print(f"提示：XML 中最新的一条记录日期是: {blocks[-1][1][:10] if blocks else '无记录'}")
        print("="*60)

    except Exception as e:
        print(f"❌ 测试异常: {e}")

if __name__ == "__main__":
    cloud_test_smart_time_filter()
