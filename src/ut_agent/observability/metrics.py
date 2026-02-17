"""可观测性指标收集.

提供指标收集、Prometheus 导出、性能追踪和健康检查功能。
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """指标类型枚举."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class Metric:
    """指标数据类.
    
    Attributes:
        name: 指标名称
        metric_type: 指标类型
        value: 指标值
        labels: 标签
        timestamp: 时间戳
    """
    name: str
    metric_type: MetricType
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    
    def to_prometheus(self) -> str:
        """转换为 Prometheus 格式."""
        labels_str = ""
        if self.labels:
            labels_str = "{" + ",".join(f'{k}="{v}"' for k, v in self.labels.items()) + "}"
        return f"{self.name}{labels_str} {self.value}"


class MetricsCollector:
    """指标收集器.
    
    收集和管理各种指标。
    """
    
    def __init__(self):
        """初始化收集器."""
        self.metrics: Dict[str, Metric] = {}
        self.logger = logging.getLogger(__name__)
        
    def record_counter(
        self,
        name: str,
        value: float = 1,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """记录计数器指标."""
        key = f"{name}:{labels or {}}"
        if key in self.metrics:
            self.metrics[key].value += value
        else:
            self.metrics[key] = Metric(
                name=name,
                metric_type=MetricType.COUNTER,
                value=value,
                labels=labels or {},
            )
            
    def record_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """记录仪表盘指标."""
        key = f"{name}:{labels or {}}"
        self.metrics[key] = Metric(
            name=name,
            metric_type=MetricType.GAUGE,
            value=value,
            labels=labels or {},
        )
        
    def record_histogram(
        self,
        name: str,
        value: float,
        buckets: Optional[List[float]] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """记录直方图指标."""
        key = f"{name}:{labels or {}}"
        self.metrics[key] = Metric(
            name=name,
            metric_type=MetricType.HISTOGRAM,
            value=value,
            labels=labels or {},
        )
        
    def get_all_metrics(self) -> List[Metric]:
        """获取所有指标."""
        return list(self.metrics.values())
        
    def clear(self) -> None:
        """清空所有指标."""
        self.metrics.clear()


class PrometheusExporter:
    """Prometheus 导出器.
    
    将指标导出为 Prometheus 格式。
    """
    
    def __init__(self, port: int = 8000):
        """初始化导出器."""
        self.port = port
        self.logger = logging.getLogger(__name__)
        
    def export(self, metrics: List[Metric]) -> str:
        """导出指标为 Prometheus 格式."""
        lines = []
        
        for metric in metrics:
            # 添加 HELP 和 TYPE
            lines.append(f"# HELP {metric.name} {metric.name}")
            lines.append(f"# TYPE {metric.name} {metric.metric_type.value}")
            lines.append(metric.to_prometheus())
            lines.append("")
            
        return "\n".join(lines)


class PerformanceTracker:
    """性能追踪器.
    
    追踪函数执行时间。
    """
    
    def __init__(self):
        """初始化追踪器."""
        self.timings: Dict[str, List[float]] = {}
        self.logger = logging.getLogger(__name__)
        
    def track(self, name: str):
        """装饰器：追踪函数执行时间."""
        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs):
                start = time.time()
                result = func(*args, **kwargs)
                duration = time.time() - start
                
                if name not in self.timings:
                    self.timings[name] = []
                self.timings[name].append(duration)
                
                return result
            return wrapper
        return decorator
        
    def get_timing_stats(self, name: str) -> Dict[str, Any]:
        """获取时间统计."""
        if name not in self.timings:
            return {"count": 0, "avg": 0, "min": 0, "max": 0}
            
        times = self.timings[name]
        return {
            "count": len(times),
            "avg": sum(times) / len(times),
            "min": min(times),
            "max": max(times),
        }


class HealthChecker:
    """健康检查器.
    
    执行各种健康检查。
    """
    
    def __init__(self):
        """初始化检查器."""
        self.checks: Dict[str, Callable] = {}
        self.logger = logging.getLogger(__name__)
        
    def register_check(self, name: str, check_func: Callable) -> None:
        """注册健康检查."""
        self.checks[name] = check_func
        
    def run_checks(self) -> Dict[str, Any]:
        """运行所有健康检查."""
        results = {"healthy": True, "checks": {}}
        
        for name, check_func in self.checks.items():
            try:
                is_healthy, message = check_func()
                results["checks"][name] = {"healthy": is_healthy, "message": message}
                if not is_healthy:
                    results["healthy"] = False
            except Exception as e:
                results["checks"][name] = {"healthy": False, "message": str(e)}
                results["healthy"] = False
                
        return results
