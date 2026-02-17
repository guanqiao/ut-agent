"""GitLab CI 集成测试."""

import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any, List, Optional

from ut_agent.ci.gitlab_ci import (
    GitLabCIJob,
    GitLabCIStage,
    GitLabCIConfig,
    GitLabCIGenerator,
    GitLabMRReporter,
    GitLabPipelineTrigger,
)


class TestGitLabCIJob:
    """GitLab CI 任务测试."""

    def test_job_creation(self):
        """测试任务创建."""
        job = GitLabCIJob(
            name="test",
            script=["pytest tests/"],
        )
        
        assert job.name == "test"
        assert job.script == ["pytest tests/"]
        
    def test_job_with_stage(self):
        """测试带阶段的任务."""
        job = GitLabCIJob(
            name="lint",
            stage="validate",
            script=["flake8 src/"],
        )
        
        assert job.stage == "validate"
        
    def test_job_to_dict(self):
        """测试任务序列化."""
        job = GitLabCIJob(
            name="build",
            stage="build",
            script=["make build"],
            image="python:3.12",
        )
        
        data = job.to_dict()
        
        assert data["script"] == ["make build"]
        assert data["stage"] == "build"
        assert data["image"] == "python:3.12"


class TestGitLabCIStage:
    """GitLab CI 阶段测试."""

    def test_stage_creation(self):
        """测试阶段创建."""
        stage = GitLabCIStage(name="test")
        
        assert stage.name == "test"
        assert stage.jobs == []
        
    def test_add_job(self):
        """测试添加任务."""
        stage = GitLabCIStage(name="build")
        
        job = GitLabCIJob(name="compile", script=["make"])
        stage.add_job(job)
        
        assert len(stage.jobs) == 1
        assert stage.jobs[0].name == "compile"


class TestGitLabCIConfig:
    """GitLab CI 配置测试."""

    def test_config_creation(self):
        """测试配置创建."""
        config = GitLabCIConfig()
        
        assert config.stages == []
        assert config.jobs == {}
        
    def test_add_stage(self):
        """测试添加阶段."""
        config = GitLabCIConfig()
        
        stage = GitLabCIStage(name="test")
        config.add_stage(stage)
        
        assert len(config.stages) == 1
        assert "test" in config.stages
        
    def test_add_job(self):
        """测试添加任务."""
        config = GitLabCIConfig()
        
        job = GitLabCIJob(name="pytest", script=["pytest"])
        config.add_job(job)
        
        assert "pytest" in config.jobs
        
    def test_to_yaml(self):
        """测试生成 YAML."""
        config = GitLabCIConfig()
        config.stages = ["build", "test"]
        
        job = GitLabCIJob(name="pytest", stage="test", script=["pytest"])
        config.add_job(job)
        
        yaml_content = config.to_yaml()
        
        assert "stages:" in yaml_content
        assert "pytest:" in yaml_content
        assert "pytest" in yaml_content


class TestGitLabCIGenerator:
    """GitLab CI 生成器测试."""

    @pytest.fixture
    def generator(self):
        """创建生成器实例."""
        return GitLabCIGenerator()
        
    def test_generate_python_test_config(self, generator):
        """测试生成 Python 测试配置."""
        config = generator.generate_python_test_config(
            python_versions=["3.10", "3.11", "3.12"],
        )
        
        assert "test" in config.stages
        assert len(config.jobs) > 0
        
    def test_generate_coverage_config(self, generator):
        """测试生成覆盖率配置."""
        config = generator.generate_coverage_config(min_coverage=80)
        
        yaml_content = config.to_yaml()
        assert "coverage" in yaml_content.lower() or "80" in yaml_content
        
    def test_save_config(self, generator, tmp_path):
        """测试保存配置."""
        config = generator.generate_python_test_config()
        
        output_path = tmp_path / ".gitlab-ci.yml"
        
        result = generator.save_config(config, str(output_path))
        
        assert result is True
        assert output_path.exists()


class TestGitLabMRReporter:
    """GitLab MR 报告器测试."""

    @pytest.fixture
    def reporter(self):
        """创建报告器实例."""
        return GitLabMRReporter(
            token="test-token",
            project_id="12345",
        )
        
    def test_format_test_report(self, reporter):
        """测试格式化测试报告."""
        results = {
            "passed": 50,
            "failed": 2,
            "total": 52,
        }
        
        report = reporter.format_test_report(results)
        
        assert "50" in report or "passed" in report.lower()
        
    @patch('requests.post')
    def test_post_mr_comment(self, mock_post, reporter):
        """测试发布 MR 评论."""
        mock_post.return_value = Mock(status_code=201)
        
        result = reporter.post_mr_comment(
            mr_iid=42,
            body="Test comment",
        )
        
        assert result is True


class TestGitLabPipelineTrigger:
    """GitLab 流水线触发器测试."""

    @pytest.fixture
    def trigger(self):
        """创建触发器实例."""
        return GitLabPipelineTrigger(
            token="trigger-token",
            project_id="12345",
        )
        
    @patch('requests.post')
    def test_trigger_pipeline(self, mock_post, trigger):
        """测试触发流水线."""
        mock_post.return_value = Mock(
            status_code=201,
            json=lambda: {"id": 123, "status": "pending"},
        )
        
        result = trigger.trigger_pipeline(ref="main")
        
        assert result is not None
        assert result["status"] == "pending"


class TestGitLabCIIntegration:
    """GitLab CI 集成测试."""

    def test_full_config_generation(self):
        """测试完整配置生成."""
        generator = GitLabCIGenerator()
        
        config = generator.generate_python_test_config(
            python_versions=["3.10", "3.11", "3.12"],
        )
        
        yaml_content = config.to_yaml()
        
        assert "stages:" in yaml_content
        assert len(config.jobs) > 0
