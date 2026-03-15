"""
简单测试脚本 - 测试视频解析
"""
import asyncio
from crawlers.hybrid.hybrid_crawler import HybridCrawler

async def test_parse():
    crawler = HybridCrawler()
    url = "https://v.douyin.com/vN43-d0nGzw/"

    print("开始解析视频...")
    result = await crawler.hybrid_parsing_single_video(url)

    print("\n解析结果:")
    print(f"状态: {result.get('status')}")
    print(f"平台: {result.get('platform')}")

    if result.get('status') == 'success':
        video_data = result.get('data', {}).get('video_data', {})
        print(f"标题: {video_data.get('desc', 'N/A')}")
        print(f"作者: {video_data.get('author', {}).get('nickname', 'N/A')}")
        print(f"视频URL: {video_data.get('nwm_video_url', 'N/A')[:100]}...")
    else:
        print(f"错误: {result}")

if __name__ == "__main__":
    asyncio.run(test_parse())
