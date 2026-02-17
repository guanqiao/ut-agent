"""可观测性指标收集测试."""

import pytest
import time
from unittest.mock import Mock, patch
from typing import Dict, Any, List, Optional

from ut_agent.observability.metrics import (
    MetricType,
    Metric,
    MetricsCollector,
    PrometheusExporter,
    PerformanceTracker,
    HealthChecker,
)


class TestMetricType:
    """指标类型测试."""

    def test_metric_type_values(self):
        """测试指标类型枚举值."""
        assert MetricType.COUNTER.value == "counter"
        assert MetricType.GAUGE.value == "gauge"
        assert MetricType.HISTOGRAM.value == "histogram"
        assert MetricType.SUMMARY.value == "summary"


class TestMetric:
    """指标测试."""

    def test_metric_creation(self):
        """测试指标创建."""
        metric = Metric(
            name="test_requests_total",
            metric_type=MetricType.COUNTER,
            value=100,
            labels={"method": "GET", "status": "200"},
        )
        
        assert metric.name == "test_requests_total"
        assert metric.metric_type == MetricType.COUNTER
        assert metric.value == 100
        assert metric.labels["method"] == "GET"
        
    def test_metric_to_prometheus(self):
        """测试转换为 Prometheus 格式."""
        metric = Metric(
            name="requests_total",
            metric_type=MetricType.COUNTER,
            value=100,
            labels={"method": "GET"},
        )
        
        prom_text = metric.to_prometheus()
        
        assert "requests_total" in prom_text
        assert "100" in prom_text


class TestMetricsCollector:
    """指标收集器测试."""

    @pytest.fixture
    def collector(self):
        """创建收集器实例."""
        return MetricsCollector()
        
    def test_collector_initialization(self):
        """测试收集器初始化."""
        collector = MetricsCollector()
        
        assert collector is not None
        assert collector.metrics == {}
        
    def test_record_counter(self, collector):
        """测试记录计数器."""
        collector.record_counter(
            name="requests_total",
            value=1,
            labels={"method": "GET"},
        )
        
        # 键名包含标签
        assert any("requests_total" in key for key in collector.metrics)
        
    def test_record_gauge(self, collector):
        """测试记录仪表盘."""
        collector.record_gauge(
            name="active_connections",
            value=10,
        )
        
        # 键名包含标签（空标签）
        key = "active_connections:{}"
        assert collector.metrics[key].value == 10
        
    def test_record_histogram(self, collector):
        """测试记录直方图."""
        collector.record_histogram(
            name="request_duration_seconds",
            value=0.5,
            buckets=[0.1, 0.5, 1.0, 2.0],
        )
        
        # 键名包含标签
        assert any("request_duration_seconds" in key for key in collector.metrics)
        
    def test_get_all_metrics(self, collector):
        """测试获取所有指标."""
        collector.record_counter("counter1", 10)
        collector.record_counter("counter2", 20)
        
        metrics = collector.get_all_metrics()
        
        assert len(metrics) == 2
        
    def test_clear(self, collector):
        """测试清空指标."""
        collector.record_counter("test", 1)
        
        collector.clear()
        
        assert len(collector.metrics) == 0


class TestPrometheusExporter:
    """Prometheus 导出器测试."""

    @pytest.fixture
    def exporter(self):
        """创建导出器实例."""
        return PrometheusExporter(port=9090)
        
    def test_exporter_initialization(self):
        """测试导出器初始化."""
        exporter = PrometheusExporter(port=9090)
        
        assert exporter.port == 9090
        
    def test_export_metrics(self, exporter):
        """测试导出指标."""
        metrics = [
            Metric("counter1", MetricType.COUNTER, 100),
            Metric("gauge1", MetricType.GAUGE, 50),
        ]
        
        output = exporter.export(metrics)
        
        assert "counter1" in output
        assert "gauge1" in output


class TestPerformanceTracker:
    """性能追踪器测试."""

    @pytest.fixture
    def tracker(self):
        """创建追踪器实例."""
        return PerformanceTracker()
        
    def test_tracker_initialization(self):
        """测试追踪器初始化."""
        tracker = PerformanceTracker()
        
        assert tracker is not None
        
    def test_track_function(self, tracker):
        """测试追踪函数."""
        @tracker.track("test_function")
        def test_func():
            time.sleep(0.01)
            return "result"
            
        result = test_func()
        
        assert result == "result"
        assert "test_function" in tracker.timings
        
    def test_get_timing_stats(self, tracker):
        """测试获取时间统计."""
        @tracker.track("slow_func")
        def slow_func():
            time.sleep(0.01)
            
        slow_func()
        slow_func()
        
        stats = tracker.get_timing_stats("slow_func")
        
        assert "count" in stats
        assert stats["count"] == 2
        assert "avg" in stats


class TestHealthChecker:
    """健康检查器测试."""

    @pytest.fixture
    def checker(self):
        """创建检查器实例."""
        return HealthChecker()
        
    def test_checker_initialization(self):
        """测试检查器初始化."""
        checker = HealthChecker()
        
        assert checker is not None
        assert checker.checks == {}
        
    def test_register_check(self, checker):
        """测试注册检查."""
        def db_check():
            return True, "Database OK"
            
        checker.register_check("database", db_check)
        
        assert "database" in checker.checks
        
    def test_run_checks(self, checker):
        """测试运行检查."""
        checker.register_check("test", lambda: (True, "OK"))
        
        results = checker.run_checks()
        
        assert results["healthy"] is True
        assert "test" in results["checks"]
        
    def test_run_checks_with_failure(self, checker):
        """测试运行检查（有失败）."""
        checker.register_check("ok", lambda: (True, "OK"))
        checker.register_check("fail", lambda: (False, "Failed"))
        
        results = checker.run_checks()
        
        assert results["healthy"] is False


class TestObservabilityIntegration:
    """可观测性集成测试."""

    def test_full_metrics_workflow(self):
        """测试完整指标工作流."""
        collector = MetricsCollector()
        
        # 记录各种指标
        collector.record_counter("requests_total", 100)
        collector.record_gauge("active_users", 50)
        collector.record_histogram("response_time", 0.5)
        
        # 导出为 Prometheus 格式
        exporter = PrometheusExporter()
        metrics = collector.get_all_metrics()
        output = exporter.export(metrics)
        
        # 验证输出
        assert "requests_total" in output
        assert "active_users" in output
        assert "response_time" in output
        
    def test_health_check_integration(self):
        """测试健康检查集成."""
        checker = HealthChecker()
        
        # 注册多个检查
        checker.register_check("api", lambda: (True, "API OK"))
        checker.register_check("db", lambda: (True, "DB OK"))
        
        # 运行检查
        results = checker.run_checks()
        
        assert results["healthy"] is True
        assert len(results["checks"]) == 2
        
    def test_performance_tracking_integration(self):
        """测试性能追踪集成."""
        tracker = PerformanceTracker()
        
        # 追踪多个函数
        @tracker.track("func1")
        def func1():
            time.sleep(0.01)
            
        @tracker.track("func2")
        def func2():
            time.sleep(0.02)
            
        func1()
        func2()
        func1()
        
        # 获取统计
        stats1 = tracker.get_timing_stats("func1")
        stats2 = tracker.get_timing_stats("func2")
        
        assert stats1["count"] == 2
        assert stats2["count"] == 1
