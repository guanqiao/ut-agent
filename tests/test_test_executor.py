"""测试执行模块单元测试."""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ut_agent.tools.test_executor import (
    check_java_environment,
    check_maven_environment,
    check_node_environment,
    execute_frontend_tests,
    execute_java_tests,
    has_script,
    run_tests_with_coverage,
)


class TestExecuteJavaTests:
    """Java 测试执行测试."""

    @patch("ut_agent.tools.test_executor.subprocess.run")
    def test_execute_java_tests_maven_success(self, mock_run):
        """测试 Maven 测试执行成功."""
        mock_run.return_value = Mock(returncode=0, stdout="Tests run: 10", stderr="")

        success, message = execute_java_tests("/project", "maven")

        assert success is True
        assert "成功" in message or "Tests run" in message
        mock_run.assert_called_once()
        args = mock_run.call_args
        assert args[0][0] == ["mvn", "test", "-q"]

    @patch("ut_agent.tools.test_executor.subprocess.run")
    def test_execute_java_tests_gradle_success(self, mock_run):
        """测试 Gradle 测试执行成功."""
        mock_run.return_value = Mock(returncode=0, stdout="BUILD SUCCESS", stderr="")

        success, message = execute_java_tests("/project", "gradle")

        assert success is True
        mock_run.assert_called_once()
        args = mock_run.call_args
        assert args[0][0] == ["gradle", "test", "-q"]

    @patch("ut_agent.tools.test_executor.subprocess.run")
    def test_execute_java_tests_failure(self, mock_run):
        """测试 Java 测试执行失败."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Test failed")

        success, message = execute_java_tests("/project", "maven")

        assert success is False
        assert "失败" in message or "Test failed" in message

    @patch("ut_agent.tools.test_executor.subprocess.run")
    def test_execute_java_tests_timeout(self, mock_run):
        """测试 Java 测试执行超时."""
        from ut_agent.exceptions import TimeoutError
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="mvn", timeout=300)

        with pytest.raises(TimeoutError):
            execute_java_tests("/project", "maven")

    @patch("ut_agent.tools.test_executor.subprocess.run")
    def test_execute_java_tests_command_not_found(self, mock_run):
        """测试 Maven 命令未找到."""
        from ut_agent.exceptions import ProjectDetectionError
        mock_run.side_effect = FileNotFoundError("mvn")

        with pytest.raises(ProjectDetectionError):
            execute_java_tests("/project", "maven")

    def test_execute_java_tests_unsupported_tool(self):
        """测试不支持的构建工具."""
        success, message = execute_java_tests("/project", "ant")

        assert success is False
        assert "不支持" in message


class TestExecuteFrontendTests:
    """前端测试执行测试."""

    @patch("ut_agent.tools.test_executor.subprocess.run")
    def test_execute_frontend_tests_npm_success(self, mock_run):
        """测试 npm 测试执行成功."""
        mock_run.return_value = Mock(returncode=0, stdout="Test passed", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建 package-lock.json
            Path(tmpdir, "package-lock.json").write_text("{}")

            success, message = execute_frontend_tests(tmpdir)

            assert success is True
            mock_run.assert_called_once()

    @patch("ut_agent.tools.test_executor.subprocess.run")
    def test_execute_frontend_tests_yarn(self, mock_run):
        """测试 yarn 测试执行."""
        mock_run.return_value = Mock(returncode=0, stdout="Test passed", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "yarn.lock").write_text("")

            success, message = execute_frontend_tests(tmpdir)

            assert success is True
            args = mock_run.call_args
            assert "yarn" in args[0][0]

    @patch("ut_agent.tools.test_executor.subprocess.run")
    def test_execute_frontend_tests_pnpm(self, mock_run):
        """测试 pnpm 测试执行."""
        mock_run.return_value = Mock(returncode=0, stdout="Test passed", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "pnpm-lock.yaml").write_text("")

            success, message = execute_frontend_tests(tmpdir)

            assert success is True
            args = mock_run.call_args
            assert "pnpm" in args[0][0]

    @patch("ut_agent.tools.test_executor.subprocess.run")
    def test_execute_frontend_tests_with_vitest(self, mock_run):
        """测试 Vitest 配置检测."""
        mock_run.return_value = Mock(returncode=0, stdout="Test passed", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "package-lock.json").write_text("{}")
            Path(tmpdir, "vitest.config.ts").write_text("")

            success, message = execute_frontend_tests(tmpdir)

            assert success is True

    @patch("ut_agent.tools.test_executor.subprocess.run")
    def test_execute_frontend_tests_failure(self, mock_run):
        """测试前端测试执行失败."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Test error")

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "package-lock.json").write_text("{}")

            success, message = execute_frontend_tests(tmpdir)

            assert success is False


class TestHasScript:
    """package.json 脚本检查测试."""

    def test_has_script_exists(self):
        """测试脚本存在."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package = {
                "scripts": {
                    "test": "jest",
                    "test:coverage": "jest --coverage",
                }
            }
            Path(tmpdir, "package.json").write_text(json.dumps(package))

            assert has_script(Path(tmpdir), "test") is True
            assert has_script(Path(tmpdir), "test:coverage") is True

    def test_has_script_not_exists(self):
        """测试脚本不存在."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package = {"scripts": {"build": "tsc"}}
            Path(tmpdir, "package.json").write_text(json.dumps(package))

            assert has_script(Path(tmpdir), "test") is False

    def test_has_script_no_package_json(self):
        """测试 package.json 不存在."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assert has_script(Path(tmpdir), "test") is False

    def test_has_script_invalid_json(self):
        """测试无效的 JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "package.json").write_text("invalid json")

            assert has_script(Path(tmpdir), "test") is False


class TestRunTestsWithCoverage:
    """覆盖率测试执行测试."""

    @patch("ut_agent.tools.test_executor.subprocess.run")
    def test_run_java_tests_with_coverage_maven(self, mock_run):
        """测试 Maven Java 覆盖率测试."""
        mock_run.return_value = Mock(returncode=0, stdout="Coverage report generated", stderr="")

        success, message = run_tests_with_coverage("/project", "java", "maven")

        assert success is True
        mock_run.assert_called_once()
        args = mock_run.call_args
        assert "jacoco:report" in args[0][0]

    @patch("ut_agent.tools.test_executor.subprocess.run")
    def test_run_java_tests_with_coverage_gradle(self, mock_run):
        """测试 Gradle Java 覆盖率测试."""
        mock_run.return_value = Mock(returncode=0, stdout="Coverage report generated", stderr="")

        success, message = run_tests_with_coverage("/project", "java", "gradle")

        assert success is True
        args = mock_run.call_args
        assert "jacocoTestReport" in args[0][0]

    @patch("ut_agent.tools.test_executor.subprocess.run")
    def test_run_frontend_tests_with_coverage(self, mock_run):
        """测试前端覆盖率测试."""
        mock_run.return_value = Mock(returncode=0, stdout="Coverage report", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "package-lock.json").write_text("{}")

            success, message = run_tests_with_coverage(tmpdir, "vue")

            assert success is True

    def test_run_tests_unsupported_project_type(self):
        """测试不支持的项目类型."""
        success, message = run_tests_with_coverage("/project", "ruby")

        assert success is False
        assert "不支持" in message


class TestCheckJavaEnvironment:
    """Java 环境检查测试."""

    @patch("ut_agent.tools.test_executor.subprocess.run")
    def test_check_java_environment_success(self, mock_run):
        """测试 Java 环境检查成功."""
        mock_run.return_value = Mock(returncode=0, stdout="java version 17", stderr="")

        success, message = check_java_environment()

        assert success is True
        assert "正常" in message

    @patch("ut_agent.tools.test_executor.subprocess.run")
    def test_check_java_environment_not_found(self, mock_run):
        """测试 Java 未安装."""
        mock_run.side_effect = FileNotFoundError("java")

        success, message = check_java_environment()

        assert success is False
        assert "未找到" in message


class TestCheckMavenEnvironment:
    """Maven 环境检查测试."""

    @patch("ut_agent.tools.test_executor.subprocess.run")
    def test_check_maven_environment_success(self, mock_run):
        """测试 Maven 环境检查成功."""
        mock_run.return_value = Mock(returncode=0, stdout="Apache Maven 3.8", stderr="")

        success, message = check_maven_environment()

        assert success is True
        assert "正常" in message

    @patch("ut_agent.tools.test_executor.subprocess.run")
    def test_check_maven_environment_not_found(self, mock_run):
        """测试 Maven 未安装."""
        mock_run.side_effect = FileNotFoundError("mvn")

        success, message = check_maven_environment()

        assert success is False
        assert "未找到" in message


class TestCheckNodeEnvironment:
    """Node.js 环境检查测试."""

    @patch("ut_agent.tools.test_executor.subprocess.run")
    def test_check_node_environment_success(self, mock_run):
        """测试 Node.js 环境检查成功."""
        mock_run.return_value = Mock(returncode=0, stdout="v18.0.0", stderr="")

        success, message = check_node_environment()

        assert success is True
        assert "正常" in message
        assert "v18.0.0" in message

    @patch("ut_agent.tools.test_executor.subprocess.run")
    def test_check_node_environment_not_found(self, mock_run):
        """测试 Node.js 未安装."""
        mock_run.side_effect = FileNotFoundError("node")

        success, message = check_node_environment()

        assert success is False
        assert "未找到" in message
