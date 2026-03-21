import asyncio
import httpx
import base64
import os
import ssl
import certifi

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
    
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    limits = httpx.Limits(max_keepalive_connections=0, max_connections=1)
    timeout = httpx.Timeout(300.0)
    
    # Try different combinations of HTTP protocol
    print("\nTrying HTTP/1.1:")
    async with httpx.AsyncClient(timeout=timeout, limits=limits, http1=True, http2=False, verify=False) as client:
        try:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Connection": "close"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    "max_tokens": 10
                }
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print("Success!")
            else:
                print(f"Error: {response.text[:100]}")
        except Exception as e:
            print(f"Failed: {type(e).__name__} - {e}")

asyncio.run(main())
