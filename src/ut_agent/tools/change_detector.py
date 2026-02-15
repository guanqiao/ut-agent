"""变更检测模块 - 检测代码变更并分析方法级变更."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from ut_agent.tools.git_analyzer import ChangeType, CodeChange, GitAnalyzer


@dataclass
class MethodInfo:
    """方法信息."""

    name: str
    signature: str
    line_start: int
    line_end: int
    content: str
    modifiers: List[str] = field(default_factory=list)
    return_type: str = ""
    parameters: List[str] = field(default_factory=list)


@dataclass
class ClassInfo:
    """类信息."""

    name: str
    line_start: int
    line_end: int
    methods: Dict[str, MethodInfo] = field(default_factory=dict)
    fields: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    package: str = ""


@dataclass
class ChangeSummary:
    """变更摘要."""

    file_path: str
    change_type: ChangeType
    affected_classes: List[str] = field(default_factory=list)
    added_methods: List[MethodInfo] = field(default_factory=list)
    modified_methods: List[Tuple[MethodInfo, MethodInfo]] = field(
        default_factory=list
    )  # (old, new)
    deleted_methods: List[MethodInfo] = field(default_factory=list)


class JavaChangeDetector:
    """Java代码变更检测器."""

    # 方法签名正则
    METHOD_PATTERN = re.compile(
        r"^\s*(?:(public|private|protected)\s+)?"  # 访问修饰符
        r"(?:(static|final|abstract|synchronized)\s+)*"  # 其他修饰符
        r"(?:<[^>]+>\s+)?"  # 泛型
        r"([\w<>,\[\]\s]+?)\s+"  # 返回类型
        r"(\w+)\s*\(\s*([^)]*)\s*\)"  # 方法名和参数
        r"(?:\s*throws\s+([\w,\s]+))?"  # throws
        r"\s*\{",
        re.MULTILINE,
    )

    # 类定义正则
    CLASS_PATTERN = re.compile(
        r"^\s*(?:(public|private|protected)\s+)?"
        r"(?:(static|final|abstract)\s+)?"
        r"(class|interface|enum)\s+"
        r"(\w+)",
        re.MULTILINE,
    )

    def __init__(self, project_path: str):
        """初始化检测器.

        Args:
            project_path: 项目路径
        """
        self.project_path = Path(project_path)

    def analyze_changes(self, code_changes: List[CodeChange]) -> List[ChangeSummary]:
        """分析代码变更.

        Args:
            code_changes: 代码变更列表

        Returns:
            变更摘要列表
        """
        summaries = []

        for change in code_changes:
            if not change.file_path.endswith(".java"):
                continue

            summary = self._analyze_file_change(change)
            if summary:
                summaries.append(summary)

        return summaries

    def _analyze_file_change(self, change: CodeChange) -> Optional[ChangeSummary]:
        """分析单个文件变更.

        Args:
            change: 代码变更

        Returns:
            变更摘要
        """
        # 获取旧版本内容
        git_analyzer = GitAnalyzer(str(self.project_path))
        old_content = git_analyzer.get_file_at_ref(change.file_path, "HEAD~1")

        # 获取新版本内容
        new_content = None
        file_path = self.project_path / change.file_path
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    new_content = f.read()
            except Exception:
                pass

        if change.change_type == ChangeType.ADDED:
            # 新增文件
            if new_content:
                new_classes = self._parse_classes(new_content)
                return ChangeSummary(
                    file_path=change.file_path,
                    change_type=ChangeType.ADDED,
                    affected_classes=[c.name for c in new_classes],
                    added_methods=[
                        m for c in new_classes for m in c.methods.values()
                    ],
                )

        elif change.change_type == ChangeType.DELETED:
            # 删除文件
            if old_content:
                old_classes = self._parse_classes(old_content)
                return ChangeSummary(
                    file_path=change.file_path,
                    change_type=ChangeType.DELETED,
                    affected_classes=[c.name for c in old_classes],
                    deleted_methods=[
                        m for c in old_classes for m in c.methods.values()
                    ],
                )

        elif change.change_type == ChangeType.MODIFIED:
            # 修改文件
            if old_content and new_content:
                return self._compare_versions(
                    change.file_path, old_content, new_content
                )

        return None

    def _parse_classes(self, content: str) -> List[ClassInfo]:
        """解析类定义.

        Args:
            content: 代码内容

        Returns:
            类信息列表
        """
        classes = []
        lines = content.split("\n")

        # 查找包声明
        package = ""
        for line in lines:
            match = re.match(r"^\s*package\s+([\w.]+);", line)
            if match:
                package = match.group(1)
                break

        # 查找所有类定义
        for match in self.CLASS_PATTERN.finditer(content):
            class_name = match.group(4)
            line_start = content[: match.start()].count("\n") + 1

            # 查找类结束位置
            line_end = self._find_class_end(lines, line_start - 1)

            class_content = "\n".join(lines[line_start - 1 : line_end])
            methods = self._parse_methods(class_content, line_start)

            class_info = ClassInfo(
                name=class_name,
                line_start=line_start,
                line_end=line_end,
                methods=methods,
                package=package,
            )
            classes.append(class_info)

        return classes

    def _parse_methods(self, class_content: str, offset: int) -> Dict[str, MethodInfo]:
        """解析方法定义.

        Args:
            class_content: 类内容
            offset: 行号偏移

        Returns:
            方法字典
        """
        methods = {}

        for match in self.METHOD_PATTERN.finditer(class_content):
            modifiers = []
            if match.group(1):
                modifiers.append(match.group(1))
            if match.group(2):
                modifiers.extend(match.group(2).split())

            return_type = match.group(3).strip()
            method_name = match.group(4)
            parameters = [
                p.strip() for p in match.group(5).split(",") if p.strip()
            ]

            line_start = class_content[: match.start()].count("\n") + offset

            # 查找方法结束位置
            lines = class_content.split("\n")
            method_start_in_content = class_content[: match.start()].count("\n")
            line_end = self._find_method_end(
                lines, method_start_in_content, offset
            )

            method_content = "\n".join(lines[method_start_in_content:line_end])

            method_info = MethodInfo(
                name=method_name,
                signature=match.group(0),
                line_start=line_start,
                line_end=line_end,
                content=method_content,
                modifiers=modifiers,
                return_type=return_type,
                parameters=parameters,
            )
            methods[method_name] = method_info

        return methods

    def _find_class_end(self, lines: List[str], start_idx: int) -> int:
        """查找类结束位置.

        Args:
            lines: 代码行
            start_idx: 起始索引

        Returns:
            结束行号
        """
        brace_count = 0
        for i in range(start_idx, len(lines)):
            line = lines[i]
            brace_count += line.count("{") - line.count("}")
            if brace_count == 0 and "{" in lines[start_idx]:
                return i + 1
        return len(lines)

    def _find_method_end(
        self, lines: List[str], start_idx: int, offset: int
    ) -> int:
        """查找方法结束位置.

        Args:
            lines: 代码行
            start_idx: 起始索引
            offset: 偏移量

        Returns:
            结束行号
        """
        brace_count = 0
        for i in range(start_idx, len(lines)):
            line = lines[i]
            brace_count += line.count("{") - line.count("}")
            if brace_count == 0 and "{" in lines[start_idx]:
                return i + offset
        return len(lines) + offset

    def _compare_versions(
        self, file_path: str, old_content: str, new_content: str
    ) -> ChangeSummary:
        """比较两个版本.

        Args:
            file_path: 文件路径
            old_content: 旧内容
            new_content: 新内容

        Returns:
            变更摘要
        """
        old_classes = {c.name: c for c in self._parse_classes(old_content)}
        new_classes = {c.name: c for c in self._parse_classes(new_content)}

        all_class_names = set(old_classes.keys()) | set(new_classes.keys())

        added_methods = []
        modified_methods = []
        deleted_methods = []
        affected_classes = []

        for class_name in all_class_names:
            old_class = old_classes.get(class_name)
            new_class = new_classes.get(class_name)

            if old_class and new_class:
                affected_classes.append(class_name)

                # 比较方法
                old_methods = old_class.methods
                new_methods = new_class.methods

                # 新增方法
                for name, method in new_methods.items():
                    if name not in old_methods:
                        added_methods.append(method)
                    elif old_methods[name].content != method.content:
                        modified_methods.append((old_methods[name], method))

                # 删除方法
                for name, method in old_methods.items():
                    if name not in new_methods:
                        deleted_methods.append(method)

        return ChangeSummary(
            file_path=file_path,
            change_type=ChangeType.MODIFIED,
            affected_classes=affected_classes,
            added_methods=added_methods,
            modified_methods=modified_methods,
            deleted_methods=deleted_methods,
        )


class TypeScriptChangeDetector:
    """TypeScript/Vue变更检测器."""

    # 函数/方法正则
    FUNCTION_PATTERN = re.compile(
        r"^\s*(?:(export|async)\s+)*"
        r"(?:function\s+)?(\w+)\s*\([^)]*\)"
        r"(?:\s*:\s*([\w<>,\s|]+))?"
        r"\s*(?:=>|\{)",
        re.MULTILINE,
    )

    # Vue组件方法正则
    VUE_METHOD_PATTERN = re.compile(
        r"^\s*(\w+)\s*\([^)]*\)\s*\{", re.MULTILINE
    )

    def __init__(self, project_path: str):
        """初始化检测器.

        Args:
            project_path: 项目路径
        """
        self.project_path = Path(project_path)

    def analyze_changes(self, code_changes: List[CodeChange]) -> List[ChangeSummary]:
        """分析代码变更.

        Args:
            code_changes: 代码变更列表

        Returns:
            变更摘要列表
        """
        summaries = []

        for change in code_changes:
            if not any(
                change.file_path.endswith(ext)
                for ext in [".ts", ".tsx", ".js", ".jsx", ".vue"]
            ):
                continue

            summary = self._analyze_file_change(change)
            if summary:
                summaries.append(summary)

        return summaries

    def _analyze_file_change(self, change: CodeChange) -> Optional[ChangeSummary]:
        """分析单个文件变更.

        Args:
            change: 代码变更

        Returns:
            变更摘要
        """
        git_analyzer = GitAnalyzer(str(self.project_path))
        old_content = git_analyzer.get_file_at_ref(change.file_path, "HEAD~1")

        new_content = None
        file_path = self.project_path / change.file_path
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    new_content = f.read()
            except Exception:
                pass

        if change.change_type == ChangeType.ADDED and new_content:
            methods = self._parse_functions(new_content)
            return ChangeSummary(
                file_path=change.file_path,
                change_type=ChangeType.ADDED,
                added_methods=[
                    MethodInfo(
                        name=name,
                        signature=info["signature"],
                        line_start=info["line_start"],
                        line_end=info["line_end"],
                        content=info["content"],
                    )
                    for name, info in methods.items()
                ],
            )

        elif change.change_type == ChangeType.DELETED and old_content:
            methods = self._parse_functions(old_content)
            return ChangeSummary(
                file_path=change.file_path,
                change_type=ChangeType.DELETED,
                deleted_methods=[
                    MethodInfo(
                        name=name,
                        signature=info["signature"],
                        line_start=info["line_start"],
                        line_end=info["line_end"],
                        content=info["content"],
                    )
                    for name, info in methods.items()
                ],
            )

        elif change.change_type == ChangeType.MODIFIED:
            if old_content and new_content:
                return self._compare_versions(
                    change.file_path, old_content, new_content
                )

        return None

    def _parse_functions(self, content: str) -> Dict[str, dict]:
        """解析函数定义.

        Args:
            content: 代码内容

        Returns:
            函数字典
        """
        functions = {}
        lines = content.split("\n")

        for match in self.FUNCTION_PATTERN.finditer(content):
            func_name = match.group(2)
            line_start = content[: match.start()].count("\n") + 1

            # 查找函数结束
            line_end = self._find_function_end(lines, line_start - 1)

            functions[func_name] = {
                "signature": match.group(0),
                "line_start": line_start,
                "line_end": line_end,
                "content": "\n".join(lines[line_start - 1 : line_end]),
            }

        return functions

    def _find_function_end(self, lines: List[str], start_idx: int) -> int:
        """查找函数结束位置.

        Args:
            lines: 代码行
            start_idx: 起始索引

        Returns:
            结束行号
        """
        brace_count = 0
        in_function = False

        for i in range(start_idx, len(lines)):
            line = lines[i]

            if not in_function:
                if "{" in line or "=>" in line:
                    in_function = True
                    if "{" in line:
                        brace_count += line.count("{") - line.count("}")
            else:
                brace_count += line.count("{") - line.count("}")
                if brace_count == 0:
                    return i + 1

        return len(lines)

    def _compare_versions(
        self, file_path: str, old_content: str, new_content: str
    ) -> ChangeSummary:
        """比较两个版本.

        Args:
            file_path: 文件路径
            old_content: 旧内容
            new_content: 新内容

        Returns:
            变更摘要
        """
        old_functions = self._parse_functions(old_content)
        new_functions = self._parse_functions(new_content)

        added = []
        modified = []
        deleted = []

        # 新增和修改
        for name, info in new_functions.items():
            if name not in old_functions:
                added.append(
                    MethodInfo(
                        name=name,
                        signature=info["signature"],
                        line_start=info["line_start"],
                        line_end=info["line_end"],
                        content=info["content"],
                    )
                )
            elif old_functions[name]["content"] != info["content"]:
                modified.append(
                    (
                        MethodInfo(
                            name=name,
                            signature=old_functions[name]["signature"],
                            line_start=old_functions[name]["line_start"],
                            line_end=old_functions[name]["line_end"],
                            content=old_functions[name]["content"],
                        ),
                        MethodInfo(
                            name=name,
                            signature=info["signature"],
                            line_start=info["line_start"],
                            line_end=info["line_end"],
                            content=info["content"],
                        ),
                    )
                )

        # 删除
        for name, info in old_functions.items():
            if name not in new_functions:
                deleted.append(
                    MethodInfo(
                        name=name,
                        signature=info["signature"],
                        line_start=info["line_start"],
                        line_end=info["line_end"],
                        content=info["content"],
                    )
                )

        return ChangeSummary(
            file_path=file_path,
            change_type=ChangeType.MODIFIED,
            added_methods=added,
            modified_methods=modified,
            deleted_methods=deleted,
        )


def create_change_detector(project_path: str, project_type: str):
    """创建变更检测器工厂函数.

    Args:
        project_path: 项目路径
        project_type: 项目类型

    Returns:
        变更检测器实例
    """
    if project_type == "java":
        return JavaChangeDetector(project_path)
    elif project_type in ["vue", "react", "typescript"]:
        return TypeScriptChangeDetector(project_path)
    else:
        raise ValueError(f"不支持的项目类型: {project_type}")
