"""性能指标收集系统."""

import time
import threading
import types
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Type
from datetime import datetime

from ut_agent.utils import get_logger

logger = get_logger("metrics")


@dataclass
class MetricValue:
    """指标值."""
    value: float
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class Counter:
    """计数器指标."""
    name: str
    value: int = 0
    tags: Dict[str, str] = field(default_factory=dict)

    def increment(self, value: int = 1) -> None:
        """增加计数."""
        self.value += value

    def reset(self) -> None:
        """重置计数器."""
        self.value = 0


@dataclass
class Gauge:
    """仪表盘指标."""
    name: str
    value: float = 0.0
    tags: Dict[str, str] = field(default_factory=dict)

    def set(self, value: float) -> None:
        """设置值."""
        self.value = value


@dataclass
class Histogram:
    """直方图指标."""
    name: str
    values: List[float] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)

    def record(self, value: float) -> None:
        """记录值."""
        self.values.append(value)

    def get_summary(self) -> Dict[str, float]:
        """获取统计摘要."""
        if not self.values:
            return {
                "count": 0,
                "min": 0,
                "max": 0,
                "mean": 0,
                "p50": 0,
                "p95": 0,
                "p99": 0
            }
        sorted_values = sorted(self.values)
        count = len(sorted_values)
        return {
            "count": count,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "mean": sum(sorted_values) / count,
            "p50": sorted_values[int(count * 0.5)],
            "p95": sorted_values[int(count * 0.95)],
            "p99": sorted_values[int(count * 0.99)]
        }

    def reset(self) -> None:
        """重置直方图."""
        self.values.clear()


class MetricsCollector:
    """指标收集器."""

    _instance: Optional["MetricsCollector"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "MetricsCollector":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_initialized"):
            self._counters: Dict[str, Counter] = {}
            self._gauges: Dict[str, Gauge] = {}
            self._histograms: Dict[str, Histogram] = {}
            self._lock = threading.Lock()
            self._initialized = True

    def counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> Counter:
        """获取或创建计数器."""
        with self._lock:
            key = f"{name}:{str(tags)}"
            if key not in self._counters:
                self._counters[key] = Counter(name, tags=tags or {})
            return self._counters[key]

    def gauge(self, name: str, tags: Optional[Dict[str, str]] = None) -> Gauge:
        """获取或创建仪表盘."""
        with self._lock:
            key = f"{name}:{str(tags)}"
            if key not in self._gauges:
                self._gauges[key] = Gauge(name, tags=tags or {})
            return self._gauges[key]

    def histogram(self, name: str, tags: Optional[Dict[str, str]] = None) -> Histogram:
        """获取或创建直方图."""
        with self._lock:
            key = f"{name}:{str(tags)}"
            if key not in self._histograms:
                self._histograms[key] = Histogram(name, tags=tags or {})
            return self._histograms[key]

    def collect(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """收集所有指标."""
        with self._lock:
            metrics: Dict[str, Dict[str, Dict[str, Any]]] = {
                "counters": {},
                "gauges": {},
                "histograms": {}
            }

            for key, counter in self._counters.items():
                metrics["counters"][key] = {
                    "name": counter.name,
                    "value": counter.value,
                    "tags": counter.tags
                }

            for key, gauge in self._gauges.items():
                metrics["gauges"][key] = {
                    "name": gauge.name,
                    "value": gauge.value,
                    "tags": gauge.tags
                }

            for key, histogram in self._histograms.items():
                metrics["histograms"][key] = {
                    "name": histogram.name,
                    "summary": histogram.get_summary(),
                    "tags": histogram.tags
                }

            return metrics

    def reset(self) -> None:
        """重置所有指标."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()

    def get_llm_metrics(self) -> Dict[str, Any]:
        """获取 LLM 相关指标."""
        metrics = self.collect()
        llm_metrics = {}

        for key, value in metrics.get("counters", {}).items():
            if "llm" in key.lower():
                llm_metrics[key] = value

        for key, value in metrics.get("histograms", {}).items():
            if "llm" in key.lower():
                llm_metrics[key] = value

        return llm_metrics

    def get_cache_metrics(self) -> Dict[str, Any]:
        """获取缓存相关指标."""
        metrics = self.collect()
        cache_metrics = {}

        for key, value in metrics.get("counters", {}).items():
            if "cache" in key.lower():
                cache_metrics[key] = value

        for key, value in metrics.get("gauges", {}).items():
            if "cache" in key.lower():
                cache_metrics[key] = value

        return cache_metrics

    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能相关指标."""
        metrics = self.collect()
        perf_metrics = {}

        for key, value in metrics.get("histograms", {}).items():
            if "time" in key.lower() or "latency" in key.lower():
                perf_metrics[key] = value

        return perf_metrics


def get_metrics_collector() -> MetricsCollector:
    """获取指标收集器实例."""
    return MetricsCollector()


def record_llm_call(provider: str, model: str, response_time: float, success: bool) -> None:
    """记录 LLM 调用指标."""
    collector = get_metrics_collector()
    tags = {"provider": provider, "model": model}

    # 计数
    collector.counter("llm.calls", tags=tags).increment()
    if success:
        collector.counter("llm.calls.success", tags=tags).increment()
    else:
        collector.counter("llm.calls.failed", tags=tags).increment()

    # 响应时间
    collector.histogram("llm.response.time", tags=tags).record(response_time)

    logger.debug(
        f"LLM call recorded: {provider}/{model} - {response_time:.2f}s - {'success' if success else 'failed'}"
    )


def record_cache_operation(cache_type: str, operation: str, hit: bool = False) -> None:
    """记录缓存操作指标."""
    collector = get_metrics_collector()
    tags = {"cache_type": cache_type}

    collector.counter(f"cache.{operation}", tags=tags).increment()
    if hit:
        collector.counter(f"cache.hits", tags=tags).increment()

    logger.debug(
        f"Cache operation recorded: {cache_type} - {operation} - {'hit' if hit else 'miss'}"
    )


def record_ast_parse(file_path: str, language: str, parse_time: float) -> None:
    """记录 AST 解析指标."""
    collector = get_metrics_collector()
    tags = {"language": language}

    collector.counter("ast.parse.count", tags=tags).increment()
    collector.histogram("ast.parse.time", tags=tags).record(parse_time)

    logger.debug(
        f"AST parse recorded: {language} - {parse_time:.2f}s - {file_path}"
    )


def record_memory_usage(used_bytes: int, total_bytes: int) -> None:
    """记录内存使用指标."""
    collector = get_metrics_collector()
    usage_percent = (used_bytes / total_bytes) * 100 if total_bytes > 0 else 0

    collector.gauge("memory.used").set(used_bytes)
    collector.gauge("memory.total").set(total_bytes)
    collector.gauge("memory.usage.percent").set(usage_percent)


def get_metrics_summary() -> Dict[str, Any]:
    """获取指标摘要."""
    collector = get_metrics_collector()
    return {
        "llm": collector.get_llm_metrics(),
        "cache": collector.get_cache_metrics(),
        "performance": collector.get_performance_metrics(),
        "timestamp": datetime.now().isoformat()
    }


def reset_metrics() -> None:
    """重置所有指标."""
    collector = get_metrics_collector()
    collector.reset()
    logger.info("Metrics reset")


def log_metrics_summary() -> None:
    """记录指标摘要到日志."""
    metrics = get_metrics_summary()
    logger.info("Metrics Summary", extra={"metrics": metrics})
    
    # 打印更友好的摘要
    llm_metrics = metrics.get("llm", {})
    cache_metrics = metrics.get("cache", {})
    perf_metrics = metrics.get("performance", {})
    
    summary_lines = []
    summary_lines.append("=== Metrics Summary ===")
    
    if llm_metrics:
        summary_lines.append("\nLLM Metrics:")
        for key, value in llm_metrics.items():
            if isinstance(value, dict) and "value" in value:
                summary_lines.append(f"  {value.get('name', key)}: {value.get('value')}")
            elif isinstance(value, dict) and "summary" in value:
                summary_lines.append(f"  {value.get('name', key)}:")
                for stat_name, stat_value in value.get('summary', {}).items():
                    summary_lines.append(f"    {stat_name}: {stat_value:.2f}")
    
    if cache_metrics:
        summary_lines.append("\nCache Metrics:")
        for key, value in cache_metrics.items():
            if isinstance(value, dict) and "value" in value:
                summary_lines.append(f"  {value.get('name', key)}: {value.get('value')}")
    
    if perf_metrics:
        summary_lines.append("\nPerformance Metrics:")
        for key, value in perf_metrics.items():
            if isinstance(value, dict) and "summary" in value:
                summary_lines.append(f"  {value.get('name', key)}:")
                for stat_name, stat_value in value.get('summary', {}).items():
                    summary_lines.append(f"    {stat_name}: {stat_value:.2f}")
    
    summary_lines.append("====================")
    logger.debug("\n".join(summary_lines))


class MetricsExporter:
    """指标导出器."""
    
    def __init__(self, export_interval: int = 300):
        """初始化指标导出器.
        
        Args:
            export_interval: 导出间隔（秒）
        """
        self.export_interval = export_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """开始定期导出指标."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._export_loop, daemon=True)
        self._thread.start()
        logger.info(f"Metrics exporter started with interval: {self.export_interval}s")
    
    def stop(self) -> None:
        """停止定期导出指标."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Metrics exporter stopped")
    
    def _export_loop(self) -> None:
        """导出循环."""
        while self._running:
            try:
                log_metrics_summary()
            except Exception as e:
                logger.error(f"Error exporting metrics: {e}")
            
            # 等待下一次导出
            for _ in range(self.export_interval):
                if not self._running:
                    break
                time.sleep(1)


# 上下文管理器
class llm_call:
    """LLM 调用上下文管理器."""

    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.model = model
        self.start_time = 0.0

    def __enter__(self) -> "llm_call":
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type: Type[BaseException] | None, exc_val: BaseException | None, exc_tb: types.TracebackType | None) -> None:
        response_time = time.time() - self.start_time
        success = exc_type is None
        record_llm_call(self.provider, self.model, response_time, success)


class ast_parse:
    """AST 解析上下文管理器."""

    def __init__(self, file_path: str, language: str):
        self.file_path = file_path
        self.language = language
        self.start_time = 0.0

    def __enter__(self) -> "ast_parse":
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type: Type[BaseException] | None, exc_val: BaseException | None, exc_tb: types.TracebackType | None) -> None:
        parse_time = time.time() - self.start_time
        record_ast_parse(self.file_path, self.language, parse_time)
