"""Reviewer Agent - 测试代码审查专家."""

import re
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


from ut_agent.agents.base import (
    BaseAgent,
    AgentContext,
    AgentResult,
    AgentCapability,
    AgentStatus,
)


class IssueSeverity(Enum):
    """问题严重程度."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class CodeIssue:
    """代码问题."""
    rule_id: str
    message: str
    severity: IssueSeverity
    line: Optional[int] = None
    column: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass
class ReviewResult:
    """审查结果."""
    score: float
    issues: List[CodeIssue]
    suggestions: List[str]
    metrics: Dict[str, Any] = field(default_factory=dict)
    needs_fix: bool = False


class AntiPatternDetector:
    """测试反模式检测器."""
    
    ANTI_PATTERNS = {
        "hardcoded_values": {
            "pattern": r'assertEquals?\s*\(\s*["\']?(\d+|"[^"]*")[\'"]?\s*,',
            "message": "硬编码值应提取为常量或使用测试数据生成器",
            "severity": IssueSeverity.MEDIUM,
        },
        "empty_test": {
            "pattern": r'@Test\s*\n\s*(?:public\s+)?void\s+\w+\s*\([^)]*\)\s*\{\s*\}',
            "message": "空测试方法，缺少实际验证",
            "severity": IssueSeverity.HIGH,
        },
        "no_assertions": {
            "pattern": r'@Test\s*\n\s*(?:public\s+)?void\s+\w+\s*\([^)]*\)\s*\{[^}]*\}',
            "check": lambda code: "assert" not in code.lower() and "expect" not in code.lower() and "verify" not in code.lower(),
            "message": "测试方法缺少断言",
            "severity": IssueSeverity.HIGH,
        },
        "sleep_in_test": {
            "pattern": r'Thread\.sleep\s*\(|timeouts\.sleep\s*\(',
            "message": "测试中使用 sleep，应使用 Awaitility 或其他异步等待机制",
            "severity": IssueSeverity.MEDIUM,
        },
        "system_out": {
            "pattern": r'System\.out\.print|console\.log',
            "message": "测试中包含调试输出，应移除",
            "severity": IssueSeverity.LOW,
        },
        "ignored_test": {
            "pattern": r'@Disabled|@Ignore|\.skip\s*\(|it\.skip',
            "message": "被忽略的测试，应修复或删除",
            "severity": IssueSeverity.MEDIUM,
        },
        "multiple_asserts": {
            "pattern": r'assert[A-Z]\w+\s*\([^)]+\);\s*\n\s*assert[A-Z]',
            "message": "多个断言应拆分为多个测试方法",
            "severity": IssueSeverity.LOW,
        },
        "magic_numbers": {
            "pattern": r'assertEquals?\s*\(\s*\d{3,}',
            "message": "魔法数字应提取为有意义的常量",
            "severity": IssueSeverity.LOW,
        },
        "duplicate_test": {
            "check": lambda code: True,
            "message": "可能存在重复的测试逻辑",
            "severity": IssueSeverity.MEDIUM,
        },
    }
    
    def detect(self, test_code: str) -> List[CodeIssue]:
        issues = []
        lines = test_code.split("\n")
        
        for pattern_id, config in self.ANTI_PATTERNS.items():
            if "pattern" in config:
                for match in re.finditer(config["pattern"], test_code, re.MULTILINE):
                    line_num = test_code[:match.start()].count("\n") + 1
                    issues.append(CodeIssue(
                        rule_id=f"anti_pattern:{pattern_id}",
                        message=config["message"],
                        severity=config["severity"],
                        line=line_num,
                        suggestion=self._get_suggestion(pattern_id),
                    ))
            
            if "check" in config and config["check"](test_code):
                if pattern_id == "no_assertions":
                    for i, line in enumerate(lines, 1):
                        if "@Test" in line:
                            issues.append(CodeIssue(
                                rule_id=f"anti_pattern:{pattern_id}",
                                message=config["message"],
                                severity=config["severity"],
                                line=i,
                                suggestion="添加适当的断言来验证测试结果",
                            ))
        
        return issues
    
    def _get_suggestion(self, pattern_id: str) -> str:
        suggestions = {
            "hardcoded_values": "使用 @BeforeEach 初始化测试数据或使用 TestDataGenerator",
            "empty_test": "添加测试逻辑或删除此测试方法",
            "no_assertions": "添加 assert/expect/verify 语句验证预期结果",
            "sleep_in_test": "使用 Awaitility.await().until() 或类似机制",
            "system_out": "移除调试输出或使用日志框架",
            "ignored_test": "修复测试问题并移除 @Disabled 注解",
            "multiple_asserts": "拆分为多个独立的测试方法",
            "magic_numbers": "定义常量如 EXPECTED_VALUE = 100",
        }
        return suggestions.get(pattern_id, "")


class CodeQualityChecker:
    """代码质量检查器."""
    
    QUALITY_RULES = {
        "naming_convention": {
            "check": lambda name: name.startswith("test") or name.startswith("should") or "when" in name.lower(),
            "message": "测试方法命名应遵循 given_when_then 或 should_xxx 风格",
            "severity": IssueSeverity.LOW,
        },
        "test_visibility": {
            "pattern": r'@Test\s+(?:private|protected)\s+void',
            "message": "测试方法应为 public 或使用默认访问级别",
            "severity": IssueSeverity.MEDIUM,
        },
        "missing_display_name": {
            "pattern": r'@Test\s+(?!.*@DisplayName)',
            "message": "建议添加 @DisplayName 注解说明测试目的",
            "severity": IssueSeverity.INFO,
        },
        "long_method": {
            "check": lambda code: len(code.split("\n")) > 30,
            "message": "测试方法过长，考虑拆分",
            "severity": IssueSeverity.LOW,
        },
        "missing_setup": {
            "check": lambda code: "@BeforeEach" not in code and "beforeEach" not in code,
            "message": "建议使用 @BeforeEach 进行测试初始化",
            "severity": IssueSeverity.INFO,
        },
    }
    
    def check(self, test_code: str) -> List[CodeIssue]:
        issues = []
        lines = test_code.split("\n")
        
        for rule_id, config in self.QUALITY_RULES.items():
            if "pattern" in config:
                for match in re.finditer(config["pattern"], test_code, re.MULTILINE):
                    line_num = test_code[:match.start()].count("\n") + 1
                    issues.append(CodeIssue(
                        rule_id=f"quality:{rule_id}",
                        message=config["message"],
                        severity=config["severity"],
                        line=line_num,
                    ))
            
            if "check" in config:
                if rule_id == "naming_convention":
                    method_pattern = r'void\s+(\w+)\s*\('
                    for match in re.finditer(method_pattern, test_code):
                        method_name = match.group(1)
                        if not config["check"](method_name):
                            line_num = test_code[:match.start()].count("\n") + 1
                            issues.append(CodeIssue(
                                rule_id=f"quality:{rule_id}",
                                message=config["message"],
                                severity=config["severity"],
                                line=line_num,
                            ))
                
                elif rule_id == "long_method":
                    test_methods = re.findall(r'@Test[^@]*', test_code, re.DOTALL)
                    for method in test_methods:
                        if config["check"](method):
                            issues.append(CodeIssue(
                                rule_id=f"quality:{rule_id}",
                                message=config["message"],
                                severity=config["severity"],
                            ))
                
                elif config["check"](test_code):
                    issues.append(CodeIssue(
                        rule_id=f"quality:{rule_id}",
                        message=config["message"],
                        severity=config["severity"],
                    ))
        
        return issues


class CoverageVerifier:
    """覆盖率验证器."""
    
    def verify(
        self,
        test_code: str,
        file_analysis: Dict[str, Any],
        coverage_report: Optional[Dict[str, Any]] = None,
    ) -> List[CodeIssue]:
        issues = []
        
        methods = file_analysis.get("methods", file_analysis.get("functions", []))
        test_code_lower = test_code.lower()
        
        for method in methods:
            method_name = method.get("name", "")
            if method_name and method_name.lower() not in test_code_lower:
                issues.append(CodeIssue(
                    rule_id="coverage:missing_test",
                    message=f"方法 '{method_name}' 缺少对应的测试",
                    severity=IssueSeverity.MEDIUM,
                    suggestion=f"为方法 '{method_name}' 添加测试用例",
                ))
        
        if coverage_report:
            coverage = coverage_report.get("overall_coverage", 0)
            if coverage < 50:
                issues.append(CodeIssue(
                    rule_id="coverage:low",
                    message=f"覆盖率过低 ({coverage:.1f}%)，目标应至少 80%",
                    severity=IssueSeverity.HIGH,
                ))
            elif coverage < 80:
                issues.append(CodeIssue(
                    rule_id="coverage:below_target",
                    message=f"覆盖率未达标 ({coverage:.1f}%)，目标 80%",
                    severity=IssueSeverity.MEDIUM,
                ))
        
        return issues


class BestPracticeSuggester:
    """最佳实践建议器."""
    
    BEST_PRACTICES = [
        {
            "condition": lambda code: "given" not in code.lower() and "when" not in code.lower(),
            "suggestion": "使用 given-when-then 结构组织测试代码",
        },
        {
            "condition": lambda code: "@Nested" not in code and "describe(" not in code,
            "suggestion": "考虑使用嵌套测试类组织相关测试",
        },
        {
            "condition": lambda code: "@ParameterizedTest" not in code and "each" not in code.lower(),
            "suggestion": "对于相似测试场景，考虑使用参数化测试",
        },
        {
            "condition": lambda code: "assertThrows" not in code and "toThrow" not in code,
            "suggestion": "添加异常场景测试",
        },
        {
            "condition": lambda code: "@MockBean" not in code and "@Mock" not in code,
            "suggestion": "对于外部依赖，使用 Mock 对象隔离测试",
        },
    ]
    
    def suggest(self, test_code: str) -> List[str]:
        suggestions = []
        
        for practice in self.BEST_PRACTICES:
            if practice["condition"](test_code):
                suggestions.append(practice["suggestion"])
        
        return suggestions


class ReviewerAgent(BaseAgent):
    """测试代码审查 Agent."""
    
    name = "reviewer"
    description = "测试代码审查专家 - 检查测试代码质量、识别反模式、提供改进建议"
    capabilities = [
        AgentCapability.CODE_QUALITY_CHECK,
        AgentCapability.COVERAGE_VERIFICATION,
        AgentCapability.ANTI_PATTERN_DETECTION,
        AgentCapability.BEST_PRACTICE_SUGGESTION,
    ]
    
    def __init__(
        self,
        memory: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(memory, config)
        self._anti_pattern_detector = AntiPatternDetector()
        self._code_quality_checker = CodeQualityChecker()
        self._coverage_verifier = CoverageVerifier()
        self._best_practice_suggester = BestPracticeSuggester()
    
    async def execute(self, context: AgentContext) -> AgentResult:
        start_time = time.time()
        self._status = AgentStatus.RUNNING
        
        errors = []
        
        try:
            generated_test = context.generated_test
            if not generated_test:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    task_id=context.task_id,
                    errors=["No generated test provided"],
                )
            
            test_code = generated_test.get("test_code", "")
            file_analysis = context.file_analysis or {}
            coverage_report = context.coverage_report
            
            anti_pattern_issues = self._anti_pattern_detector.detect(test_code)
            
            quality_issues = self._code_quality_checker.check(test_code)
            
            coverage_issues = self._coverage_verifier.verify(
                test_code, file_analysis, coverage_report
            )
            
            all_issues = anti_pattern_issues + quality_issues + coverage_issues
            
            best_practice_suggestions = self._best_practice_suggester.suggest(test_code)
            
            score = self._calculate_score(all_issues)
            
            needs_fix = any(
                issue.severity in [IssueSeverity.CRITICAL, IssueSeverity.HIGH]
                for issue in all_issues
            )
            
            review_result = ReviewResult(
                score=score,
                issues=all_issues,
                suggestions=best_practice_suggestions,
                metrics={
                    "total_issues": len(all_issues),
                    "critical_issues": len([i for i in all_issues if i.severity == IssueSeverity.CRITICAL]),
                    "high_issues": len([i for i in all_issues if i.severity == IssueSeverity.HIGH]),
                    "medium_issues": len([i for i in all_issues if i.severity == IssueSeverity.MEDIUM]),
                    "low_issues": len([i for i in all_issues if i.severity == IssueSeverity.LOW]),
                },
                needs_fix=needs_fix,
            )
            
            self.remember(f"review:{context.task_id}", {
                "score": score,
                "issues_count": len(all_issues),
                "needs_fix": needs_fix,
            })
            
            duration_ms = int((time.time() - start_time) * 1000)
            self._status = AgentStatus.SUCCESS
            
            result = AgentResult(
                success=True,
                agent_name=self.name,
                task_id=context.task_id,
                data={
                    "review_result": {
                        "score": review_result.score,
                        "issues": [
                            {
                                "rule_id": i.rule_id,
                                "message": i.message,
                                "severity": i.severity.value,
                                "line": i.line,
                                "suggestion": i.suggestion,
                            }
                            for i in review_result.issues
                        ],
                        "suggestions": review_result.suggestions,
                        "metrics": review_result.metrics,
                        "needs_fix": review_result.needs_fix,
                    },
                },
                suggestions=best_practice_suggestions,
                metrics={
                    "duration_ms": duration_ms,
                    "score": score,
                    "issues_count": len(all_issues),
                },
                duration_ms=duration_ms,
            )
            
            self.record_execution(result)
            return result
            
        except Exception as e:
            self._status = AgentStatus.FAILED
            errors.append(str(e))
            return AgentResult(
                success=False,
                agent_name=self.name,
                task_id=context.task_id,
                errors=errors,
            )
    
    def _calculate_score(self, issues: List[CodeIssue]) -> float:
        base_score = 100.0
        
        penalties = {
            IssueSeverity.CRITICAL: 25,
            IssueSeverity.HIGH: 15,
            IssueSeverity.MEDIUM: 8,
            IssueSeverity.LOW: 3,
            IssueSeverity.INFO: 1,
        }
        
        for issue in issues:
            base_score -= penalties.get(issue.severity, 0)
        
        return max(0.0, min(100.0, base_score))
