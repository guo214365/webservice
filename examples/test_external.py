#!/usr/bin/env python3
"""
外部触发工具测试脚本
"""

import external_trigger
import subprocess
import sys
import os

def test_external_trigger_module():
    """测试 ExternalTrigger 类"""
    print("=== 测试 ExternalTrigger 类 ===")
    
    # 创建触发器实例
    trigger = external_trigger.ExternalTrigger()
    
    # 定义测试监听器
    def listener1(data):
        print(f"监听器1: 收到数据 - {data}")
    
    def listener2(data):
        print(f"监听器2: 处理数据 - {data.upper()}")
    
    # 添加监听器
    trigger.add_listener(listener1)
    trigger.add_listener(listener2)
    
    # 触发事件
    print("触发 'hello world' 事件:")
    trigger.trigger("hello world")
    
    # 清除监听器测试
    trigger.clear_listeners()
    print("\n清除监听器后再次触发:")
    trigger.trigger("test after clear")


def test_command_line():
    """测试命令行接口"""
    print("\n=== 测试命令行接口 ===")
    
    # 测试普通模式
    print("1. 普通模式测试:")
    result = subprocess.run([sys.executable, "external_trigger.py", "测试消息"], 
                          capture_output=True, text=True, cwd=os.path.dirname(__file__))
    print("输出:", result.stdout)
    
    # 测试静默模式
    print("2. 静默模式测试:")
    result = subprocess.run([sys.executable, "external_trigger.py", "静默测试", "--silent"], 
                          capture_output=True, text=True, cwd=os.path.dirname(__file__))
    print("输出:", result.stdout)


if __name__ == '__main__':
    test_external_trigger_module()
    test_command_line()
    print("\n=== 测试完成 ===")