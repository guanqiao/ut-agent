"""模型微调支持测试."""

import os
import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
from typing import Dict, Any, List, Optional

from ut_agent.ai.model_finetuning import (
    FinetuningJob,
    FinetuningStatus,
    FinetuningDataset,
    FinetuningManager,
    OpenAIFinetuningProvider,
    DatasetValidator,
)


class TestFinetuningStatus:
    """微调状态测试."""

    def test_status_values(self):
        """测试状态枚举值."""
        assert FinetuningStatus.PENDING.value == "pending"
        assert FinetuningStatus.RUNNING.value == "running"
        assert FinetuningStatus.COMPLETED.value == "completed"
        assert FinetuningStatus.FAILED.value == "failed"
        assert FinetuningStatus.CANCELLED.value == "cancelled"


class TestFinetuningJob:
    """微调任务测试."""

    def test_job_creation(self):
        """测试任务创建."""
        job = FinetuningJob(
            job_id="ft-123",
            model="gpt-3.5-turbo",
            training_file="file-123",
        )
        
        assert job.job_id == "ft-123"
        assert job.model == "gpt-3.5-turbo"
        assert job.training_file == "file-123"
        assert job.status == FinetuningStatus.PENDING
        
    def test_job_to_dict(self):
        """测试任务序列化."""
        job = FinetuningJob(
            job_id="ft-123",
            model="gpt-3.5-turbo",
            training_file="file-123",
            status=FinetuningStatus.RUNNING,
        )
        
        data = job.to_dict()
        
        assert data["job_id"] == "ft-123"
        assert data["status"] == "running"


class TestFinetuningDataset:
    """微调数据集测试."""

    def test_dataset_creation(self):
        """测试数据集创建."""
        dataset = FinetuningDataset(
            name="test_dataset",
            examples=[],
        )
        
        assert dataset.name == "test_dataset"
        assert dataset.examples == []
        
    def test_add_example(self):
        """测试添加示例."""
        dataset = FinetuningDataset(name="test")
        
        dataset.add_example(
            prompt="Generate test for add function",
            completion="def test_add(): ...",
        )
        
        assert len(dataset.examples) == 1
        assert dataset.examples[0]["prompt"] == "Generate test for add function"
        
    def test_to_jsonl(self):
        """测试转换为 JSONL."""
        dataset = FinetuningDataset(name="test")
        dataset.add_example("prompt1", "completion1")
        dataset.add_example("prompt2", "completion2")
        
        jsonl = dataset.to_jsonl()
        
        assert "prompt1" in jsonl
        assert "completion1" in jsonl
        assert "\n" in jsonl


class TestDatasetValidator:
    """数据集验证器测试."""

    @pytest.fixture
    def validator(self):
        """创建验证器实例."""
        return DatasetValidator()
        
    def test_validate_valid_dataset(self, validator):
        """测试验证有效数据集."""
        dataset = FinetuningDataset(name="test")
        dataset.add_example("prompt", "completion")
        
        is_valid, errors = validator.validate(dataset)
        
        assert is_valid is True
        assert errors == []
        
    def test_validate_empty_dataset(self, validator):
        """测试验证空数据集."""
        dataset = FinetuningDataset(name="test")
        
        is_valid, errors = validator.validate(dataset)
        
        assert is_valid is False
        assert len(errors) > 0
        
    def test_validate_missing_fields(self, validator):
        """测试验证缺少字段."""
        dataset = FinetuningDataset(name="test")
        dataset.examples.append({"prompt": "test"})  # 缺少 completion
        
        is_valid, errors = validator.validate(dataset)
        
        assert is_valid is False


class TestOpenAIFinetuningProvider:
    """OpenAI 微调提供者测试."""

    @pytest.fixture(autouse=True)
    def setup_openai_env(self, monkeypatch):
        """设置 OpenAI 环境变量."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")

    @pytest.fixture
    def provider(self):
        """创建提供者实例."""
        return OpenAIFinetuningProvider(api_key="test-key")
        
    def test_provider_initialization(self):
        """测试提供者初始化."""
        provider = OpenAIFinetuningProvider(api_key="test-key")
        
        assert provider.api_key == "test-key"
        
    @patch('openai.files.create')
    def test_upload_dataset(self, mock_create, provider):
        """测试上传数据集."""
        mock_create.return_value = Mock(id="file-123")
        
        dataset = FinetuningDataset(name="test")
        dataset.add_example("prompt", "completion")
        
        file_id = provider.upload_dataset(dataset)
        
        assert file_id == "file-123"
        
    @patch('openai.fine_tuning.jobs.create')
    def test_create_job(self, mock_create, provider):
        """测试创建微调任务."""
        mock_create.return_value = Mock(id="ft-123")
        
        job = provider.create_job(
            training_file="file-123",
            model="gpt-3.5-turbo",
        )
        
        assert job.job_id == "ft-123"
        
    @patch('openai.fine_tuning.jobs.retrieve')
    def test_get_job_status(self, mock_retrieve, provider):
        """测试获取任务状态."""
        mock_retrieve.return_value = Mock(
            id="ft-123",
            status="running",
            model="gpt-3.5-turbo",
        )
        
        job = provider.get_job_status("ft-123")
        
        assert job.job_id == "ft-123"
        assert job.status == FinetuningStatus.RUNNING


class TestFinetuningManager:
    """微调管理器测试."""

    @pytest.fixture
    def manager(self):
        """创建管理器实例."""
        return FinetuningManager()
        
    def test_manager_initialization(self):
        """测试管理器初始化."""
        manager = FinetuningManager()
        
        assert manager is not None
        assert manager.jobs == {}
        
    def test_register_provider(self, manager):
        """测试注册提供者."""
        provider = OpenAIFinetuningProvider(api_key="test")
        
        manager.register_provider("openai", provider)
        
        assert "openai" in manager.providers
        
    def test_create_dataset(self, manager):
        """测试创建数据集."""
        dataset = manager.create_dataset(name="test_dataset")
        
        assert dataset.name == "test_dataset"
        assert "test_dataset" in manager.datasets
        
    def test_add_example_to_dataset(self, manager):
        """测试向数据集添加示例."""
        manager.create_dataset(name="test")
        
        manager.add_example_to_dataset(
            dataset_name="test",
            prompt="Generate test",
            completion="def test(): ...",
        )
        
        assert len(manager.datasets["test"].examples) == 1
        
    def test_validate_dataset(self, manager):
        """测试验证数据集."""
        manager.create_dataset(name="test")
        manager.add_example_to_dataset("test", "prompt", "completion")
        
        is_valid, errors = manager.validate_dataset("test")
        
        assert is_valid is True


class TestModelFinetuningIntegration:
    """模型微调集成测试."""

    def test_full_finetuning_workflow(self):
        """测试完整微调工作流."""
        manager = FinetuningManager()
        
        # 1. 创建数据集
        dataset = manager.create_dataset(name="test_generation")
        
        # 2. 添加训练示例
        manager.add_example_to_dataset(
            dataset_name="test_generation",
            prompt="Generate test for: def add(a, b): return a + b",
            completion="def test_add():\n    assert add(1, 2) == 3",
        )
        manager.add_example_to_dataset(
            dataset_name="test_generation",
            prompt="Generate test for: def subtract(a, b): return a - b",
            completion="def test_subtract():\n    assert subtract(5, 3) == 2",
        )
        
        # 3. 验证数据集
        is_valid, errors = manager.validate_dataset("test_generation")
        assert is_valid is True
        
        # 4. 转换为 JSONL
        jsonl = dataset.to_jsonl()
        assert "test_add" in jsonl
        
    def test_dataset_validation_flow(self):
        """测试数据集验证流程."""
        validator = DatasetValidator()
        
        # 有效数据集
        valid_dataset = FinetuningDataset(name="valid")
        valid_dataset.add_example("prompt", "completion")
        
        is_valid, errors = validator.validate(valid_dataset)
        assert is_valid is True
        
        # 无效数据集（空）
        invalid_dataset = FinetuningDataset(name="invalid")
        
        is_valid, errors = validator.validate(invalid_dataset)
        assert is_valid is False
