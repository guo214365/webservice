#!/bin/bash
# 启动 WebSocket 版本的 AI Chat


echo "======================================"
echo "启动 AI Chat WebSocket 服务"
echo "======================================"
echo ""

cd "$(dirname "$0")/backend"

echo "✓ 工作目录: $(pwd)"
echo "✓ Python: $(which python)"
echo ""

echo "启动服务..."
python app_websocket.py

# 如果服务意外退出
echo ""
echo "服务已停止"
