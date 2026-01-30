#!/usr/bin/env python3
"""
医疗报告解读质量评估结果导出工具 - JSON格式
支持从文件读取避免转义问题
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

def _default_output_dir() -> str:
    """
    默认输出到项目内的 outputs 目录，避免写死他人机器路径。
    位置：.../evaluate-record/outputs/
    """
    return str((Path(__file__).resolve().parent.parent / "outputs"))


def save_evaluation_json(evaluation_data, output_dir: str | None = None):
    """
    保存评估结果为 JSON 文件
    
    Args:
        evaluation_data: 评估数据字典
        output_dir: 输出目录路径
    
    Returns:
        str: JSON文件路径
    """
    
    if not output_dir:
        output_dir = _default_output_dir()

    # 确保输出目录存在
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"evaluation_report_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    # 完整的字段结构
    complete_data = {
        # 元数据
        "meta": {
            "version": "1.0",
            "generated_at": evaluation_data.get("assessment_time") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "evaluator": evaluation_data.get("evaluator", "AI系统"),
            "reviewer": evaluation_data.get("reviewer", "无")
        },
        
        # 报告基本信息
        "report_info": {
            "type": evaluation_data.get("report_type", ""),
            "exam_part": evaluation_data.get("exam_part", "")
        },
        
        # 综合评分
        "overall": {
            "total_score": evaluation_data.get("overall_score", "N/A"),
            "category_a_score": evaluation_data.get("category_a_score", "N/A"),
            "category_b_score": evaluation_data.get("category_b_score", "N/A"),
            "category_c_score": evaluation_data.get("category_c_score", "N/A")
        },
        
        # A类：核心维度
        "category_a": {
            "accuracy": {
                "score": evaluation_data.get("accuracy", "N/A"),
                "reason": evaluation_data.get("accuracy_reason", "未提供评分依据")
            },
            "relevance": {
                "score": evaluation_data.get("relevance", "N/A"),
                "reason": evaluation_data.get("relevance_reason", "未提供评分依据")
            }
        },
        
        # B类：专业维度
        "category_b": {
            "timeliness": {
                "score": evaluation_data.get("timeliness", "N/A"),
                "reason": evaluation_data.get("timeliness_reason", "未提供评分依据")
            },
            "comprehensiveness": {
                "score": evaluation_data.get("comprehensiveness", "N/A"),
                "reason": evaluation_data.get("comprehensiveness_reason", "未提供评分依据")
            },
            "suggestion_quality": {
                "score": evaluation_data.get("suggestion_quality", "N/A"),
                "reason": evaluation_data.get("suggestion_quality_reason", "未提供评分依据"),
                "rag_coverage": evaluation_data.get("rag_coverage", "N/A")
            }
        },
        
        # C类：体验维度
        "category_c": {
            "memory_retention": {
                "score": evaluation_data.get("memory_retention", "N/A"),
                "reason": evaluation_data.get("memory_retention_reason", "未提供评分依据")
            },
            "understandability": {
                "score": evaluation_data.get("understandability", "N/A"),
                "reason": evaluation_data.get("understandability_reason", "未提供评分依据")
            },
            "conciseness": {
                "score": evaluation_data.get("conciseness", "N/A"),
                "reason": evaluation_data.get("conciseness_reason", "未提供评分依据")
            },
            "personification": {
                "score": evaluation_data.get("personification", "N/A"),
                "reason": evaluation_data.get("personification_reason", "未提供评分依据")
            }
        },
        
        # 关键发现
        "key_findings": {
            "issues": evaluation_data.get("key_issues", ""),
            "rag_coverage": evaluation_data.get("rag_coverage", "N/A")
        }
    }
    
    # 写入JSON文件（美化格式，便于阅读）
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(complete_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 评估结果已保存至: {filepath}")
    return filepath

def main():
    """主函数 - 支持两种调用方式"""
    
    # 方式1: --data-file 从JSON文件读取（推荐）
    if "--data-file" in sys.argv:
        file_index = sys.argv.index("--data-file") + 1
        if file_index < len(sys.argv):
            try:
                with open(sys.argv[file_index], 'r', encoding='utf-8') as f:
                    evaluation_data = json.load(f)
            except Exception as e:
                print(json.dumps({
                    "status": "error",
                    "message": f"无法读取JSON文件: {e}"
                }), file=sys.stderr)
                sys.exit(1)
        else:
            print("❌ 错误: 请在 --data-file 后提供JSON文件路径", file=sys.stderr)
            sys.exit(1)
    
    # 方式2: 显示帮助信息
    else:
        print("医疗报告解读质量评估结果导出工具 - JSON格式")
        print("\n" + "="*60)
        print("使用方法:")
        print("="*60)
        
        print("\n【方式1: 从JSON文件读取（推荐）】")
        print("  用法: python save_json.py --data-file data.json")
        print("\n  示例:")
        print("    python save_json.py --data-file eval_data.json --output-dir /tmp")
        
        print("\n【方式2: 在Python代码中直接调用】")
        print("  用法: from save_json import save_evaluation_json")
        print("\n  示例:")
        print("    from save_json import save_evaluation_json")
        print("    data = {'report_type': '血常规', 'overall_score': 2.15}")
        print("    filepath = save_evaluation_json(data)")
        
        print("\n" + "="*60)
        print("参数说明:")
        print("="*60)
        print("  --data-file: JSON文件路径（包含评估数据）")
        print("  --output-dir: 输出目录路径（可选，默认: /home/xieshiao/user-data/outputs/)")
        
        sys.exit(0)
    
    # 获取输出目录
    output_dir = "/home/xieshiao/user-data/outputs/"
    if "--output-dir" in sys.argv:
        output_dir_index = sys.argv.index("--output-dir") + 1
        if output_dir_index < len(sys.argv):
            output_dir = sys.argv[output_dir_index]
    
    # 执行保存
    try:
        filepath = save_evaluation_json(evaluation_data, output_dir)
        print(json.dumps({"filepath": filepath, "status": "success"}))
    except Exception as e:
        import traceback
        print(json.dumps({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()