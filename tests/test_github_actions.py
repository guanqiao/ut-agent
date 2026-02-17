"""GitHub Actions 集成测试."""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List, Optional

from ut_agent.ci.github_actions import (
    GitHubActionsWorkflow,
    WorkflowTrigger,
    WorkflowJob,
    WorkflowStep,
    GitHubActionsGenerator,
    GitHubCommentReporter,
    GitHubStatusReporter,
)


class TestWorkflowTrigger:
    """工作流触发器测试."""

    def test_trigger_creation(self):
        """测试触发器创建."""
        trigger = WorkflowTrigger(
            event="push",
            branches=["main", "develop"],
        )
        
        assert trigger.event == "push"
        assert trigger.branches == ["main", "develop"]
        
    def test_trigger_to_dict(self):
        """测试触发器序列化."""
        trigger = WorkflowTrigger(
            event="pull_request",
            branches=["main"],
            paths=["src/**", "tests/**"],
        )
        
        data = trigger.to_dict()
        
        assert data["event"] == "pull_request"
        assert data["branches"] == ["main"]
        assert data["paths"] == ["src/**", "tests/**"]


class TestWorkflowStep:
    """工作流步骤测试."""

    def test_step_creation(self):
        """测试步骤创建."""
        step = WorkflowStep(
            name="Checkout code",
            uses="actions/checkout@v4",
        )
        
        assert step.name == "Checkout code"
        assert step.uses == "actions/checkout@v4"
        
    def test_step_with_run(self):
        """测试带运行命令的步骤."""
        step = WorkflowStep(
            name="Run tests",
            run="pytest tests/",
            env={"PYTHONPATH": "."},
        )
        
        assert step.run == "pytest tests/"
        assert step.env == {"PYTHONPATH": "."}
        
    def test_step_to_dict(self):
        """测试步骤序列化."""
        step = WorkflowStep(
            name="Setup Python",
            uses="actions/setup-python@v5",
            with_={"python-version": "3.12"},
        )
        
        data = step.to_dict()
        
        assert data["name"] == "Setup Python"
        assert data["uses"] == "actions/setup-python@v5"
        assert data["with"]["python-version"] == "3.12"


class TestWorkflowJob:
    """工作流任务测试."""

    def test_job_creation(self):
        """测试任务创建."""
        job = WorkflowJob(
            name="test",
            runs_on="ubuntu-latest",
        )
        
        assert job.name == "test"
        assert job.runs_on == "ubuntu-latest"
        assert job.steps == []
        
    def test_add_step(self):
        """测试添加步骤."""
        job = WorkflowJob(name="test", runs_on="ubuntu-latest")
        
        step = WorkflowStep(name="Checkout", uses="actions/checkout@v4")
        job.add_step(step)
        
        assert len(job.steps) == 1
        assert job.steps[0].name == "Checkout"
        
    def test_job_to_dict(self):
        """测试任务序列化."""
        job = WorkflowJob(name="build", runs_on="ubuntu-latest")
        job.add_step(WorkflowStep(name="Build", run="make build"))
        
        data = job.to_dict()
        
        assert data["name"] == "build"
        assert data["runs-on"] == "ubuntu-latest"
        assert len(data["steps"]) == 1


class TestGitHubActionsWorkflow:
    """GitHub Actions 工作流测试."""

    def test_workflow_creation(self):
        """测试工作流创建."""
        workflow = GitHubActionsWorkflow(
            name="CI",
            on_events=["push", "pull_request"],
        )
        
        assert workflow.name == "CI"
        assert workflow.on_events == ["push", "pull_request"]
        assert workflow.jobs == {}
        
    def test_add_job(self):
        """测试添加任务."""
        workflow = GitHubActionsWorkflow(name="CI")
        
        job = WorkflowJob(name="test", runs_on="ubuntu-latest")
        workflow.add_job("test", job)
        
        assert "test" in workflow.jobs
        assert workflow.jobs["test"].name == "test"
        
    def test_to_yaml(self):
        """测试生成 YAML."""
        workflow = GitHubActionsWorkflow(
            name="Test Workflow",
            on_events=["push"],
        )
        
        job = WorkflowJob(name="test", runs_on="ubuntu-latest")
        job.add_step(WorkflowStep(name="Checkout", uses="actions/checkout@v4"))
        workflow.add_job("test", job)
        
        yaml_content = workflow.to_yaml()
        
        assert "name: Test Workflow" in yaml_content
        assert "on:" in yaml_content
        assert "jobs:" in yaml_content
        assert "checkout@v4" in yaml_content


class TestGitHubActionsGenerator:
    """GitHub Actions 生成器测试."""

    @pytest.fixture
    def generator(self):
        """创建生成器实例."""
        return GitHubActionsGenerator()
        
    def test_generator_initialization(self):
        """测试生成器初始化."""
        generator = GitHubActionsGenerator()
        
        assert generator is not None
        
    def test_generate_python_test_workflow(self, generator):
        """测试生成 Python 测试工作流."""
        workflow = generator.generate_python_test_workflow(
            python_versions=["3.10", "3.11", "3.12"],
            test_command="pytest tests/",
        )
        
        assert workflow.name == "Python Tests"
        assert "test" in workflow.jobs
        
        yaml_content = workflow.to_yaml()
        assert "3.10" in yaml_content
        assert "3.11" in yaml_content
        assert "3.12" in yaml_content
        assert "pytest" in yaml_content
        
    def test_generate_coverage_workflow(self, generator):
        """测试生成覆盖率工作流."""
        workflow = generator.generate_coverage_workflow(
            coverage_tool="pytest-cov",
            min_coverage=80,
        )
        
        assert workflow.name == "Coverage"
        
        yaml_content = workflow.to_yaml()
        assert "80" in yaml_content or "pytest-cov" in yaml_content
        
    def test_generate_lint_workflow(self, generator):
        """测试生成代码检查工作流."""
        workflow = generator.generate_lint_workflow(
            linters=["flake8", "black", "mypy"],
        )
        
        assert workflow.name == "Lint"
        
        yaml_content = workflow.to_yaml()
        assert "flake8" in yaml_content or "black" in yaml_content
        
    def test_generate_ut_agent_workflow(self, generator):
        """测试生成 UT-Agent 专用工作流."""
        workflow = generator.generate_ut_agent_workflow(
            generate_tests=True,
            analyze_quality=True,
        )
        
        assert "ut-agent" in workflow.name.lower() or "UT Agent" in workflow.name
        
        yaml_content = workflow.to_yaml()
        # 应该包含 UT-Agent 相关的步骤
        assert "pip install" in yaml_content or "pytest" in yaml_content
        
    def test_save_workflow(self, generator, tmp_path):
        """测试保存工作流."""
        workflow = generator.generate_python_test_workflow()
        
        output_path = tmp_path / ".github" / "workflows"
        output_path.mkdir(parents=True, exist_ok=True)
        
        result = generator.save_workflow(
            workflow=workflow,
            filename="test.yml",
            output_path=str(output_path),
        )
        
        assert result is True
        assert (output_path / "test.yml").exists()
        
    def test_validate_workflow(self, generator):
        """测试验证工作流."""
        workflow = GitHubActionsWorkflow(
            name="Test",
            on_events=["push"],
        )
        
        is_valid = generator.validate_workflow(workflow)
        
        # 空工作流应该无效（没有任务）
        assert is_valid is False
        
        # 添加任务后应该有效
        job = WorkflowJob(name="test", runs_on="ubuntu-latest")
        job.add_step(WorkflowStep(name="Test", run="echo test"))
        workflow.add_job("test", job)
        
        is_valid = generator.validate_workflow(workflow)
        assert is_valid is True


class TestGitHubCommentReporter:
    """GitHub 评论报告器测试."""

    @pytest.fixture
    def reporter(self):
        """创建报告器实例."""
        return GitHubCommentReporter(
            token="test-token",
            repository="owner/repo",
        )
        
    def test_reporter_initialization(self):
        """测试报告器初始化."""
        reporter = GitHubCommentReporter(
            token="test-token",
            repository="owner/repo",
        )
        
        assert reporter.token == "test-token"
        assert reporter.repository == "owner/repo"
        
    def test_format_test_report(self, reporter):
        """测试格式化测试报告."""
        results = {
            "passed": 50,
            "failed": 2,
            "skipped": 3,
            "total": 55,
            "duration": 120.5,
        }
        
        report = reporter.format_test_report(results)
        
        assert "50 passed" in report or "passed" in report.lower()
        assert "2 failed" in report or "failed" in report.lower()
        assert "120.5" in report or "duration" in report.lower()
        
    def test_format_coverage_report(self, reporter):
        """测试格式化覆盖率报告."""
        coverage = {
            "total": 85.5,
            "files": [
                {"name": "src/main.py", "coverage": 90.0},
                {"name": "src/utils.py", "coverage": 80.0},
            ],
        }
        
        report = reporter.format_coverage_report(coverage)
        
        assert "85.5" in report or "85" in report
        assert "coverage" in report.lower()
        
    @patch('requests.post')
    def test_post_comment(self, mock_post, reporter):
        """测试发布评论."""
        mock_post.return_value = Mock(
            status_code=201,
            json=lambda: {"id": 12345},
        )
        
        result = reporter.post_comment(
            pr_number=42,
            body="Test comment",
        )
        
        assert result is True
        mock_post.assert_called_once()
        
    @patch('requests.post')
    def test_post_comment_failure(self, mock_post, reporter):
        """测试发布评论失败."""
        mock_post.return_value = Mock(
            status_code=403,
            text="Forbidden",
        )
        
        result = reporter.post_comment(
            pr_number=42,
            body="Test comment",
        )
        
        assert result is False


class TestGitHubStatusReporter:
    """GitHub 状态报告器测试."""

    @pytest.fixture
    def reporter(self):
        """创建报告器实例."""
        return GitHubStatusReporter(
            token="test-token",
            repository="owner/repo",
        )
        
    def test_reporter_initialization(self):
        """测试报告器初始化."""
        reporter = GitHubStatusReporter(
            token="test-token",
            repository="owner/repo",
        )
        
        assert reporter.token == "test-token"
        assert reporter.repository == "owner/repo"
        
    @patch('requests.post')
    def test_set_status_success(self, mock_post, reporter):
        """测试设置成功状态."""
        mock_post.return_value = Mock(status_code=201)
        
        result = reporter.set_status(
            sha="abc123",
            state="success",
            context="ci/tests",
            description="All tests passed",
        )
        
        assert result is True
        mock_post.assert_called_once()
        
    @patch('requests.post')
    def test_set_status_failure(self, mock_post, reporter):
        """测试设置失败状态."""
        mock_post.return_value = Mock(status_code=201)
        
        result = reporter.set_status(
            sha="abc123",
            state="failure",
            context="ci/tests",
            description="Tests failed",
        )
        
        assert result is True
        
    @patch('requests.post')
    def test_set_status_error(self, mock_post, reporter):
        """测试设置错误状态."""
        mock_post.return_value = Mock(status_code=403)
        
        result = reporter.set_status(
            sha="abc123",
            state="error",
            context="ci/tests",
            description="Error running tests",
        )
        
        assert result is False


class TestGitHubActionsIntegration:
    """GitHub Actions 集成测试."""

    def test_full_workflow_generation(self):
        """测试完整工作流生成."""
        generator = GitHubActionsGenerator()
        
        # 生成多个工作流
        test_workflow = generator.generate_python_test_workflow(
            python_versions=["3.10", "3.11", "3.12"],
        )
        coverage_workflow = generator.generate_coverage_workflow(min_coverage=80)
        lint_workflow = generator.generate_lint_workflow()
        
        # 验证所有工作流
        assert generator.validate_workflow(test_workflow) is True
        assert generator.validate_workflow(coverage_workflow) is True
        assert generator.validate_workflow(lint_workflow) is True
        
        # 验证 YAML 内容
        test_yaml = test_workflow.to_yaml()
        assert "on:" in test_yaml
        assert "jobs:" in test_yaml
        
    def test_workflow_with_matrix(self):
        """测试带矩阵的工作流."""
        generator = GitHubActionsGenerator()
        
        workflow = generator.generate_python_test_workflow(
            python_versions=["3.9", "3.10", "3.11", "3.12"],
            os_versions=["ubuntu-latest", "windows-latest", "macos-latest"],
        )
        
        yaml_content = workflow.to_yaml()
        
        # 应该包含矩阵配置
        assert "matrix" in yaml_content or "strategy" in yaml_content
        
    def test_pr_comment_integration(self):
        """测试 PR 评论集成."""
        reporter = GitHubCommentReporter(
            token="test-token",
            repository="owner/repo",
        )
        
        # 格式化测试报告
        test_results = {
            "passed": 100,
            "failed": 0,
            "skipped": 5,
            "total": 105,
            "duration": 60.0,
        }
        
        report = reporter.format_test_report(test_results)
        
        # 报告应该包含关键信息
        assert "passed" in report.lower()
        assert "100" in report
        
    def test_status_check_integration(self):
        """测试状态检查集成."""
        reporter = GitHubStatusReporter(
            token="test-token",
            repository="owner/repo",
        )
        
        # 验证状态上下文格式
        context = reporter._format_context("test", "python-3.12")
        
        assert "test" in context
        assert "python" in context.lower()
