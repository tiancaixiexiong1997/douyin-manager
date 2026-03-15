import asyncio
import os
import time

import yaml
from pywebio.input import *
from pywebio.output import *
from pywebio_battery import put_video

from app.web.views.ViewsUtils import ViewsUtils
from crawlers.douyin.web.web_crawler import DouyinWebCrawler

DouyinWebCrawler = DouyinWebCrawler()

# 读取配置文件
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'config.yaml')
with open(config_path, 'r', encoding='utf-8') as file:
    config = yaml.safe_load(file)


def parse_user_videos():
    """解析用户主页视频"""
    put_markdown(ViewsUtils.t('## 📱 解析用户主页视频', '## 📱 Parse User Homepage Videos'))
    put_markdown(ViewsUtils.t(
        '> 请输入抖音用户主页链接或sec_user_id，系统将获取该用户的作品列表。',
        '> Please enter the Douyin user homepage link or sec_user_id, the system will get the user\'s video list.'
    ))

    # 输入用户链接或ID
    user_input = input(
        ViewsUtils.t('用户主页链接或sec_user_id', 'User homepage link or sec_user_id'),
        type=TEXT,
        required=True,
        placeholder=ViewsUtils.t(
            '例如: https://www.douyin.com/user/MS4wLjABAAAA... 或直接输入 sec_user_id',
            'e.g.: https://www.douyin.com/user/MS4wLjABAAAA... or enter sec_user_id directly'
        )
    )

    # 获取数量
    count = input(
        ViewsUtils.t('获取视频数量', 'Number of videos to fetch'),
        type=NUMBER,
        value=20,
        help_text=ViewsUtils.t('建议不超过50个', 'Recommended not to exceed 50')
    )

    # 提取sec_user_id
    sec_user_id = user_input
    if 'douyin.com' in user_input or 'v.douyin.com' in user_input:
        put_info(ViewsUtils.t('正在提取用户ID...', 'Extracting user ID...'))
        try:
            sec_user_id = asyncio.run(DouyinWebCrawler.get_sec_user_id(user_input))
            if not sec_user_id:
                put_error(ViewsUtils.t('无法提取用户ID，请检查链接是否正确', 'Unable to extract user ID, please check if the link is correct'))
                return
            put_success(ViewsUtils.t(f'用户ID: {sec_user_id}', f'User ID: {sec_user_id}'))
        except Exception as e:
            put_error(ViewsUtils.t(f'提取用户ID失败: {str(e)}', f'Failed to extract user ID: {str(e)}'))
            return

    # 开始解析
    start_time = time.time()
    put_warning(ViewsUtils.t('正在获取用户视频列表，请稍候...', 'Fetching user video list, please wait...'))

    try:
        # 调用API获取用户视频
        data = asyncio.run(DouyinWebCrawler.fetch_user_post_videos(sec_user_id, 0, int(count)))

        if data.get('status_code') != 0:
            put_error(ViewsUtils.t('获取失败，可能是Cookie过期或用户不存在', 'Failed to fetch, Cookie may be expired or user does not exist'))
            return

        aweme_list = data.get('aweme_list', [])
        if not aweme_list:
            put_warning(ViewsUtils.t('该用户没有公开作品', 'This user has no public videos'))
            return

        # 显示结果
        put_markdown(ViewsUtils.t(f'## ✅ 成功获取 {len(aweme_list)} 个视频', f'## ✅ Successfully fetched {len(aweme_list)} videos'))
        put_html('<hr>')

        # 遍历视频列表
        for idx, aweme in enumerate(aweme_list, 1):
            aweme_id = aweme.get('aweme_id', '')
            desc = aweme.get('desc', ViewsUtils.t('无描述', 'No description'))
            author = aweme.get('author', {})
            nickname = author.get('nickname', ViewsUtils.t('未知', 'Unknown'))

            # 判断是视频还是图集
            video_data = aweme.get('video', {})
            images = aweme.get('images', [])
            is_video = bool(video_data and video_data.get('play_addr'))

            # 获取统计数据
            statistics = aweme.get('statistics', {})
            digg_count = statistics.get('digg_count', 0)
            comment_count = statistics.get('comment_count', 0)
            share_count = statistics.get('share_count', 0)
            collect_count = statistics.get('collect_count', 0)
            play_count = statistics.get('play_count', 0)

            with use_scope(f'video_{idx}'):
                put_markdown(f'### {idx}. {desc[:50]}{"..." if len(desc) > 50 else ""}')

                table_data = [
                    [ViewsUtils.t('类型', 'Type'), ViewsUtils.t('内容', 'Content')],
                    [ViewsUtils.t('作品ID', 'Video ID'), aweme_id],
                    [ViewsUtils.t('描述', 'Description'), desc],
                    [ViewsUtils.t('作者', 'Author'), nickname],
                    [ViewsUtils.t('类型', 'Type'), ViewsUtils.t('视频', 'Video') if is_video else ViewsUtils.t('图集', 'Images')],
                    [ViewsUtils.t('👍点赞', '👍Likes'), f'{digg_count:,}'],
                    [ViewsUtils.t('💬评论', '💬Comments'), f'{comment_count:,}'],
                    [ViewsUtils.t('🔗分享', '🔗Shares'), f'{share_count:,}'],
                    [ViewsUtils.t('⭐收藏', '⭐Collects'), f'{collect_count:,}'],
                ]

                # 如果播放量不为0，则显示
                if play_count > 0:
                    table_data.append([ViewsUtils.t('▶️播放', '▶️Views'), f'{play_count:,}'])

                # 构建视频链接
                video_url = f'https://www.douyin.com/video/{aweme_id}'

                if is_video:
                    # 视频预览
                    play_addr = video_data.get('play_addr', {})
                    url_list = play_addr.get('url_list', [])
                    if url_list:
                        video_preview_url = url_list[0]
                        table_data.insert(0, [put_video(video_preview_url, width='50%', loop=True)])

                    table_data.append([ViewsUtils.t('下载-无水印', 'Download-No Watermark'),
                                     put_link(ViewsUtils.t('点击下载', 'Click to download'),
                                            f'/api/download?url={video_url}&prefix=true&with_watermark=false',
                                            new_window=True)])
                else:
                    # 图集预览
                    if images:
                        table_data.append([ViewsUtils.t('图片数量', 'Image count'), len(images)])
                        table_data.append([ViewsUtils.t('下载图集', 'Download Images'),
                                         put_link(ViewsUtils.t('点击下载', 'Click to download'),
                                                f'/api/download?url={video_url}&prefix=true&with_watermark=false',
                                                new_window=True)])

                table_data.append([ViewsUtils.t('原视频链接', 'Original URL'),
                                 put_link(ViewsUtils.t('点击查看', 'Click to view'), video_url, new_window=True)])

                put_table(table_data)
                put_html('<hr>')

        # 统计信息
        end_time = time.time()
        time_consuming = round(end_time - start_time, 2)

        put_success(ViewsUtils.t(
            f'✅ 解析完成！共获取 {len(aweme_list)} 个作品，耗时 {time_consuming}秒',
            f'✅ Parsing completed! Fetched {len(aweme_list)} videos, time: {time_consuming}s'
        ))

        # 返回按钮
        put_button(ViewsUtils.t('回到顶部', 'Back to top'),
                  onclick=lambda: scroll_to('video_1'),
                  color='success', outline=True)
        put_link(ViewsUtils.t('返回首页', 'Back to home'), '/')

    except Exception as e:
        put_error(ViewsUtils.t(f'解析失败: {str(e)}', f'Parsing failed: {str(e)}'))
        put_markdown(ViewsUtils.t('> 可能的原因:', '> Possible reasons:'))
        put_markdown(ViewsUtils.t('- Cookie已过期，需要更新配置文件中的Cookie', '- Cookie expired, need to update Cookie in config file'))
        put_markdown(ViewsUtils.t('- 用户不存在或主页已设置为私密', '- User does not exist or homepage is set to private'))
        put_markdown(ViewsUtils.t('- 网络问题或接口限流', '- Network issue or API rate limit'))
