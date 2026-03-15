#!/bin/bash

# AI二创专家启动脚本

echo "🚀 启动AI二创专家服务..."

# 进入项目目录
cd "$(dirname "$0")"

# 激活虚拟环境
if [ -d "venv" ]; then
    echo "✅ 激活虚拟环境..."
    source venv/bin/activate
else
    echo "❌ 虚拟环境不存在，请先创建虚拟环境"
    exit 1
fi

# 检查配置文件
if [ ! -f "ai_config.yaml" ]; then
    echo "❌ ai_config.yaml 配置文件不存在"
    exit 1
fi

# 启动服务
echo "✅ 启动服务..."
echo "📝 Web界面: http://localhost/"
echo "📝 API文档: http://localhost/docs"
echo "📝 AI二创: 选择 '🎬AI二创专家' 功能"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

python start.py
