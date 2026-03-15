import sys
import asyncio
sys.path.insert(0, '/app/douyin_api')
from crawlers.douyin.web.web_crawler import DouyinWebCrawler

async def main():
    crawler = DouyinWebCrawler()
    url = "https://v.douyin.com/Vxe9D-eLtfk/"
    aweme_id = await crawler.get_aweme_id(url)
    print(f"aweme_id: {aweme_id}")
    if aweme_id:
        detail = await crawler.fetch_video_detail(aweme_id)
        if detail and "aweme_detail" in detail:
            print("Successfully fetched video detail")
        else:
            print("Failed to fetch video detail", detail)

asyncio.run(main())
