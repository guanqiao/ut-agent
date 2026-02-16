"""测试文件映射模块 - 管理源文件与测试文件的映射关系."""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from ut_agent.tools.change_detector import MethodInfo


@dataclass
class TestMapping:
    """测试映射信息."""

    source_file: str
    test_file: str
    method_mappings: Dict[str, str] = field(default_factory=dict)
    last_generated: datetime = field(default_factory=datetime.now)
    source_hash: str = ""
    test_hash: str = ""
    has_manual_changes: bool = False
    manual_sections: List[Tuple[int, int]] = field(default_factory=list)


@dataclass
class MethodTestMapping:
    """方法到测试方法的映射."""

    source_method: str
    test_method: str
    test_file: str
    line_start: int
    line_end: int
    is_auto_generated: bool = True


class TestFileMapper:
    """测试文件映射器."""

    # 手工修改标记
    MANUAL_MARKER = "// MANUAL"
    AUTO_GENERATED_MARKER = "// AUTO-GENERATED"

    def __init__(self, project_path: str, project_type: str):
        """初始化映射器.

        Args:
            project_path: 项目路径
            project_type: 项目类型
        """
        self.project_path = Path(project_path)
        self.project_type = project_type
        self.mappings: Dict[str, TestMapping] = {}
        self.mapping_file = self.project_path / ".ut-agent" / "mappings.json"
        self._load_mappings()

    def _load_mappings(self) -> None:
        """加载映射关系."""
        if self.mapping_file.exists():
            try:
                with open(self.mapping_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for key, value in data.items():
                        self.mappings[key] = TestMapping(
                            source_file=value["source_file"],
                            test_file=value["test_file"],
                            method_mappings=value.get("method_mappings", {}),
                            last_generated=datetime.fromisoformat(
                                value.get("last_generated", datetime.now().isoformat())
                            ),
                            source_hash=value.get("source_hash", ""),
                            test_hash=value.get("test_hash", ""),
                            has_manual_changes=value.get("has_manual_changes", False),
                            manual_sections=[
                                tuple(s) for s in value.get("manual_sections", [])
                            ],
                        )
            except Exception as e:
                print(f"加载映射文件失败: {e}")

    def _save_mappings(self) -> None:
        """保存映射关系."""
        self.mapping_file.parent.mkdir(parents=True, exist_ok=True)

        data = {}
        for key, mapping in self.mappings.items():
            data[key] = {
                "source_file": mapping.source_file,
                "test_file": mapping.test_file,
                "method_mappings": mapping.method_mappings,
                "last_generated": mapping.last_generated.isoformat(),
                "source_hash": mapping.source_hash,
                "test_hash": mapping.test_hash,
                "has_manual_changes": mapping.has_manual_changes,
                "manual_sections": mapping.manual_sections,
            }

        try:
            with open(self.mapping_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存映射文件失败: {e}")

    def _compute_hash(self, content: str) -> str:
        """计算内容哈希.

        Args:
            content: 内容

        Returns:
            哈希值
        """
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def find_test_file(self, source_file: str) -> Optional[str]:
        """查找源文件对应的测试文件.

        Args:
            source_file: 源文件路径

        Returns:
            测试文件路径
        """
        # 检查已有映射
        if source_file in self.mappings:
            test_file = self.mappings[source_file].test_file
            if (self.project_path / test_file).exists():
                return test_file

        # 推断测试文件路径
        test_file = self._infer_test_file_path(source_file)
        if test_file and (self.project_path / test_file).exists():
            return test_file

        return None

    def _infer_test_file_path(self, source_file: str) -> Optional[str]:
        """推断测试文件路径.

        Args:
            source_file: 源文件路径

        Returns:
            测试文件路径
        """
        source_path = Path(source_file)
        file_name = source_path.stem
        parent = source_path.parent

        if self.project_type == "java":
            # Maven/Gradle 标准结构
            # 提取包路径（去掉 src/main/java 前缀）
            parent_str = str(parent)
            # 直接使用空字符串作为父路径，因为测试文件直接在 src/test/java 下
            parent_str = ""
            
            test_paths = [
                f"src/test/java/{file_name}Test.java",
                f"src/test/java/Test{file_name}.java",
                f"src/test/java/{file_name}Tests.java",
            ]
        elif self.project_type in ["vue", "react", "typescript"]:
            # 前端项目结构
            test_paths = [
                f"{parent}/{file_name}.test.ts",
                f"{parent}/{file_name}.spec.ts",
                f"{parent}/__tests__/{file_name}.test.ts",
                f"tests/{parent}/{file_name}.test.ts",
            ]
        else:
            return None

        for test_path in test_paths:
            if (self.project_path / test_path).exists():
                return test_path

        # 返回默认路径
        return test_paths[0] if test_paths else None

    def create_mapping(
        self, source_file: str, test_file: str, source_content: str, test_content: str
    ) -> TestMapping:
        """创建映射关系.

        Args:
            source_file: 源文件路径
            test_file: 测试文件路径
            source_content: 源文件内容
            test_content: 测试文件内容

        Returns:
            映射信息
        """
        # 分析方法映射
        method_mappings = self._extract_method_mappings(test_content)

        # 检测手工修改
        has_manual, manual_sections = self._detect_manual_changes(test_content)

        mapping = TestMapping(
            source_file=source_file,
            test_file=test_file,
            method_mappings=method_mappings,
            last_generated=datetime.now(),
            source_hash=self._compute_hash(source_content),
            test_hash=self._compute_hash(test_content),
            has_manual_changes=has_manual,
            manual_sections=manual_sections,
        )

        self.mappings[source_file] = mapping
        self._save_mappings()

        return mapping

    def _extract_method_mappings(self, test_content: str) -> Dict[str, str]:
        """提取方法映射关系.

        Args:
            test_content: 测试文件内容

        Returns:
            方法映射字典 {源方法名: 测试方法名}
        """
        mappings = {}

        if self.project_type == "java":
            # 匹配 @Test 方法
            pattern = re.compile(
                r"@Test\s+(?:@\w+\s+)*"
                r"(?:public\s+)?void\s+(\w+)\s*\(",
                re.MULTILINE,
            )
            for match in pattern.finditer(test_content):
                test_method = match.group(1)
                # 推断源方法名 (去掉Test前缀/后缀)
                source_method = self._infer_source_method(test_method)
                if source_method:
                    mappings[source_method] = test_method

        elif self.project_type in ["vue", "react", "typescript"]:
            # 匹配 test/it 调用
            pattern = re.compile(
                r"(?:test|it)\s*\(\s*['\"]([^'\"]+)['\"]", re.MULTILINE
            )
            for match in pattern.finditer(test_content):
                test_desc = match.group(1)
                # 从描述推断方法名
                source_method = self._extract_method_from_desc(test_desc)
                if source_method:
                    mappings[source_method] = test_desc

        return mappings

    def _infer_source_method(self, test_method: str) -> Optional[str]:
        """从测试方法名推断源方法名.

        Args:
            test_method: 测试方法名

        Returns:
            源方法名
        """
        # 去掉常见的测试前缀/后缀
        prefixes = ["test", "should"]
        suffixes = ["Test", "Tests"]

        result = test_method
        
        # 先检查前缀
        for prefix in prefixes:
            if result.lower().startswith(prefix.lower()):
                result = result[len(prefix):]
                break
        
        # 再检查后缀
        for suffix in suffixes:
            if result.endswith(suffix):
                result = result[:-len(suffix)]
                break

        # 首字母小写
        if result:
            result = result[0].lower() + result[1:]

        return result if result else None

    def _extract_method_from_desc(self, test_desc: str) -> Optional[str]:
        """从测试描述中提取方法名.

        Args:
            test_desc: 测试描述

        Returns:
            方法名
        """
        # 常见模式: "should do something when methodName called"
        patterns = [
            r"when\s+(\w+)\s+called",
            r"(\w+)\s+should",
            r"should\s+\w+\s+(\w+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, test_desc, re.IGNORECASE)
            if match:
                return match.group(1)

        # 返回第一个单词
        words = test_desc.split()
        return words[0] if words else None

    def _detect_manual_changes(self, test_content: str) -> Tuple[bool, List[Tuple[int, int]]]:
        """检测手工修改.

        Args:
            test_content: 测试文件内容

        Returns:
            (是否有手工修改, 手工修改区域列表)
        """
        has_manual = self.MANUAL_MARKER in test_content
        manual_sections = []

        lines = test_content.split("\n")
        in_manual_section = False
        section_start = 0

        for i, line in enumerate(lines, 1):
            if self.MANUAL_MARKER in line:
                if not in_manual_section:
                    in_manual_section = True
                    section_start = i
                else:
                    manual_sections.append((section_start, i))
                    in_manual_section = False

        return has_manual, manual_sections

    def update_mapping(
        self,
        source_file: str,
        new_source_content: str,
        new_test_content: str,
        added_methods: List[MethodInfo],
        modified_methods: List[Tuple[MethodInfo, MethodInfo]],
        deleted_methods: List[MethodInfo],
    ) -> Tuple[str, List[str]]:
        """更新映射关系并合并测试.

        Args:
            source_file: 源文件路径
            new_source_content: 新源文件内容
            new_test_content: 新生成的测试内容
            added_methods: 新增方法
            modified_methods: 修改的方法
            deleted_methods: 删除的方法

        Returns:
            (合并后的测试内容, 警告信息列表)
        """
        warnings = []

        if source_file not in self.mappings:
            # 新映射
            test_file = self._infer_test_file_path(source_file)
            if test_file:
                self.create_mapping(
                    source_file, test_file, new_source_content, new_test_content
                )
            return new_test_content, warnings

        mapping = self.mappings[source_file]
        existing_test_path = self.project_path / mapping.test_file

        if not existing_test_path.exists():
            # 测试文件不存在，使用新生成的
            self.create_mapping(
                source_file, mapping.test_file, new_source_content, new_test_content
            )
            return new_test_content, warnings

        # 读取现有测试内容
        try:
            with open(existing_test_path, "r", encoding="utf-8") as f:
                existing_content = f.read()
        except Exception as e:
            warnings.append(f"读取现有测试文件失败: {e}")
            return new_test_content, warnings

        # 检查源文件是否有变化
        new_source_hash = self._compute_hash(new_source_content)
        if new_source_hash == mapping.source_hash:
            # 源文件未变化，跳过
            return existing_content, warnings

        # 合并测试
        merged_content = self._merge_tests(
            existing_content,
            new_test_content,
            mapping,
            added_methods,
            modified_methods,
            deleted_methods,
        )

        # 更新映射
        mapping.source_hash = new_source_hash
        mapping.test_hash = self._compute_hash(merged_content)
        mapping.last_generated = datetime.now()
        mapping.method_mappings = self._extract_method_mappings(merged_content)
        has_manual, manual_sections = self._detect_manual_changes(merged_content)
        mapping.has_manual_changes = has_manual
        mapping.manual_sections = manual_sections

        # 保存合并后的测试文件
        try:
            with open(existing_test_path, "w", encoding="utf-8") as f:
                f.write(merged_content)
        except Exception as e:
            warnings.append(f"保存测试文件失败: {e}")

        self._save_mappings()

        return merged_content, warnings

    def _merge_tests(
        self,
        existing_content: str,
        new_content: str,
        mapping: TestMapping,
        added_methods: List[MethodInfo],
        modified_methods: List[Tuple[MethodInfo, MethodInfo]],
        deleted_methods: List[MethodInfo],
    ) -> str:
        """合并测试内容.

        Args:
            existing_content: 现有测试内容
            new_content: 新生成的测试内容
            mapping: 映射信息
            added_methods: 新增方法
            modified_methods: 修改的方法
            deleted_methods: 删除的方法

        Returns:
            合并后的内容
        """
        result_lines = existing_content.split("\n")

        # 处理删除的方法 - 标记为废弃
        for method in deleted_methods:
            test_method = mapping.method_mappings.get(method.name)
            if test_method:
                self._mark_test_deprecated(result_lines, test_method)

        # 处理修改的方法 - 如果未手工修改则更新
        for old_method, new_method in modified_methods:
            test_method = mapping.method_mappings.get(old_method.name)
            if test_method:
                if not self._is_test_manually_modified(
                    existing_content, test_method
                ):
                    # 替换测试方法
                    new_test_method = self._extract_test_method(
                        new_content, test_method
                    )
                    if new_test_method:
                        result_lines = self._replace_test_method(
                            result_lines, test_method, new_test_method
                        )

        # 处理新增的方法 - 追加到文件
        for method in added_methods:
            # 尝试提取测试方法
            new_test_method = self._extract_test_method_for_source_method(
                new_content, method.name
            )
            if new_test_method:
                result_lines.extend(["", ""])  # 空行
                result_lines.extend(new_test_method.split("\n"))
            else:
                # 如果提取失败，直接从新测试内容中查找
                if "test" + method.name.capitalize() in new_content:
                    # 简单处理：直接追加新测试内容的相关部分
                    lines = new_content.split("\n")
                    in_method = False
                    method_lines = []
                    for line in lines:
                        if "test" + method.name.capitalize() in line:
                            in_method = True
                        if in_method:
                            method_lines.append(line)
                            if "}" in line and len(method_lines) > 1:
                                break
                    if method_lines:
                        result_lines.extend(["", ""])
                        result_lines.extend(method_lines)

        return "\n".join(result_lines)

    def _mark_test_deprecated(self, lines: List[str], test_method: str) -> None:
        """标记测试为废弃.

        Args:
            lines: 代码行列表
            test_method: 测试方法名
        """
        method_pattern = re.compile(
            rf"(@Test\s+)?(?:public\s+)?void\s+{re.escape(test_method)}\s*\("
        )

        for i, line in enumerate(lines):
            if method_pattern.search(line):
                # 在方法前添加@Deprecated注释
                lines.insert(i, "@Deprecated // 对应的方法已被删除")
                break

    def _is_test_manually_modified(
        self, test_content: str, test_method: str
    ) -> bool:
        """检查测试方法是否被手工修改.

        Args:
            test_content: 测试内容
            test_method: 测试方法名

        Returns:
            是否手工修改
        """
        # 检查整个测试文件是否有手工标记
        if self.MANUAL_MARKER in test_content:
            return True
        
        # 提取测试方法内容并检查
        method_content = self._extract_test_method(test_content, test_method)
        if not method_content:
            return False

        # 检查是否有手工标记
        return self.MANUAL_MARKER in method_content

    def _extract_test_method(self, test_content: str, test_method: str) -> Optional[str]:
        """提取测试方法内容.

        Args:
            test_content: 测试内容
            test_method: 测试方法名

        Returns:
            方法内容
        """
        lines = test_content.split("\n")

        # 查找方法开始
        start_idx = -1
        method_pattern = re.compile(
            rf"(@Test\s+)?(?:public\s+)?void\s+{re.escape(test_method)}\s*\("
        )

        for i, line in enumerate(lines):
            if method_pattern.search(line):
                start_idx = i
                break

        if start_idx == -1:
            return None

        # 查找方法结束
        brace_count = 0
        end_idx = start_idx

        for i in range(start_idx, len(lines)):
            line = lines[i]
            brace_count += line.count("{") - line.count("}")
            if brace_count == 0 and "{" in lines[start_idx]:
                end_idx = i
                break

        return "\n".join(lines[start_idx : end_idx + 1])

    def _extract_test_method_for_source_method(
        self, test_content: str, source_method: str
    ) -> Optional[str]:
        """根据源方法名提取测试方法.

        Args:
            test_content: 测试内容
            source_method: 源方法名

        Returns:
            测试方法内容
        """
        # 推断可能的测试方法名
        possible_names = [
            f"test{source_method.capitalize()}",
            f"{source_method}Test",
            f"should{source_method.capitalize()}",
            f"test_{source_method}",
        ]

        for name in possible_names:
            content = self._extract_test_method(test_content, name)
            if content:
                return content

        return None

    def _replace_test_method(
        self,
        lines: List[str],
        test_method: str,
        new_method_content: str,
    ) -> List[str]:
        """替换测试方法.

        Args:
            lines: 代码行列表
            test_method: 测试方法名
            new_method_content: 新方法内容

        Returns:
            更新后的代码行列表
        """
        # 查找方法范围
        start_idx = -1
        end_idx = -1
        brace_count = 0

        method_pattern = re.compile(
            rf"(@Test\s+)?(?:public\s+)?void\s+{re.escape(test_method)}\s*\("
        )

        for i, line in enumerate(lines):
            if start_idx == -1 and method_pattern.search(line):
                start_idx = i

            if start_idx != -1:
                brace_count += line.count("{") - line.count("}")
                if brace_count == 0 and "{" in lines[start_idx]:
                    end_idx = i
                    break

        if start_idx == -1 or end_idx == -1:
            return lines

        # 替换方法
        new_lines = new_method_content.split("\n")
        return lines[:start_idx] + new_lines + lines[end_idx + 1 :]

    def get_affected_tests(
        self, source_file: str, changed_methods: List[str]
    ) -> List[str]:
        """获取受影响的测试方法.

        Args:
            source_file: 源文件路径
            changed_methods: 变更的方法列表

        Returns:
            受影响的测试方法名列表
        """
        if source_file not in self.mappings:
            return []

        mapping = self.mappings[source_file]
        affected_tests = []

        for method in changed_methods:
            if method in mapping.method_mappings:
                affected_tests.append(mapping.method_mappings[method])

        return affected_tests

    def get_mapping_summary(self) -> Dict[str, any]:
        """获取映射摘要.

        Returns:
            摘要信息
        """
        total_mappings = len(self.mappings)
        with_manual_changes = sum(
            1 for m in self.mappings.values() if m.has_manual_changes
        )
        total_methods = sum(
            len(m.method_mappings) for m in self.mappings.values()
        )

        return {
            "total_source_files": total_mappings,
            "with_manual_changes": with_manual_changes,
            "total_mapped_methods": total_methods,
            "last_updated": max(
                (m.last_generated for m in self.mappings.values()),
                default=None,
            ),
        }
