"""
AI二创专家测试脚本
用于测试API是否正常工作
"""
import asyncio
import httpx


async def test_ai_creative():
    """测试AI二创API"""

    print("🧪 开始测试AI二创API...")
    print()

    # 测试视频链接（使用一个示例链接）
    test_url = input("请输入测试视频链接（抖音/TikTok/B站）: ").strip()

    if not test_url:
        print("❌ 未输入视频链接")
        return

    test_prompt = input("请输入测试需求（例如：帮我分析这个视频）: ").strip()

    if not test_prompt:
        test_prompt = "请帮我分析这个视频的内容，并提供二创建议"

    print()
    print("📝 测试参数:")
    print(f"  视频链接: {test_url}")
    print(f"  用户需求: {test_prompt}")
    print(f"  二创类型: general")
    print()

    try:
        print("🔄 正在调用API...")

        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.get(
                "http://localhost/api/ai/ai_creative_simple",
                params={
                    'url': test_url,
                    'prompt': test_prompt,
                    'type': 'general'
                }
            )

            if response.status_code == 200:
                result = response.json()
                print("✅ API调用成功!")
                print()
                print("=" * 60)
                print("📹 视频信息:")
                print("=" * 60)
                video_info = result.get('data', {}).get('video_info', {})
                print(f"平台: {video_info.get('platform', 'N/A')}")
                print(f"标题: {video_info.get('title', 'N/A')}")
                print(f"作者: {video_info.get('author', 'N/A')}")
                print()

                print("=" * 60)
                print("🤖 AI分析结果:")
                print("=" * 60)
                ai_analysis = result.get('data', {}).get('ai_analysis', {})
                content = ai_analysis.get('content', '')
                print(content)
                print()

                print("=" * 60)
                print("📊 使用统计:")
                print("=" * 60)
                usage = ai_analysis.get('usage', {})
                print(f"模型: {ai_analysis.get('model', 'N/A')}")
                print(f"输入Token: {usage.get('prompt_tokens', 'N/A')}")
                print(f"输出Token: {usage.get('completion_tokens', 'N/A')}")
                print(f"总Token: {usage.get('total_tokens', 'N/A')}")

            else:
                print(f"❌ API调用失败: {response.status_code}")
                print(f"错误信息: {response.text}")

    except httpx.TimeoutException:
        print("❌ 请求超时，请检查网络或视频大小")
    except httpx.ConnectError:
        print("❌ 无法连接到服务器，请确保服务已启动")
        print("   运行: python start.py")
    except Exception as e:
        print(f"❌ 发生错误: {str(e)}")


if __name__ == "__main__":
    print("=" * 60)
    print("🎬 AI二创专家 - API测试工具")
    print("=" * 60)
    print()
    print("⚠️  请确保服务已启动: python start.py")
    print()

    asyncio.run(test_ai_creative())
