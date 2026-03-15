import httpx
import asyncio

async def test():
    async with httpx.AsyncClient() as client:
        res = await client.post("http://localhost:8000/api/bloggers", json={
            "url": "https://v.douyin.com/iMe3tSNa/"
        }, timeout=60.0)
        print("Status", res.status_code)
        print("Body", res.text)

if __name__ == "__main__":
    asyncio.run(test())
