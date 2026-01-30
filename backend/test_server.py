"""
简易测试服务器 - 用于验证前端功能而不需要依赖 deepagents
"""
import asyncio
import json
import time
from datetime import datetime
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

app = FastAPI(title="AI Chat Test Server")

# 配置静态文件和模板
backend_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(backend_dir)
static_dir = os.path.join(project_root, "frontend", "static")
templates_dir = os.path.join(project_root, "frontend", "templates")

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[TEST] 新连接，当前连接数: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"[TEST] 连接断开，当前连接数: {len(self.active_connections)}")
    
    async def send_message(self, websocket: WebSocket, message: dict):
        """发送消息到指定客户端"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"[TEST] 发送失败: {e}")

manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """主页面"""
    return templates.TemplateResponse("index_ws.html", {"request": request })

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket端点 - 模拟AI响应"""
    await manager.connect(websocket)
    
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_json()
            message = data.get("message", "")
            history = data.get("history", [])
            
            print(f"[TEST] 收到消息: {message}")
            
            # 广播用户消息
            await manager.send_message(websocket, {
                "type": "user_message",
                "content": message
            })
            
            # 模拟AI思考过程
            await manager.send_message(websocket, {
                "type": "assistant_message",
                "content": "🤔 **思考过程**\n让我来分析一下您的问题..."
            })
            
            await asyncio.sleep(1)
            
            # 模拟工具调用
            await manager.send_message(websocket, {
                "type": "assistant_message",
                "content": "📖 加载相关医学资料..."
            })
            
            await asyncio.sleep(1)
            
            # 最终回复
            response = f"""
## AI回复

感谢您的咨询！

**您的问题**: {message}

这是一个模拟回复，实际系统会基于专业的医学知识库为您提供准确的健康建议。

**建议**：
- 保持良好的生活习惯
- 定期体检
- 如有不适请及时就医

---

*这是测试服务器的模拟回复，如需完整功能请安装 deepagents 依赖*
            """
            
            # 分段发送以模拟流式效果
            for i in range(0, len(response), 50):
                chunk = response[i:i+50]
                await manager.send_message(websocket, {
                    "type": "assistant_message", 
                    "content": chunk
                })
                await asyncio.sleep(0.1)
            
            # 发送完成信号
            await manager.send_message(websocket, {
                "type": "complete"
            })
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[TEST] 错误: {e}")
        await manager.send_message(websocket, {
            "type": "error",
            "content": f"测试错误: {str(e)}"
        })

if __name__ == "__main__":
    import uvicorn
    print("🎯 启动测试服务器 (端口 8001)")
    print("📱 访问地址: http://localhost:8001")
    print("⚠️  这是一个简化测试服务器，用于验证前端功能")
    uvicorn.run(app, host="0.0.0.0", port=8001