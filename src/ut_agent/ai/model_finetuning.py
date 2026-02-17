"""模型微调支持.

提供模型微调任务管理、数据集准备和提供者抽象。
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FinetuningStatus(Enum):
    """微调状态枚举."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class FinetuningJob:
    """微调任务.
    
    Attributes:
        job_id: 任务 ID
        model: 模型名称
        training_file: 训练文件 ID
        status: 任务状态
        created_at: 创建时间
    """
    job_id: str
    model: str
    training_file: str
    status: FinetuningStatus = FinetuningStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "job_id": self.job_id,
            "model": self.model,
            "training_file": self.training_file,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
        }


class FinetuningDataset:
    """微调数据集.
    
    管理微调训练数据。
    """
    
    def __init__(self, name: str, examples: Optional[List[Dict]] = None):
        """初始化数据集."""
        self.name = name
        self.examples = examples or []
        
    def add_example(self, prompt: str, completion: str) -> None:
        """添加示例."""
        self.examples.append({
            "prompt": prompt,
            "completion": completion,
        })
        
    def to_jsonl(self) -> str:
        """转换为 JSONL 格式."""
        lines = []
        for example in self.examples:
            lines.append(json.dumps(example, ensure_ascii=False))
        return "\n".join(lines)


class DatasetValidator:
    """数据集验证器.
    
    验证微调数据集的有效性。
    """
    
    def validate(self, dataset: FinetuningDataset) -> tuple[bool, List[str]]:
        """验证数据集.
        
        Returns:
            tuple[bool, List[str]]: (是否有效, 错误列表)
        """
        errors = []
        
        if not dataset.examples:
            errors.append("Dataset is empty")
            return False, errors
            
        for i, example in enumerate(dataset.examples):
            if "prompt" not in example:
                errors.append(f"Example {i}: missing 'prompt' field")
            if "completion" not in example:
                errors.append(f"Example {i}: missing 'completion' field")
                
        return len(errors) == 0, errors


class OpenAIFinetuningProvider:
    """OpenAI 微调提供者.
    
    与 OpenAI API 集成进行模型微调。
    """
    
    def __init__(self, api_key: str):
        """初始化提供者."""
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
        
    def upload_dataset(self, dataset: FinetuningDataset) -> Optional[str]:
        """上传数据集.
        
        Returns:
            Optional[str]: 文件 ID
        """
        try:
            import openai
            openai.api_key = self.api_key
            
            # 创建临时文件
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
                f.write(dataset.to_jsonl())
                temp_path = f.name
                
            # 上传文件
            with open(temp_path, 'rb') as f:
                response = openai.files.create(file=f, purpose='fine-tune')
                
            return response.id
        except Exception as e:
            self.logger.exception(f"Failed to upload dataset: {e}")
            return None
            
    def create_job(
        self,
        training_file: str,
        model: str = "gpt-3.5-turbo",
    ) -> Optional[FinetuningJob]:
        """创建微调任务."""
        try:
            import openai
            openai.api_key = self.api_key
            
            response = openai.fine_tuning.jobs.create(
                training_file=training_file,
                model=model,
            )
            
            return FinetuningJob(
                job_id=response.id,
                model=model,
                training_file=training_file,
            )
        except Exception as e:
            self.logger.exception(f"Failed to create job: {e}")
            return None
            
    def get_job_status(self, job_id: str) -> Optional[FinetuningJob]:
        """获取任务状态."""
        try:
            import openai
            openai.api_key = self.api_key
            
            response = openai.fine_tuning.jobs.retrieve(job_id)
            
            return FinetuningJob(
                job_id=response.id,
                model=response.model,
                training_file=response.training_file,
                status=FinetuningStatus(response.status),
            )
        except Exception as e:
            self.logger.exception(f"Failed to get job status: {e}")
            return None


class FinetuningManager:
    """微调管理器.
    
    统一管理微调任务和数据集。
    """
    
    def __init__(self):
        """初始化管理器."""
        self.datasets: Dict[str, FinetuningDataset] = {}
        self.jobs: Dict[str, FinetuningJob] = {}
        self.providers: Dict[str, Any] = {}
        self.validator = DatasetValidator()
        self.logger = logging.getLogger(__name__)
        
    def register_provider(self, name: str, provider: Any) -> None:
        """注册提供者."""
        self.providers[name] = provider
        
    def create_dataset(self, name: str) -> FinetuningDataset:
        """创建数据集."""
        dataset = FinetuningDataset(name=name)
        self.datasets[name] = dataset
        return dataset
        
    def add_example_to_dataset(
        self,
        dataset_name: str,
        prompt: str,
        completion: str,
    ) -> bool:
        """向数据集添加示例."""
        if dataset_name not in self.datasets:
            return False
        self.datasets[dataset_name].add_example(prompt, completion)
        return True
        
    def validate_dataset(self, name: str) -> tuple[bool, List[str]]:
        """验证数据集."""
        if name not in self.datasets:
            return False, ["Dataset not found"]
        return self.validator.validate(self.datasets[name])
        
    def start_finetuning(
        self,
        dataset_name: str,
        provider_name: str = "openai",
        model: str = "gpt-3.5-turbo",
    ) -> Optional[FinetuningJob]:
        """开始微调."""
        provider = self.providers.get(provider_name)
        if not provider:
            self.logger.error(f"Provider {provider_name} not found")
            return None
            
        dataset = self.datasets.get(dataset_name)
        if not dataset:
            self.logger.error(f"Dataset {dataset_name} not found")
            return None
            
        # 验证数据集
        is_valid, errors = self.validate_dataset(dataset_name)
        if not is_valid:
            self.logger.error(f"Dataset validation failed: {errors}")
            return None
            
        # 上传数据集
        file_id = provider.upload_dataset(dataset)
        if not file_id:
            return None
            
        # 创建微调任务
        job = provider.create_job(training_file=file_id, model=model)
        if job:
            self.jobs[job.job_id] = job
            
        return job
