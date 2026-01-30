"""
交互式对话模块
提供命令行交互式对话功能
"""

class InteractiveChat:
    def __init__(self, greeting="欢迎使用交互式对话系统"):
        self.greeting = greeting
        self.commands = {}
    
    def register_command(self, name, callback, help_text=""):
        """注册新命令"""
        self.commands[name] = {
            'callback': callback,
            'help': help_text
        }
    
    def start(self):
        """启动交互式对话"""
        print(self.greeting)
        print("输入 'help' 查看可用命令, 'exit' 退出")
        
        while True:
            try:
                user_input = input("> ").strip()
                if not user_input:
                    continue
                
                if user_input.lower() == 'exit':
                    print("再见!")
                    break
                
                if user_input.lower() == 'help':
                    self._show_help()
                    continue
                
                parts = user_input.split()
                command = parts[0]
                args = parts[1:] if len(parts) > 1 else []
                
                if command in self.commands:
                    self.commands[command]['callback'](*args)
                else:
                    print(f"未知命令: {command}")
            
            except KeyboardInterrupt:
                print("\n再见!")
                break
            except Exception as e:
                print(f"错误: {e}")
    
    def _show_help(self):
        """显示帮助信息"""
        print("\n可用命令:")
        for cmd, info in self.commands.items():
            print(f"{cmd}: {info['help']}")
        print("help: 显示此帮助信息")
        print("exit: 退出程序\n")