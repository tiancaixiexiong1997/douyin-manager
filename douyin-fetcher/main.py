import sys
import os
import re
from fastapi import FastAPI, Request, HTTPException, Query
from typing import Optional

app = FastAPI(title="Douyin Fetcher API")

DOUYIN_API_PATH = os.environ.get("DOUYIN_API_PATH", "/app/douyin_api")
if DOUYIN_API_PATH not in sys.path:
    sys.path.insert(0, DOUYIN_API_PATH)

def get_crawler():
    try:
        from crawlers.douyin.web.web_crawler import DouyinWebCrawler
        return DouyinWebCrawler()
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Crawler module import failed: {e}")

def get_config():
    try:
        from crawlers.douyin.web.web_crawler import config
        return config
    except ImportError:
        return {}

def clean_url(text: str) -> str:
    if not text:
        return ""
    match = re.search(r'https?://[a-zA-Z0-9./\-_=&?%]+', text)
    if match:
        return match.group(0)
    return text

def apply_dynamic_cookie(request: Request):
    """
    检查请求头中是否传了 X-Douyin-Cookie，如果传了，
    则临时覆盖到底层全局配置中供接下来马上执行的 crawler 抓取使用。
    """
    custom_cookie = request.headers.get("x-douyin-cookie")
    if custom_cookie:
        cfg = get_config()
        if cfg and "TokenManager" in cfg:
            cfg["TokenManager"].setdefault("douyin", {}).setdefault("headers", {})["Cookie"] = custom_cookie


@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/api/user")
async def get_user_profile(request: Request, url: str = Query(...)):
    apply_dynamic_cookie(request)
    crawler = get_crawler()
    clean = clean_url(url)
    sec_user_id = await crawler.get_sec_user_id(clean)
    if not sec_user_id:
        raise HTTPException(status_code=400, detail="Cannot extract sec_user_id from URL")
    
    profile_data = await crawler.handler_user_profile(sec_user_id)
    if not profile_data:
        raise HTTPException(status_code=404, detail="User profile not found")
        
    return {"sec_user_id": sec_user_id, "profile": profile_data}

@app.get("/api/videos")
async def get_videos(request: Request, sec_user_id: str = Query(...), count: int = Query(50), max_cursor: int = Query(0)):
    apply_dynamic_cookie(request)
    crawler = get_crawler()
    data = await crawler.fetch_user_post_videos(sec_user_id=sec_user_id, max_cursor=max_cursor, count=count)
    if not data:
        raise HTTPException(status_code=404, detail="No videos found or fetch failed")
    return {"data": data}

@app.get("/api/video")
async def get_video_detail(request: Request, url: str = Query(None), aweme_id: str = Query(None)):
    apply_dynamic_cookie(request)
    if not url and not aweme_id:
        raise HTTPException(status_code=400, detail="Must provide either url or aweme_id")
        
    crawler = get_crawler()
    
    if not aweme_id:
        clean = clean_url(url)
        try:
            aweme_id = await crawler.get_aweme_id(clean)
        except Exception:
            match = re.search(r'video/(\d+)', clean)
            if match:
                aweme_id = match.group(1)
                
    if not aweme_id:
        raise HTTPException(status_code=400, detail="Cannot extract aweme_id")
        
    data = await crawler.fetch_one_video(aweme_id)
    if not data:
        raise HTTPException(status_code=404, detail="Video details not found")
        
    return {"aweme_detail": data.get("aweme_detail", {})}

@app.get("/api/cookie")
async def get_douyin_cookie():
    douyin_config = get_config()
    cookie = douyin_config.get("TokenManager", {}).get("douyin", {}).get("headers", {}).get("Cookie", "")
    return {"cookie": cookie}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
