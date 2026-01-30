"""
外部触发工具模块
用于接收和处理外部系统触发事件

使用示例:
# 普通消息
python examples/external_trigger.py "你好"

# 静默模式（只显示 AI 回复）
python examples/external_trigger.py "今天的健康建议" --silent
"""

import sys
import argparse

class ExternalTrigger:
    def __init__(self):
        self.listeners = []
    
    def add_listener(self, callback):
        """添加事件监听器"""
        self.listeners.append(callback)
    
    def trigger(self, event_data):
        """触发事件"""
        for callback in self.listeners:
            callback(event_data)
    
    def clear_listeners(self):
        """清除所有监听器"""
        self.listeners.clear()


def handle_message(message):
    """默认消息处理器"""
    response = f"AI回复: 已收到消息 - {message}"
    print(response)
    return response


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description='外部触发工具')
    parser.add_argument('message', help='要发送的消息内容')
    parser.add_argument('--silent', action='store_true', 
                       help='静默模式，只显示AI回复')
    args = parser.parse_args()

    if not args.silent:
        print(f"用户消息: {args.message}")
    
    trigger = ExternalTrigger()
    trigger.add_listener(handle_message)
    trigger.trigger(args.message)


if __name__ == '__main__':
    main()