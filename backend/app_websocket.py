#############################################################  当前最优版本   #####################################################
"""
WebSocket 版本的 AI Chat
支持外部触发消息并在聊天页面实时显示
"""
import asyncio
import os
import re
import uuid
from pathlib import Path
from typing import List, Dict, Set, Tuple, Union

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend, CompositeBackend
from deepagents_cli.config import settings
from deepagents.middleware.skills import SkillsMiddleware
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from langchain.agents.middleware import ShellToolMiddleware, HostExecutionPolicy
from langchain_community.agent_toolkits import FileManagementToolkit
from custom_llm import create_custom_llm
import config
# from safe_skills_middleware import SafeSkillsMiddleware  # 添加这行

app = FastAPI(title="AI Chat API - WebSocket")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 使用绝对路径确保能找到静态文件和模板
import os
backend_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(backend_dir)
static_dir = os.path.join(project_root, "frontend", "static")
templates_dir = os.path.join(project_root, "frontend", "templates")

print(f"[CONFIG] Backend dir: {backend_dir}")
print(f"[CONFIG] Project root: {project_root}")
print(f"[CONFIG] Static dir: {static_dir}")
print(f"[CONFIG] Templates dir: {templates_dir}")
print(f"[CONFIG] Static dir exists: {os.path.exists(static_dir)}")
print(f"[CONFIG] Templates dir exists: {os.path.exists(templates_dir)}")

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)
jobs_db = {}

# WebSocket 连接管理类
class ConnectionManager:
    """WebSocket连接管理器，负责连接的生命周期管理和消息广播"""
    
    def __init__(self):
        """初始化连接管理器"""
        self.active_connections: Set[WebSocket] = set()
        # 添加对话长度监控
        self.conversation_stats = {}
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"[WS] 新连接，当前连接数: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        print(f"[WS] 连接断开，当前连接数: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """广播消息到所有连接的客户端"""
        dead_connections = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"[WS] 发送失败: {e}")
                dead_connections.add(connection)
        
        # 清理失效连接
        for conn in dead_connections:
            self.disconnect(conn)

manager = ConnectionManager()

# 创建Deep Agent实例
backend_dir = Path(__file__).parent
backend_dir_str = str(backend_dir.resolve())  # 转换为绝对路径字符串
os.chdir(backend_dir_str)

# assistant_id = "medical-jiedu"
assistant_id = "medical"
agent_dir = backend_dir / 'agents' / assistant_id
skills_dir = backend_dir / 'agents' / assistant_id / 'skills'
project_dir = backend_dir / 'agents'

# 转换为绝对路径字符串
agent_dir_str = str(agent_dir.resolve())
skills_dir_str = str(skills_dir.resolve())
project_dir_str = str(project_dir.resolve())

settings = settings.from_environment(start_path=backend_dir_str)


print(f"[INFO] assistant_id: {assistant_id}")
print(f"[INFO] agent_dir: {agent_dir_str}")
print(f"[INFO] skills_dir: {skills_dir_str}")


# 读取 agent.md / system.md
agent_prompt_path = agent_dir / 'agent.md'
system_prompt_path = agent_dir / 'system.md'


def load_full_system_prompt() -> str:
    agent_prompt = agent_prompt_path.read_text() if agent_prompt_path.exists() else ""
    system_prompt = system_prompt_path.read_text() if system_prompt_path.exists() else ""
    if system_prompt and agent_prompt:
        return system_prompt + "\n\n" + agent_prompt
    return system_prompt or agent_prompt


# ========== 2. 创建 LLM ==========
base_llm = create_custom_llm()

# ========== 4. 创建 Backend ==========
# 使用本机实际路径，避免硬编码 Linux 路径导致找不到文件
composite_backend = CompositeBackend(default=FilesystemBackend(root_dir=project_dir_str), routes={})


def build_agent():
    # ========== 5. 创建 Middleware（不包含 FilesystemMiddleware）==========
    agent_middleware = [
        # deepagents>=? 的 SkillsMiddleware 新签名为 (backend=..., sources=[...])
        SkillsMiddleware(backend=FilesystemBackend(root_dir=skills_dir_str), sources=["."]),
        ShellToolMiddleware(
            workspace_root=backend_dir_str,
            execution_policy=HostExecutionPolicy(),
            env=os.environ,
        ),
    ]
    # ========== 6. 创建 Agent（使用绑定了工具的模型 + tools 参数）==========
    return create_deep_agent(
        name=assistant_id,
        system_prompt=load_full_system_prompt(),
        middleware=agent_middleware,
        backend=composite_backend,
        model=base_llm
    )


def reload_agent():
    global agent
    agent = build_agent()
    print("[INFO] Agent reloaded to apply skill changes")


agent = build_agent()
print(f"✓ WebSocket server initialized")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """主页面路由，返回WebSocket聊天界面HTML页面"""
    return templates.TemplateResponse("index_ws.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 连接端点，处理实时消息交互和批量评估功能

    Args:
        websocket: WebSocket连接对象，用于与客户端进行双向通信

    功能说明：
    - 建立和维护WebSocket连接
    - 接收客户端发送的消息（支持文本、批量评估数据）
    - 广播用户消息到所有连接的客户端
    - 调用process_chat处理不同类型的数据输入

    支持的数据格式：
    - 普通聊天消息：包含message和history字段
    - 批量评估数据：包含case_data、case_index、total_cases字段
    
    Returns:
        None: 函数持续运行直到连接断开
    """
    await manager.connect(websocket)
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_json()
            message = data.get("message", "")
            history = data.get("history", [])
            
            # 新增JSON数据字段
            case_data = data.get("case_data")
            case_index = data.get("case_index")
            total_cases = data.get("total_cases")
        
            if case_data:
                print(f"[JSON] 批量处理模式 - Case {case_index}/{total_cases}")
            
            # 构建完整消息内容（包含图片和JSON描述）
            full_message = message
            
            if case_data:
                json_info = f"\n\n[批量评估模式] - Case {case_index}/{total_cases}"
                if isinstance(case_data, dict):
                    if "id" in case_data:
                        json_info += f" (ID: {case_data['id']})"
                    if "type" in case_data:
                        json_info += f" (类型: {case_data['type']})"
                full_message += json_info
            
            
            # 发送用户消息到所有客户端
            await manager.broadcast({
                "type": "user_message",
                "content": full_message
            })
            
            # 调用process_chat处理消息
            await process_chat(
                message,
                history,
                case_data  # 传递case_data（可能是单个对象或列表）
            )
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WS] 错误: {e}")
        manager.disconnect(websocket)

async def process_chat(message: str, history: List[Dict[str, str]], case_data: Union[Dict, List] = None) -> Dict:
    """
    处理聊天消息，支持三种输入模式：
    1. 纯文本聊天
    2. 文本+图像
    3. 文本+JSON数据
    
    Args:
        message: 用户输入的文本消息
        history: 对话历史记录
        images: 用户上传的图片URL列表，可选
        case_data: JSON格式的病例数据，可选
    """
    try:
        # 处理多个case的情况
        if isinstance(case_data, list):
            for idx, single_case in enumerate(case_data):
                print(f"[PROCESSING] 处理病例 {idx+1}/{len(case_data)}")
                
                # 为当前case发送处理进度
                await manager.broadcast({
                    "type": "progress",
                    "content": f"正在处理病例 {idx+1}/{len(case_data)}",
                    "current": idx + 1,
                    "total": len(case_data)
                })
                
                # 递归处理单个case
                await process_chat(
                    single_case.get("query", ""),
                    single_case.get("history", []),
                    single_case.get("image_url", []),
                    single_case  # 传递单个case数据
                )
            return {"status": "success"}

        # 构建消息上下文
        messages = [{"role": m["role"], "content": m["content"]} for m in history]
        
        # 构建多模态消息内容
        content = [{"type": "text", "text": message}]

        # 处理病例数据
        if case_data:
            # 结构化case_data中的关键字段
            case_info = []
            if "id" in case_data:
                case_info.append(f"ID: {case_data['id']}")
            if "history" in case_data:
                case_info.append(f"history: {case_data['history']}")
            if "query" in case_data:
                case_info.append(f"query: {case_data['query']}")
            if "assessment_result" in case_data:
                case_info.append(f"assessment_result: {case_data['assessment_result']}")

            if case_info:
                content.append({
                    "type": "text",
                    "text": f"\n病例信息: {', '.join(case_info)}"
                })
        
        # 只有在有case_data且包含image_url时才添加图片
        if case_data and 'image_url' in case_data:
            if isinstance(case_data['image_url'], list):
                for url in case_data['image_url']:  # 确保图片URL不为空
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": url, "detail": "auto"}
                    })
            else:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": case_data['image_url'], "detail": "auto"}
                })
        
        messages.append({"role": "user", "content": content})
        # ========== 简化版流式处理 ==========
        tool_call_tracking = {}  # 初始化工具调用跟踪
        
        async for chunk in agent.astream({'messages': messages}):
            if not isinstance(chunk, dict):
                continue
            
            print(chunk)
            
            # 跟踪工具调用
            if 'model' in chunk:
                model_data = chunk['model']
                if isinstance(model_data, dict) and 'messages' in model_data:
                    for msg in model_data['messages']:
                        if hasattr(msg, 'content') and msg.content:
                            if isinstance(msg.content, list):
                                for item in msg.content:
                                    # 处理文本内容
                                    if item.get('type') == 'text':
                                        print(f"[DEBUG] 发送文本内容 ({len(item['text'])} 字符): {item['text'][:100]}...")        
                                        await manager.broadcast({
                                            "type": "assistant_message",
                                            "content": item['text']
                                        })
                                    
                                    # 处理工具调用
                                    elif item.get('type') == 'tool_use':
                                        tool_call_id = item.get('id', '')
                                        tool_name = item.get('name', '')
                                        tool_args = item.get('input', {})
                                        
                                        # 记录工具调用
                                        tool_call_tracking[tool_call_id] = {
                                            'tool_name': tool_name,
                                            'args': tool_args
                                        }
                                        
                                        # 显示工具调用提示
                                        if tool_name == 'read_file':
                                            file_path = tool_args.get('file_path', '')
                                            display_path = file_path.split('/skills/')[-1] if '/skills/' in file_path else file_path.split('/')[-1]
                                            tip_msg = f"\n📖 加载文件: `{display_path}`\n"
                                        elif tool_name == 'write_file':
                                            file_path = tool_args.get('file_path', '')
                                            display_path = file_path.split('/')[-1]
                                            tip_msg = f"\n📝 创建文件: `{display_path}`\n"
                                        elif tool_name == 'edit_file':
                                            file_path = tool_args.get('file_path', '')
                                            display_path = file_path.split('/')[-1]
                                            tip_msg = f"\n✏️ 更新文件: `{display_path}`\n"
                                        elif tool_name == 'shell':
                                            command = tool_args.get('command', '')
                                            import re
                                            match = re.search(r'--name="([^"]+)"', command)
                                            prefix = f'发送随访通知: {match.group(1)}' if match and 'followup_plan.py' in command else ''
                                            cmd_display = f'{prefix} {command}'
                                            tip_msg = f"\n🔧 执行命令: `{cmd_display}`\n"
                                        else:
                                            tip_msg = f"\n🔧 执行工具: `{tool_name}`\n"
                                        
                                        print(f"[TOOL] 工具调用: {tool_name}, 参数: {tool_args}")
                                        await manager.broadcast({
                                            "type": "assistant_message",
                                            "content": tip_msg
                                        })
                                        
                            # 处理纯文本内容
                            elif isinstance(msg.content, str):
                                print(f"[DEBUG] 发送文本内容 ({len(msg.content)} 字符): {msg.content[:100]}...")        
                                await manager.broadcast({
                                    "type": "assistant_message",
                                    "content": msg.content
                                })
            
            # 处理工具结果
            if 'tools' in chunk:
                tools_data = chunk['tools']
                if isinstance(tools_data, dict) and 'messages' in tools_data:
                    for msg in tools_data['messages']:
                        if hasattr(msg, 'content'):
                            result_content = msg.content if isinstance(msg.content, str) else str(msg.content)
                            tool_call_id = getattr(msg, 'tool_call_id', '')
                            
                            tool_info = tool_call_tracking.get(tool_call_id, {})
                            tool_name = tool_info.get('tool_name', 'unknown')
                            
                            # 检查是否有错误
                            has_error = any(keyword in str(msg).lower() for keyword in ['error', 'stderr'])
                            has_error = has_error or 'Error:' in result_content
                            
                            if has_error:
                                print(f"[TOOL] ⚠️ 工具执行错误 ({tool_name}): {result_content[:200]}")
                                error_msg = f"\n⚠️ 执行错误: {result_content[:100]}\n\n"
                                await manager.broadcast({
                                    "type": "assistant_message",
                                    "content": error_msg
                                })
                            else:
                                # 成功时只记录日志，不显示消息（保持界面简洁）
                                if tool_name == 'shell' and 'followup_plan.py' in str(tool_info.get('args', {})):
                                    try:
                                        import json
                                        output_data = json.loads(result_content)
                                        if output_data.get('errno') == 0:
                                            result_msg = f"✅ 随访通知已发送\n"
                                            await manager.broadcast({
                                                "type": "assistant_message",
                                                "content": result_msg
                                            })
                                    except:
                                        pass
                                print(f"[TOOL] ✅ 工具执行成功: {tool_name}")
        
        # 发送完成信号
        await manager.broadcast({"type": "complete"})
        
    except Exception as e:
        import traceback
        print(f"[ERROR] {e}")
        print(traceback.format_exc())
        await manager.broadcast({
            "type": "error",
            "content": f"错误: {str(e)}"
        })

@app.post("/api/external")
async def external_trigger(request: Request):
    """
    外部触发端点
    接收外部消息，通过 WebSocket 广播到聊天页面
    
    参数:
        message: 消息内容（必需）
        source: 来源标识（可选，默认 "external"）
        silent: 是否静默模式（可选，默认 False）
               - False: 在聊天界面显示用户消息和 AI 回复
               - True: 只显示 AI 回复，不显示用户消息
    """
    data = await request.json()
    message = data.get("message", "")
    source = data.get("source", "external")
    silent = data.get("silent", False)
    api_key = request.headers.get("X-API-Key", "")
    
    # 简单的 API Key 验证（可选）
    # if api_key != "your-secret-key":
    #     return {"error": "Unauthorized"}, 401
    
    if not message:
        return {"error": "Message is required"}, 400
    
    print(f"[EXTERNAL] 来自 {source}: {message} {'(静默)' if silent else ''}")
    
    # 只有非静默消息才广播用户消息到聊天界面
    if not silent:
        await manager.broadcast({
            "type": "external_trigger",
            "source": source,
            "message": message
        })
    
    # 处理消息（AI 回复始终会广播）
    await process_chat(message, [])
    
    return {
        "success": True,
        "message": "Message sent to chat" if not silent else "Message processed silently",
        "silent": silent,
        "active_connections": len(manager.active_connections)
    }


async def execute_task(data):
    """异步执行任务的函数，用于处理调度系统产生的任务消息处理"""
    message = data.get("message", "")
    source = data.get("source", "external")
    silent = data.get("silent", False)
    print('execute',data)
    
    if not message:
        return {"error": "Message is required"}, 400
    
    print(f"[EXTERNAL] 来自 {source}: {message} {'(静默)' if silent else ''}")
    
    # 只有非静默消息才广播用户消息到聊天界面
    if not silent:
        await manager.broadcast({
            "type": "external_trigger",
            "source": source,
            "message": message
        })
    print("data")
    
    # 处理消息（AI 回复始终会广播）
    await process_chat(message, [])
    return {"success": True, "message": "Message sent to chat" if not silent else "Message processed silently"}


@app.post("/api/schedule")
async def schedule_task(request: Request):
    """调度任务接口，用于创建和管理异步任务执行"""
    data = await request.json()
    print('schedule',data)
    job_id = data.get("job_id")
    task = data.get("task")
    delay_seconds = data.get("delay_seconds")

    if task in ['started', 'Started', 'scheduled']:
        # run_time = datetime.now() + timedelta(seconds=delay_seconds)
        # job = scheduler.add_job(
        #     execute_task,
        #     'date',
        #     run_date=run_time,
        #     args=[data],
        #     id=job_id,
        #     name=f"task_{job_id[:8]}"
        # )
        # jobs_db[job_id] = job
        # print(jobs_db)

        # 使用asyncio.create_task创建后台任务
        async def delayed_task():
            print('delayed_task')
            await asyncio.sleep(delay_seconds)
            print('delayed_task')
            await execute_task(data)
        asyncio.create_task(delayed_task())
    else:
        # job = jobs_db.pop(job_id)
        # job.remove()
        pass
    return {'job_id': job_id}

@app.get("/api/status")
async def status():
    """查看当前系统状态，包括WebSocket连接数和agent状态信息"""
    return {
        "active_connections": len(manager.active_connections),
        # "agent": "medical",
        "agent": "medical_jiedu",
        "websocket_enabled": True
    }


# =========================
# Skill 文件管理 API
# =========================

@app.get("/api/skills")
async def list_skills():
    """获取所有skill列表"""
    skills_list = []
    
    if skills_dir.exists():
        for skill_folder in skills_dir.iterdir():
            if skill_folder.is_dir():
                skill_md_path = skill_folder / "SKILL.md"
                if skill_md_path.exists():
                    # 读取skill的name和description
                    content = skill_md_path.read_text(encoding='utf-8')
                    name = skill_folder.name
                    description = ""
                    
                    # 解析 frontmatter 获取 description
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            frontmatter = parts[1]
                            for line in frontmatter.split("\n"):
                                if line.startswith("description:"):
                                    description = line.replace("description:", "").strip()
                                    break
                    
                    skills_list.append({
                        "name": name,
                        "description": description,
                        "path": str(skill_md_path.relative_to(backend_dir))
                    })
    
    return {"skills": skills_list}


@app.get("/api/skills/{skill_name}")
async def get_skill(skill_name: str):
    """获取指定skill的内容"""
    if ".." in skill_name or "/" in skill_name or "\\" in skill_name:
        return {"error": "Invalid skill name"}, 400
    skill_path = skills_dir / skill_name / "SKILL.md"
    
    if not skill_path.exists():
        return {"error": f"Skill '{skill_name}' not found"}, 404
    
    content = skill_path.read_text(encoding='utf-8')
    return {
        "name": skill_name,
        "content": content,
        "path": str(skill_path.relative_to(backend_dir))
    }


@app.put("/api/skills/{skill_name}")
async def update_skill(skill_name: str, request: Request):
    """更新指定skill的内容"""
    if ".." in skill_name or "/" in skill_name or "\\" in skill_name:
        return {"error": "Invalid skill name"}, 400
    data = await request.json()
    content = data.get("content", "")
    
    skill_path = skills_dir / skill_name / "SKILL.md"
    
    if not skill_path.exists():
        return {"error": f"Skill '{skill_name}' not found"}, 404
    
    try:
        # 写入新内容
        skill_path.write_text(content, encoding='utf-8')
        print(f"[SKILL] 更新技能文件: {skill_name}")
        reload_error = None
        try:
            reload_agent()
        except Exception as e:
            reload_error = str(e)
            print(f"[SKILL] Agent reload failed: {reload_error}")
        return {
            "success": True,
            "message": f"Skill '{skill_name}' updated successfully",
            "name": skill_name,
            "reloaded": reload_error is None,
            "reload_error": reload_error
        }
    except Exception as e:
        print(f"[SKILL] 更新失败: {e}")
        return {"error": str(e)}, 500


###################################### 主文件入口 ####################################
if __name__ == "__main__":
    """程序主入口，启动基于uvicorn的WebSocket聊天服务器"""
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)






# ############################################################################ 支持批量json测试的版本  ###############################################################
# """
# WebSocket 版本的 AI Chat
# 支持外部触发消息并在聊天页面实时显示
# """
# import asyncio
# import os
# import re
# import uuid
# from pathlib import Path
# from typing import List, Dict, Set, Tuple, Union

# from deepagents import create_deep_agent
# from deepagents.backends import FilesystemBackend, CompositeBackend
# from deepagents_cli.agent_memory import AgentMemoryMiddleware
# from deepagents_cli.config import settings
# from deepagents_cli.skills import SkillsMiddleware
# from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import HTMLResponse
# from fastapi.staticfiles import StaticFiles
# from fastapi.templating import Jinja2Templates
# from langchain.agents.middleware import ShellToolMiddleware, HostExecutionPolicy
# from langchain_community.agent_toolkits import FileManagementToolkit
# from custom_llm import create_custom_llm
# import config

# app = FastAPI(title="AI Chat API - WebSocket")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=config.CORS_ORIGINS,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # 使用绝对路径确保能找到静态文件和模板
# import os
# backend_dir = os.path.dirname(os.path.abspath(__file__))
# project_root = os.path.dirname(backend_dir)
# static_dir = os.path.join(project_root, "frontend", "static")
# templates_dir = os.path.join(project_root, "frontend", "templates")

# print(f"[CONFIG] Backend dir: {backend_dir}")
# print(f"[CONFIG] Project root: {project_root}")
# print(f"[CONFIG] Static dir: {static_dir}")
# print(f"[CONFIG] Templates dir: {templates_dir}")
# print(f"[CONFIG] Static dir exists: {os.path.exists(static_dir)}")
# print(f"[CONFIG] Templates dir exists: {os.path.exists(templates_dir)}")

# app.mount("/static", StaticFiles(directory=static_dir), name="static")
# templates = Jinja2Templates(directory=templates_dir)
# jobs_db = {}

# # WebSocket 连接管理类
# class ConnectionManager:
#     """WebSocket连接管理器，负责连接的生命周期管理和消息广播"""
    
#     def __init__(self):
#         """初始化连接管理器"""
#         self.active_connections: Set[WebSocket] = set()
#         # 添加对话长度监控
#         self.conversation_stats = {}
    
#     async def connect(self, websocket: WebSocket):
#         await websocket.accept()
#         self.active_connections.add(websocket)
#         print(f"[WS] 新连接，当前连接数: {len(self.active_connections)}")
    
#     def disconnect(self, websocket: WebSocket):
#         self.active_connections.discard(websocket)
#         print(f"[WS] 连接断开，当前连接数: {len(self.active_connections)}")
    
#     async def broadcast(self, message: dict):
#         """广播消息到所有连接的客户端"""
#         dead_connections = set()
#         for connection in self.active_connections:
#             try:
#                 await connection.send_json(message)
#             except Exception as e:
#                 print(f"[WS] 发送失败: {e}")
#                 dead_connections.add(connection)
        
#         # 清理失效连接
#         for conn in dead_connections:
#             self.disconnect(conn)

# manager = ConnectionManager()

# # 创建Deep Agent实例
# backend_dir = Path(__file__).parent
# os.chdir(backend_dir)

# # assistant_id = "medical-jiedu"
# assistant_id = "medical"
# agent_dir = backend_dir / 'agents' / assistant_id
# skills_dir = backend_dir / 'agents' / assistant_id / 'skills'
# project_dir = backend_dir / 'agents'

# settings = settings.from_environment(start_path=backend_dir)


# print(f"[INFO] assistant_id: {assistant_id}")
# print(f"[INFO] agent_dir: {agent_dir}")
# print(f"[INFO] skills_dir: {skills_dir}")


# # 读取 agent.md/ agent-think.md
# agent_prompt_path = agent_dir / 'agent.md'
# agent_prompt = ""
# if agent_prompt_path.exists():
#     agent_prompt = agent_prompt_path.read_text()

# # 读取 system.md
# system_prompt_path = agent_dir / 'system.md'
# system_prompt = ""
# if system_prompt_path.exists():
#     system_prompt = system_prompt_path.read_text()


# full_system_prompt = system_prompt + "\n\n" + agent_prompt


# # ========== 2. 创建 LLM ==========
# base_llm = create_custom_llm()

# # ========== 4. 创建 Backend ==========
# composite_backend = CompositeBackend(default=FilesystemBackend(root_dir="/home/xieshiao/baidu/personal-code/skillsdemo/backend/agents"), routes={})


# # # ========== 5. 创建 Middleware（不包含 FilesystemMiddleware）==========
# agent_middleware = [
#     AgentMemoryMiddleware(settings=settings, assistant_id=assistant_id),
#     SkillsMiddleware(
#         skills_dir=str(skills_dir),
#         assistant_id=assistant_id,
#         project_skills_dir=None
#     ),
#     ShellToolMiddleware(
#         workspace_root=str(backend_dir),
#         execution_policy=HostExecutionPolicy(),
#         env=os.environ,
#     ),
# ]

# # ========== 6. 创建 Agent（使用绑定了工具的模型 + tools 参数）==========
# agent = create_deep_agent(
#     name=assistant_id,
#     system_prompt=full_system_prompt,
#     middleware=agent_middleware,
#     backend=composite_backend,
#     model=base_llm
# )
# print(f"✓ WebSocket server initialized")


# @app.get("/", response_class=HTMLResponse)
# async def index(request: Request):
#     """主页面路由，返回WebSocket聊天界面HTML页面"""
#     return templates.TemplateResponse("index_ws.html", {"request": request})

# @app.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     """
#     WebSocket 连接端点，处理实时消息交互和批量评估功能

#     Args:
#         websocket: WebSocket连接对象，用于与客户端进行双向通信

#     功能说明：
#     - 建立和维护WebSocket连接
#     - 接收客户端发送的消息（支持文本、批量评估数据）
#     - 广播用户消息到所有连接的客户端
#     - 调用process_chat处理不同类型的数据输入

#     支持的数据格式：
#     - 普通聊天消息：包含message和history字段
#     - 批量评估数据：包含case_data、case_index、total_cases字段
    
#     Returns:
#         None: 函数持续运行直到连接断开
#     """
#     await manager.connect(websocket)
#     try:
#         while True:
#             # 接收客户端消息
#             data = await websocket.receive_json()
#             message = data.get("message", "")
#             history = data.get("history", [])
            
#             # 新增JSON数据字段
#             case_data = data.get("case_data")
#             case_index = data.get("case_index")
#             total_cases = data.get("total_cases")
        
#             if case_data:
#                 print(f"[JSON] 批量处理模式 - Case {case_index}/{total_cases}")
            
#             # 构建完整消息内容（包含图片和JSON描述）
#             full_message = message
            
#             if case_data:
#                 json_info = f"\n\n[批量评估模式] - Case {case_index}/{total_cases}"
#                 if isinstance(case_data, dict):
#                     if "id" in case_data:
#                         json_info += f" (ID: {case_data['id']})"
#                     if "type" in case_data:
#                         json_info += f" (类型: {case_data['type']})"
#                 full_message += json_info
            
            
#             # 发送用户消息到所有客户端
#             await manager.broadcast({
#                 "type": "user_message",
#                 "content": full_message
#             })
            
#             # 调用process_chat处理消息
#             await process_chat(
#                 message,
#                 history,
#                 case_data  # 传递case_data（可能是单个对象或列表）
#             )
            
#     except WebSocketDisconnect:
#         manager.disconnect(websocket)
#     except Exception as e:
#         print(f"[WS] 错误: {e}")
#         manager.disconnect(websocket)

# async def process_chat(message: str, history: List[Dict[str, str]], case_data: Union[Dict, List] = None) -> Dict:
#     """
#     处理聊天消息，支持三种输入模式：
#     1. 纯文本聊天
#     2. 文本+图像
#     3. 文本+JSON数据
    
#     Args:
#         message: 用户输入的文本消息
#         history: 对话历史记录
#         case_data: JSON格式的病例数据，可选（单个dict或list）
#     """
#     try:
#         # 处理多个case的情况
#         if isinstance(case_data, list):
#             total_cases = len(case_data)
            
#             # 🆕 首先发送批量处理的总体说明
#             batch_intro = f"📋 **批量处理模式启动**\n\n用户上传了 **{total_cases} 个病例数据**，将按顺序逐个处理。\n"
#             await manager.broadcast({
#                 "type": "assistant_message",
#                 "content": batch_intro
#             })
            
#             for idx, single_case in enumerate(case_data):
#                 print(f"[PROCESSING] 处理病例 {idx+1}/{total_cases}")
                
#                 # 发送当前处理进度
#                 progress_msg = f"\n{'─'*50}\n**正在处理: 病例 {idx+1}/{total_cases}**\n{'─'*50}\n"
#                 await manager.broadcast({
#                     "type": "assistant_message",
#                     "content": progress_msg
#                 })
                
#                 await manager.broadcast({
#                     "type": "progress",
#                     "content": f"正在处理病例 {idx+1}/{total_cases}",
#                     "current": idx + 1,
#                     "total": total_cases
#                 })
                
#                 # 🆕 在query中添加批量上下文信息
#                 enhanced_query = single_case.get("query", "")
#                 batch_context = f"[批量处理模式 - 这是第 {idx+1}/{total_cases} 个病例] "
                
#                 # 如果query不为空且没有批量标记，则添加
#                 if enhanced_query and not enhanced_query.startswith("[批量处理"):
#                     enhanced_query = batch_context + enhanced_query
#                 elif not enhanced_query:
#                     enhanced_query = batch_context + "请分析此病例。"
                
#                 # 递归处理单个case，传入增强的query
#                 await process_single_case(
#                     enhanced_query,
#                     single_case.get("history", []),
#                     single_case,  # 传递单个case数据
#                     batch_info={
#                         "current": idx + 1,
#                         "total": total_cases,
#                         "is_batch": True
#                     }
#                 )
            
#             # 🆕 所有case处理完成后的总结
#             completion_msg = f"\n\n{'='*50}\n✅ **批量处理完成**\n{'='*50}\n\n已成功处理全部 **{total_cases} 个病例**。\n"
#             await manager.broadcast({
#                 "type": "assistant_message",
#                 "content": completion_msg
#             })
            
#             # 发送最终完成信号
#             await manager.broadcast({"type": "complete"})
            
#             return {"status": "success", "processed": total_cases}

#         # 单个case的处理逻辑
#         return await process_single_case(message, history, case_data)
        
#     except Exception as e:
#         import traceback
#         print(f"[ERROR] process_chat: {e}")
#         print(traceback.format_exc())
#         await manager.broadcast({
#             "type": "error",
#             "content": f"批量处理错误: {str(e)}"
#         })
#         return {"status": "error", "message": str(e)}


# async def process_single_case(
#     message: str, 
#     history: List[Dict[str, str]], 
#     case_data: Dict = None,
#     batch_info: Dict = None
# ) -> Dict:
#     """
#     处理单个病例的核心逻辑
    
#     Args:
#         message: 用户输入的文本消息
#         history: 对话历史记录
#         case_data: 单个病例的JSON数据
#         batch_info: 批量处理信息 {"current": 1, "total": 10, "is_batch": True}
#     """
#     try:
#         # 构建消息上下文
#         messages = [{"role": m["role"], "content": m["content"]} for m in history]
        
#         # 构建多模态消息内容
#         content = [{"type": "text", "text": message}]

#         # 🆕 处理病例数据 - 更结构化的呈现
#         if case_data:
#             case_summary_parts = []
            
#             # 添加批量处理上下文（如果存在）
#             if batch_info and batch_info.get("is_batch"):
#                 case_summary_parts.append(
#                     f"**批量处理进度**: 第 {batch_info['current']}/{batch_info['total']} 个病例"
#                 )
            
#             case_summary_parts.append("\n**病例详细信息**:")
            
#             # 结构化展示各个字段
#             if "id" in case_data:
#                 case_summary_parts.append(f"• **病例ID**: {case_data['id']}")
            
#             if "type" in case_data:
#                 case_summary_parts.append(f"• **病例类型**: {case_data['type']}")
            
#             if "history" in case_data:
#                 history_text = case_data['history']
#                 # 如果病史太长，可以截断
#                 if len(history_text) > 500:
#                     history_text = history_text[:500] + "..."
#                 case_summary_parts.append(f"• **病史**: {history_text}")
            
#             if "query" in case_data and not batch_info:  # 非批量模式才显示query（批量模式已在message中）
#                 case_summary_parts.append(f"• **咨询问题**: {case_data['query']}")
            
#             if "assessment_result" in case_data:
#                 case_summary_parts.append(f"• **评估结果**: {case_data['assessment_result']}")
            
#             # 添加其他字段（动态处理未预期的字段）
#             excluded_keys = {"id", "type", "history", "query", "assessment_result", "image_url"}
#             for key, value in case_data.items():
#                 if key not in excluded_keys and value:
#                     case_summary_parts.append(f"• **{key}**: {value}")
            
#             if len(case_summary_parts) > 1:  # 确保不只有标题
#                 content.append({
#                     "type": "text",
#                     "text": "\n" + "\n".join(case_summary_parts)
#                 })
        
#         # 处理图片
#         if case_data and 'image_url' in case_data:
#             if isinstance(case_data['image_url'], list):
#                 for url in case_data['image_url']:
#                     if url:  # 确保URL不为空
#                         content.append({
#                             "type": "image_url",
#                             "image_url": {"url": url, "detail": "auto"}
#                         })
#             elif case_data['image_url']:  # 单个URL
#                 content.append({
#                     "type": "image_url",
#                     "image_url": {"url": case_data['image_url'], "detail": "auto"}
#                 })
        
#         messages.append({"role": "user", "content": content})
        
#         # ========== 流式处理 ==========
#         tool_call_tracking = {}  # 初始化工具调用跟踪
        
#         async for chunk in agent.astream({'messages': messages}):
#             if not isinstance(chunk, dict):
#                 continue
            
#             print(chunk)
            
#             # 跟踪工具调用
#             if 'model' in chunk:
#                 model_data = chunk['model']
#                 if isinstance(model_data, dict) and 'messages' in model_data:
#                     for msg in model_data['messages']:
#                         if hasattr(msg, 'content') and msg.content:
#                             if isinstance(msg.content, list):
#                                 for item in msg.content:
#                                     # 处理文本内容
#                                     if item.get('type') == 'text':
#                                         print(f"[DEBUG] 发送文本内容 ({len(item['text'])} 字符): {item['text'][:100]}...")        
#                                         await manager.broadcast({
#                                             "type": "assistant_message",
#                                             "content": item['text']
#                                         })
                                    
#                                     # 处理工具调用
#                                     elif item.get('type') == 'tool_use':
#                                         tool_call_id = item.get('id', '')
#                                         tool_name = item.get('name', '')
#                                         tool_args = item.get('input', {})
                                        
#                                         # 记录工具调用
#                                         tool_call_tracking[tool_call_id] = {
#                                             'tool_name': tool_name,
#                                             'args': tool_args
#                                         }
                                        
#                                         # 显示工具调用提示
#                                         if tool_name == 'read_file':
#                                             file_path = tool_args.get('file_path', '')
#                                             display_path = file_path.split('/skills/')[-1] if '/skills/' in file_path else file_path.split('/')[-1]
#                                             tip_msg = f"\n📖 加载文件: `{display_path}`\n"
#                                         elif tool_name == 'write_file':
#                                             file_path = tool_args.get('file_path', '')
#                                             display_path = file_path.split('/')[-1]
#                                             tip_msg = f"\n📝 创建文件: `{display_path}`\n"
#                                         elif tool_name == 'edit_file':
#                                             file_path = tool_args.get('file_path', '')
#                                             display_path = file_path.split('/')[-1]
#                                             tip_msg = f"\n✏️ 更新文件: `{display_path}`\n"
#                                         elif tool_name == 'shell':
#                                             command = tool_args.get('command', '')
#                                             import re
#                                             match = re.search(r'--name="([^"]+)"', command)
#                                             prefix = f'发送随访通知: {match.group(1)}' if match and 'followup_plan.py' in command else ''
#                                             cmd_display = f'{prefix} {command}'
#                                             tip_msg = f"\n🔧 执行命令: `{cmd_display}`\n"
#                                         else:
#                                             tip_msg = f"\n🔧 执行工具: `{tool_name}`\n"
                                        
#                                         print(f"[TOOL] 工具调用: {tool_name}, 参数: {tool_args}")
#                                         await manager.broadcast({
#                                             "type": "assistant_message",
#                                             "content": tip_msg
#                                         })
                                        
#                             # 处理纯文本内容
#                             elif isinstance(msg.content, str):
#                                 print(f"[DEBUG] 发送文本内容 ({len(msg.content)} 字符): {msg.content[:100]}...")        
#                                 await manager.broadcast({
#                                     "type": "assistant_message",
#                                     "content": msg.content
#                                 })
            
#             # 处理工具结果
#             if 'tools' in chunk:
#                 tools_data = chunk['tools']
#                 if isinstance(tools_data, dict) and 'messages' in tools_data:
#                     for msg in tools_data['messages']:
#                         if hasattr(msg, 'content'):
#                             result_content = msg.content if isinstance(msg.content, str) else str(msg.content)
#                             tool_call_id = getattr(msg, 'tool_call_id', '')
                            
#                             tool_info = tool_call_tracking.get(tool_call_id, {})
#                             tool_name = tool_info.get('tool_name', 'unknown')
                            
#                             # 检查是否有错误
#                             has_error = any(keyword in str(msg).lower() for keyword in ['error', 'stderr'])
#                             has_error = has_error or 'Error:' in result_content
                            
#                             if has_error:
#                                 print(f"[TOOL] ⚠️ 工具执行错误 ({tool_name}): {result_content[:200]}")
#                                 error_msg = f"\n⚠️ 执行错误: {result_content[:100]}\n\n"
#                                 await manager.broadcast({
#                                     "type": "assistant_message",
#                                     "content": error_msg
#                                 })
#                             else:
#                                 # 成功时只记录日志，不显示消息（保持界面简洁）
#                                 if tool_name == 'shell' and 'followup_plan.py' in str(tool_info.get('args', {})):
#                                     try:
#                                         import json
#                                         output_data = json.loads(result_content)
#                                         if output_data.get('errno') == 0:
#                                             result_msg = f"✅ 随访通知已发送\n"
#                                             await manager.broadcast({
#                                                 "type": "assistant_message",
#                                                 "content": result_msg
#                                             })
#                                     except:
#                                         pass
#                                 print(f"[TOOL] ✅ 工具执行成功: {tool_name}")
        
#         # 🆕 单个case处理完成（仅在批量模式下不发送complete，由外层统一发送）
#         if not batch_info or not batch_info.get("is_batch"):
#             await manager.broadcast({"type": "complete"})
        
#         return {"status": "success"}
        
#     except Exception as e:
#         import traceback
#         print(f"[ERROR] process_single_case: {e}")
#         print(traceback.format_exc())
#         await manager.broadcast({
#             "type": "error",
#             "content": f"处理错误: {str(e)}"
#         })
#         return {"status": "error", "message": str(e)}


# @app.post("/api/external")
# async def external_trigger(request: Request):
#     """
#     外部触发端点
#     接收外部消息，通过 WebSocket 广播到聊天页面
    
#     参数:
#         message: 消息内容（必需）
#         source: 来源标识（可选，默认 "external"）
#         silent: 是否静默模式（可选，默认 False）
#                - False: 在聊天界面显示用户消息和 AI 回复
#                - True: 只显示 AI 回复，不显示用户消息
#     """
#     data = await request.json()
#     message = data.get("message", "")
#     source = data.get("source", "external")
#     silent = data.get("silent", False)
#     api_key = request.headers.get("X-API-Key", "")
    
#     # 简单的 API Key 验证（可选）
#     # if api_key != "your-secret-key":
#     #     return {"error": "Unauthorized"}, 401
    
#     if not message:
#         return {"error": "Message is required"}, 400
    
#     print(f"[EXTERNAL] 来自 {source}: {message} {'(静默)' if silent else ''}")
    
#     # 只有非静默消息才广播用户消息到聊天界面
#     if not silent:
#         await manager.broadcast({
#             "type": "external_trigger",
#             "source": source,
#             "message": message
#         })
    
#     # 处理消息（AI 回复始终会广播）
#     await process_chat(message, [])
    
#     return {
#         "success": True,
#         "message": "Message sent to chat" if not silent else "Message processed silently",
#         "silent": silent,
#         "active_connections": len(manager.active_connections)
#     }


# async def execute_task(data):
#     """异步执行任务的函数，用于处理调度系统产生的任务消息处理"""
#     message = data.get("message", "")
#     source = data.get("source", "external")
#     silent = data.get("silent", False)
#     print('execute',data)
    
#     if not message:
#         return {"error": "Message is required"}, 400
    
#     print(f"[EXTERNAL] 来自 {source}: {message} {'(静默)' if silent else ''}")
    
#     # 只有非静默消息才广播用户消息到聊天界面
#     if not silent:
#         await manager.broadcast({
#             "type": "external_trigger",
#             "source": source,
#             "message": message
#         })
#     print("data")
    
#     # 处理消息（AI 回复始终会广播）
#     await process_chat(message, [])
#     return {"success": True, "message": "Message sent to chat" if not silent else "Message processed silently"}


# @app.post("/api/schedule")
# async def schedule_task(request: Request):
#     """调度任务接口，用于创建和管理异步任务执行"""
#     data = await request.json()
#     print('schedule',data)
#     job_id = data.get("job_id")
#     task = data.get("task")
#     delay_seconds = data.get("delay_seconds")

#     if task in ['started', 'Started', 'scheduled']:
#         # 使用asyncio.create_task创建后台任务
#         async def delayed_task():
#             print('delayed_task')
#             await asyncio.sleep(delay_seconds)
#             print('delayed_task')
#             await execute_task(data)
#         asyncio.create_task(delayed_task())
#     else:
#         pass
#     return {'job_id': job_id}

# @app.get("/api/status")
# async def status():
#     """查看当前系统状态，包括WebSocket连接数和agent状态信息"""
#     return {
#         "active_connections": len(manager.active_connections),
#         "agent": "medical",
#         # "agent": "medical_jiedu",
#         "websocket_enabled": True
#     }


# ###################################### 主文件入口 ####################################
# if __name__ == "__main__":
#     """程序主入口，启动基于uvicorn的WebSocket聊天服务器"""
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)