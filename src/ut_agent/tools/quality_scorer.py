"""测试质量评分系统.

评估测试有效性、代码质量和覆盖深度。
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ScoringDimension(Enum):
    """评分维度."""
    EFFECTIVENESS = "effectiveness"
    CODE_QUALITY = "code_quality"
    COVERAGE_DEPTH = "coverage_depth"


@dataclass
class TestEffectivenessScore:
    """测试有效性评分."""
    mutation_kill_rate: float = 0.0
    assertion_density: float = 0.0
    boundary_coverage: float = 0.0
    exception_coverage: float = 0.0
    overall_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mutation_kill_rate": self.mutation_kill_rate,
            "assertion_density": self.assertion_density,
            "boundary_coverage": self.boundary_coverage,
            "exception_coverage": self.exception_coverage,
            "overall_score": round(self.overall_score, 2),
        }


@dataclass
class TestCodeQualityScore:
    """测试代码质量评分."""
    readability: float = 0.0
    maintainability: float = 0.0
    naming_conventions: float = 0.0
    documentation: float = 0.0
    code_duplication: float = 0.0
    overall_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "readability": self.readability,
            "maintainability": self.maintainability,
            "naming_conventions": self.naming_conventions,
            "documentation": self.documentation,
            "code_duplication": self.code_duplication,
            "overall_score": round(self.overall_score, 2),
        }


@dataclass
class CoverageDepthScore:
    """覆盖深度评分."""
    normal_path_coverage: float = 0.0
    boundary_path_coverage: float = 0.0
    exception_path_coverage: float = 0.0
    edge_case_coverage: float = 0.0
    overall_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "normal_path_coverage": self.normal_path_coverage,
            "boundary_path_coverage": self.boundary_path_coverage,
            "exception_path_coverage": self.exception_path_coverage,
            "edge_case_coverage": self.edge_case_coverage,
            "overall_score": round(self.overall_score, 2),
        }


@dataclass
class QualityReport:
    """质量报告."""
    test_file: str
    effectiveness: TestEffectivenessScore
    code_quality: TestCodeQualityScore
    coverage_depth: CoverageDepthScore
    overall_score: float
    grade: str
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_file": self.test_file,
            "effectiveness": self.effectiveness.to_dict(),
            "code_quality": self.code_quality.to_dict(),
            "coverage_depth": self.coverage_depth.to_dict(),
            "overall_score": round(self.overall_score, 2),
            "grade": self.grade,
            "recommendations": self.recommendations,
        }


class TestQualityScorer:
    """测试质量评分器."""

    TEST_METHOD_PATTERN = re.compile(
        r'@Test\s*(?:\([^)]*\))?\s*'
        r'(?:public\s+)?(?:void\s+)?'
        r'(\w+)\s*\([^)]*\)\s*\{',
        re.MULTILINE
    )

    ASSERTION_PATTERNS = [
        re.compile(r'assert(?:Equals|True|False|NotNull|Null|Throws|Same|NotSame|ArrayEquals)\s*\(', re.IGNORECASE),
        re.compile(r'expect\s*\(', re.IGNORECASE),
        re.compile(r'verify\s*\(', re.IGNORECASE),
        re.compile(r'should\s*\(', re.IGNORECASE),
    ]

    BOUNDARY_INDICATORS = [
        'MAX_VALUE', 'MIN_VALUE', 'Integer.MAX', 'Integer.MIN',
        'Long.MAX', 'Long.MIN', 'Double.MAX', 'Double.MIN',
        'boundary', 'edge', 'limit', 'max', 'min', 'zero', 'empty',
    ]

    EXCEPTION_INDICATORS = [
        'assertThrows', 'expect(Exception', 'expect(Error',
        'throws', 'exception', 'error', 'fail',
    ]

    DOCUMENTATION_PATTERNS = [
        re.compile(r'/\*\*[\s\S]*?\*/', re.MULTILINE),
        re.compile(r'@DisplayName\s*\(\s*"([^"]+)"', re.MULTILINE),
        re.compile(r'//.*$', re.MULTILINE),
    ]

    NAMING_CONVENTION_PATTERN = re.compile(
        r'@Test\s*(?:\([^)]*\))?\s*'
        r'(?:public\s+)?(?:void\s+)?'
        r'(test|should|when|given|verify|check|ensure)\w*',
        re.IGNORECASE
    )

    def score_effectiveness(
        self,
        test_code: str,
        mutation_report: Optional[Dict[str, Any]] = None,
    ) -> TestEffectivenessScore:
        """评分测试有效性.

        Args:
            test_code: 测试代码
            mutation_report: 变异测试报告

        Returns:
            有效性评分
        """
        if not test_code.strip():
            return TestEffectivenessScore()

        mutation_kill_rate = 0.0
        if mutation_report:
            total = mutation_report.get("total_mutations", 0)
            killed = mutation_report.get("killed", 0)
            if total > 0:
                mutation_kill_rate = (killed / total) * 100

        assertion_density = self._calculate_assertion_density(test_code)

        boundary_coverage = self._calculate_boundary_coverage(test_code)

        exception_coverage = self._calculate_exception_coverage(test_code)

        weights = {
            "mutation": 0.4,
            "assertion": 0.25,
            "boundary": 0.2,
            "exception": 0.15,
        }

        overall = (
            mutation_kill_rate * weights["mutation"] +
            assertion_density * 100 * weights["assertion"] +
            boundary_coverage * 100 * weights["boundary"] +
            exception_coverage * 100 * weights["exception"]
        )

        return TestEffectivenessScore(
            mutation_kill_rate=mutation_kill_rate,
            assertion_density=assertion_density,
            boundary_coverage=boundary_coverage,
            exception_coverage=exception_coverage,
            overall_score=overall,
        )

    def score_code_quality(self, test_code: str) -> TestCodeQualityScore:
        """评分代码质量.

        Args:
            test_code: 测试代码

        Returns:
            代码质量评分
        """
        if not test_code.strip():
            return TestCodeQualityScore()

        readability = self._score_readability(test_code)

        maintainability = self._score_maintainability(test_code)

        naming_conventions = self._score_naming_conventions(test_code)

        documentation = self._score_documentation(test_code)

        code_duplication = self._detect_code_duplication(test_code)

        overall = (
            readability * 0.25 +
            maintainability * 0.25 +
            naming_conventions * 0.25 +
            documentation * 0.15 +
            (100 - code_duplication * 100) * 0.1
        )

        return TestCodeQualityScore(
            readability=readability,
            maintainability=maintainability,
            naming_conventions=naming_conventions,
            documentation=documentation,
            code_duplication=code_duplication,
            overall_score=overall,
        )

    def score_coverage_depth(
        self,
        test_code: str,
        source_code: str,
    ) -> CoverageDepthScore:
        """评分覆盖深度.

        Args:
            test_code: 测试代码
            source_code: 源代码

        Returns:
            覆盖深度评分
        """
        if not test_code.strip():
            return CoverageDepthScore()

        test_methods = self.analyze_test_methods(test_code)
        total_tests = len(test_methods)

        if total_tests == 0:
            return CoverageDepthScore()

        normal_tests = self._count_normal_tests(test_code)
        boundary_tests = self.detect_boundary_tests(test_code)
        exception_tests = self.detect_exception_tests(test_code)
        edge_case_tests = self._count_edge_case_tests(test_code)

        normal_coverage = min(1.0, normal_tests / max(1, total_tests * 0.3))
        boundary_coverage = min(1.0, len(boundary_tests) / max(1, total_tests * 0.2))
        exception_coverage = min(1.0, len(exception_tests) / max(1, total_tests * 0.2))
        edge_case_coverage = min(1.0, edge_case_tests / max(1, total_tests * 0.15))

        overall = (
            normal_coverage * 100 * 0.3 +
            boundary_coverage * 100 * 0.3 +
            exception_coverage * 100 * 0.25 +
            edge_case_coverage * 100 * 0.15
        )

        return CoverageDepthScore(
            normal_path_coverage=normal_coverage,
            boundary_path_coverage=boundary_coverage,
            exception_path_coverage=exception_coverage,
            edge_case_coverage=edge_case_coverage,
            overall_score=overall,
        )

    def generate_report(
        self,
        test_code: str,
        source_code: str,
        test_file: str,
        mutation_report: Optional[Dict[str, Any]] = None,
    ) -> QualityReport:
        """生成质量报告.

        Args:
            test_code: 测试代码
            source_code: 源代码
            test_file: 测试文件名
            mutation_report: 变异测试报告

        Returns:
            质量报告
        """
        effectiveness = self.score_effectiveness(test_code, mutation_report)
        code_quality = self.score_code_quality(test_code)
        coverage_depth = self.score_coverage_depth(test_code, source_code)

        weights = {
            "effectiveness": 0.4,
            "code_quality": 0.3,
            "coverage_depth": 0.3,
        }

        overall = (
            effectiveness.overall_score * weights["effectiveness"] +
            code_quality.overall_score * weights["code_quality"] +
            coverage_depth.overall_score * weights["coverage_depth"]
        )

        grade = self.calculate_grade(overall)

        recommendations = self._generate_recommendations(
            effectiveness, code_quality, coverage_depth
        )

        return QualityReport(
            test_file=test_file,
            effectiveness=effectiveness,
            code_quality=code_quality,
            coverage_depth=coverage_depth,
            overall_score=overall,
            grade=grade,
            recommendations=recommendations,
        )

    def calculate_grade(self, score: float) -> str:
        """根据分数计算等级.

        Args:
            score: 分数 (0-100)

        Returns:
            等级 (A/B/C/D/F)
        """
        if score >= 80:
            return "A"
        elif score >= 70:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 50:
            return "D"
        else:
            return "F"

    def analyze_test_methods(self, test_code: str) -> List[Dict[str, Any]]:
        """分析测试方法.

        Args:
            test_code: 测试代码

        Returns:
            测试方法列表
        """
        methods = []
        for match in self.TEST_METHOD_PATTERN.finditer(test_code):
            method_name = match.group(1)
            start_pos = match.end()

            brace_count = 1
            end_pos = start_pos
            for i, char in enumerate(test_code[start_pos:], start_pos):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i
                        break

            method_body = test_code[start_pos:end_pos]

            methods.append({
                'name': method_name,
                'body': method_body,
                'line_number': test_code[:match.start()].count('\n') + 1,
                'has_assertion': self._has_assertion(method_body),
            })

        return methods

    def detect_boundary_tests(self, test_code: str) -> List[str]:
        """检测边界测试.

        Args:
            test_code: 测试代码

        Returns:
            边界测试方法名列表
        """
        boundary_tests = []
        test_methods = self.analyze_test_methods(test_code)

        for method in test_methods:
            body_lower = method['body'].lower()
            name_lower = method['name'].lower()

            for indicator in self.BOUNDARY_INDICATORS:
                if indicator.lower() in body_lower or indicator.lower() in name_lower:
                    boundary_tests.append(method['name'])
                    break

        return boundary_tests

    def detect_exception_tests(self, test_code: str) -> List[str]:
        """检测异常测试.

        Args:
            test_code: 测试代码

        Returns:
            异常测试方法名列表
        """
        exception_tests = []
        test_methods = self.analyze_test_methods(test_code)

        for method in test_methods:
            body = method['body']
            name_lower = method['name'].lower()

            for indicator in self.EXCEPTION_INDICATORS:
                if indicator.lower() in body.lower() or indicator.lower() in name_lower:
                    exception_tests.append(method['name'])
                    break

        return exception_tests

    def _calculate_assertion_density(self, test_code: str) -> float:
        """计算断言密度."""
        test_methods = self.analyze_test_methods(test_code)
        if not test_methods:
            return 0.0

        methods_with_assertions = sum(
            1 for m in test_methods if m['has_assertion']
        )

        return methods_with_assertions / len(test_methods)

    def _has_assertion(self, method_body: str) -> bool:
        """检查方法体是否包含断言."""
        for pattern in self.ASSERTION_PATTERNS:
            if pattern.search(method_body):
                return True
        return False

    def _calculate_boundary_coverage(self, test_code: str) -> float:
        """计算边界覆盖."""
        test_methods = self.analyze_test_methods(test_code)
        if not test_methods:
            return 0.0

        boundary_tests = self.detect_boundary_tests(test_code)
        return len(boundary_tests) / len(test_methods)

    def _calculate_exception_coverage(self, test_code: str) -> float:
        """计算异常覆盖."""
        test_methods = self.analyze_test_methods(test_code)
        if not test_methods:
            return 0.0

        exception_tests = self.detect_exception_tests(test_code)
        return len(exception_tests) / len(test_methods)

    def _score_readability(self, test_code: str) -> float:
        """评分可读性."""
        score = 50.0

        lines = test_code.split('\n')
        avg_line_length = sum(len(line) for line in lines) / max(1, len(lines))
        if avg_line_length < 80:
            score += 15
        elif avg_line_length < 100:
            score += 10
        elif avg_line_length > 120:
            score -= 10

        if '    ' in test_code or '\t' in test_code:
            score += 10

        blank_lines = sum(1 for line in lines if not line.strip())
        blank_ratio = blank_lines / max(1, len(lines))
        if 0.1 <= blank_ratio <= 0.3:
            score += 10

        return min(100, max(0, score))

    def _score_maintainability(self, test_code: str) -> float:
        """评分可维护性."""
        score = 60.0

        test_methods = self.analyze_test_methods(test_code)
        if test_methods:
            avg_method_length = sum(
                len(m['body'].split('\n')) for m in test_methods
            ) / len(test_methods)

            if avg_method_length < 15:
                score += 20
            elif avg_method_length < 25:
                score += 10
            elif avg_method_length > 40:
                score -= 15

        if '@BeforeEach' in test_code or '@Before' in test_code:
            score += 10

        if 'private ' in test_code and 'helper' in test_code.lower():
            score += 5

        return min(100, max(0, score))

    def _score_naming_conventions(self, test_code: str) -> float:
        """评分命名规范."""
        score = 50.0

        test_methods = self.analyze_test_methods(test_code)
        if not test_methods:
            return score

        well_named = 0
        for method in test_methods:
            name = method['name']
            if self.NAMING_CONVENTION_PATTERN.search(f"@Test void {name}()"):
                well_named += 1
            elif len(name) > 5 and not name.startswith('test'):
                if any(word in name.lower() for word in ['should', 'when', 'given', 'verify']):
                    well_named += 1

        naming_ratio = well_named / len(test_methods)
        score = naming_ratio * 100

        if any(m['name'].startswith('test') for m in test_methods):
            score = min(100, score + 10)

        return min(100, max(0, score))

    def _score_documentation(self, test_code: str) -> float:
        """评分文档."""
        score = 0.0

        test_methods = self.analyze_test_methods(test_code)
        if not test_methods:
            return 50.0

        documented = 0
        for pattern in self.DOCUMENTATION_PATTERNS:
            matches = pattern.findall(test_code)
            documented += len(matches)

        doc_ratio = documented / len(test_methods)
        score = min(100, doc_ratio * 100)

        if '/**' in test_code:
            score = min(100, score + 10)

        return min(100, max(0, score))

    def _detect_code_duplication(self, test_code: str) -> float:
        """检测代码重复."""
        lines = [line.strip() for line in test_code.split('\n') if line.strip()]
        if len(lines) < 5:
            return 0.0

        unique_lines = set(lines)
        duplication = 1 - (len(unique_lines) / len(lines))

        return min(1.0, max(0.0, duplication))

    def _count_normal_tests(self, test_code: str) -> int:
        """计算普通测试数量."""
        test_methods = self.analyze_test_methods(test_code)
        boundary_tests = set(self.detect_boundary_tests(test_code))
        exception_tests = set(self.detect_exception_tests(test_code))

        normal_count = 0
        for method in test_methods:
            if method['name'] not in boundary_tests and method['name'] not in exception_tests:
                normal_count += 1

        return normal_count

    def _count_edge_case_tests(self, test_code: str) -> int:
        """计算边缘案例测试数量."""
        edge_case_tests = []
        test_methods = self.analyze_test_methods(test_code)

        edge_indicators = [
            'null', 'empty', 'blank', 'whitespace',
            'special', 'unicode', 'invalid', 'malformed',
        ]

        for method in test_methods:
            body_lower = method['body'].lower()
            for indicator in edge_indicators:
                if indicator in body_lower:
                    edge_case_tests.append(method['name'])
                    break

        return len(edge_case_tests)

    def _generate_recommendations(
        self,
        effectiveness: TestEffectivenessScore,
        code_quality: TestCodeQualityScore,
        coverage_depth: CoverageDepthScore,
    ) -> List[str]:
        """生成改进建议."""
        recommendations = []

        if effectiveness.assertion_density < 0.8:
            recommendations.append(
                "Consider adding more assertions to verify test outcomes"
            )

        if effectiveness.boundary_coverage < 0.3:
            recommendations.append(
                "Add boundary tests for edge cases (max/min values, empty inputs)"
            )

        if effectiveness.exception_coverage < 0.2:
            recommendations.append(
                "Add exception tests to verify error handling"
            )

        if code_quality.naming_conventions < 70:
            recommendations.append(
                "Improve test method naming (use 'should', 'when', 'given' patterns)"
            )

        if code_quality.documentation < 50:
            recommendations.append(
                "Add @DisplayName annotations or documentation comments"
            )

        if code_quality.code_duplication > 0.3:
            recommendations.append(
                "Reduce code duplication by extracting common setup to helper methods"
            )

        if coverage_depth.normal_path_coverage < 0.5:
            recommendations.append(
                "Add more normal path tests for typical use cases"
            )

        return recommendations
