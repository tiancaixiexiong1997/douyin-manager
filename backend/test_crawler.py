import asyncio
from app.services.crawler_service import crawler_service

async def main():
    urls = [
        "https://v.douyin.com/vSo6kwWt8Ck/",
        "https://www.douyin.com/video/7463519822606863656"
    ]
    for url in urls:
        print(f"Testing URL: {url}")
        res = await crawler_service.get_single_video_by_url(url)
        if res:
            print(f"SUCCESS: {res.get('title')}")
        else:
            print("FAILED")

if __name__ == "__main__":
    asyncio.run(main())
