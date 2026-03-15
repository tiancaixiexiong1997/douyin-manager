# AI二创专家使用文档

## 功能介绍

AI二创专家是一个基于AI大模型的智能视频二创助手，可以帮你：
- 深度分析抖音/TikTok/B站视频内容
- 根据需求生成二创方案
- 提供文案、剪辑建议等

## 快速开始

### 1. 启动服务

```bash
cd /Users/xiexiong/Desktop/douyin/douyin_api
python start.py
```

### 2. 访问方式

#### Web界面
访问: http://localhost/
选择 "🎬AI二创专家" 功能

#### API接口
访问API文档: http://localhost/docs
找到 "AI-Creative" 分组

### 3. 使用步骤

1. 粘贴视频链接（支持抖音/TikTok/B站）
2. 选择二创类型：
   - 通用分析：全面分析视频
   - 文案创作：生成解说文案
   - 精彩片段：识别亮点片段
   - 深度解说：提供评论角度
3. 描述你的需求
4. 点击开始分析
5. 等待AI生成结果

## API使用示例

### GET请求（简单测试）

```bash
curl "http://localhost/api/ai/ai_creative_simple?url=视频链接&prompt=帮我写一个搞笑版的解说文案&type=script"
```

### POST请求（推荐）

```bash
curl -X POST "http://localhost/api/ai/ai_creative" \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "视频链接",
    "user_prompt": "帮我写一个搞笑版的解说文案",
    "creative_type": "script"
  }'
```

### Python调用示例

```python
import requests

url = "http://localhost/api/ai/ai_creative"
data = {
    "video_url": "https://v.douyin.com/xxxxx",
    "user_prompt": "帮我分析这个视频的创意点，给我改编建议",
    "creative_type": "general"
}

response = requests.post(url, json=data)
result = response.json()

print(result['data']['ai_analysis']['content'])
```

## 二创类型说明

### general - 通用分析
全面分析视频内容，提供综合性的二创建议

**适用场景：**
- 不确定具体需求时
- 需要全面了解视频
- 寻找多种二创可能性

### script - 文案创作
专注于生成解说文案、标题、字幕等文字内容

**适用场景：**
- 需要配音文案
- 生成视频标题
- 改写视频内容

### highlights - 精彩片段
识别视频中的亮点时刻，提供剪辑建议

**适用场景：**
- 制作短视频剪辑
- 提取精彩瞬间
- 优化视频节奏

### commentary - 深度解说
深入分析视频内容，提供评论和解说角度

**适用场景：**
- 制作解说视频
- 深度分析内容
- 提供独特观点

## 配置说明

AI配置文件位置: `/Users/xiexiong/Desktop/douyin/douyin_api/ai_config.yaml`

```yaml
AI:
  API_KEY: "你的API密钥"
  BASE_URL: "API代理地址"
  MODEL: "模型名称"
  MAX_TOKENS: 4096
  TEMPERATURE: 0.7
```

## 注意事项

1. **API调用时间**: AI分析需要30-120秒，请耐心等待
2. **视频大小限制**: 建议视频不超过100MB
3. **API费用**: 按token计费，注意控制成本
4. **版权问题**: 仅用于学习研究，注意版权保护
5. **Cookie配置**: 确保config.yaml中配置了有效的Cookie

## 常见问题

### Q: 视频解析失败？
A: 检查Cookie是否有效，参考主项目README配置Cookie

### Q: AI分析超时？
A: 视频太大或网络问题，尝试使用较短的视频

### Q: API返回错误？
A: 检查ai_config.yaml中的API配置是否正确

### Q: 如何修改AI模型？
A: 编辑ai_config.yaml，修改MODEL字段

## 技术支持

- 项目地址: https://github.com/Evil0ctal/Douyin_TikTok_Download_API
- 问题反馈: 提交Issue到GitHub仓库
