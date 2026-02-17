"""测试事件总线模块."""

import pytest
from datetime import datetime

from ut_agent.utils.events import (
    Event, EventType, ProgressEvent, LLMStreamingEvent,
    PerformanceMetricEvent, ErrorEvent,
)
from ut_agent.utils.event_bus import EventBus, event_bus, emit_progress, emit_metric


class TestEventType:
    def test_event_types_exist(self):
        assert EventType.WORKFLOW_STARTED.value == "workflow_started"
        assert EventType.NODE_PROGRESS.value == "node_progress"
        assert EventType.ERROR_OCCURRED.value == "error_occurred"
        assert EventType.PERFORMANCE_METRIC.value == "performance_metric"


class TestEvent:
    def test_event_creation(self):
        event = Event(
            event_type=EventType.NODE_STARTED,
            source="test_source",
            data={"key": "value"},
        )
        assert event.event_type == EventType.NODE_STARTED
        assert event.source == "test_source"
        assert event.data == {"key": "value"}
        assert isinstance(event.timestamp, datetime)
    
    def test_event_to_dict(self):
        event = Event(
            event_type=EventType.NODE_COMPLETED,
            source="test",
            data={"count": 10},
        )
        result = event.to_dict()
        assert result["event_type"] == "node_completed"
        assert result["source"] == "test"
        assert result["data"]["count"] == 10
        assert "timestamp" in result


class TestProgressEvent:
    def test_progress_event_creation(self):
        event = ProgressEvent(
            stage="generate_tests",
            current=5,
            total=10,
            message="Generating tests",
            current_file="test.py",
        )
        assert event.event_type == EventType.NODE_PROGRESS
        assert event.data["stage"] == "generate_tests"
        assert event.data["current"] == 5
        assert event.data["total"] == 10
        assert event.data["percentage"] == 50.0
        assert event.data["current_file"] == "test.py"
    
    def test_progress_event_percentage_calculation(self):
        event = ProgressEvent(stage="test", current=3, total=4)
        assert event.data["percentage"] == 75.0
    
    def test_progress_event_zero_total(self):
        event = ProgressEvent(stage="test", current=0, total=0)
        assert event.data["percentage"] == 0


class TestPerformanceMetricEvent:
    def test_metric_event_creation(self):
        event = PerformanceMetricEvent(
            metric_name="duration",
            value=123.45,
            unit="ms",
            tags={"stage": "analyze"},
        )
        assert event.event_type == EventType.PERFORMANCE_METRIC
        assert event.data["metric_name"] == "duration"
        assert event.data["value"] == 123.45
        assert event.data["unit"] == "ms"
        assert event.data["tags"]["stage"] == "analyze"


class TestErrorEvent:
    def test_error_event_creation(self):
        event = ErrorEvent(
            error_type="ValueError",
            error_message="Invalid value",
            stack_trace="line 1\nline 2",
            context={"file": "test.py"},
        )
        assert event.event_type == EventType.ERROR_OCCURRED
        assert event.data["error_type"] == "ValueError"
        assert event.data["error_message"] == "Invalid value"
        assert event.data["stack_trace"] == "line 1\nline 2"


class TestEventBus:
    def setup_method(self):
        event_bus.reset()
    
    def test_singleton(self):
        bus1 = EventBus()
        bus2 = EventBus()
        assert bus1 is bus2
    
    def test_subscribe_and_emit(self):
        received_events = []
        
        def handler(event: Event):
            received_events.append(event)
        
        event_bus.subscribe(EventType.NODE_STARTED, handler)
        event_bus.emit_simple(EventType.NODE_STARTED, {"test": "data"}, "source")
        
        assert len(received_events) == 1
        assert received_events[0].event_type == EventType.NODE_STARTED
    
    def test_subscribe_all(self):
        received_events = []
        
        def handler(event: Event):
            received_events.append(event)
        
        event_bus.subscribe_all(handler)
        event_bus.emit_simple(EventType.NODE_STARTED, {}, "")
        event_bus.emit_simple(EventType.NODE_COMPLETED, {}, "")
        event_bus.emit_simple(EventType.ERROR_OCCURRED, {}, "")
        
        assert len(received_events) == 3
    
    def test_unsubscribe(self):
        received_events = []
        
        def handler(event: Event):
            received_events.append(event)
        
        event_bus.subscribe(EventType.NODE_STARTED, handler)
        event_bus.emit_simple(EventType.NODE_STARTED, {}, "")
        assert len(received_events) == 1
        
        event_bus.unsubscribe(EventType.NODE_STARTED, handler)
        event_bus.emit_simple(EventType.NODE_STARTED, {}, "")
        assert len(received_events) == 1
    
    def test_event_history(self):
        event_bus.emit_simple(EventType.NODE_STARTED, {"a": 1}, "")
        event_bus.emit_simple(EventType.NODE_COMPLETED, {"b": 2}, "")
        
        history = event_bus.get_history()
        assert len(history) == 2
        
        filtered = event_bus.get_history(EventType.NODE_STARTED)
        assert len(filtered) == 1
    
    def test_event_counts(self):
        event_bus.emit_simple(EventType.NODE_STARTED, {}, "")
        event_bus.emit_simple(EventType.NODE_STARTED, {}, "")
        event_bus.emit_simple(EventType.NODE_COMPLETED, {}, "")
        
        counts = event_bus.get_event_counts()
        assert counts["node_started"] == 2
        assert counts["node_completed"] == 1
    
    def test_disable_enable(self):
        received = []
        
        def handler(event: Event):
            received.append(event)
        
        event_bus.subscribe_all(handler)
        
        event_bus.disable()
        event_bus.emit_simple(EventType.NODE_STARTED, {}, "")
        assert len(received) == 0
        
        event_bus.enable()
        event_bus.emit_simple(EventType.NODE_STARTED, {}, "")
        assert len(received) == 1
    
    def test_track_event_context(self):
        with event_bus.track_event(EventType.NODE_STARTED, "test", key="value"):
            pass
        
        history = event_bus.get_history()
        assert len(history) == 2
        assert history[0].data["status"] == "started"
        assert history[1].data["status"] == "completed"
        assert "duration_ms" in history[1].data


class TestHelperFunctions:
    def setup_method(self):
        event_bus.reset()
    
    def test_emit_progress(self):
        received = []
        
        def handler(event: Event):
            received.append(event)
        
        event_bus.subscribe_all(handler)
        emit_progress("test_stage", 5, 10, "message", "file.py", "source")
        
        assert len(received) == 1
        assert received[0].event_type == EventType.NODE_PROGRESS
        assert received[0].data["stage"] == "test_stage"
    
    def test_emit_metric(self):
        received = []
        
        def handler(event: Event):
            received.append(event)
        
        event_bus.subscribe_all(handler)
        emit_metric("test_metric", 100.0, "ms", {"tag": "value"}, "source")
        
        assert len(received) == 1
        assert received[0].event_type == EventType.PERFORMANCE_METRIC
        assert received[0].data["metric_name"] == "test_metric"
