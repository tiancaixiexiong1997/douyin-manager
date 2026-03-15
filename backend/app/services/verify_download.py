import asyncio
import os
import tempfile
import sys
import logging

# Mock logging for standalone test
logging.basicConfig(level=logging.INFO)

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.services.ai_analysis_service import ai_analysis_service

async def test_download():
    # 使用一个典型的长视频链接进行测试（如果有效）
    # 或者是一个已知会产生问题的链接
    url = "https://v26-web.douyinvod.com/0114fcfb29eb54bc7a0ca2f073289052/67caf595/video/tos/cn/tos-cn-ve-15c001-alinc2/oQe7H9B2C3k2AebFDe7vA8eAn6BAgIA8PBA4sC/?a=6383&ch=0&cr=3&dr=0&lr=all&cd=0%7C0%7C0%7C3&cv=1&br=1762&bt=1762&cs=0&ds=6&ft=rl&mime_type=video_mp4&qs=14&rc=aDk3ZmZkNTZndWk3OWQ7O0BpM3N5b2c5cmhpcjMzNGkzM0AuYF80LjQwNTEyMzA0Mi4yYSNrMmpxcjRvcmxgLS1kLS9zcw%3D%3D&btag=e00028000&cquery=100b&yhtpi=1810574b1"
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp_path = tmp.name
    
    try:
        print(f"Starting download to {tmp_path}...")
        success, detail = await ai_analysis_service._download_video_with_retry(url, tmp_path)
        
        if success:
            file_size = os.path.getsize(tmp_path)
            print(f"Download Success! Size: {file_size / 1024 / 1024:.2f} MB")
            if file_size < 1024 * 1024:
                print("WARNING: File is still suspiciously small (< 1MB)")
        else:
            print(f"Download Failed: {detail or 'unknown error'}")
            
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

if __name__ == "__main__":
    asyncio.run(test_download())
