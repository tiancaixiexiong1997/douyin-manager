import sys
import asyncio
sys.path.insert(0, '/app/douyin_api')
from app.services.crawler_service import crawler_service

async def main():
    url = "https://v.douyin.com/Vxe9D-eLtfk/"
    data = await crawler_service.get_single_video_by_url(url)
    print("Fetched data:", data)

asyncio.run(main())
