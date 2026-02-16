"""CI 模式支持模块."""

import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ExitCode(Enum):
    SUCCESS = 0
    TEST_GENERATION_FAILED = 1
    COVERAGE_BELOW_TARGET = 2
    CONFIGURATION_ERROR = 3
    ENVIRONMENT_ERROR = 4


@dataclass
class CIResult:
    status: str
    success: bool
    coverage: float = 0.0
    target_coverage: float = 80.0
    generated_tests: List[Dict[str, str]] = field(default_factory=list)
    coverage_gaps: List[Dict[str, Any]] = field(default_factory=list)
    mutations: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_seconds: float = 0.0
    
    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)
    
    def to_github_summary(self) -> str:
        lines = [
            "## 🧪 UT-Agent Test Generation Report",
            "",
            f"**Status**: {'✅ Success' if self.success else '❌ Failed'}",
            f"**Timestamp**: {self.timestamp}",
            f"**Duration**: {self.duration_seconds:.1f}s",
            "",
            "### Coverage",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Coverage | {self.coverage:.1f}% |",
            f"| Target | {self.target_coverage:.1f}% |",
            f"| Status | {'✅ Passed' if self.coverage >= self.target_coverage else '⚠️ Below target'} |",
        ]
        
        if self.generated_tests:
            lines.extend([
                "",
                "### Generated Tests",
                "",
            ])
            for test in self.generated_tests:
                lines.append(f"- `{test.get('test_file_path', 'unknown')}`")
        
        if self.coverage_gaps:
            lines.extend([
                "",
                "### Top Coverage Gaps",
                "",
            ])
            for gap in self.coverage_gaps[:10]:
                lines.append(f"- `{gap.get('file_path', 'unknown')}:{gap.get('line_number', '?')}`")
        
        if self.mutations:
            lines.extend([
                "",
                "### Mutation Testing",
                "",
                f"| Metric | Value |",
                f"|--------|-------|",
                f"| Mutation Coverage | {self.mutations.get('mutation_coverage', 0):.1f}% |",
                f"| Killed | {self.mutations.get('killed', 0)} |",
                f"| Survived | {self.mutations.get('survived', 0)} |",
            ])
        
        return "\n".join(lines)
    
    def to_gitlab_comment(self) -> str:
        return self.to_github_summary()


class CIReporter:
    def __init__(
        self,
        output_format: str = "json",
        output_file: Optional[Path] = None,
        fail_on_coverage: bool = False,
        github_output: bool = False,
    ):
        self.output_format = output_format
        self.output_file = output_file
        self.fail_on_coverage = fail_on_coverage
        self.github_output = github_output
        self.start_time = datetime.now()
    
    def create_result(
        self,
        status: str,
        success: bool,
        coverage: float = 0.0,
        target_coverage: float = 80.0,
        generated_tests: Optional[List[Dict[str, str]]] = None,
        coverage_gaps: Optional[List[Dict[str, Any]]] = None,
        mutations: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> CIResult:
        duration = (datetime.now() - self.start_time).total_seconds()
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
    
    def report(self, result: CIResult) -> int:
        output = self._format_output(result)
        
        if self.output_file:
            self.output_file.write_text(output, encoding="utf-8")
        else:
            print(output)
        
        if self.github_output:
            self._write_github_output(result)
        
        return self._get_exit_code(result)
    
    def _format_output(self, result: CIResult) -> str:
        if self.output_format == "json":
            return result.to_json()
        elif self.output_format == "markdown" or self.output_format == "md":
            return result.to_github_summary()
        elif self.output_format == "summary":
            return self._format_summary(result)
        else:
            return result.to_json()
    
    def _format_summary(self, result: CIResult) -> str:
        lines = [
            f"UT-Agent Summary",
            f"================",
            f"Status: {result.status}",
            f"Coverage: {result.coverage:.1f}% (Target: {result.target_coverage:.1f}%)",
            f"Generated Tests: {len(result.generated_tests)}",
            f"Coverage Gaps: {len(result.coverage_gaps)}",
        ]
        if result.error:
            lines.append(f"Error: {result.error}")
        return "\n".join(lines)
    
    def _write_github_output(self, result: CIResult) -> None:
        github_output_path = os.environ.get("GITHUB_OUTPUT", "")
        if github_output_path:
            github_output_file = Path(github_output_path)
            if github_output_file.exists():
                with open(github_output_file, "a", encoding="utf-8") as f:
                    f.write(f"coverage={result.coverage}\n")
                    f.write(f"success={str(result.success).lower()}\n")
                    f.write(f"generated_tests={len(result.generated_tests)}\n")
        
        github_summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
        if github_summary_path:
            github_step_summary = Path(github_summary_path)
            if github_step_summary.exists():
                with open(github_step_summary, "a", encoding="utf-8") as f:
                    f.write(result.to_github_summary())
    
    def _get_exit_code(self, result: CIResult) -> int:
        if not result.success:
            return ExitCode.TEST_GENERATION_FAILED.value
        
        if self.fail_on_coverage and result.coverage < result.target_coverage:
            return ExitCode.COVERAGE_BELOW_TARGET.value
        
        return ExitCode.SUCCESS.value


import os
