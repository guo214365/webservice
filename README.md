ba# AI Chat Web - WebSocket 版本

基于 Deep Agents 的 AI 聊天 Web 应用，支持外部触发和实时消息推送。

## 🚀 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置 API Key

编辑 `backend/config.py`，设置你的 Anthropic API Key：

```python
API_KEY = "your-api-key-here"
MODEL = "claude-3-5-sonnet-20241022"
```

### 3. 启动服务

```bash
# 方式1: 使用启动脚本
./start_websocket.sh

# 方式2: 直接运行
cd backend
python app_websocket.py
```

### 4. 访问应用

浏览器打开: http://localhost:8000

---

## ✨ 核心特性

- ✅ **WebSocket 实时通信** - 多客户端同步显示
- ✅ **外部触发** - 从任何程序触发 AI 对话
- ✅ **静默模式** - 定时任务不显示触发消息
- ✅ **打字机效果** - 逐字显示，体验流畅
- ✅ **思考过程样式** - 清晰展示 AI 思考
- ✅ **技能系统** - 支持医疗问诊、健康建议等

---

## 📁 项目结构

```
ai-chat-web/
├── backend/
│   ├── app_websocket.py      # WebSocket 服务器（主程序）
│   ├── config.py              # 配置文件
│   ├── requirements.txt       # Python 依赖
│   └── skills/                # 技能目录
│
├── frontend/
│   ├── templates/index_ws.html  # 前端页面
│   └── static/
│       ├── css/style.css        # 样式
│       └── js/app_ws.js         # 客户端
│
├── examples/                    # 示例脚本
│   ├── external_trigger.py     # 外部触发工具
│   ├── simple_client.py        # 简单客户端
│   └── interactive_chat.py     # 交互式对话
│
└── start_websocket.sh          # 启动脚本
```

---

## 💡 外部触发示例

### 命令行

```bash
# 普通消息
python examples/external_trigger.py "你好"

# 静默模式（只显示 AI 回复）
python examples/external_trigger.py "今天的健康建议" --silent
```

### curl

```bash
# 普通消息
curl -X POST http://localhost:8000/api/external \
  -H "Content-Type: application/json" \
  -d '{"message": "你好"}'

# 静默模式
curl -X POST http://localhost:8000/api/external \
  -H "Content-Type: application/json" \
  -d '{"message": "健康建议", "silent": true}'
```

---

## 🧪 测试

```bash
cd examples

# 测试外部触发
python test_external.py

# 交互式对话
python interactive_chat.py
```

---

## 📚 API 端点

### POST /api/external
外部触发 AI 对话

**参数**:
- `message` (必需): 消息内容
- `source` (可选): 来源标识
- `silent` (可选): 是否静默，默认 false

### GET /api/status
查看服务状态

---

## 📖 技能说明

- **basic-persona** - 自然对话风格
- **symptom-diagnosis** - 症状问诊
- **medical-qa** - 医学知识问答
- **time-query** - 时间查询

---

## 📄 License

MIT
