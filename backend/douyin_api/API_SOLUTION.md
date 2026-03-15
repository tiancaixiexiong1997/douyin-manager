# Google Gemini API配置说明

## 🎯 为什么需要更换API

你当前使用的API代理：
- 地址：https://api.openai-hub.com/v1
- 模型：gemini-3.1-pro-preview
- **问题**：不支持视频分析，只支持文本

## ✅ 推荐方案：使用Google Gemini官方API

### 1. 获取API密钥

访问：https://aistudio.google.com/app/apikey
- 登录Google账号
- 创建API密钥
- 免费额度：每分钟15次请求

### 2. 修改配置

编辑 `ai_config.yaml`：

```yaml
AI:
  API_KEY: "你的Gemini API密钥"
  BASE_URL: "https://generativelanguage.googleapis.com/v1beta"
  MODEL: "gemini-1.5-flash"  # 或 gemini-1.5-pro
  MAX_TOKENS: 4096
  TEMPERATURE: 0.7
```

### 3. 修改代码

Gemini API的调用方式与OpenAI不同，需要修改 `app/ai_service.py`

## 🔄 方案2：继续使用当前API（文本分析）

如果不想更换API，系统会：
- 自动降级为文本分析
- 基于视频标题提供建议
- 不需要修改任何配置

## 📊 对比

| 特性 | 当前API | Gemini官方API |
|------|---------|---------------|
| 视频分析 | ❌ 不支持 | ✅ 支持 |
| 文本分析 | ✅ 支持 | ✅ 支持 |
| 费用 | 按你的代理计费 | 免费额度 |
| 稳定性 | 取决于代理 | 官方稳定 |

## 🤔 你的选择

1. **继续使用当前配置**
   - 优点：不需要改动
   - 缺点：只能文本分析
   - 适合：快速测试

2. **切换到Gemini官方API**
   - 优点：真正的视频分析
   - 缺点：需要修改代码
   - 适合：完整功能

需要我帮你实现Gemini官方API的集成吗？
