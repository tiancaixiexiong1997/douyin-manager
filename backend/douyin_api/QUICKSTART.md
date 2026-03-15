# AI二创专家 - 快速开始指南

## 🎯 项目概述

AI二创专家是基于原有的抖音/TikTok视频解析项目，新增的AI视频二创功能。它可以：
- 自动解析视频内容
- 使用AI深度分析视频
- 根据需求生成二创方案
- 提供文案、剪辑建议等

## 📦 已完成的功能

### 1. AI配置文件
- 文件位置: `ai_config.yaml`
- 已配置你的API密钥和代理地址

### 2. AI服务模块
- 文件位置: `app/ai_service.py`
- 支持视频URL分析
- 支持多种二创类型

### 3. API接口
- POST接口: `/api/ai/ai_creative`
- GET接口: `/api/ai/ai_creative_simple`
- 已集成到FastAPI路由

### 4. Web交互界面
- 文件位置: `app/web/views/AICreative.py`
- 已集成到主应用菜单
- 支持中英文界面

## 🚀 启动服务

### 方法1: 使用启动脚本
```bash
cd /Users/xiexiong/Desktop/douyin/douyin_api
./start_ai_creative.sh
```

### 方法2: 手动启动
```bash
cd /Users/xiexiong/Desktop/douyin/douyin_api
source venv/bin/activate
python start.py
```

## 🌐 访问方式

### Web界面
1. 打开浏览器访问: http://localhost/
2. 在功能选择中选择 "🎬AI二创专家"
3. 输入视频链接和需求
4. 点击开始分析

### API文档
访问: http://localhost/docs
找到 "AI-Creative" 分组查看API文档

## 🧪 测试功能

运行测试脚本：
```bash
source venv/bin/activate
python test_ai_creative.py
```

## 📝 使用示例

### 示例1: 生成搞笑文案
```
视频链接: https://v.douyin.com/xxxxx
二创类型: 文案创作
用户需求: 帮我写一个搞笑版的解说文案，要幽默风趣
```

### 示例2: 提取精彩片段
```
视频链接: https://www.tiktok.com/@xxx/video/xxx
二创类型: 精彩片段
用户需求: 找出视频中最精彩的3个片段，标注时间点
```

### 示例3: 深度分析
```
视频链接: https://www.bilibili.com/video/BVxxx
二创类型: 深度解说
用户需求: 分析这个视频的创意点，给我改编建议
```

## 🔧 配置说明

### AI配置 (ai_config.yaml)
```yaml
AI:
  API_KEY: "你的密钥"
  BASE_URL: "https://api.openai-hub.com/v1"
  MODEL: "gemini-3.1-pro-preview"
  MAX_TOKENS: 4096
  TEMPERATURE: 0.7
```

### Cookie配置 (config.yaml)
确保配置了有效的抖音/TikTok Cookie，否则视频解析会失败。

## ⚠️ 注意事项

1. **首次使用前**
   - 确保ai_config.yaml中的API配置正确
   - 确保config.yaml中配置了有效的Cookie

2. **API调用时间**
   - AI分析需要30-120秒
   - 请耐心等待，不要重复提交

3. **视频限制**
   - 建议视频不超过100MB
   - 视频时长建议在5分钟以内

4. **费用控制**
   - API按token计费
   - 注意控制使用频率

5. **版权问题**
   - 仅用于学习研究
   - 注意保护原创者版权

## 🐛 常见问题

### Q: 服务启动失败？
A: 检查虚拟环境是否激活，依赖是否安装完整

### Q: 视频解析失败？
A: 检查config.yaml中的Cookie是否有效

### Q: AI分析超时？
A: 视频太大或网络问题，尝试使用较短的视频

### Q: API返回错误？
A: 检查ai_config.yaml中的API配置是否正确

## 📚 文件结构

```
douyin_api/
├── ai_config.yaml              # AI配置文件
├── app/
│   ├── ai_service.py          # AI服务模块
│   ├── api/
│   │   └── endpoints/
│   │       └── ai_creative.py # AI API端点
│   └── web/
│       └── views/
│           └── AICreative.py  # Web界面
├── start_ai_creative.sh       # 启动脚本
├── test_ai_creative.py        # 测试脚本
└── AI_CREATIVE_README.md      # 详细文档
```

## 🎉 开始使用

1. 启动服务: `./start_ai_creative.sh`
2. 访问: http://localhost/
3. 选择 "🎬AI二创专家"
4. 开始创作！

## 📞 技术支持

如有问题，请查看详细文档: `AI_CREATIVE_README.md`
