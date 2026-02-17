"""Prompt 版本管理.

提供 Prompt 版本控制、A/B 测试和性能追踪功能。
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PromptVersion:
    """Prompt 版本.
    
    Attributes:
        version_id: 版本 ID
        content: Prompt 内容
        description: 版本描述
        metadata: 元数据
        created_at: 创建时间
    """
    version_id: str
    content: str
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "version_id": self.version_id,
            "content": self.content,
            "description": self.description,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


class PromptTemplate:
    """Prompt 模板.
    
    管理多个版本的 Prompt 模板。
    """
    
    def __init__(self, name: str, description: str = ""):
        """初始化模板.
        
        Args:
            name: 模板名称
            description: 模板描述
        """
        self.name = name
        self.description = description
        self.versions: List[PromptVersion] = []
        self.current_version: Optional[str] = None
        
    def add_version(self, version: PromptVersion) -> None:
        """添加版本."""
        self.versions.append(version)
        self.current_version = version.version_id
        
    def get_version(self, version_id: str) -> Optional[PromptVersion]:
        """获取指定版本."""
        for version in self.versions:
            if version.version_id == version_id:
                return version
        return None
        
    def get_current_version(self) -> Optional[PromptVersion]:
        """获取当前版本."""
        if self.current_version:
            return self.get_version(self.current_version)
        return None
        
    def render(self, **kwargs) -> str:
        """渲染模板."""
        version = self.get_current_version()
        if version:
            return version.content.format(**kwargs)
        return ""


class PromptVersionManager:
    """Prompt 版本管理器.
    
    管理所有 Prompt 模板和版本。
    """
    
    def __init__(self, storage_path: str):
        """初始化管理器."""
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.templates: Dict[str, PromptTemplate] = {}
        self.logger = logging.getLogger(__name__)
        
    def create_template(self, name: str, description: str = "") -> PromptTemplate:
        """创建模板."""
        template = PromptTemplate(name=name, description=description)
        self.templates[name] = template
        return template
        
    def add_version(
        self,
        template_name: str,
        content: str,
        description: str = "",
    ) -> PromptVersion:
        """添加版本."""
        if template_name not in self.templates:
            raise ValueError(f"Template {template_name} not found")
            
        version_id = f"v{len(self.templates[template_name].versions) + 1}.0.0"
        version = PromptVersion(
            version_id=version_id,
            content=content,
            description=description,
        )
        
        self.templates[template_name].add_version(version)
        return version
        
    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """获取模板."""
        return self.templates.get(name)
        
    def list_templates(self) -> List[str]:
        """列出所有模板."""
        return list(self.templates.keys())
        
    def rollback_version(self, template_name: str, version_id: str) -> bool:
        """回滚版本."""
        template = self.templates.get(template_name)
        if template and template.get_version(version_id):
            template.current_version = version_id
            return True
        return False
        
    def render_template(self, template_name: str, **kwargs) -> str:
        """渲染模板."""
        template = self.templates.get(template_name)
        if template:
            return template.render(**kwargs)
        return ""


class PromptABTest:
    """Prompt A/B 测试.
    
    比较两个 Prompt 版本的效果。
    """
    
    def __init__(
        self,
        test_name: str,
        template_name: str,
        version_a: str,
        version_b: str,
    ):
        """初始化 A/B 测试."""
        self.test_name = test_name
        self.template_name = template_name
        self.version_a = version_a
        self.version_b = version_b
        self.results: Dict[str, Dict[str, float]] = {}
        
    def record_result(self, version: str, metric: str, value: float) -> None:
        """记录结果."""
        if version not in self.results:
            self.results[version] = {}
        self.results[version][metric] = value
        
    def get_winner(self, metric: str) -> Optional[str]:
        """获取获胜版本."""
        a_value = self.results.get(self.version_a, {}).get(metric, 0)
        b_value = self.results.get(self.version_b, {}).get(metric, 0)
        
        if b_value > a_value:
            return self.version_b
        return self.version_a


class PromptPerformanceTracker:
    """Prompt 性能追踪器.
    
    追踪 Prompt 版本的性能指标。
    """
    
    def __init__(self):
        """初始化追踪器."""
        self.metrics: Dict[str, Dict[str, Dict[str, List[float]]]] = {}
        
    def record_metric(
        self,
        template_name: str,
        version_id: str,
        metric_name: str,
        value: float,
    ) -> None:
        """记录指标."""
        if template_name not in self.metrics:
            self.metrics[template_name] = {}
        if version_id not in self.metrics[template_name]:
            self.metrics[template_name][version_id] = {}
        if metric_name not in self.metrics[template_name][version_id]:
            self.metrics[template_name][version_id][metric_name] = []
            
        self.metrics[template_name][version_id][metric_name].append(value)
        
    def get_average_metric(
        self,
        template_name: str,
        version_id: str,
        metric_name: str,
    ) -> float:
        """获取平均指标."""
        values = self.metrics.get(template_name, {}).get(version_id, {}).get(metric_name, [])
        if not values:
            return 0.0
        return sum(values) / len(values)
        
    def compare_versions(
        self,
        template_name: str,
        version_a: str,
        version_b: str,
        metric: str,
    ) -> Dict[str, Any]:
        """比较两个版本."""
        avg_a = self.get_average_metric(template_name, version_a, metric)
        avg_b = self.get_average_metric(template_name, version_b, metric)
        
        improvement = ((avg_b - avg_a) / avg_a * 100) if avg_a > 0 else 0
        
        return {
            "version_a": version_a,
            "version_b": version_b,
            "metric_a": avg_a,
            "metric_b": avg_b,
            "improvement": improvement,
        }
