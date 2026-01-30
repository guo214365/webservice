#!/usr/bin/env python3
"""
交互式对话演示脚本
"""

import interactive_chat

def demo_interactive_chat():
    """演示交互式对话功能"""
    
    # 创建聊天实例
    chat = interactive_chat.InteractiveChat("欢迎使用演示对话系统")
    
    # 注册一些示例命令
    def say_hello(name=""):
        if name:
            print(f"你好，{name}！")
        else:
            print("你好！")
    
    def echo_message(*args):
        if args:
            print(" ".join(args))
        else:
            print("请输入要回显的消息")
    
    def show_info():
        print("这是一个交互式对话系统演示")
        print("当前时间: 2025-12-30")
        print("版本: 1.0")
    
    # 注册命令
    chat.register_command("hello", say_hello, "打招呼")
    chat.register_command("echo", echo_message, "回显消息")
    chat.register_command("info", show_info, "显示系统信息")
    
    print("开始交互式对话演示...")
    print("尝试输入: hello, hello 张三, echo 这是一条消息, info")
    chat.start()

if __name__ == '__main__':
    demo_interactive_chat()