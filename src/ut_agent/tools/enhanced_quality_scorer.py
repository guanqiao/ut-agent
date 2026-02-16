"""增强版测试质量评分系统.

深度集成变异测试、可测试性分析、稳定性评估等多维度质量指标。
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime


class QualityDimension(Enum):
    EFFECTIVENESS = "effectiveness"
    CODE_QUALITY = "code_quality"
    COVERAGE_DEPTH = "coverage_depth"
    STABILITY = "stability"
    TESTABILITY = "testability"
    MAINTAINABILITY = "maintainability"


class QualityLevel(Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    CRITICAL = "critical"


@dataclass
class MutationQualityScore:
    kill_rate: float = 0.0
    mutation_coverage: float = 0.0
    test_strength: float = 0.0
    survived_mutations: int = 0
    equivalent_mutations: int = 0
    overall_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "kill_rate": round(self.kill_rate, 2),
            "mutation_coverage": round(self.mutation_coverage, 2),
            "test_strength": round(self.test_strength, 2),
            "survived_mutations": self.survived_mutations,
            "equivalent_mutations": self.equivalent_mutations,
            "overall_score": round(self.overall_score, 2),
        }


@dataclass
class StabilityQualityScore:
    flaky_rate: float = 0.0
    flaky_test_count: int = 0
    execution_variance: float = 0.0
    stability_score: float = 100.0
    quarantine_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "flaky_rate": round(self.flaky_rate, 4),
            "flaky_test_count": self.flaky_test_count,
            "execution_variance": round(self.execution_variance, 4),
            "stability_score": round(self.stability_score, 2),
            "quarantine_count": self.quarantine_count,
        }


@dataclass
class TestabilityQualityScore:
    overall_score: float = 100.0
    dependency_score: float = 100.0
    coupling_score: float = 100.0
    complexity_score: float = 100.0
    design_score: float = 100.0
    issue_count: int = 0
    critical_issues: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 2),
            "dependency_score": round(self.dependency_score, 2),
            "coupling_score": round(self.coupling_score, 2),
            "complexity_score": round(self.complexity_score, 2),
            "design_score": round(self.design_score, 2),
            "issue_count": self.issue_count,
            "critical_issues": self.critical_issues,
        }


@dataclass
class DebtQualityScore:
    total_debt_score: float = 0.0
    open_items: int = 0
    critical_items: int = 0
    debt_interest: float = 0.0
    trend_direction: str = "stable"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_debt_score": round(self.total_debt_score, 2),
            "open_items": self.open_items,
            "critical_items": self.critical_items,
            "debt_interest": round(self.debt_interest, 4),
            "trend_direction": self.trend_direction,
        }


@dataclass
class EnhancedQualityReport:
    test_file: str
    source_file: Optional[str] = None
    
    effectiveness_score: float = 0.0
    code_quality_score: float = 0.0
    coverage_depth_score: float = 0.0
    mutation_score: float = 0.0
    stability_score: float = 100.0
    testability_score: float = 100.0
    debt_score: float = 0.0
    
    overall_score: float = 0.0
    quality_level: QualityLevel = QualityLevel.ACCEPTABLE
    grade: str = "C"
    
    mutation_details: Optional[MutationQualityScore] = None
    stability_details: Optional[StabilityQualityScore] = None
    testability_details: Optional[TestabilityQualityScore] = None
    debt_details: Optional[DebtQualityScore] = None
    
    recommendations: List[str] = field(default_factory=list)
    critical_issues: List[str] = field(default_factory=list)
    improvement_priorities: List[Dict[str, Any]] = field(default_factory=list)
    
    generated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_file": self.test_file,
            "source_file": self.source_file,
            "scores": {
                "effectiveness": round(self.effectiveness_score, 2),
                "code_quality": round(self.code_quality_score, 2),
                "coverage_depth": round(self.coverage_depth_score, 2),
                "mutation": round(self.mutation_score, 2),
                "stability": round(self.stability_score, 2),
                "testability": round(self.testability_score, 2),
                "debt": round(self.debt_score, 2),
                "overall": round(self.overall_score, 2),
            },
            "quality_level": self.quality_level.value,
            "grade": self.grade,
            "mutation_details": self.mutation_details.to_dict() if self.mutation_details else None,
            "stability_details": self.stability_details.to_dict() if self.stability_details else None,
            "testability_details": self.testability_details.to_dict() if self.testability_details else None,
            "debt_details": self.debt_details.to_dict() if self.debt_details else None,
            "recommendations": self.recommendations,
            "critical_issues": self.critical_issues,
            "improvement_priorities": self.improvement_priorities,
            "generated_at": self.generated_at.isoformat(),
        }


class EnhancedQualityScorer:
    
    DIMENSION_WEIGHTS = {
        QualityDimension.EFFECTIVENESS: 0.20,
        QualityDimension.CODE_QUALITY: 0.15,
        QualityDimension.COVERAGE_DEPTH: 0.15,
        QualityDimension.STABILITY: 0.15,
        QualityDimension.TESTABILITY: 0.15,
        QualityDimension.MAINTAINABILITY: 0.20,
    }
    
    GRADE_THRESHOLDS = {
        "A+": 95,
        "A": 90,
        "A-": 85,
        "B+": 80,
        "B": 75,
        "B-": 70,
        "C+": 65,
        "C": 60,
        "C-": 55,
        "D": 50,
        "F": 0,
    }
    
    LEVEL_THRESHOLDS = {
        QualityLevel.EXCELLENT: 90,
        QualityLevel.GOOD: 75,
        QualityLevel.ACCEPTABLE: 60,
        QualityLevel.POOR: 40,
        QualityLevel.CRITICAL: 0,
    }
    
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
    
    def __init__(self):
        self.mutation_analyzer = None
        self.stability_analyzer = None
        self.testability_analyzer = None
        self.debt_tracker = None
    
    def set_mutation_analyzer(self, analyzer) -> None:
        self.mutation_analyzer = analyzer
    
    def set_stability_analyzer(self, analyzer) -> None:
        self.stability_analyzer = analyzer
    
    def set_testability_analyzer(self, analyzer) -> None:
        self.testability_analyzer = analyzer
    
    def set_debt_tracker(self, tracker) -> None:
        self.debt_tracker = tracker
    
    def generate_comprehensive_report(
        self,
        test_code: str,
        source_code: str,
        test_file: str,
        source_file: Optional[str] = None,
        mutation_report: Optional[Dict[str, Any]] = None,
        coverage_report: Optional[Dict[str, Any]] = None,
        execution_history: Optional[List[Dict[str, Any]]] = None,
    ) -> EnhancedQualityReport:
        report = EnhancedQualityReport(
            test_file=test_file,
            source_file=source_file,
        )
        
        report.effectiveness_score = self._score_effectiveness(
            test_code, mutation_report
        )
        
        report.code_quality_score = self._score_code_quality(test_code)
        
        report.coverage_depth_score = self._score_coverage_depth(
            test_code, source_code, coverage_report
        )
        
        report.mutation_score, report.mutation_details = self._score_mutation(
            mutation_report
        )
        
        report.stability_score, report.stability_details = self._score_stability(
            execution_history
        )
        
        report.testability_score, report.testability_details = self._score_testability(
            source_code, source_file
        )
        
        report.debt_score, report.debt_details = self._score_debt(test_file)
        
        report.overall_score = self._calculate_overall_score(report)
        
        report.quality_level = self._determine_quality_level(report.overall_score)
        report.grade = self._determine_grade(report.overall_score)
        
        report.recommendations = self._generate_recommendations(report)
        report.critical_issues = self._identify_critical_issues(report)
        report.improvement_priorities = self._prioritize_improvements(report)
        
        return report
    
    def _score_effectiveness(
        self,
        test_code: str,
        mutation_report: Optional[Dict[str, Any]] = None,
    ) -> float:
        score = 0.0
        
        assertion_density = self._calculate_assertion_density(test_code)
        score += assertion_density * 40
        
        boundary_coverage = self._calculate_boundary_coverage(test_code)
        score += boundary_coverage * 30
        
        exception_coverage = self._calculate_exception_coverage(test_code)
        score += exception_coverage * 30
        
        return min(100, score)
    
    def _score_code_quality(self, test_code: str) -> float:
        score = 50.0
        
        lines = test_code.split('\n')
        non_empty_lines = [l for l in lines if l.strip()]
        
        if non_empty_lines:
            avg_length = sum(len(l) for l in non_empty_lines) / len(non_empty_lines)
            if avg_length < 80:
                score += 15
            elif avg_length < 100:
                score += 10
            elif avg_length > 120:
                score -= 10
        
        if '@BeforeEach' in test_code or '@Before' in test_code:
            score += 10
        
        if '@DisplayName' in test_code:
            score += 10
        
        naming_score = self._score_naming_conventions(test_code)
        score += naming_score * 0.2
        
        return min(100, max(0, score))
    
    def _score_coverage_depth(
        self,
        test_code: str,
        source_code: str,
        coverage_report: Optional[Dict[str, Any]] = None,
    ) -> float:
        score = 0.0
        
        if coverage_report:
            line_coverage = coverage_report.get("line_coverage", 0)
            branch_coverage = coverage_report.get("branch_coverage", 0)
            score = line_coverage * 0.4 + branch_coverage * 0.6
        else:
            test_methods = self._analyze_test_methods(test_code)
            total_tests = len(test_methods)
            
            if total_tests > 0:
                boundary_tests = len(self._detect_boundary_tests(test_code, test_methods))
                exception_tests = len(self._detect_exception_tests(test_code, test_methods))
                
                normal_ratio = min(1.0, (total_tests - boundary_tests - exception_tests) / max(1, total_tests * 0.5))
                boundary_ratio = min(1.0, boundary_tests / max(1, total_tests * 0.3))
                exception_ratio = min(1.0, exception_tests / max(1, total_tests * 0.2))
                
                score = (normal_ratio * 40 + boundary_ratio * 35 + exception_ratio * 25)
        
        return min(100, score)
    
    def _score_mutation(
        self,
        mutation_report: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, Optional[MutationQualityScore]]:
        if not mutation_report:
            return 0.0, None
        
        details = MutationQualityScore()
        
        total = mutation_report.get("total_mutations", 0)
        killed = mutation_report.get("killed", 0)
        survived = mutation_report.get("survived", 0)
        
        if total > 0:
            details.kill_rate = (killed / total) * 100
            details.mutation_coverage = mutation_report.get("mutation_coverage", 0)
            details.test_strength = mutation_report.get("test_strength", details.kill_rate)
        
        details.survived_mutations = survived
        details.equivalent_mutations = mutation_report.get("equivalent_mutations", 0)
        
        details.overall_score = details.kill_rate * 0.5 + details.test_strength * 0.3 + details.mutation_coverage * 0.2
        
        return details.overall_score, details
    
    def _score_stability(
        self,
        execution_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[float, Optional[StabilityQualityScore]]:
        details = StabilityQualityScore()
        
        if not execution_history or len(execution_history) < 2:
            return 100.0, details
        
        total_runs = len(execution_history)
        failed_runs = sum(1 for e in execution_history if e.get("status") in ("failed", "error"))
        
        if total_runs > 0:
            details.flaky_rate = self._calculate_flaky_rate(execution_history)
            details.flaky_test_count = failed_runs
        
        durations = [e.get("duration_ms", 0) for e in execution_history if e.get("duration_ms")]
        if len(durations) >= 2:
            avg = sum(durations) / len(durations)
            variance = sum((d - avg) ** 2 for d in durations) / len(durations)
            details.execution_variance = (variance ** 0.5) / avg if avg > 0 else 0
        
        details.stability_score = max(0, 100 - details.flaky_rate * 100 - details.execution_variance * 50)
        
        return details.stability_score, details
    
    def _score_testability(
        self,
        source_code: str,
        source_file: Optional[str] = None,
    ) -> Tuple[float, Optional[TestabilityQualityScore]]:
        details = TestabilityQualityScore()
        
        if not source_code:
            return 100.0, details
        
        issues = self._detect_testability_issues(source_code)
        
        details.issue_count = len(issues)
        details.critical_issues = sum(1 for i in issues if i.get("severity") == "critical")
        
        severity_weights = {"critical": 20, "high": 10, "medium": 5, "low": 2}
        
        dependency_penalty = 0
        coupling_penalty = 0
        complexity_penalty = 0
        design_penalty = 0
        
        for issue in issues:
            severity = issue.get("severity", "medium")
            penalty = severity_weights.get(severity, 5)
            
            issue_type = issue.get("type", "")
            if "dependency" in issue_type.lower():
                dependency_penalty += penalty
            elif "coupling" in issue_type.lower():
                coupling_penalty += penalty
            elif "complexity" in issue_type.lower() or "long" in issue_type.lower():
                complexity_penalty += penalty
            else:
                design_penalty += penalty
        
        details.dependency_score = max(0, 100 - dependency_penalty)
        details.coupling_score = max(0, 100 - coupling_penalty)
        details.complexity_score = max(0, 100 - complexity_penalty)
        details.design_score = max(0, 100 - design_penalty)
        
        details.overall_score = (
            details.dependency_score * 0.3 +
            details.coupling_score * 0.2 +
            details.complexity_score * 0.25 +
            details.design_score * 0.25
        )
        
        return details.overall_score, details
    
    def _score_debt(self, test_file: str) -> Tuple[float, Optional[DebtQualityScore]]:
        details = DebtQualityScore()
        
        if self.debt_tracker:
            debt_summary = self.debt_tracker.get_debt_summary()
            details.total_debt_score = debt_summary.get("total_debt_score", 0)
            details.open_items = debt_summary.get("open_items", 0)
            details.critical_items = debt_summary.get("by_priority", {}).get("critical", 0)
            details.debt_interest = self.debt_tracker.calculate_debt_interest()
        
        return details.total_debt_score, details
    
    def _calculate_overall_score(self, report: EnhancedQualityReport) -> float:
        scores = {
            QualityDimension.EFFECTIVENESS: report.effectiveness_score,
            QualityDimension.CODE_QUALITY: report.code_quality_score,
            QualityDimension.COVERAGE_DEPTH: report.coverage_depth_score,
            QualityDimension.STABILITY: report.stability_score,
            QualityDimension.TESTABILITY: report.testability_score,
            QualityDimension.MAINTAINABILITY: 100 - report.debt_score,
        }
        
        total = 0.0
        for dimension, score in scores.items():
            weight = self.DIMENSION_WEIGHTS.get(dimension, 0.1)
            total += score * weight
        
        if report.mutation_score > 0:
            mutation_bonus = (report.mutation_score - 50) * 0.1
            total += max(0, mutation_bonus)
        
        return min(100, max(0, total))
    
    def _determine_quality_level(self, score: float) -> QualityLevel:
        for level, threshold in self.LEVEL_THRESHOLDS.items():
            if score >= threshold:
                return level
        return QualityLevel.CRITICAL
    
    def _determine_grade(self, score: float) -> str:
        for grade, threshold in self.GRADE_THRESHOLDS.items():
            if score >= threshold:
                return grade
        return "F"
    
    def _generate_recommendations(self, report: EnhancedQualityReport) -> List[str]:
        recommendations = []
        
        if report.effectiveness_score < 60:
            recommendations.append("增加更多断言以验证测试结果")
            recommendations.append("添加边界条件测试用例")
        
        if report.mutation_score < 60 and report.mutation_details:
            if report.mutation_details.survived_mutations > 0:
                recommendations.append(
                    f"有 {report.mutation_details.survived_mutations} 个变异体存活，"
                    "建议添加针对性测试用例"
                )
        
        if report.stability_score < 80 and report.stability_details:
            if report.stability_details.flaky_rate > 0.1:
                recommendations.append(
                    f"Flaky测试率 {report.stability_details.flaky_rate:.1%}，"
                    "建议检查时间依赖、随机值或竞态条件"
                )
        
        if report.testability_score < 70 and report.testability_details:
            if report.testability_details.critical_issues > 0:
                recommendations.append(
                    f"发现 {report.testability_details.critical_issues} 个关键可测试性问题，"
                    "建议优先重构"
                )
        
        if report.debt_score > 50 and report.debt_details:
            recommendations.append(
                f"测试债务评分 {report.debt_score:.0f}，"
                f"有 {report.debt_details.open_items} 个待处理项"
            )
        
        return recommendations
    
    def _identify_critical_issues(self, report: EnhancedQualityReport) -> List[str]:
        issues = []
        
        if report.overall_score < 40:
            issues.append(f"整体质量评分过低: {report.overall_score:.1f}")
        
        if report.mutation_details and report.mutation_details.kill_rate < 30:
            issues.append(f"变异杀死率过低: {report.mutation_details.kill_rate:.1f}%")
        
        if report.stability_details and report.stability_details.flaky_rate > 0.2:
            issues.append(f"Flaky测试率过高: {report.stability_details.flaky_rate:.1%}")
        
        if report.testability_details and report.testability_details.critical_issues > 3:
            issues.append(f"可测试性问题过多: {report.testability_details.critical_issues} 个关键问题")
        
        return issues
    
    def _prioritize_improvements(self, report: EnhancedQualityReport) -> List[Dict[str, Any]]:
        improvements = []
        
        scores = [
            ("effectiveness", report.effectiveness_score, "提高测试有效性"),
            ("mutation", report.mutation_score, "提高变异测试得分"),
            ("stability", report.stability_score, "提高测试稳定性"),
            ("testability", report.testability_score, "改善代码可测试性"),
            ("coverage", report.coverage_depth_score, "增加覆盖深度"),
            ("code_quality", report.code_quality_score, "改善测试代码质量"),
        ]
        
        sorted_scores = sorted(scores, key=lambda x: x[1])
        
        for i, (name, score, action) in enumerate(sorted_scores[:3]):
            if score < 80:
                improvements.append({
                    "priority": i + 1,
                    "dimension": name,
                    "current_score": round(score, 1),
                    "target_score": 80,
                    "action": action,
                    "impact": "high" if score < 50 else "medium",
                })
        
        return improvements
    
    def _calculate_assertion_density(self, test_code: str) -> float:
        test_methods = self._analyze_test_methods(test_code)
        if not test_methods:
            return 0.0
        
        methods_with_assertions = sum(
            1 for m in test_methods if self._has_assertion(m['body'])
        )
        
        return methods_with_assertions / len(test_methods)
    
    def _calculate_boundary_coverage(self, test_code: str) -> float:
        test_methods = self._analyze_test_methods(test_code)
        if not test_methods:
            return 0.0
        
        boundary_tests = self._detect_boundary_tests(test_code, test_methods)
        return len(boundary_tests) / len(test_methods)
    
    def _calculate_exception_coverage(self, test_code: str) -> float:
        test_methods = self._analyze_test_methods(test_code)
        if not test_methods:
            return 0.0
        
        exception_tests = self._detect_exception_tests(test_code, test_methods)
        return len(exception_tests) / len(test_methods)
    
    def _analyze_test_methods(self, test_code: str) -> List[Dict[str, Any]]:
        test_pattern = re.compile(
            r'@Test\s*(?:\([^)]*\))?\s*'
            r'(?:public\s+)?(?:void\s+)?'
            r'(\w+)\s*\([^)]*\)\s*\{',
            re.MULTILINE
        )
        
        methods = []
        for match in test_pattern.finditer(test_code):
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
            })
        
        return methods
    
    def _has_assertion(self, method_body: str) -> bool:
        for pattern in self.ASSERTION_PATTERNS:
            if pattern.search(method_body):
                return True
        return False
    
    def _detect_boundary_tests(
        self,
        test_code: str,
        test_methods: List[Dict[str, Any]],
    ) -> List[str]:
        boundary_tests = []
        
        for method in test_methods:
            body_lower = method['body'].lower()
            name_lower = method['name'].lower()
            
            for indicator in self.BOUNDARY_INDICATORS:
                if indicator.lower() in body_lower or indicator.lower() in name_lower:
                    boundary_tests.append(method['name'])
                    break
        
        return boundary_tests
    
    def _detect_exception_tests(
        self,
        test_code: str,
        test_methods: List[Dict[str, Any]],
    ) -> List[str]:
        exception_tests = []
        
        for method in test_methods:
            body = method['body']
            name_lower = method['name'].lower()
            
            for indicator in self.EXCEPTION_INDICATORS:
                if indicator.lower() in body.lower() or indicator.lower() in name_lower:
                    exception_tests.append(method['name'])
                    break
        
        return exception_tests
    
    def _score_naming_conventions(self, test_code: str) -> float:
        test_methods = self._analyze_test_methods(test_code)
        if not test_methods:
            return 50.0
        
        well_named = 0
        naming_pattern = re.compile(
            r'(test|should|when|given|verify|check|ensure)\w*',
            re.IGNORECASE
        )
        
        for method in test_methods:
            if naming_pattern.match(method['name']):
                well_named += 1
        
        return (well_named / len(test_methods)) * 100
    
    def _calculate_flaky_rate(self, execution_history: List[Dict[str, Any]]) -> float:
        if len(execution_history) < 2:
            return 0.0
        
        transitions = 0
        statuses = [e.get("status") for e in execution_history]
        
        for i in range(1, len(statuses)):
            if statuses[i] != statuses[i-1]:
                transitions += 1
        
        return transitions / (len(statuses) - 1)
    
    def _detect_testability_issues(self, source_code: str) -> List[Dict[str, Any]]:
        issues = []
        
        singleton_pattern = re.compile(
            r'private\s+static\s+\w+\s+instance\s*;|'
            r'public\s+static\s+\w+\s+getInstance\s*\(',
            re.MULTILINE
        )
        for match in singleton_pattern.finditer(source_code):
            issues.append({
                "type": "singleton",
                "severity": "high",
                "line": source_code[:match.start()].count('\n') + 1,
            })
        
        static_method_pattern = re.compile(
            r'public\s+static\s+(?!void\s+main\b)(\w+)\s+(\w+)\s*\(',
            re.MULTILINE
        )
        for match in static_method_pattern.finditer(source_code):
            issues.append({
                "type": "static_method",
                "severity": "medium",
                "line": source_code[:match.start()].count('\n') + 1,
            })
        
        new_keyword_pattern = re.compile(r'new\s+(\w+)\s*\(', re.MULTILINE)
        for match in new_keyword_pattern.finditer(source_code):
            type_name = match.group(1)
            if type_name not in ('String', 'Integer', 'ArrayList', 'HashMap', 'Object'):
                issues.append({
                    "type": "hardcoded_dependency",
                    "severity": "medium",
                    "line": source_code[:match.start()].count('\n') + 1,
                })
        
        return issues


def create_quality_report(
    test_code: str,
    source_code: str,
    test_file: str,
    **kwargs,
) -> EnhancedQualityReport:
    scorer = EnhancedQualityScorer()
    return scorer.generate_comprehensive_report(
        test_code=test_code,
        source_code=source_code,
        test_file=test_file,
        **kwargs,
    )
