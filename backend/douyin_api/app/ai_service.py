"""
AI二创服务模块
用于调用AI模型分析视频并生成二创内容
"""
import os
import yaml
import httpx
import base64
from typing import Optional, Dict, Any
from pathlib import Path
import tempfile


class AICreativeService:
    """AI二创服务类"""

    def __init__(self):
        # 加载AI配置
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ai_config.yaml')
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)

        self.api_key = config['AI']['API_KEY']
        self.base_url = config['AI']['BASE_URL']
        self.model = config['AI']['MODEL']
        self.max_tokens = config['AI']['MAX_TOKENS']
        self.temperature = config['AI']['TEMPERATURE']

    async def download_video(self, video_url: str) -> str:
        """
        下载视频到临时文件

        Args:
            video_url: 视频URL

        Returns:
            临时文件路径
        """
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.get(video_url)

                if response.status_code == 200:
                    # 创建临时文件
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
                    temp_file.write(response.content)
                    temp_file.close()
                    return temp_file.name
                else:
                    raise Exception(f"下载视频失败: HTTP {response.status_code}")
        except Exception as e:
            raise Exception(f"下载视频时出错: {str(e)}")

    async def analyze_video_from_url(
        self,
        video_url: str,
        video_title: str,
        user_prompt: str,
        creative_type: str = "general"
    ) -> Dict[str, Any]:
        """
        下载视频并分析

        Args:
            video_url: 视频URL
            video_title: 视频标题（用于上下文）
            user_prompt: 用户自定义需求
            creative_type: 二创类型

        Returns:
            AI分析结果
        """
        temp_file = None
        try:
            # 1. 下载视频
            print(f"正在下载视频: {video_url}")
            temp_file = await self.download_video(video_url)
            print(f"视频已下载到: {temp_file}")

            file_size = os.path.getsize(temp_file)
            file_size_mb = file_size / (1024 * 1024)
            print(f"视频文件大小: {file_size_mb:.2f} MB")

            # 2. 优先使用关键帧分析（更稳定、更高效）
            print("使用关键帧分析模式...")
            result = await self.analyze_video_by_frames(temp_file, video_title, user_prompt, creative_type)

            if result.get('success'):
                return result

            # 3. 如果关键帧分析失败，尝试完整视频分析
            print("关键帧分析失败，尝试完整视频分析...")

            # 如果视频太大，尝试压缩
            MAX_SIZE_MB = 5
            if file_size_mb > MAX_SIZE_MB:
                print(f"视频过大({file_size_mb:.2f}MB)，尝试压缩...")
                try:
                    compressed_file = await self.compress_video_simple(temp_file)
                    if compressed_file:
                        compressed_size = os.path.getsize(compressed_file)
                        compressed_size_mb = compressed_size / (1024 * 1024)
                        print(f"压缩后大小: {compressed_size_mb:.2f} MB")
                        os.unlink(temp_file)
                        temp_file = compressed_file
                        file_size_mb = compressed_size_mb
                except Exception as e:
                    print(f"压缩失败: {str(e)}，尝试使用原文件")

            with open(temp_file, 'rb') as video_file:
                video_data = base64.b64encode(video_file.read()).decode('utf-8')

            base64_size_mb = len(video_data) / (1024 * 1024)
            print(f"Base64编码后大小: {base64_size_mb:.2f} MB")

            # 3. 根据二创类型构建系统提示词
            system_prompts = {
                "general": "你是一个专业的短视频二创专家，擅长分析视频内容并提供创意建议。",
                "script": "你是一个专业的文案撰写专家，擅长为视频创作吸引人的解说文案。",
                "highlights": "你是一个专业的视频剪辑师，擅长识别视频中的精彩片段和关键时刻。",
                "commentary": "你是一个专业的视频解说员，擅长深度分析视频内容并提供独特见解。"
            }

            system_prompt = system_prompts.get(creative_type, system_prompts["general"])

            # 4. 构建完整的提示词
            full_prompt = f"""
请分析这个视频，并根据以下用户需求提供二创建议：

视频标题：{video_title}

用户需求：{user_prompt}

请提供以下内容：
1. 视频内容概述（主题、情节、亮点）
2. 二创建议（创意角度、改编方向）
3. 具体文案或脚本
4. 剪辑建议（如果适用）
5. 注意事项

请用清晰的结构化格式输出。
"""

            # 5. 调用AI API（增加超时时间以支持大文件）
            print(f"准备调用AI API，视频大小: {base64_size_mb:.2f} MB")
            timeout_seconds = 300.0  # 5分钟超时

            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                try:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": self.model,
                            "messages": [
                                {
                                    "role": "system",
                                    "content": system_prompt
                                },
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": full_prompt
                                        },
                                        {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:video/mp4;base64,{video_data}"
                                            }
                                        }
                                    ]
                                }
                            ],
                            "max_tokens": self.max_tokens,
                            "temperature": self.temperature
                        }
                    )

                    print(f"AI API响应状态码: {response.status_code}")
                    if response.status_code == 200:
                        result = response.json()
                        return {
                            "success": True,
                            "content": result['choices'][0]['message']['content'],
                            "model": self.model,
                            "usage": result.get('usage', {})
                        }
                    else:
                        error_detail = response.text
                        print(f"AI API错误: {error_detail}")

                        # 如果是请求体过大的错误，降级为文本分析
                        if response.status_code in [413, 400]:  # 413 Payload Too Large, 400 Bad Request
                            print("检测到请求体过大，降级为文本分析模式")
                            return await self.analyze_by_text(video_title, user_prompt, creative_type)

                        return {
                            "success": False,
                            "error": f"API调用失败: {response.status_code}",
                            "detail": error_detail
                        }

                except httpx.ReadError as e:
                    # 连接被断开，可能是因为请求体太大
                    print(f"连接错误（可能是请求体过大）: {str(e)}")
                    print("降级为文本分析模式")
                    return await self.analyze_by_text(video_title, user_prompt, creative_type)

                except httpx.TimeoutException as e:
                    print(f"请求超时: {str(e)}")
                    return {
                        "success": False,
                        "error": f"请求超时（{timeout_seconds}秒），视频可能过大"
                    }

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"处理视频时发生异常: {str(e)}")
            print(f"详细错误: {error_trace}")
            return {
                "success": False,
                "error": f"处理失败: {str(e)}"
            }
        finally:
            # 清理临时文件
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                    print(f"已删除临时文件: {temp_file}")
                except:
                    pass

    async def extract_video_frames(self, video_path: str, max_frames: int = None, smart_mode: bool = True) -> list:
        """
        从视频中提取关键帧（智能模式）

        Args:
            video_path: 视频路径
            max_frames: 最多提取多少帧（None=自动根据时长计算）
            smart_mode: 是否使用智能场景检测

        Returns:
            帧图片的base64列表
        """
        try:
            import subprocess
            import json

            # 1. 获取视频信息
            probe_cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'json',
                video_path
            ]
            result = subprocess.run(probe_cmd, capture_output=True, text=True)
            duration = float(json.loads(result.stdout)['format']['duration'])
            print(f"视频时长: {duration:.2f}秒")

            # 2. 根据视频时长自动计算最佳帧数（10秒1帧）
            if max_frames is None:
                # 按照10秒1帧的策略
                max_frames = int(duration / 10)

                # 设置合理的上下限
                if max_frames < 5:
                    max_frames = 5  # 最少5帧
                elif max_frames > 100:
                    max_frames = 100  # 最多100帧（避免API超载）

                print(f"根据视频时长({duration:.0f}秒)，按10秒1帧策略，提取 {max_frames} 帧")
            else:
                print(f"使用指定的帧数: {max_frames} 帧")

            # 2. 创建临时目录
            import tempfile
            temp_dir = tempfile.mkdtemp()

            if smart_mode:
                # 智能模式：使用场景检测
                print("使用智能场景检测模式...")

                # 使用ffmpeg的场景检测滤镜
                # select='gt(scene,0.3)' 表示场景变化超过30%时提取帧
                extract_cmd = [
                    'ffmpeg',
                    '-i', video_path,
                    '-vf', f"select='gt(scene,0.3)',scale=640:-2",  # 场景变化检测
                    '-vsync', 'vfr',  # 可变帧率
                    '-frames:v', str(max_frames),  # 最多提取max_frames帧
                    '-q:v', '2',  # 高质量
                    f'{temp_dir}/frame_%03d.jpg'
                ]

                print(f"场景检测命令: {' '.join(extract_cmd)}")
                result = subprocess.run(extract_cmd, capture_output=True, timeout=60)

                # 检查是否提取到足够的帧
                import glob
                frame_files = sorted(glob.glob(f'{temp_dir}/frame_*.jpg'))

                # 如果场景检测提取的帧太少，补充均匀采样
                if len(frame_files) < max_frames // 2:
                    print(f"场景检测只提取到 {len(frame_files)} 帧，补充均匀采样...")
                    # 清理已有帧
                    for f in frame_files:
                        os.unlink(f)

                    # 使用均匀采样
                    fps = max_frames / duration
                    extract_cmd = [
                        'ffmpeg',
                        '-i', video_path,
                        '-vf', f'fps={fps},scale=640:-2',
                        '-frames:v', str(max_frames),
                        '-q:v', '2',
                        f'{temp_dir}/frame_%03d.jpg'
                    ]
                    print(f"均匀采样命令: {' '.join(extract_cmd)}")
                    result = subprocess.run(extract_cmd, capture_output=True, timeout=60)
                else:
                    print(f"场景检测成功提取 {len(frame_files)} 帧")
            else:
                # 普通模式：均匀采样
                fps = max_frames / duration
                print(f"使用均匀采样模式，fps={fps:.2f}...")

                extract_cmd = [
                    'ffmpeg',
                    '-i', video_path,
                    '-vf', f'fps={fps},scale=640:-2',
                    '-frames:v', str(max_frames),
                    '-q:v', '2',
                    f'{temp_dir}/frame_%03d.jpg'
                ]

                print(f"均匀采样命令: {' '.join(extract_cmd)}")
                result = subprocess.run(extract_cmd, capture_output=True, timeout=60)

            if result.returncode != 0:
                print(f"提取帧失败: {result.stderr.decode()}")
                return []

            # 3. 读取所有帧并转换为base64
            import glob
            frame_files = sorted(glob.glob(f'{temp_dir}/frame_*.jpg'))
            frames_base64 = []

            print(f"\n提取的帧信息：")
            for i, frame_file in enumerate(frame_files):
                with open(frame_file, 'rb') as f:
                    frame_data = base64.b64encode(f.read()).decode('utf-8')
                    frames_base64.append(frame_data)
                    file_size_kb = len(frame_data) / 1024
                    print(f"  第 {i+1} 帧: {file_size_kb:.2f} KB")

            # 4. 清理临时文件
            import shutil
            shutil.rmtree(temp_dir)

            total_size_kb = sum(len(f) for f in frames_base64) / 1024
            print(f"\n✅ 成功提取 {len(frames_base64)} 帧，总大小: {total_size_kb:.2f} KB")
            return frames_base64

        except Exception as e:
            print(f"提取帧时出错: {str(e)}")
            return []

    async def analyze_video_by_frames(
        self,
        video_path: str,
        video_title: str,
        user_prompt: str,
        creative_type: str = "general"
    ) -> Dict[str, Any]:
        """
        通过提取关键帧分析视频

        Args:
            video_path: 视频路径
            video_title: 视频标题
            user_prompt: 用户需求
            creative_type: 二创类型

        Returns:
            AI分析结果
        """
        try:
            # 1. 提取视频帧（智能场景检测，自动计算帧数）
            print("开始提取视频关键帧（智能模式）...")
            frames = await self.extract_video_frames(video_path, max_frames=None, smart_mode=True)

            if not frames:
                print("提取帧失败，降级为文本分析")
                return await self.analyze_by_text(video_title, user_prompt, creative_type)

            # 2. 构建系统提示词
            system_prompts = {
                "general": "你是一个专业的短视频二创专家，擅长分析视频内容并提供创意建议。",
                "script": "你是一个专业的文案撰写专家，擅长为视频创作吸引人的解说文案。",
                "highlights": "你是一个专业的视频剪辑师，擅长识别视频中的精彩片段和关键时刻。",
                "commentary": "你是一个专业的视频解说员，擅长深度分析视频内容并提供独特见解。"
            }
            system_prompt = system_prompts.get(creative_type, system_prompts["general"])

            # 3. 构建提示词
            full_prompt = f"""
请分析这个视频的关键帧，并根据以下用户需求提供二创建议：

视频标题：{video_title}
提供的帧数：{len(frames)} 帧（按时间顺序）

用户需求：{user_prompt}

请提供以下内容：
1. 视频内容概述（基于关键帧分析主题、情节、亮点）
2. 二创建议（创意角度、改编方向）
3. 具体文案或脚本
4. 剪辑建议（标注关键时刻）
5. 注意事项

请用清晰的结构化格式输出。
"""

            # 4. 构建消息内容（文本 + 多张图片）
            content = [{"type": "text", "text": full_prompt}]

            for i, frame_base64 in enumerate(frames):
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{frame_base64}"
                    }
                })

            # 5. 调用AI API
            print(f"准备调用AI API，发送 {len(frames)} 帧图片")
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": system_prompt
                            },
                            {
                                "role": "user",
                                "content": content
                            }
                        ],
                        "max_tokens": self.max_tokens,
                        "temperature": self.temperature
                    }
                )

                print(f"AI API响应状态码: {response.status_code}")
                if response.status_code == 200:
                    result = response.json()
                    return {
                        "success": True,
                        "content": result['choices'][0]['message']['content'] + f"\n\n---\n📊 分析方式：关键帧分析（{len(frames)}帧）",
                        "model": self.model,
                        "usage": result.get('usage', {})
                    }
                else:
                    error_detail = response.text
                    print(f"AI API错误: {error_detail}")
                    return {
                        "success": False,
                        "error": f"API调用失败: {response.status_code}",
                        "detail": error_detail
                    }

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"关键帧分析失败: {str(e)}")
            print(f"详细错误: {error_trace}")
            return {
                "success": False,
                "error": f"关键帧分析失败: {str(e)}"
            }

    async def compress_video_simple(self, video_path: str) -> Optional[str]:
        """
        简单的视频压缩（通过重新编码降低质量）

        Args:
            video_path: 原视频路径

        Returns:
            压缩后的视频路径，失败返回None
        """
        try:
            # 检查是否安装了ffmpeg
            import subprocess
            result = subprocess.run(['which', 'ffmpeg'], capture_output=True)
            if result.returncode != 0:
                print("未安装ffmpeg，无法压缩视频")
                return None

            # 创建压缩后的临时文件
            compressed_file = tempfile.NamedTemporaryFile(delete=False, suffix='_compressed.mp4')
            compressed_path = compressed_file.name
            compressed_file.close()

            # 使用ffmpeg压缩（降低分辨率和码率）
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vf', 'scale=640:-2',  # 降低分辨率到640宽
                '-b:v', '500k',  # 视频码率500k
                '-b:a', '64k',   # 音频码率64k
                '-y',  # 覆盖输出文件
                compressed_path
            ]

            print(f"执行压缩命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, timeout=60)

            if result.returncode == 0 and os.path.exists(compressed_path):
                return compressed_path
            else:
                print(f"压缩失败: {result.stderr.decode()}")
                if os.path.exists(compressed_path):
                    os.unlink(compressed_path)
                return None

        except Exception as e:
            print(f"压缩过程出错: {str(e)}")
            return None

    async def analyze_by_text(
        self,
        video_title: str,
        user_prompt: str,
        creative_type: str = "general"
    ) -> Dict[str, Any]:
        """
        基于视频标题进行文本分析（当视频太大无法上传时使用）

        Args:
            video_title: 视频标题
            user_prompt: 用户需求
            creative_type: 二创类型

        Returns:
            AI分析结果
        """
        try:
            # 根据二创类型构建系统提示词
            system_prompts = {
                "general": "你是一个专业的短视频二创专家，擅长分析视频内容并提供创意建议。",
                "script": "你是一个专业的文案撰写专家，擅长为视频创作吸引人的解说文案。",
                "highlights": "你是一个专业的视频剪辑师，擅长识别视频中的精彩片段和关键时刻。",
                "commentary": "你是一个专业的视频解说员，擅长深度分析视频内容并提供独特见解。"
            }

            system_prompt = system_prompts.get(creative_type, system_prompts["general"])

            # 构建提示词
            full_prompt = f"""
基于以下视频标题，提供二创建议：

视频标题：{video_title}

用户需求：{user_prompt}

注意：由于视频文件较大，我只能看到标题。请基于标题内容提供：
1. 视频可能的主题和内容推测
2. 二创建议（创意角度、改编方向）
3. 具体文案或脚本建议
4. 剪辑建议
5. 注意事项

请用清晰的结构化格式输出。
"""

            # 调用AI API（纯文本）
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": system_prompt
                            },
                            {
                                "role": "user",
                                "content": full_prompt
                            }
                        ],
                        "max_tokens": self.max_tokens,
                        "temperature": self.temperature
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    return {
                        "success": True,
                        "content": result['choices'][0]['message']['content'] + "\n\n---\n💡 提示：由于视频文件较大，本次分析仅基于视频标题。如需完整视频分析，请使用较短的视频（< 5MB）。",
                        "model": self.model,
                        "usage": result.get('usage', {})
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API调用失败: {response.status_code}",
                        "detail": response.text
                    }

        except Exception as e:
            return {
                "success": False,
                "error": f"文本分析失败: {str(e)}"
            }
