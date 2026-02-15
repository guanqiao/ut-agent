"""Git差异分析模块."""

import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple


class ChangeType(Enum):
    """变更类型."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass
class CodeChange:
    """代码变更信息."""

    file_path: str
    change_type: ChangeType
    old_path: Optional[str] = None
    line_range: Tuple[int, int] = field(default_factory=lambda: (0, 0))
    diff_content: str = ""
    added_lines: List[int] = field(default_factory=list)
    deleted_lines: List[int] = field(default_factory=list)


@dataclass
class MethodChange:
    """方法级变更信息."""

    file_path: str
    method_name: str
    change_type: ChangeType
    signature: str = ""
    line_start: int = 0
    line_end: int = 0


class GitAnalyzer:
    """Git差异分析器."""

    def __init__(self, project_path: str):
        """初始化Git分析器.

        Args:
            project_path: 项目路径
        """
        self.project_path = Path(project_path)
        self._check_git_repo()

    def _check_git_repo(self) -> None:
        """检查是否为Git仓库."""
        git_dir = self.project_path / ".git"
        if not git_dir.exists():
            raise ValueError(f"{self.project_path} 不是Git仓库")

    def _run_git_command(self, args: List[str]) -> str:
        """执行Git命令.

        Args:
            args: Git命令参数

        Returns:
            命令输出
        """
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if result.returncode != 0:
                raise RuntimeError(f"Git命令失败: {result.stderr}")
            return result.stdout
        except FileNotFoundError:
            raise RuntimeError("未找到Git命令，请确保Git已安装")

    def get_changed_files(
        self,
        base_ref: Optional[str] = None,
        head_ref: Optional[str] = None,
        include_untracked: bool = False,
    ) -> List[CodeChange]:
        """获取变更文件列表.

        Args:
            base_ref: 基准分支/提交 (默认: HEAD~1)
            head_ref: 目标分支/提交 (默认: HEAD)
            include_untracked: 是否包含未跟踪文件

        Returns:
            变更列表
        """
        changes = []

        # 获取diff统计
        if base_ref or head_ref:
            # 比较两个引用
            base = base_ref or "HEAD~1"
            head = head_ref or "HEAD"
            diff_stat = self._run_git_command(["diff", "--stat", f"{base}...{head}"])
        else:
            # 获取工作区变更
            diff_stat = self._run_git_command(["diff", "--stat", "HEAD"])

        # 解析diff统计
        for line in diff_stat.strip().split("\n"):
            if "|" in line:
                parts = line.split("|")
                if len(parts) >= 2:
                    file_path = parts[0].strip()
                    if file_path:
                        change = self._get_file_diff(file_path, base_ref, head_ref)
                        if change:
                            changes.append(change)

        # 获取未跟踪文件
        if include_untracked:
            untracked = self._get_untracked_files()
            changes.extend(untracked)

        return changes

    def _get_file_diff(
        self,
        file_path: str,
        base_ref: Optional[str] = None,
        head_ref: Optional[str] = None,
    ) -> Optional[CodeChange]:
        """获取单个文件的diff.

        Args:
            file_path: 文件路径
            base_ref: 基准引用
            head_ref: 目标引用

        Returns:
            变更信息
        """
        try:
            if base_ref or head_ref:
                base = base_ref or "HEAD~1"
                head = head_ref or "HEAD"
                diff_output = self._run_git_command(
                    ["diff", "-u", f"{base}...{head}", "--", file_path]
                )
            else:
                diff_output = self._run_git_command(["diff", "-u", "HEAD", "--", file_path])

            if not diff_output:
                return None

            return self._parse_diff(file_path, diff_output)
        except RuntimeError:
            return None

    def _parse_diff(self, file_path: str, diff_content: str) -> CodeChange:
        """解析diff内容.

        Args:
            file_path: 文件路径
            diff_content: diff内容

        Returns:
            变更信息
        """
        added_lines = []
        deleted_lines = []
        current_line = 0

        for line in diff_content.split("\n"):
            if line.startswith("@@"):
                # 解析hunk头
                match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
                if match:
                    current_line = int(match.group(2))
            elif line.startswith("+") and not line.startswith("+++"):
                added_lines.append(current_line)
                current_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                deleted_lines.append(current_line)
            elif not line.startswith("\\"):
                current_line += 1

        # 确定变更类型
        if not added_lines and not deleted_lines:
            change_type = ChangeType.MODIFIED
        elif not deleted_lines:
            change_type = ChangeType.ADDED
        elif not added_lines:
            change_type = ChangeType.DELETED
        else:
            change_type = ChangeType.MODIFIED

        # 计算行范围
        all_lines = added_lines + deleted_lines
        line_range = (min(all_lines), max(all_lines)) if all_lines else (0, 0)

        return CodeChange(
            file_path=file_path,
            change_type=change_type,
            line_range=line_range,
            diff_content=diff_content,
            added_lines=added_lines,
            deleted_lines=deleted_lines,
        )

    def _get_untracked_files(self) -> List[CodeChange]:
        """获取未跟踪文件.

        Returns:
            未跟踪文件列表
        """
        output = self._run_git_command(["ls-files", "--others", "--exclude-standard"])
        changes = []

        for line in output.strip().split("\n"):
            if line:
                file_path = Path(self.project_path) / line
                if file_path.exists():
                    changes.append(
                        CodeChange(
                            file_path=line,
                            change_type=ChangeType.ADDED,
                            line_range=(1, self._count_file_lines(file_path)),
                        )
                    )

        return changes

    def _count_file_lines(self, file_path: Path) -> int:
        """计算文件行数.

        Args:
            file_path: 文件路径

        Returns:
            行数
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return len(f.readlines())
        except Exception:
            return 0

    def get_staged_changes(self) -> List[CodeChange]:
        """获取暂存区的变更.

        Returns:
            变更列表
        """
        output = self._run_git_command(["diff", "--cached", "--name-only"])
        changes = []

        for line in output.strip().split("\n"):
            if line:
                diff_output = self._run_git_command(["diff", "--cached", "-u", "--", line])
                if diff_output:
                    changes.append(self._parse_diff(line, diff_output))

        return changes

    def get_file_at_ref(self, file_path: str, ref: str = "HEAD") -> Optional[str]:
        """获取指定引用处的文件内容.

        Args:
            file_path: 文件路径
            ref: Git引用

        Returns:
            文件内容
        """
        try:
            return self._run_git_command(["show", f"{ref}:{file_path}"])
        except RuntimeError:
            return None

    def get_last_commit_hash(self) -> str:
        """获取最后一次提交的哈希.

        Returns:
            提交哈希
        """
        return self._run_git_command(["rev-parse", "HEAD"]).strip()

    def get_commit_message(self, ref: str = "HEAD") -> str:
        """获取提交信息.

        Args:
            ref: Git引用

        Returns:
            提交信息
        """
        return self._run_git_command(["log", "-1", "--pretty=%B", ref]).strip()


def filter_source_files(
    changes: List[CodeChange],
    project_type: str,
) -> List[CodeChange]:
    """过滤出源代码文件.

    Args:
        changes: 变更列表
        project_type: 项目类型

    Returns:
        源代码文件变更列表
    """
    if project_type == "java":
        extensions = [".java"]
    elif project_type in ["vue", "react", "typescript"]:
        extensions = [".ts", ".tsx", ".js", ".jsx", ".vue"]
    else:
        return changes

    filtered = []
    for change in changes:
        if any(change.file_path.endswith(ext) for ext in extensions):
            # 排除测试文件
            if "test" not in change.file_path.lower() and "spec" not in change.file_path.lower():
                filtered.append(change)

    return filtered


def get_changed_methods(
    git_analyzer: GitAnalyzer,
    changes: List[CodeChange],
) -> List[MethodChange]:
    """获取变更的方法列表.

    Args:
        git_analyzer: Git分析器
        changes: 变更列表

    Returns:
        方法变更列表
    """
    method_changes = []

    for change in changes:
        # 获取变更前后的内容
        old_content = git_analyzer.get_file_at_ref(change.file_path, "HEAD~1")
        new_content = None

        file_path = Path(git_analyzer.project_path) / change.file_path
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    new_content = f.read()
            except Exception:
                pass

        # 分析方法变更
        if old_content and new_content:
            # 对比分析方法
            old_methods = _extract_methods(old_content)
            new_methods = _extract_methods(new_content)

            # 检测新增方法
            for method_name, method_info in new_methods.items():
                if method_name not in old_methods:
                    method_changes.append(
                        MethodChange(
                            file_path=change.file_path,
                            method_name=method_name,
                            change_type=ChangeType.ADDED,
                            signature=method_info["signature"],
                            line_start=method_info["line_start"],
                            line_end=method_info["line_end"],
                        )
                    )
                elif _method_changed(old_methods[method_name], method_info):
                    method_changes.append(
                        MethodChange(
                            file_path=change.file_path,
                            method_name=method_name,
                            change_type=ChangeType.MODIFIED,
                            signature=method_info["signature"],
                            line_start=method_info["line_start"],
                            line_end=method_info["line_end"],
                        )
                    )

            # 检测删除的方法
            for method_name, method_info in old_methods.items():
                if method_name not in new_methods:
                    method_changes.append(
                        MethodChange(
                            file_path=change.file_path,
                            method_name=method_name,
                            change_type=ChangeType.DELETED,
                            signature=method_info["signature"],
                            line_start=method_info["line_start"],
                            line_end=method_info["line_end"],
                        )
                    )

    return method_changes


def _extract_methods(content: str) -> dict:
    """从代码内容中提取方法.

    Args:
        content: 代码内容

    Returns:
        方法字典
    """
    methods = {}
    lines = content.split("\n")

    # 简单的正则匹配方法签名
    # Java: public|private|protected [static] [final] ReturnType methodName(...)
    # TypeScript: function|const|async function|methodName(...)
    method_pattern = re.compile(
        r"^\s*(?:public|private|protected)?\s*(?:static|final)?\s*"
        r"(?:[\w<>\[\]]+\s+)?(\w+)\s*\([^)]*\)\s*(?:throws\s+\w+)?\s*\{"
    )

    current_method = None
    brace_count = 0
    line_start = 0

    for i, line in enumerate(lines, 1):
        match = method_pattern.match(line)
        if match and brace_count == 0:
            current_method = match.group(1)
            line_start = i
            brace_count = line.count("{") - line.count("}")
        elif current_method:
            brace_count += line.count("{") - line.count("}")
            if brace_count == 0:
                methods[current_method] = {
                    "signature": line.strip(),
                    "line_start": line_start,
                    "line_end": i,
                    "content": "\n".join(lines[line_start - 1 : i]),
                }
                current_method = None

    return methods


def _method_changed(old_info: dict, new_info: dict) -> bool:
    """检查方法是否发生变化.

    Args:
        old_info: 旧方法信息
        new_info: 新方法信息

    Returns:
        是否变化
    """
    return old_info.get("content") != new_info.get("content")
