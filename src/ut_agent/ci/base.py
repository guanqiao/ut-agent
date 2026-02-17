"""CI/CD 基础模块.

提供 CI/CD 集成的基类和通用类型。
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ExitCode(Enum):
    """CI 退出码枚举.
    
    Attributes:
        SUCCESS: 成功
        TEST_GENERATION_FAILED: 测试生成失败
        COVERAGE_BELOW_TARGET: 覆盖率低于目标
        CONFIGURATION_ERROR: 配置错误
        ENVIRONMENT_ERROR: 环境错误
    """
    SUCCESS = 0
    TEST_GENERATION_FAILED = 1
    COVERAGE_BELOW_TARGET = 2
    CONFIGURATION_ERROR = 3
    ENVIRONMENT_ERROR = 4


@dataclass
class CIResult:
    """CI 结果.
    
    Attributes:
        status: 状态
        success: 是否成功
        coverage: 覆盖率
        target_coverage: 目标覆盖率
        generated_tests: 生成的测试列表
        coverage_gaps: 覆盖率缺口列表
        mutations: 变异测试结果
        error: 错误信息
        timestamp: 时间戳
        duration_seconds: 持续时间（秒）
    """
    status: str
    success: bool
    coverage: float = 0.0
    target_coverage: float = 80.0
    generated_tests: List[Dict] = field(default_factory=list)
    coverage_gaps: List[Dict] = field(default_factory=list)
    mutations: Optional[Dict] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    duration_seconds: float = 0.0
    
    def to_json(self) -> str:
        """转换为 JSON 字符串."""
        return json.dumps({
            "status": self.status,
            "success": self.success,
            "coverage": self.coverage,
            "target_coverage": self.target_coverage,
            "generated_tests": self.generated_tests,
            "coverage_gaps": self.coverage_gaps,
            "mutations": self.mutations,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
            "duration_seconds": self.duration_seconds,
        })
    
    def to_github_summary(self) -> str:
        """生成 GitHub Summary."""
        status_emoji = "✅" if self.success else "❌"
        status_text = "Success" if self.success else "Failed"
        lines = [
            f"## 🧪 UT-Agent Test Generation Report",
            "",
            f"**Status:** {status_emoji} {status_text}",
            f"**Coverage:** {self.coverage}%",
            f"**Target:** {self.target_coverage}%",
        ]
        
        if self.coverage < self.target_coverage:
            lines.append(f"⚠️ Below target by {self.target_coverage - self.coverage}%")
        
        if self.generated_tests:
            lines.extend(["", "### Generated Tests"])
            lines.append(f"✅ Passed ({len(self.generated_tests)} tests)")
            for test in self.generated_tests:
                test_path = test.get("test_file_path", "unknown")
                lines.append(f"- ✅ {test_path}")
        
        if self.coverage_gaps:
            lines.extend(["", "### Coverage Gaps"])
            for gap in self.coverage_gaps:
                file_path = gap.get("file_path", "unknown")
                line_no = gap.get("line_number", "?")
                lines.append(f"- {file_path}:{line_no}")
        
        if self.mutations:
            lines.extend(["", "### Mutation Testing"])
            lines.append(f"- Coverage: {self.mutations.get('mutation_coverage', 0)}%")
            lines.append(f"- Killed: {self.mutations.get('killed', 0)}")
            lines.append(f"- Survived: {self.mutations.get('survived', 0)}")
        
        if self.error:
            lines.extend(["", f"**Error:** {self.error}"])
        
        return "\n".join(lines)
    
    def to_gitlab_comment(self) -> str:
        """生成 GitLab 评论."""
        return self.to_github_summary()


class CIReporter:
    """CI 报告器.
    
    生成 CI/CD 报告。
    """
    
    def __init__(
        self,
        output_format: str = "json",
        output_file: Optional[Path] = None,
        fail_on_coverage: bool = False,
        github_output: bool = False,
    ):
        """初始化报告器.
        
        Args:
            output_format: 输出格式 (json, markdown, md, summary)
            output_file: 输出文件路径
            fail_on_coverage: 覆盖率低于目标时是否失败
            github_output: 是否输出到 GitHub Actions
        """
        self.output_format = output_format
        self.output_file = output_file
        self.fail_on_coverage = fail_on_coverage
        self.github_output = github_output
        self._start_time = datetime.now()
    
    def create_result(
        self,
        status: str,
        success: bool,
        coverage: float = 0.0,
        target_coverage: float = 80.0,
        generated_tests: Optional[List[Dict]] = None,
        coverage_gaps: Optional[List[Dict]] = None,
        mutations: Optional[Dict] = None,
        error: Optional[str] = None,
    ) -> CIResult:
        """创建结果."""
        duration = (datetime.now() - self._start_time).total_seconds()
        return CIResult(
            status=status,
            success=success,
            coverage=coverage,
            target_coverage=target_coverage,
            generated_tests=generated_tests or [],
            coverage_gaps=coverage_gaps or [],
            mutations=mutations,
            error=error,
            duration_seconds=duration,
        )
    
    def _format_output(self, result: CIResult) -> str:
        """格式化输出."""
        if self.output_format in ("markdown", "md"):
            return result.to_github_summary()
        elif self.output_format == "summary":
            return self._format_summary(result)
        else:  # json or unknown
            return result.to_json()
    
    def _format_summary(self, result: CIResult) -> str:
        """格式化摘要."""
        lines = [
            "UT-Agent Summary",
            "================",
            f"Status: {result.status}",
            f"Success: {result.success}",
            f"Coverage: {result.coverage}%",
            f"Target: {result.target_coverage}%",
            f"Generated Tests: {len(result.generated_tests)}",
            f"Coverage Gaps: {len(result.coverage_gaps)}",
        ]
        if result.error:
            lines.append(f"Error: {result.error}")
        return "\n".join(lines)
    
    def _get_exit_code(self, result: CIResult) -> int:
        """获取退出码."""
        if not result.success:
            return ExitCode.TEST_GENERATION_FAILED.value
        if self.fail_on_coverage and result.coverage < result.target_coverage:
            return ExitCode.COVERAGE_BELOW_TARGET.value
        return ExitCode.SUCCESS.value
    
    def _write_github_output(self, result: CIResult) -> None:
        """写入 GitHub 输出."""
        github_output = os.environ.get("GITHUB_OUTPUT")
        github_summary = os.environ.get("GITHUB_STEP_SUMMARY")
        
        if github_output:
            with open(github_output, "a", encoding="utf-8") as f:
                f.write(f"coverage={result.coverage}\n")
                f.write(f"success={str(result.success).lower()}\n")
                f.write(f"generated_tests={len(result.generated_tests)}\n")
        
        if github_summary:
            with open(github_summary, "a", encoding="utf-8") as f:
                f.write(result.to_github_summary())
    
    def report(self, result: CIResult) -> None:
        """报告结果."""
        output = self._format_output(result)
        
        if self.output_file:
            self.output_file.write_text(output, encoding="utf-8")
        else:
            print(output)
        
        if self.github_output:
            self._write_github_output(result)


@dataclass
class TestGenerationReport:
    """测试生成报告.
    
    Attributes:
        files_processed: 处理的文件数
        tests_generated: 生成的测试数
        tests_passed: 通过的测试数
        coverage_before: 之前的覆盖率
        coverage_after: 之后的覆盖率
        duration_seconds: 执行时长（秒）
    """
    files_processed: int = 0
    tests_generated: int = 0
    tests_passed: int = 0
    coverage_before: float = 0.0
    coverage_after: float = 0.0
    duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "files_processed": self.files_processed,
            "tests_generated": self.tests_generated,
            "tests_passed": self.tests_passed,
            "coverage_before": self.coverage_before,
            "coverage_after": self.coverage_after,
            "duration_seconds": self.duration_seconds,
        }
