import sys
import requests
import xml.etree.ElementTree as ET

def test_nyt_rss():
    url = "https://rss.nytimes.com/services/xml/rss/nyt/Books/Review.xml"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    print(f"🚀 [测试启动] 正在尝试访问 NYT RSS: {url}")
    
    try:
        # 测试 1: 网络连通性
        response = requests.get(url, headers=headers, timeout=10)
        print(f"✅ [网络状态] HTTP {response.status_code}")
        response.raise_for_status()
        
        # 测试 2: XML 解析
        root = ET.fromstring(response.content)
        items = root.findall('.//item')
        print(f"✅ [解析结果] 成功获取到 {len(items)} 个 <item> 节点")
        
        if not items:
            print("⚠️ 警告：节点列表为空！")
            sys.exit(1)
            
        # 测试 3: 提取并清洗前 3 个链接展示
        print("-" * 40)
        print("🔍 预览最新 3 篇文章数据：")
        for i, item in enumerate(items[:3]):
            title = item.find('title').text if item.find('title') is not None else "无标题"
            raw_link = item.find('link').text if item.find('link') is not None else "无链接"
            clean_link = raw_link.split('?')[0] # 测试清洗逻辑
            
            print(f"\n[{i+1}] 标题: {title}")
            print(f"    原始链接: {raw_link}")
            print(f"    清洗后链接: {clean_link}")
            
        print("-" * 40)
        print("🎉 RSS 爬取测试通过！")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ [请求失败] 网络错误或被拦截: {e}")
        sys.exit(1)
    except ET.ParseError as e:
        print(f"❌ [解析失败] XML 格式错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ [未知错误] {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_nyt_rss()
