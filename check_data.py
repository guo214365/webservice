#!/usr/bin/env python3
"""
强力诊断工具：精确定位生成旧JSON格式的代码
"""

import os
import re

print("="*70)
print("🔍 诊断：查找生成旧JSON格式的代码位置")
print("="*70)

# 旧JSON格式的特征关键词（按优先级排序）
search_patterns = [
    # 最明显的特征
    ('"advice_reasonableness"', "建议合理性字段（旧名）", "高"),
    ('"multiturn_memory"', "多轮记忆字段（旧名）", "高"),
    ('"humanization"', "拟人化字段（旧名）", "高"),
    ("'advice_reasonableness'", "建议合理性字段（旧名-单引号）", "高"),
    ("'multiturn_memory'", "多轮记忆字段（旧名-单引号）", "高"),
    ("'humanization'", "拟人化字段（旧名-单引号）", "高"),
    
    # JSON结构特征
    ('"scores"\\s*:\\s*{', "scores扁平结构", "中"),
    ('"overall"\\s*:\\s*{\\s*"weighted_score"', "overall.weighted_score结构", "高"),
    
    # 文件保存相关
    ('json\\.dump\\(.*"scores"', "直接dump scores结构", "高"),
    ('evaluation_report.*\\.json', "evaluation_report文件名", "低"),
]

# 搜索路径
base_paths = [
    "/home/xieshiao/baidu/personal-code/skillsdemo/backend/agents/medical/skills/evaluate-record/",
    "/home/xieshiao/baidu/personal-code/skillsdemo/backend/agents/medical/",
    "/home/xieshiao/baidu/personal-code/skillsdemo/backend/",
]

found_files = {}

print("\n正在搜索...")
print("-"*70)

for base_path in base_paths:
    if not os.path.exists(base_path):
        continue
    
    print(f"\n📂 搜索: {base_path}")
    
    for root, dirs, files in os.walk(base_path):
        # 跳过无关目录
        dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules', '.venv', 'venv']]
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    matches = []
                    for pattern, desc, priority in search_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            # 找到匹配行
                            lines = content.split('\n')
                            for line_num, line in enumerate(lines, 1):
                                if re.search(pattern, line, re.IGNORECASE):
                                    matches.append({
                                        'pattern': pattern,
                                        'desc': desc,
                                        'priority': priority,
                                        'line_num': line_num,
                                        'line_content': line.strip()
                                    })
                    
                    if matches:
                        if filepath not in found_files:
                            found_files[filepath] = []
                        found_files[filepath].extend(matches)
                
                except:
                    pass

# 按优先级排序并输出
if found_files:
    print("\n" + "="*70)
    print(f"🎯 找到 {len(found_files)} 个可疑文件")
    print("="*70)
    
    # 按高优先级匹配数量排序
    sorted_files = sorted(
        found_files.items(),
        key=lambda x: sum(1 for m in x[1] if m['priority'] == '高'),
        reverse=True
    )
    
    for filepath, matches in sorted_files:
        high_priority = sum(1 for m in matches if m['priority'] == '高')
        
        print(f"\n{'🔴' if high_priority >= 2 else '🟡'} 文件: {filepath}")
        print(f"   匹配数: {len(matches)} (高优先级: {high_priority})")
        
        # 显示前5个匹配
        shown_matches = sorted(matches, key=lambda x: {'高': 0, '中': 1, '低': 2}[x['priority']])[:5]
        
        for match in shown_matches:
            priority_emoji = {'高': '🔴', '中': '🟡', '低': '🟢'}[match['priority']]
            print(f"   {priority_emoji} 行{match['line_num']}: {match['desc']}")
            print(f"      {match['line_content'][:80]}")
        
        if len(matches) > 5:
            print(f"   ... 还有 {len(matches) - 5} 处匹配")
    
    # 输出最可疑的文件
    print("\n" + "="*70)
    print("🎯 最可疑的文件 (最有可能是问题所在):")
    print("="*70)
    
    top_suspects = [f for f, m in sorted_files if sum(1 for x in m if x['priority'] == '高') >= 2]
    
    if top_suspects:
        for i, filepath in enumerate(top_suspects[:3], 1):
            print(f"\n{i}. {filepath}")
            print(f"   👉 这个文件很可能包含生成旧JSON格式的代码")
            
            # 显示关键代码片段
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # 查找包含多个旧字段的代码块
                if 'advice_reasonableness' in content and 'multiturn_memory' in content:
                    print(f"   ⚠️  包含多个旧字段名，确认度：极高")
                    
                    # 尝试找到定义这些字段的函数
                    funcs = re.findall(r'def\s+(\w+)\s*\([^)]*\):', content)
                    if funcs:
                        print(f"   📝 可能的相关函数: {', '.join(funcs[:5])}")
            except:
                pass
    else:
        print("   未找到高度可疑的文件，请手动检查上述文件")
    
    print("\n" + "="*70)
    print("🔧 下一步操作:")
    print("="*70)
    print("1. 打开上述最可疑的文件")
    print("2. 搜索以下旧字段名:")
    print("   - advice_reasonableness")
    print("   - multiturn_memory")
    print("   - humanization")
    print("3. 找到构造JSON的代码，应该类似:")
    print('   result = {')
    print('       "scores": {')
    print('           "advice_reasonableness": ...,')
    print('           "multiturn_memory": ...,')
    print('       }')
    print('   }')
    print("4. 删除这段代码，改用skill.md中的调用方式")

else:
    print("\n❌ 未找到明显的旧格式代码")
    print("\n可能原因:")
    print("1. 搜索路径不对")
    print("2. 代码使用变量名而非字符串字面量")
    print("3. JSON在其他位置生成（如配置文件）")
    
    print("\n建议:")
    print("1. 检查你的评估主程序入口")
    print("2. 搜索所有Python文件中的 'weighted_score'")
    print("3. 查看最近修改的文件")

print("\n" + "="*70)