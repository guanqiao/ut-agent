"""Prompt 版本管理测试."""

import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
from typing import Dict, Any, List, Optional

from ut_agent.ai.prompt_versioning import (
    PromptVersion,
    PromptTemplate,
    PromptVersionManager,
    PromptABTest,
    PromptPerformanceTracker,
)


class TestPromptVersion:
    """Prompt 版本测试."""

    def test_version_creation(self):
        """测试版本创建."""
        version = PromptVersion(
            version_id="v1.0.0",
            content="Generate test for {function_name}",
            description="Initial version",
        )
        
        assert version.version_id == "v1.0.0"
        assert version.content == "Generate test for {function_name}"
        assert version.description == "Initial version"
        assert version.created_at is not None
        
    def test_version_to_dict(self):
        """测试版本序列化."""
        version = PromptVersion(
            version_id="v1.0.0",
            content="Test content",
            description="Test description",
            metadata={"author": "test"},
        )
        
        data = version.to_dict()
        
        assert data["version_id"] == "v1.0.0"
        assert data["content"] == "Test content"
        assert data["metadata"]["author"] == "test"


class TestPromptTemplate:
    """Prompt 模板测试."""

    def test_template_creation(self):
        """测试模板创建."""
        template = PromptTemplate(
            name="test_generator",
            description="Generate unit tests",
        )
        
        assert template.name == "test_generator"
        assert template.description == "Generate unit tests"
        assert template.versions == []
        
    def test_add_version(self):
        """测试添加版本."""
        template = PromptTemplate(name="test_generator")
        
        version = PromptVersion(
            version_id="v1.0.0",
            content="Generate test",
        )
        template.add_version(version)
        
        assert len(template.versions) == 1
        assert template.current_version == "v1.0.0"
        
    def test_get_version(self):
        """测试获取版本."""
        template = PromptTemplate(name="test_generator")
        
        version = PromptVersion(version_id="v1.0.0", content="Test")
        template.add_version(version)
        
        retrieved = template.get_version("v1.0.0")
        
        assert retrieved is not None
        assert retrieved.version_id == "v1.0.0"
        
    def test_render(self):
        """测试渲染模板."""
        template = PromptTemplate(name="test_generator")
        
        version = PromptVersion(
            version_id="v1.0.0",
            content="Generate test for {function_name} in {language}",
        )
        template.add_version(version)
        
        rendered = template.render(
            function_name="add",
            language="python",
        )
        
        assert "add" in rendered
        assert "python" in rendered


class TestPromptVersionManager:
    """Prompt 版本管理器测试."""

    @pytest.fixture
    def manager(self):
        """创建管理器实例."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield PromptVersionManager(storage_path=tmpdir)
            
    def test_manager_initialization(self):
        """测试管理器初始化."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = PromptVersionManager(storage_path=tmpdir)
            
            assert manager is not None
            assert manager.templates == {}
            
    def test_create_template(self, manager):
        """测试创建模板."""
        template = manager.create_template(
            name="test_gen",
            description="Test generator",
        )
        
        assert template.name == "test_gen"
        assert "test_gen" in manager.templates
        
    def test_add_version(self, manager):
        """测试添加版本."""
        manager.create_template(name="test_gen")
        
        version = manager.add_version(
            template_name="test_gen",
            content="Generate test for {func}",
            description="Version 1",
        )
        
        assert version.version_id is not None
        assert len(manager.templates["test_gen"].versions) == 1
        
    def test_get_template(self, manager):
        """测试获取模板."""
        manager.create_template(name="test_gen")
        
        template = manager.get_template("test_gen")
        
        assert template is not None
        assert template.name == "test_gen"
        
    def test_list_templates(self, manager):
        """测试列出所有模板."""
        manager.create_template(name="template1")
        manager.create_template(name="template2")
        
        templates = manager.list_templates()
        
        assert len(templates) == 2
        assert "template1" in templates
        assert "template2" in templates
        
    def test_rollback_version(self, manager):
        """测试回滚版本."""
        manager.create_template(name="test_gen")
        
        v1 = manager.add_version(
            template_name="test_gen",
            content="Version 1",
            description="First",
        )
        v2 = manager.add_version(
            template_name="test_gen",
            content="Version 2",
            description="Second",
        )
        
        result = manager.rollback_version("test_gen", v1.version_id)
        
        assert result is True
        assert manager.templates["test_gen"].current_version == v1.version_id


class TestPromptABTest:
    """Prompt A/B 测试测试."""

    @pytest.fixture
    def ab_test(self):
        """创建 A/B 测试实例."""
        return PromptABTest(
            test_name="quality_test",
            template_name="test_gen",
            version_a="v1.0.0",
            version_b="v1.1.0",
        )
        
    def test_ab_test_creation(self):
        """测试 A/B 测试创建."""
        test = PromptABTest(
            test_name="quality_test",
            template_name="test_gen",
            version_a="v1.0.0",
            version_b="v1.1.0",
        )
        
        assert test.test_name == "quality_test"
        assert test.version_a == "v1.0.0"
        assert test.version_b == "v1.1.0"
        
    def test_record_result(self, ab_test):
        """测试记录结果."""
        ab_test.record_result(
            version="v1.0.0",
            metric="quality_score",
            value=0.85,
        )
        
        assert "v1.0.0" in ab_test.results
        assert ab_test.results["v1.0.0"]["quality_score"] == 0.85
        
    def test_get_winner(self, ab_test):
        """测试获取获胜版本."""
        ab_test.record_result("v1.0.0", "score", 0.8)
        ab_test.record_result("v1.1.0", "score", 0.9)
        
        winner = ab_test.get_winner(metric="score")
        
        assert winner == "v1.1.0"


class TestPromptPerformanceTracker:
    """Prompt 性能追踪器测试."""

    @pytest.fixture
    def tracker(self):
        """创建追踪器实例."""
        return PromptPerformanceTracker()
        
    def test_tracker_initialization(self):
        """测试追踪器初始化."""
        tracker = PromptPerformanceTracker()
        
        assert tracker is not None
        assert tracker.metrics == {}
        
    def test_record_metric(self, tracker):
        """测试记录指标."""
        tracker.record_metric(
            template_name="test_gen",
            version_id="v1.0.0",
            metric_name="success_rate",
            value=0.95,
        )
        
        assert "test_gen" in tracker.metrics
        assert "v1.0.0" in tracker.metrics["test_gen"]
        
    def test_get_average_metric(self, tracker):
        """测试获取平均指标."""
        tracker.record_metric("test_gen", "v1.0.0", "score", 0.8)
        tracker.record_metric("test_gen", "v1.0.0", "score", 0.9)
        tracker.record_metric("test_gen", "v1.0.0", "score", 0.85)
        
        avg = tracker.get_average_metric("test_gen", "v1.0.0", "score")
        
        assert avg == pytest.approx(0.85, 0.01)
        
    def test_compare_versions(self, tracker):
        """测试比较版本."""
        tracker.record_metric("test_gen", "v1.0.0", "quality", 0.8)
        tracker.record_metric("test_gen", "v1.1.0", "quality", 0.9)
        
        comparison = tracker.compare_versions(
            template_name="test_gen",
            version_a="v1.0.0",
            version_b="v1.1.0",
            metric="quality",
        )
        
        assert comparison["improvement"] > 0


class TestPromptVersioningIntegration:
    """Prompt 版本管理集成测试."""

    def test_full_workflow(self):
        """测试完整工作流."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = PromptVersionManager(storage_path=tmpdir)
            
            # 1. 创建模板
            template = manager.create_template(
                name="test_generator",
                description="Generate unit tests",
            )
            
            # 2. 添加多个版本
            v1 = manager.add_version(
                template_name="test_generator",
                content="Generate test for {function}",
                description="Basic version",
            )
            
            v2 = manager.add_version(
                template_name="test_generator",
                content="Generate comprehensive test for {function} with edge cases",
                description="Improved version",
            )
            
            # 3. 渲染模板
            rendered = manager.render_template(
                template_name="test_generator",
                function="add",
            )
            
            assert "add" in rendered
            
            # 4. 创建 A/B 测试
            ab_test = PromptABTest(
                test_name="quality_comparison",
                template_name="test_generator",
                version_a=v1.version_id,
                version_b=v2.version_id,
            )
            
            # 5. 记录性能指标
            tracker = PromptPerformanceTracker()
            tracker.record_metric("test_generator", v1.version_id, "quality", 0.75)
            tracker.record_metric("test_generator", v2.version_id, "quality", 0.90)
            
            # 6. 比较版本
            comparison = tracker.compare_versions(
                "test_generator", v1.version_id, v2.version_id, "quality"
            )
            
            assert comparison["improvement"] > 0
            
    def test_version_rollback(self):
        """测试版本回滚."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = PromptVersionManager(storage_path=tmpdir)
            
            manager.create_template(name="generator")
            v1 = manager.add_version("generator", "Content 1", "First")
            v2 = manager.add_version("generator", "Content 2", "Second")
            
            # 回滚到 v1
            manager.rollback_version("generator", v1.version_id)
            
            template = manager.get_template("generator")
            assert template.current_version == v1.version_id
