import asyncio
import httpx
import base64
import os

async def main():
    api_key = "sk-nirYVw0B6njVfHWlpHU4RMelA3hP29xhbN8o0FXImrDECjYj"
    base_url = "https://api.openai-hub.com/v1"
    model = "gemini-3.1-pro-preview"
    
    dummy_b64 = "A" * (128 * 1024)
    print(f"Testing with payload size: {len(dummy_b64) / 1024 / 1024:.2f} MB")
    
    system_prompt = "You are a helpful assistant."
    user_content = [
        {"type": "text", "text": "Analyze these dummy keyframes"},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{dummy_b64}"}}
    ]
    
    # Create client with NO connection pooling and very generous limits
    limits = httpx.Limits(max_keepalive_connections=0, max_connections=1, keepalive_expiry=0.0)
    timeout = httpx.Timeout(180.0, connect=60.0, read=180.0, write=180.0)
    
    async with httpx.AsyncClient(timeout=timeout, limits=limits, http2=False) as client:
        try:
            print(f"Testing AI API connection to {base_url}...")
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Connection": "close"  # Force close
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    "max_tokens": 100,
                    "temperature": 0.7
                }
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print("Success!")
            else:
                print(f"Error response: {response.text[:200]}")
        except Exception as e:
            print(f"Connection failed: {type(e).__name__} - {e}")

asyncio.run(main())
