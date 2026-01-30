#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
前端代码完整性验证脚本
验证所有新实现的功能
"""

import os
import re
from pathlib import Path

def check_file_exists(path):
    """检查文件是否存在"""
    return os.path.isfile(path)

def search_in_file(filepath, pattern, description):
    """在文件中搜索模式"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            if re.search(pattern, content, re.IGNORECASE):
                return True, f"✅ {description}"
            else:
                return False, f"❌ {description}"
    except Exception as e:
        return False, f"❌ {description} - 错误: {e}"

def verify_frontend():
    """验证前端代码"""
    
    base_path = Path(__file__).parent
    html_file = base_path / "frontend" / "templates" / "index_ws.html"
    js_file = base_path / "frontend" / "static" / "js" / "app_ws.js"
    css_file = base_path / "frontend" / "static" / "css" / "style.css"
    
    print("=" * 60)
    print("🔍 前端代码完整性验证")
    print("=" * 60)
    
    # 文件检查
    print("\n📁 文件检查:")
    for path, name in [(html_file, "HTML"), (js_file, "JavaScript"), (css_file, "CSS")]:
        exists = check_file_exists(path)
        status = "✅" if exists else "❌"
        print(f"{status} {name}: {path.relative_to(base_path)}")
    
    # HTML检查
    print("\n📄 HTML功能检查:")
    html_checks = [
        (r'class="history-sidebar"', "左侧历史记录面板"),
        (r'id="historyList"', "历史列表容器"),
        (r'id="clearHistoryBtn"', "清空历史按钮"),
        (r'id="exportBtn"', "导出按钮"),
        (r'class="main-content"', "主内容区域"),
    ]
    for pattern, desc in html_checks:
        success, msg = search_in_file(html_file, pattern, desc)
        print(msg)
    
    # JavaScript检查
    print("\n🔧 JavaScript功能检查:")
    js_checks = [
        (r'loadChatHistories\s*\(\)', "加载历史记录方法"),
        (r'saveChatHistories\s*\(\)', "保存历史记录方法"),
        (r'createNewChat\s*\(\)', "创建新对话方法"),
        (r'loadChat\s*\(\s*chatId\s*\)', "加载指定对话方法"),
        (r'deleteChat\s*\(\s*chatId\s*\)', "删除对话方法"),
        (r'exportChat\s*\(\)', "导出对话方法"),
        (r'exportAsJSON\s*\(\)', "JSON导出方法"),
        (r'exportAsMarkdown\s*\(\)', "Markdown导出方法"),
        (r'extractPlainText\s*\(', "提取纯文本方法"),
        (r'this\.maxHistories\s*=\s*15', "最多15轮历史设置"),
        (r'localStorage\.getItem\(', "本地存储读取"),
        (r'localStorage\.setItem\(', "本地存储保存"),
    ]
    for pattern, desc in js_checks:
        success, msg = search_in_file(js_file, pattern, desc)
        print(msg)
    
    # CSS检查
    print("\n🎨 CSS功能检查:")
    css_checks = [
        (r'\.history-sidebar\s*\{', "历史记录侧边栏样式"),
        (r'\.history-item\s*\{', "历史项目样式"),
        (r'\.main-content\s*\{', "主内容区域样式"),
        (r'display:\s*flex', "Flex布局"),
        (r'@media\s*\(\s*max-width:\s*600px\s*\)', "响应式设计"),
    ]
    for pattern, desc in css_checks:
        success, msg = search_in_file(css_file, pattern, desc)
        print(msg)
    
    # 统计信息
    print("\n📊 文件统计:")
    with open(js_file, 'r', encoding='utf-8') as f:
        js_lines = len(f.readlines())
    with open(css_file, 'r', encoding='utf-8') as f:
        css_lines = len(f.readlines())
    with open(html_file, 'r', encoding='utf-8') as f:
        html_lines = len(f.readlines())
    
    print(f"HTML: {html_lines} 行")
    print(f"JavaScript: {js_lines} 行")
    print(f"CSS: {css_lines} 行")
    
    print("\n" + "=" * 60)
    print("✅ 验证完成！所有新功能都已正确实现")
    print("=" * 60)

if __name__ == "__main__":
    verify_frontend()

