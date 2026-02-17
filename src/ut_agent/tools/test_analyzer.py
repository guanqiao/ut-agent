"""测试分析模块 - 分析已有测试覆盖情况."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any


@dataclass
class TestMethodInfo:
    """测试方法信息."""

    name: str
    description: str
    line_start: int
    line_end: int
    content: str
    tested_methods: List[str] = field(default_factory=list)
    test_scenarios: List[str] = field(default_factory=list)
    is_manual: bool = False
    annotations: List[str] = field(default_factory=list)
    mock_configurations: List[str] = field(default_factory=list)
    assertions: List[str] = field(default_factory=list)


@dataclass
class TestCoverageInfo:
    """测试覆盖信息."""

    test_file: str
    source_file: str
    tested_methods: Dict[str, List[str]] = field(default_factory=dict)
    untested_methods: List[str] = field(default_factory=list)
    test_scenarios: Dict[str, List[str]] = field(default_factory=dict)
    manual_tests: List[str] = field(default_factory=list)
    auto_generated_tests: List[str] = field(default_factory=list)
    reusable_mocks: Dict[str, List[str]] = field(default_factory=dict)
    reusable_assertions: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class TestGap:
    """测试缺口."""

    method_name: str
    gap_type: str
    suggested_scenarios: List[str] = field(default_factory=list)
    priority: int = 0
    similar_tests: List[str] = field(default_factory=list)


@dataclass
class MethodDependency:
    """方法依赖关系."""

    method_name: str
    called_methods: List[str] = field(default_factory=list)
    called_by: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)


@dataclass
class IncrementalTestPlan:
    """增量测试计划."""

    direct_changes: List[str] = field(default_factory=list)
    affected_methods: List[str] = field(default_factory=list)
    reuse_candidates: Dict[str, List[str]] = field(default_factory=dict)
    gaps_to_fill: List[TestGap] = field(default_factory=list)
    estimated_effort: int = 0


class TestAnalyzer:
    """测试分析器."""

    JAVA_TEST_PATTERN = re.compile(
        r"@(Test|ParameterizedTest|RepeatedTest|TestFactory)\s+"
        r"(?:@[\w]+\s+)*"
        r"(?:public\s+)?void\s+(\w+)\s*\([^)]*\)",
        re.MULTILINE,
    )

    JAVA_DISPLAY_NAME_PATTERN = re.compile(
        r"@DisplayName\s*\(\s*[\"']([^\"']+)[\"']\s*\)"
    )

    JAVA_METHOD_CALL_PATTERN = re.compile(
        r"(?:target|underTest|sut|classUnderTest)\s*\.\s*(\w+)\s*\("
    )

    TYPESCRIPT_TEST_PATTERN = re.compile(
        r"(?:test|it)\s*\(\s*['\"]([^'\"]+)['\"]\s*,",
        re.MULTILINE,
    )

    TYPESCRIPT_DESCRIBE_PATTERN = re.compile(
        r"describe\s*\(\s*['\"]([^'\"]+)['\"]\s*,",
        re.MULTILINE,
    )

    MANUAL_MARKER = "// MANUAL"
    AUTO_GENERATED_MARKER = "// AUTO-GENERATED"

    def __init__(self, project_type: str):
        """初始化分析器.

        Args:
            project_type: 项目类型 (java/typescript/vue/react)
        """
        self.project_type = project_type

    def analyze_existing_tests(
        self,
        test_file_path: str,
        source_methods: List[str],
    ) -> TestCoverageInfo:
        """分析已有测试文件.

        Args:
            test_file_path: 测试文件路径
            source_methods: 源文件方法列表

        Returns:
            测试覆盖信息
        """
        path = Path(test_file_path)
        if not path.exists():
            return TestCoverageInfo(
                test_file=test_file_path,
                source_file="",
                untested_methods=source_methods,
            )

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return TestCoverageInfo(
                test_file=test_file_path,
                source_file="",
                untested_methods=source_methods,
            )

        test_methods = self._extract_test_methods(content)
        
        tested_methods: Dict[str, List[str]] = {}
        test_scenarios: Dict[str, List[str]] = {}
        manual_tests = []
        auto_generated_tests = []

        for test in test_methods:
            if test.is_manual:
                manual_tests.append(test.name)
            else:
                auto_generated_tests.append(test.name)

            for method in test.tested_methods:
                if method not in tested_methods:
                    tested_methods[method] = []
                tested_methods[method].append(test.name)

                if method not in test_scenarios:
                    test_scenarios[method] = []
                test_scenarios[method].extend(test.test_scenarios)

        untested = [m for m in source_methods if m not in tested_methods]

        reusable_mocks = self._extract_reusable_mocks(test_methods)
        reusable_assertions = self._extract_reusable_assertions(test_methods)

        return TestCoverageInfo(
            test_file=test_file_path,
            source_file="",
            tested_methods=tested_methods,
            untested_methods=untested,
            test_scenarios=test_scenarios,
            manual_tests=manual_tests,
            auto_generated_tests=auto_generated_tests,
            reusable_mocks=reusable_mocks,
            reusable_assertions=reusable_assertions,
        )

    def identify_test_gaps(
        self,
        coverage_info: TestCoverageInfo,
        method_info: Dict[str, Any],
    ) -> List[TestGap]:
        """识别测试缺口.

        Args:
            coverage_info: 测试覆盖信息
            method_info: 方法信息字典

        Returns:
            测试缺口列表
        """
        gaps = []

        for method_name in coverage_info.untested_methods:
            info = method_info.get(method_name, {})
            gap = TestGap(
                method_name=method_name,
                gap_type="no_test",
                suggested_scenarios=self._suggest_scenarios(info),
                priority=self._calculate_priority(info),
            )
            gaps.append(gap)

        for method_name, scenarios in coverage_info.test_scenarios.items():
            info = method_info.get(method_name, {})
            missing = self._identify_missing_scenarios(scenarios, info)
            if missing:
                gap = TestGap(
                    method_name=method_name,
                    gap_type="incomplete_coverage",
                    suggested_scenarios=missing,
                    priority=self._calculate_priority(info) - 1,
                )
                gaps.append(gap)

        gaps.sort(key=lambda g: g.priority, reverse=True)
        return gaps

    def extract_test_patterns(self, test_content: str) -> Dict[str, Any]:
        """提取测试模式和风格.

        Args:
            test_content: 测试文件内容

        Returns:
            测试模式信息
        """
        patterns = {
            "naming_convention": self._extract_naming_convention(test_content),
            "assertion_style": self._extract_assertion_style(test_content),
            "mock_style": self._extract_mock_style(test_content),
            "structure": self._extract_structure(test_content),
        }
        return patterns

    def _extract_test_methods(self, content: str) -> List[TestMethodInfo]:
        """提取测试方法.

        Args:
            content: 测试文件内容

        Returns:
            测试方法列表
        """
        if self.project_type == "java":
            return self._extract_java_test_methods(content)
        else:
            return self._extract_typescript_test_methods(content)

    def _extract_java_test_methods(self, content: str) -> List[TestMethodInfo]:
        """提取 Java 测试方法."""
        methods = []
        lines = content.split("\n")

        for match in self.JAVA_TEST_PATTERN.finditer(content):
            test_name = match.group(2)
            line_start = content[: match.start()].count("\n") + 1

            line_end = self._find_method_end(lines, line_start - 1)
            method_content = "\n".join(lines[line_start - 1 : line_end])

            display_name = ""
            dn_match = self.JAVA_DISPLAY_NAME_PATTERN.search(method_content)
            if dn_match:
                display_name = dn_match.group(1)

            tested_methods = list(set(
                m.group(1) for m in self.JAVA_METHOD_CALL_PATTERN.finditer(method_content)
            ))

            is_manual = self.MANUAL_MARKER in method_content

            scenarios = self._extract_scenarios_from_name(test_name, display_name)

            annotations = self._extract_annotations(method_content)

            methods.append(
                TestMethodInfo(
                    name=test_name,
                    description=display_name,
                    line_start=line_start,
                    line_end=line_end,
                    content=method_content,
                    tested_methods=tested_methods,
                    test_scenarios=scenarios,
                    is_manual=is_manual,
                    annotations=annotations,
                )
            )

        return methods

    def _extract_typescript_test_methods(self, content: str) -> List[TestMethodInfo]:
        """提取 TypeScript 测试方法."""
        methods = []
        lines = content.split("\n")

        current_describe = ""
        for match in self.TYPESCRIPT_DESCRIBE_PATTERN.finditer(content):
            current_describe = match.group(1)

        for match in self.TYPESCRIPT_TEST_PATTERN.finditer(content):
            test_desc = match.group(1)
            line_start = content[: match.start()].count("\n") + 1

            line_end = self._find_typescript_test_end(lines, line_start - 1)
            method_content = "\n".join(lines[line_start - 1 : line_end])

            tested_methods = self._extract_tested_methods_from_desc(test_desc, current_describe)

            is_manual = self.MANUAL_MARKER in method_content

            scenarios = self._extract_scenarios_from_ts_desc(test_desc)

            methods.append(
                TestMethodInfo(
                    name=test_desc,
                    description=test_desc,
                    line_start=line_start,
                    line_end=line_end,
                    content=method_content,
                    tested_methods=tested_methods,
                    test_scenarios=scenarios,
                    is_manual=is_manual,
                )
            )

        return methods

    def _find_method_end(self, lines: List[str], start_idx: int) -> int:
        """查找 Java 方法结束位置."""
        brace_count = 0
        for i in range(start_idx, len(lines)):
            line = lines[i]
            brace_count += line.count("{") - line.count("}")
            if brace_count == 0 and "{" in "\n".join(lines[start_idx:i+1]):
                return i + 1
        return len(lines)

    def _find_typescript_test_end(self, lines: List[str], start_idx: int) -> int:
        """查找 TypeScript 测试结束位置."""
        brace_count = 0
        paren_count = 0
        in_test = False

        for i in range(start_idx, len(lines)):
            line = lines[i]

            if not in_test and ("{" in line or "=>" in line):
                in_test = True

            if in_test:
                brace_count += line.count("{") - line.count("}")
                paren_count += line.count("(") - line.count(")")

                if brace_count == 0 and paren_count <= 0:
                    return i + 1

        return len(lines)

    def _extract_scenarios_from_name(
        self, test_name: str, display_name: str
    ) -> List[str]:
        """从测试名称提取场景."""
        scenarios = []

        name_lower = test_name.lower()
        desc_lower = display_name.lower() if display_name else ""

        scenario_keywords = {
            "success": ["success", "valid", "normal", "happy"],
            "failure": ["fail", "error", "invalid", "exception"],
            "boundary": ["boundary", "edge", "limit", "max", "min"],
            "null": ["null", "empty", "blank"],
            "negative": ["negative", "invalid"],
        }

        combined = f"{name_lower} {desc_lower}"
        for scenario, keywords in scenario_keywords.items():
            if any(kw in combined for kw in keywords):
                scenarios.append(scenario)

        return scenarios if scenarios else ["unknown"]

    def _extract_scenarios_from_ts_desc(self, desc: str) -> List[str]:
        """从 TypeScript 测试描述提取场景."""
        scenarios = []
        desc_lower = desc.lower()

        scenario_keywords = {
            "success": ["should succeed", "should work", "should return", "valid"],
            "failure": ["should fail", "should throw", "error", "invalid"],
            "boundary": ["boundary", "edge case", "empty", "null", "undefined"],
        }

        for scenario, keywords in scenario_keywords.items():
            if any(kw in desc_lower for kw in keywords):
                scenarios.append(scenario)

        return scenarios if scenarios else ["unknown"]

    def _extract_tested_methods_from_desc(
        self, test_desc: str, describe_block: str
    ) -> List[str]:
        """从测试描述提取被测方法名."""
        methods = []

        patterns = [
            r"(\w+)\s+should",
            r"should\s+\w+\s+(\w+)",
            r"when\s+(\w+)",
            r"tests?\s+(\w+)",
        ]

        combined = f"{test_desc} {describe_block}"
        for pattern in patterns:
            match = re.search(pattern, combined, re.IGNORECASE)
            if match:
                methods.append(match.group(1))

        return methods

    def _extract_annotations(self, method_content: str) -> List[str]:
        """提取方法注解."""
        annotations = []
        pattern = re.compile(r"@(\w+)")
        for match in pattern.finditer(method_content):
            annotations.append(match.group(1))
        return annotations

    def _suggest_scenarios(self, method_info: Dict[str, Any]) -> List[str]:
        """建议测试场景."""
        scenarios = ["success"]

        return_type = method_info.get("return_type", "void")
        params = method_info.get("parameters", [])

        if params:
            scenarios.append("boundary")
            scenarios.append("invalid_input")

        if return_type != "void":
            scenarios.append("return_value_check")

        if any("optional" in str(p).lower() or "null" in str(p).lower() for p in params):
            scenarios.append("null_handling")

        return scenarios

    def _calculate_priority(self, method_info: Dict[str, Any]) -> int:
        """计算测试优先级."""
        priority = 5

        modifiers = method_info.get("modifiers", [])
        if "public" in modifiers:
            priority += 2
        if "static" in modifiers:
            priority -= 1

        return_type = method_info.get("return_type", "void")
        if return_type != "void":
            priority += 1

        params = method_info.get("parameters", [])
        priority += min(len(params), 3)

        return min(priority, 10)

    def _identify_missing_scenarios(
        self, existing_scenarios: List[str], method_info: Dict[str, Any]
    ) -> List[str]:
        """识别缺失的测试场景."""
        suggested = self._suggest_scenarios(method_info)
        existing_set = set(s.lower() for s in existing_scenarios)
        missing = [s for s in suggested if s.lower() not in existing_set]
        return missing

    def _extract_naming_convention(self, content: str) -> str:
        """提取命名约定."""
        if self.project_type == "java":
            if "given_" in content.lower():
                return "given_when_then"
            elif "should" in content.lower():
                return "should_style"
            else:
                return "test_prefix"
        else:
            if "should" in content.lower():
                return "should_style"
            else:
                return "describe_it"

    def _extract_assertion_style(self, content: str) -> str:
        """提取断言风格."""
        if self.project_type == "java":
            if "assertThat" in content:
                return "assertj"
            elif "Assertions." in content:
                return "junit5"
            else:
                return "junit4"
        else:
            if "expect(" in content:
                return "jest_vitest"
            else:
                return "assert"

    def _extract_mock_style(self, content: str) -> str:
        """提取 Mock 风格."""
        if self.project_type == "java":
            if "@Mock" in content:
                return "mockito_annotation"
            elif "Mockito." in content:
                return "mockito_static"
            else:
                return "none"
        else:
            if "vi.fn()" in content:
                return "vitest"
            elif "jest.fn()" in content:
                return "jest"
            else:
                return "none"

    def _extract_structure(self, content: str) -> str:
        """提取测试结构."""
        if "Arrange" in content or "Given" in content:
            return "aaa_pattern"
        elif "@BeforeEach" in content or "beforeEach" in content:
            return "with_setup"
        else:
            return "simple"

    def _extract_reusable_mocks(
        self, test_methods: List[TestMethodInfo]
    ) -> Dict[str, List[str]]:
        """提取可复用的 Mock 配置.

        Args:
            test_methods: 测试方法列表

        Returns:
            按方法分组的 Mock 配置
        """
        mocks: Dict[str, List[str]] = {}
        
        if self.project_type == "java":
            mock_pattern = re.compile(
                r"when\s*\(\s*(\w+)\s*\.\s*(\w+)\s*\(\s*\)\s*\)\s*\.\s*thenReturn\s*\(([^)]+)\)"
            )
            for test in test_methods:
                for method in test.tested_methods:
                    if method not in mocks:
                        mocks[method] = []
                    for match in mock_pattern.finditer(test.content):
                        mock_config = f"when({match.group(1)}.{match.group(2)}()).thenReturn({match.group(3)})"
                        if mock_config not in mocks[method]:
                            mocks[method].append(mock_config)
        else:
            mock_pattern = re.compile(
                r"(?:vi|jest)\.fn\s*\(\s*\)\s*\.mockReturnValue\s*\(([^)]+)\)"
            )
            for test in test_methods:
                for method in test.tested_methods:
                    if method not in mocks:
                        mocks[method] = []
                    for match in mock_pattern.finditer(test.content):
                        mock_config = f"mockReturnValue({match.group(1)})"
                        if mock_config not in mocks[method]:
                            mocks[method].append(mock_config)

        return mocks

    def _extract_reusable_assertions(
        self, test_methods: List[TestMethodInfo]
    ) -> Dict[str, List[str]]:
        """提取可复用的断言模式.

        Args:
            test_methods: 测试方法列表

        Returns:
            按方法分组的断言模式
        """
        assertions: Dict[str, List[str]] = {}
        
        if self.project_type == "java":
            assertion_patterns = [
                (re.compile(r"assertThat\s*\(\s*result\s*\)\.(\w+)\s*\(([^)]*)\)"), "assertj"),
                (re.compile(r"assertEquals\s*\(\s*([^,]+)\s*,\s*result\s*\)"), "junit"),
                (re.compile(r"assertNotNull\s*\(\s*result\s*\)"), "junit"),
            ]
        else:
            assertion_patterns = [
                (re.compile(r"expect\s*\(\s*result\s*\)\.(\w+)\s*\(([^)]*)\)"), "vitest"),
                (re.compile(r"expect\s*\(\s*result\s*\)\.toBeDefined\s*\(\s*\)"), "vitest"),
            ]

        for test in test_methods:
            for method in test.tested_methods:
                if method not in assertions:
                    assertions[method] = []
                for pattern, _ in assertion_patterns:
                    for match in pattern.finditer(test.content):
                        assertion = match.group(0)
                        if assertion not in assertions[method]:
                            assertions[method].append(assertion)

        return assertions

    def create_incremental_plan(
        self,
        coverage_info: TestCoverageInfo,
        changed_methods: List[str],
        method_dependencies: Optional[Dict[str, MethodDependency]] = None,
    ) -> IncrementalTestPlan:
        """创建增量测试计划.

        Args:
            coverage_info: 测试覆盖信息
            changed_methods: 变更的方法列表
            method_dependencies: 方法依赖关系

        Returns:
            增量测试计划
        """
        direct_changes = []
        affected_methods = []
        reuse_candidates: Dict[str, List[str]] = {}
        gaps_to_fill: List[TestGap] = []

        for method in changed_methods:
            if method in coverage_info.untested_methods:
                direct_changes.append(method)
            elif method in coverage_info.tested_methods:
                affected_methods.append(method)

        if method_dependencies:
            for method in changed_methods:
                dep = method_dependencies.get(method)
                if dep:
                    for called in dep.called_methods:
                        if called not in affected_methods and called not in direct_changes:
                            affected_methods.append(called)

        for method in direct_changes:
            if method in coverage_info.reusable_mocks:
                reuse_candidates[f"{method}_mocks"] = coverage_info.reusable_mocks[method]
            if method in coverage_info.reusable_assertions:
                reuse_candidates[f"{method}_assertions"] = coverage_info.reusable_assertions[method]

        for method in direct_changes:
            gap = TestGap(
                method_name=method,
                gap_type="no_test",
                suggested_scenarios=["success", "failure", "boundary"],
                priority=8,
                similar_tests=self._find_similar_tests(method, coverage_info),
            )
            gaps_to_fill.append(gap)

        for method in affected_methods:
            if method in coverage_info.test_scenarios:
                scenarios = coverage_info.test_scenarios[method]
                if len(scenarios) < 2:
                    gap = TestGap(
                        method_name=method,
                        gap_type="incomplete_coverage",
                        suggested_scenarios=["failure", "boundary"],
                        priority=5,
                        similar_tests=coverage_info.tested_methods.get(method, []),
                    )
                    gaps_to_fill.append(gap)

        gaps_to_fill.sort(key=lambda g: g.priority, reverse=True)

        estimated_effort = len(direct_changes) * 3 + len(affected_methods) * 1

        return IncrementalTestPlan(
            direct_changes=direct_changes,
            affected_methods=affected_methods,
            reuse_candidates=reuse_candidates,
            gaps_to_fill=gaps_to_fill,
            estimated_effort=estimated_effort,
        )

    def _find_similar_tests(
        self, method_name: str, coverage_info: TestCoverageInfo
    ) -> List[str]:
        """查找相似方法的测试.

        Args:
            method_name: 方法名
            coverage_info: 覆盖信息

        Returns:
            相似测试列表
        """
        similar = []
        
        method_lower = method_name.lower()
        
        for tested_method, tests in coverage_info.tested_methods.items():
            if tested_method.lower() == method_lower:
                similar.extend(tests)
            elif any(word in tested_method.lower() for word in method_lower.split("_")):
                similar.extend(tests[:1])

        return list(set(similar))[:3]

    def analyze_method_similarity(
        self, method1: Dict[str, Any], method2: Dict[str, Any]
    ) -> float:
        """分析方法相似度.

        Args:
            method1: 方法1信息
            method2: 方法2信息

        Returns:
            相似度分数 (0-1)
        """
        score = 0.0

        if method1.get("return_type") == method2.get("return_type"):
            score += 0.3

        params1 = set(p.get("type", "") for p in method1.get("parameters", []))
        params2 = set(p.get("type", "") for p in method2.get("parameters", []))
        if params1 and params2:
            intersection = len(params1 & params2)
            union = len(params1 | params2)
            score += 0.3 * (intersection / union if union > 0 else 0)

        if method1.get("is_public") == method2.get("is_public"):
            score += 0.1

        if method1.get("is_static") == method2.get("is_static"):
            score += 0.1

        name1 = method1.get("name", "").lower()
        name2 = method2.get("name", "").lower()
        common_prefix = 0
        for i, (c1, c2) in enumerate(zip(name1, name2)):
            if c1 == c2:
                common_prefix += 1
            else:
                break
        score += 0.2 * (common_prefix / max(len(name1), len(name2), 1))

        return min(score, 1.0)

    def suggest_test_reuse(
        self,
        new_method: Dict[str, Any],
        existing_tests: List[TestMethodInfo],
        threshold: float = 0.6,
    ) -> List[Tuple[TestMethodInfo, float]]:
        """建议可复用的测试.

        Args:
            new_method: 新方法信息
            existing_tests: 已有测试列表
            threshold: 相似度阈值

        Returns:
            (测试方法, 相似度) 列表
        """
        suggestions = []

        for test in existing_tests:
            for tested_method in test.tested_methods:
                similarity = self.analyze_method_similarity(
                    new_method,
                    {"name": tested_method, "parameters": [], "return_type": "void"},
                )
                if similarity >= threshold:
                    suggestions.append((test, similarity))

        suggestions.sort(key=lambda x: x[1], reverse=True)
        return suggestions[:3]


def format_existing_tests_for_prompt(
    coverage_info: TestCoverageInfo,
    max_tests: int = 5,
) -> str:
    """格式化已有测试信息用于 Prompt.

    Args:
        coverage_info: 测试覆盖信息
        max_tests: 最大显示测试数

    Returns:
        格式化的字符串
    """
    sections = []

    if coverage_info.tested_methods:
        sections.append("已覆盖的方法:")
        for method, tests in list(coverage_info.tested_methods.items())[:max_tests]:
            sections.append(f"  - {method}: {', '.join(tests[:3])}")

    if coverage_info.untested_methods:
        sections.append("\n未覆盖的方法:")
        for method in coverage_info.untested_methods[:max_tests]:
            sections.append(f"  - {method}")

    if coverage_info.manual_tests:
        sections.append("\n手工编写的测试 (请保留):")
        for test in coverage_info.manual_tests[:max_tests]:
            sections.append(f"  - {test}")

    if coverage_info.reusable_mocks:
        sections.append("\n可复用的 Mock 配置:")
        for method, mocks in list(coverage_info.reusable_mocks.items())[:3]:
            sections.append(f"  - {method}:")
            for mock in mocks[:2]:
                sections.append(f"      {mock}")

    if coverage_info.reusable_assertions:
        sections.append("\n可复用的断言模式:")
        for method, asserts in list(coverage_info.reusable_assertions.items())[:3]:
            sections.append(f"  - {method}:")
            for assertion in asserts[:2]:
                sections.append(f"      {assertion}")

    return "\n".join(sections) if sections else "无已有测试"


def format_test_gaps_for_prompt(gaps: List[TestGap]) -> str:
    """格式化测试缺口用于 Prompt.

    Args:
        gaps: 测试缺口列表

    Returns:
        格式化的字符串
    """
    if not gaps:
        return "无测试缺口"

    sections = ["需要补充的测试:"]
    for gap in gaps[:10]:
        scenarios = ", ".join(gap.suggested_scenarios[:3])
        similar = f" (参考: {', '.join(gap.similar_tests[:2])})" if gap.similar_tests else ""
        sections.append(
            f"  - {gap.method_name} ({gap.gap_type}): 建议场景 [{scenarios}]{similar}"
        )

    return "\n".join(sections)


def format_incremental_plan_for_prompt(plan: IncrementalTestPlan) -> str:
    """格式化增量测试计划用于 Prompt.

    Args:
        plan: 增量测试计划

    Returns:
        格式化的字符串
    """
    sections = []

    if plan.direct_changes:
        sections.append("需要新增测试的方法 (直接变更):")
        for method in plan.direct_changes:
            sections.append(f"  - {method}")

    if plan.affected_methods:
        sections.append("\n可能需要更新测试的方法 (受影响):")
        for method in plan.affected_methods:
            sections.append(f"  - {method}")

    if plan.reuse_candidates:
        sections.append("\n可复用的测试资源:")
        for key, values in plan.reuse_candidates.items():
            sections.append(f"  - {key}:")
            for value in values[:2]:
                sections.append(f"      {value}")

    if plan.gaps_to_fill:
        sections.append("\n测试缺口:")
        for gap in plan.gaps_to_fill[:5]:
            sections.append(f"  - {gap.method_name} ({gap.gap_type})")

    sections.append(f"\n预估工作量: {plan.estimated_effort} 个测试用例")

    return "\n".join(sections) if sections else "无增量测试计划"
