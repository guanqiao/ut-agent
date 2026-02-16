"""CI 模块单元测试."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from ut_agent.ci import ExitCode, CIResult, CIReporter


class TestExitCode:
    """ExitCode 枚举测试."""

    def test_exit_code_values(self):
        """测试 ExitCode 枚举值."""
        assert ExitCode.SUCCESS.value == 0
        assert ExitCode.TEST_GENERATION_FAILED.value == 1
        assert ExitCode.COVERAGE_BELOW_TARGET.value == 2
        assert ExitCode.CONFIGURATION_ERROR.value == 3
        assert ExitCode.ENVIRONMENT_ERROR.value == 4


class TestCIResult:
    """CIResult 数据类测试."""

    def test_ci_result_creation(self):
        """测试 CIResult 创建."""
        result = CIResult(
            status="completed",
            success=True,
            coverage=85.5,
            target_coverage=80.0,
            generated_tests=[{"test_file_path": "/test/Test.java"}],
            coverage_gaps=[{"file_path": "/src/Main.java", "line_number": 10}],
            duration_seconds=120.5,
        )

        assert result.status == "completed"
        assert result.success is True
        assert result.coverage == 85.5
        assert result.target_coverage == 80.0
        assert len(result.generated_tests) == 1
        assert len(result.coverage_gaps) == 1
        assert result.duration_seconds == 120.5

    def test_ci_result_defaults(self):
        """测试 CIResult 默认值."""
        result = CIResult(status="test", success=True)

        assert result.coverage == 0.0
        assert result.target_coverage == 80.0
        assert result.generated_tests == []
        assert result.coverage_gaps == []
        assert result.mutations is None
        assert result.error is None
        assert result.timestamp is not None
        assert result.duration_seconds == 0.0

    def test_to_json(self):
        """测试 to_json 方法."""
        result = CIResult(
            status="completed",
            success=True,
            coverage=85.5,
            target_coverage=80.0,
        )

        json_str = result.to_json()
        data = json.loads(json_str)

        assert data["status"] == "completed"
        assert data["success"] is True
        assert data["coverage"] == 85.5
        assert data["target_coverage"] == 80.0

    def test_to_github_summary_success(self):
        """测试成功状态的 GitHub Summary."""
        result = CIResult(
            status="completed",
            success=True,
            coverage=85.5,
            target_coverage=80.0,
            generated_tests=[
                {"test_file_path": "/test/Test1.java"},
                {"test_file_path": "/test/Test2.java"},
            ],
            coverage_gaps=[
                {"file_path": "/src/Main.java", "line_number": 10},
            ],
        )

        summary = result.to_github_summary()

        assert "✅ Success" in summary
        assert "85.5%" in summary
        assert "80.0%" in summary
        assert "✅ Passed" in summary
        assert "/test/Test1.java" in summary
        assert "/src/Main.java:10" in summary

    def test_to_github_summary_failed(self):
        """测试失败状态的 GitHub Summary."""
        result = CIResult(
            status="failed",
            success=False,
            coverage=70.0,
            target_coverage=80.0,
        )

        summary = result.to_github_summary()

        assert "❌ Failed" in summary
        assert "⚠️ Below target" in summary

    def test_to_github_summary_with_mutations(self):
        """测试带变异测试结果的 GitHub Summary."""
        result = CIResult(
            status="completed",
            success=True,
            coverage=85.5,
            target_coverage=80.0,
            mutations={
                "mutation_coverage": 75.0,
                "killed": 30,
                "survived": 10,
            },
        )

        summary = result.to_github_summary()

        assert "Mutation Testing" in summary
        assert "75.0%" in summary
        assert "30" in summary
        assert "10" in summary

    def test_to_gitlab_comment(self):
        """测试 to_gitlab_comment 方法."""
        result = CIResult(status="completed", success=True)

        # GitLab 评论使用与 GitHub 相同的格式
        comment = result.to_gitlab_comment()
        summary = result.to_github_summary()

        assert comment == summary


class TestCIReporter:
    """CIReporter 测试."""

    def test_reporter_initialization_defaults(self):
        """测试 CIReporter 默认初始化."""
        reporter = CIReporter()

        assert reporter.output_format == "json"
        assert reporter.output_file is None
        assert reporter.fail_on_coverage is False
        assert reporter.github_output is False

    def test_reporter_initialization_custom(self):
        """测试 CIReporter 自定义初始化."""
        output_file = Path("/tmp/output.json")
        reporter = CIReporter(
            output_format="markdown",
            output_file=output_file,
            fail_on_coverage=True,
            github_output=True,
        )

        assert reporter.output_format == "markdown"
        assert reporter.output_file == output_file
        assert reporter.fail_on_coverage is True
        assert reporter.github_output is True

    def test_create_result(self):
        """测试 create_result 方法."""
        reporter = CIReporter()

        result = reporter.create_result(
            status="completed",
            success=True,
            coverage=85.5,
            target_coverage=80.0,
            generated_tests=[{"test_file_path": "/test/Test.java"}],
            error=None,
        )

        assert result.status == "completed"
        assert result.success is True
        assert result.coverage == 85.5
        assert result.duration_seconds >= 0.0

    def test_create_result_with_duration(self):
        """测试 create_result 计算持续时间."""
        import time

        reporter = CIReporter()
        time.sleep(0.1)  # 等待一小段时间

        result = reporter.create_result(status="test", success=True)

        assert result.duration_seconds >= 0.1

    def test_format_output_json(self):
        """测试 JSON 格式输出."""
        reporter = CIReporter(output_format="json")
        result = CIResult(status="test", success=True, coverage=85.5)

        output = reporter._format_output(result)
        data = json.loads(output)

        assert data["coverage"] == 85.5

    def test_format_output_markdown(self):
        """测试 Markdown 格式输出."""
        reporter = CIReporter(output_format="markdown")
        result = CIResult(status="test", success=True)

        output = reporter._format_output(result)

        assert "## 🧪 UT-Agent" in output

    def test_format_output_md(self):
        """测试 MD 格式输出（与 markdown 相同）."""
        reporter = CIReporter(output_format="md")
        result = CIResult(status="test", success=True)

        output = reporter._format_output(result)

        assert "## 🧪 UT-Agent" in output

    def test_format_output_summary(self):
        """测试 Summary 格式输出."""
        reporter = CIReporter(output_format="summary")
        result = CIResult(
            status="completed",
            success=True,
            coverage=85.5,
            target_coverage=80.0,
            generated_tests=[{"test_file_path": "/test/Test.java"}],
        )

        output = reporter._format_output(result)

        assert "UT-Agent Summary" in output
        assert "85.5%" in output
        assert "completed" in output

    def test_format_output_unknown(self):
        """测试未知格式输出（默认 JSON）."""
        reporter = CIReporter(output_format="unknown")
        result = CIResult(status="test", success=True, coverage=85.5)

        output = reporter._format_output(result)
        data = json.loads(output)

        assert data["coverage"] == 85.5

    def test_format_summary(self):
        """测试 _format_summary 方法."""
        reporter = CIReporter()
        result = CIResult(
            status="completed",
            success=True,
            coverage=85.5,
            target_coverage=80.0,
            generated_tests=[{}, {}],
            coverage_gaps=[{}],
        )

        output = reporter._format_summary(result)

        assert "UT-Agent Summary" in output
        assert "85.5%" in output
        assert "Target: 80.0%" in output
        assert "Generated Tests: 2" in output
        assert "Coverage Gaps: 1" in output

    def test_format_summary_with_error(self):
        """测试带错误的 summary."""
        reporter = CIReporter()
        result = CIResult(
            status="failed",
            success=False,
            error="Something went wrong",
        )

        output = reporter._format_summary(result)

        assert "Error: Something went wrong" in output

    def test_get_exit_code_success(self):
        """测试成功状态的退出码."""
        reporter = CIReporter()
        result = CIResult(status="completed", success=True)

        exit_code = reporter._get_exit_code(result)

        assert exit_code == ExitCode.SUCCESS.value

    def test_get_exit_code_failed(self):
        """测试失败状态的退出码."""
        reporter = CIReporter()
        result = CIResult(status="failed", success=False)

        exit_code = reporter._get_exit_code(result)

        assert exit_code == ExitCode.TEST_GENERATION_FAILED.value

    def test_get_exit_code_coverage_below_target(self):
        """测试覆盖率低于目标的退出码."""
        reporter = CIReporter(fail_on_coverage=True)
        result = CIResult(
            status="completed",
            success=True,
            coverage=70.0,
            target_coverage=80.0,
        )

        exit_code = reporter._get_exit_code(result)

        assert exit_code == ExitCode.COVERAGE_BELOW_TARGET.value

    def test_get_exit_code_coverage_pass(self):
        """测试覆盖率达标的退出码."""
        reporter = CIReporter(fail_on_coverage=True)
        result = CIResult(
            status="completed",
            success=True,
            coverage=85.0,
            target_coverage=80.0,
        )

        exit_code = reporter._get_exit_code(result)

        assert exit_code == ExitCode.SUCCESS.value

    def test_report_to_stdout(self, capsys):
        """测试输出到 stdout."""
        reporter = CIReporter()
        result = CIResult(status="test", success=True)

        reporter.report(result)

        captured = capsys.readouterr()
        assert "test" in captured.out

    def test_report_to_file(self):
        """测试输出到文件."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            output_file = Path(f.name)

        try:
            reporter = CIReporter(output_file=output_file)
            result = CIResult(status="test", success=True, coverage=85.5)

            reporter.report(result)

            content = output_file.read_text(encoding="utf-8")
            data = json.loads(content)
            assert data["coverage"] == 85.5
        finally:
            output_file.unlink(missing_ok=True)

    def test_write_github_output(self, tmp_path):
        """测试写入 GitHub 输出."""
        github_output = tmp_path / "github_output.txt"
        github_output.write_text("", encoding="utf-8")

        env = os.environ.copy()
        env["GITHUB_OUTPUT"] = str(github_output)
        env.pop("GITHUB_STEP_SUMMARY", None)

        with patch.dict(os.environ, env, clear=True):
            reporter = CIReporter(github_output=True)
            result = CIResult(
                status="completed",
                success=True,
                coverage=85.5,
                generated_tests=[{}, {}, {}],
            )

            reporter._write_github_output(result)

            content = github_output.read_text(encoding="utf-8")
            assert "coverage=85.5" in content
            assert "success=true" in content
            assert "generated_tests=3" in content

    def test_write_github_step_summary(self, tmp_path):
        """测试写入 GitHub Step Summary."""
        github_summary = tmp_path / "github_summary.md"
        github_summary.write_text("", encoding="utf-8")

        env = os.environ.copy()
        env["GITHUB_STEP_SUMMARY"] = str(github_summary)
        env.pop("GITHUB_OUTPUT", None)

        with patch.dict(os.environ, env, clear=True):
            reporter = CIReporter(github_output=True)
            result = CIResult(status="completed", success=True)

            reporter._write_github_output(result)

            content = github_summary.read_text(encoding="utf-8")
            assert "## 🧪 UT-Agent" in content
