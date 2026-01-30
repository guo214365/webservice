"""
安全技能中间件 - 防止工具冲突和嵌套调用

直接包装 deepagents_cli.skills.SkillsMiddleware
在不修改原始代码的情况下，自动清理技能文件中的问题内容
"""

import re
from pathlib import Path
from typing import Optional
from deepagents.middleware.skills import SkillsMiddleware
from deepagents.backends.filesystem import FilesystemBackend


class SafeSkillsMiddleware(SkillsMiddleware):
    """
    安全技能中间件 - 自动清理技能文件问题
    
    功能：
    1. 移除技能文件中的工具定义（避免重复）
    2. 替换"调用XX技能"为"执行XX方法"（避免嵌套）
    3. 添加安全检查和警告
    """
    
    def __init__(
        self,
        *,
        skills_dir: str | Path,
        assistant_id: str,
        project_skills_dir: str | Path | None = None,
        auto_clean: bool = True,
        verbose: bool = True,
    ) -> None:
        """
        初始化安全技能中间件
        
        Args:
            skills_dir: 用户级技能目录
            assistant_id: 助手ID
            project_skills_dir: 项目级技能目录（可选）
            auto_clean: 是否自动清理技能文件（默认True）
            verbose: 是否打印详细日志（默认True）
        """
        self.auto_clean = auto_clean
        self.verbose = verbose
        self.cleaned_files = []
        self.warnings = []
        
        # 如果启用自动清理，预处理技能文件
        if self.auto_clean:
            self._preprocess_skills(Path(skills_dir), project_skills_dir)
        
        # deepagents.middleware.skills.SkillsMiddleware 新签名：
        # __init__(self, *, backend: BACKEND_TYPES, sources: list[str])
        # 这里用 FilesystemBackend 直接指向技能目录，并从根目录 "." 加载
        super().__init__(backend=FilesystemBackend(root_dir=str(skills_dir)), sources=["."])
        
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"[SafeSkills] ✓ 安全技能中间件已启用")
            print(f"[SafeSkills]   清理的文件数: {len(self.cleaned_files)}")
            print(f"[SafeSkills]   警告数: {len(self.warnings)}")
            print(f"{'='*60}\n")
    
    def _preprocess_skills(
        self, 
        skills_dir: Path, 
        project_skills_dir: Optional[str | Path]
    ):
        """
        预处理技能文件
        
        Args:
            skills_dir: 用户技能目录
            project_skills_dir: 项目技能目录
        """
        if self.verbose:
            print(f"\n[SafeSkills] 开始预处理技能文件...")
        
        # 收集所有需要处理的目录
        dirs_to_process = [skills_dir]
        if project_skills_dir:
            dirs_to_process.append(Path(project_skills_dir))
        
        # 处理每个目录
        for directory in dirs_to_process:
            if not directory.exists():
                if self.verbose:
                    print(f"[SafeSkills] ⚠️ 目录不存在: {directory}")
                continue
            
            # 查找所有 SKILL.md 文件
            skill_files = list(directory.rglob("SKILL.md"))
            
            if self.verbose:
                print(f"[SafeSkills] 处理目录: {directory}")
                print(f"[SafeSkills]   发现 {len(skill_files)} 个技能文件")
            
            for skill_file in skill_files:
                self._clean_skill_file(skill_file)
    
    def _clean_skill_file(self, skill_file: Path):
        """
        清理单个技能文件
        
        处理内容：
        1. 移除工具定义部分
        2. 替换嵌套调用指令
        3. 添加执行约束说明
        
        Args:
            skill_file: 技能文件路径
        """
        try:
            # 读取原始内容
            content = skill_file.read_text(encoding='utf-8')
            original_content = content
            modified = False
            
            # ========== 1. 移除工具定义章节 ==========
            # 匹配模式：## 可用工具 或 ## 工具 或 ## Tools
            tool_section_pattern = r'##\s+(可用工具|工具|Tools?|Available\s+Tools?)\s*\n(.*?)(?=\n##|\Z)'
            
            if re.search(tool_section_pattern, content, re.DOTALL | re.IGNORECASE):
                content = re.sub(
                    tool_section_pattern,
                    '',
                    content,
                    flags=re.DOTALL | re.IGNORECASE
                )
                modified = True
                warning = f"移除了工具定义章节: {skill_file.relative_to(skill_file.parent.parent.parent)}"
                self.warnings.append(warning)
                
                if self.verbose:
                    print(f"[SafeSkills]   ✓ {warning}")
            
            # ========== 2. 移除单独的工具列表项 ==========
            # 匹配模式：- read_file: ... 或 - write_file: ...
            tool_list_pattern = r'^[\s]*[-*]\s+(read_file|write_file|edit_file|ls|glob|grep|execute_bash|web_search|http_request|write_todos|shell)[:：].*?$'
            
            tool_matches = re.findall(tool_list_pattern, content, re.MULTILINE | re.IGNORECASE)
            if tool_matches:
                content = re.sub(
                    tool_list_pattern,
                    '',
                    content,
                    flags=re.MULTILINE | re.IGNORECASE
                )
                modified = True
                
                if self.verbose:
                    print(f"[SafeSkills]   ✓ 移除了 {len(tool_matches)} 个工具列表项")
            
            # ========== 3. 替换嵌套调用指令 ==========
            # 匹配模式：调用技能、触发技能、调用XX skill等
            nesting_patterns = [
                (r'调用\s*技能[:：]\s*`?([^`\n]+)`?', '参考 \\1 的方法论'),
                (r'触发\s*技能[:：]\s*`?([^`\n]+)`?', '执行 \\1 的流程'),
                (r'调用\s+`?([^`\n]+\.md)`?\s+技能', '参考 \\1 中的方法'),
                (r'使用\s+([^\s]+)\s+技能', '按照 \\1 的方法执行'),
            ]
            
            for pattern, replacement in nesting_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
                    modified = True
                    
                    if self.verbose:
                        print(f"[SafeSkills]   ✓ 替换了嵌套调用: {len(matches)} 处")
            
            # ========== 4. 写回文件（如果有修改）==========
            if modified:
                # 创建备份
                backup_file = skill_file.with_suffix('.md.backup')
                if not backup_file.exists():
                    backup_file.write_text(original_content, encoding='utf-8')
                
                # 写入清理后的内容
                skill_file.write_text(content, encoding='utf-8')
                self.cleaned_files.append(str(skill_file))
                
                if self.verbose:
                    print(f"[SafeSkills] ✓ 已清理: {skill_file.name}")
                    print(f"[SafeSkills]   备份: {backup_file.name}")
        
        except Exception as e:
            error_msg = f"清理失败 {skill_file}: {e}"
            self.warnings.append(error_msg)
            if self.verbose:
                print(f"[SafeSkills] ❌ {error_msg}")
    
    def get_cleaning_report(self) -> dict:
        """
        获取清理报告
        
        Returns:
            包含清理统计的字典
        """
        return {
            "cleaned_files_count": len(self.cleaned_files),
            "warnings_count": len(self.warnings),
            "cleaned_files": self.cleaned_files,
            "warnings": self.warnings
        }


# ========== 使用示例 ==========
if __name__ == "__main__":
    # 测试清理功能
    middleware = SafeSkillsMiddleware(
        skills_dir="/home/xieshiao/baidu/personal-code/skillsdemo/backend/agents/medical-jiedu/skills",
        assistant_id="medical-jiedu",
        auto_clean=True,
        verbose=True
    )
    
    # 打印清理报告
    report = middleware.get_cleaning_report()
    print("\n" + "="*60)
    print("清理报告:")
    print(f"  清理的文件数: {report['cleaned_files_count']}")
    print(f"  警告数: {report['warnings_count']}")
    print("="*60)