"""
AI二创专家 Web界面
"""
from pywebio.input import *
from pywebio.output import *
from pywebio.pin import *
from pywebio.session import run_js, run_async
import httpx
import asyncio


class AICreativeView:
    """AI二创专家Web视图"""

    def __init__(self):
        self.api_base = "http://localhost:8080/api/ai"

    def main_view(self):
        """主视图"""
        # 页面头部
        put_html("""
        <div style="text-align: center; padding: 20px;">
            <h1>🎬 AI二创专家</h1>
            <p style="color: #666;">基于AI大模型的智能视频二创助手</p>
        </div>
        """)

        # 功能说明
        put_collapse('📖 使用说明', [
            put_markdown("""
            ### 功能介绍
            - 支持抖音、TikTok、B站视频链接解析
            - AI深度分析视频内容
            - 根据需求生成二创方案
            - 提供文案、剪辑建议等

            ### 使用步骤
            1. 粘贴视频链接
            2. 选择二创类型
            3. 描述你的二创需求
            4. 点击开始分析
            5. 等待AI生成结果

            ### 二创类型说明
            - **通用分析**: 全面分析视频，提供综合建议
            - **文案创作**: 专注于生成解说文案和标题
            - **精彩片段**: 识别视频亮点，提供剪辑建议
            - **深度解说**: 深入分析内容，提供评论角度
            """)
        ], open=False)

        put_html("<hr>")

        # 输入表单
        put_markdown("### 📝 输入信息")

        # 视频链接输入
        put_input('video_url', label='视频链接',
                  placeholder='粘贴抖音/TikTok/B站视频链接...',
                  help_text='支持分享链接、短链接、完整链接')

        # 二创类型选择
        put_radio('creative_type', label='二创类型',
                  options=[
                      {'label': '🎯 通用分析', 'value': 'general'},
                      {'label': '✍️ 文案创作', 'value': 'script'},
                      {'label': '✂️ 精彩片段', 'value': 'highlights'},
                      {'label': '🎤 深度解说', 'value': 'commentary'}
                  ],
                  value='general')

        # 用户需求输入
        put_textarea('user_prompt', label='二创需求',
                     placeholder='描述你的二创需求，例如：\n- 帮我写一个搞笑版的解说文案\n- 找出视频中最精彩的3个片段\n- 分析这个视频的创意点，给我改编建议',
                     rows=5,
                     help_text='详细描述你想要的二创效果')

        put_html("<br>")

        # 提交按钮
        put_buttons([
            {'label': '🚀 开始AI分析', 'value': 'analyze', 'color': 'primary'}
        ], onclick=lambda _: self.analyze_video_sync())

        # 结果显示区域
        put_html("<div id='result_area'></div>")

    def analyze_video_sync(self):
        """同步包装的分析视频函数"""
        asyncio.run(self.analyze_video())

    async def analyze_video(self):
        """分析视频"""
        # 获取输入值
        video_url = pin.video_url
        creative_type = pin.creative_type
        user_prompt = pin.user_prompt

        # 验证输入
        if not video_url:
            toast('请输入视频链接', color='error')
            return

        if not user_prompt:
            toast('请描述你的二创需求', color='error')
            return

        # 显示加载状态
        clear('result_area')
        with use_scope('result_area'):
            put_html("<hr>")
            put_markdown("### 🔄 AI分析中...")
            put_loading(shape='border', color='primary')
            put_text("正在解析视频...")

        try:
            # 调用API
            async with httpx.AsyncClient(timeout=180.0) as client:
                # 更新状态
                with use_scope('result_area', clear=True):
                    put_html("<hr>")
                    put_markdown("### 🔄 AI分析中...")
                    put_loading(shape='border', color='primary')
                    put_text("视频解析完成，AI正在深度分析...")

                response = await client.get(
                    f"{self.api_base}/ai_creative_simple",
                    params={
                        'url': video_url,
                        'prompt': user_prompt,
                        'type': creative_type
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    await self.display_result(result)
                else:
                    error_msg = response.json().get('detail', '未知错误')
                    with use_scope('result_area', clear=True):
                        put_html("<hr>")
                        put_error(f"❌ 分析失败: {error_msg}")

        except httpx.TimeoutException:
            with use_scope('result_area', clear=True):
                put_html("<hr>")
                put_error("❌ 请求超时，请稍后重试")
        except Exception as e:
            with use_scope('result_area', clear=True):
                put_html("<hr>")
                put_error(f"❌ 发生错误: {str(e)}")

    async def display_result(self, result):
        """显示分析结果"""
        with use_scope('result_area', clear=True):
            put_html("<hr>")
            put_markdown("### ✅ AI分析完成")

            # 视频信息
            video_info = result.get('data', {}).get('video_info', {})
            put_collapse('📹 视频信息', [
                put_table([
                    ['平台', video_info.get('platform', 'N/A')],
                    ['标题', video_info.get('title', 'N/A')],
                    ['作者', video_info.get('author', 'N/A')],
                ])
            ])

            put_html("<br>")

            # AI分析结果
            ai_analysis = result.get('data', {}).get('ai_analysis', {})
            content = ai_analysis.get('content', '')

            put_markdown("### 🤖 AI二创建议")
            put_scrollable(
                put_markdown(content),
                height=500,
                keep_bottom=False
            )

            put_html("<br>")

            # 使用信息
            usage = ai_analysis.get('usage', {})
            if usage:
                put_collapse('📊 使用统计', [
                    put_table([
                        ['模型', ai_analysis.get('model', 'N/A')],
                        ['输入Token', usage.get('prompt_tokens', 'N/A')],
                        ['输出Token', usage.get('completion_tokens', 'N/A')],
                        ['总Token', usage.get('total_tokens', 'N/A')],
                    ])
                ], open=False)

            put_html("<br>")

            # 操作按钮
            put_buttons([
                {'label': '🔄 继续分析', 'value': 'continue', 'color': 'primary'},
                {'label': '📋 复制结果', 'value': 'copy', 'color': 'success'}
            ], onclick=[
                lambda: self.reset_form_sync(),
                lambda: self.copy_result(content)
            ])

    def reset_form_sync(self):
        """同步包装的重置表单函数"""
        asyncio.run(self.reset_form())

    async def reset_form(self):
        """重置表单"""
        pin.video_url = ''
        pin.user_prompt = ''
        clear('result_area')
        toast('已重置，可以开始新的分析', color='success')

    def copy_result(self, content):
        """复制结果到剪贴板"""
        # 使用JavaScript复制到剪贴板
        run_js(f"""
        navigator.clipboard.writeText(`{content}`).then(() => {{
            console.log('复制成功');
        }});
        """)
        toast('结果已复制到剪贴板', color='success')


def ai_creative_app():
    """启动AI二创应用"""
    view = AICreativeView()
    asyncio.run(view.main_view())
