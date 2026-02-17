"""测试阶段计时器模块."""

import pytest
import time

from ut_agent.utils.stage_timer import StageTimer, StageRecord, stage_timer, time_stage
from ut_agent.utils.event_bus import event_bus
from ut_agent.utils.events import EventType


class TestStageRecord:
    def test_stage_record_creation(self):
        record = StageRecord(stage_name="test_stage")
        assert record.stage_name == "test_stage"
        assert record.start_time is None
        assert record.end_time is None
        assert record.duration_ms == 0.0
    
    def test_stage_record_start(self):
        record = StageRecord(stage_name="test")
        record.start()
        assert record.start_time is not None
    
    def test_stage_record_stop(self):
        record = StageRecord(stage_name="test")
        record.start()
        time.sleep(0.01)
        duration = record.stop()
        
        assert record.end_time is not None
        assert duration > 0


class TestStageTimer:
    def setup_method(self):
        stage_timer.reset()
        event_bus.reset()
    
    def test_singleton(self):
        timer1 = StageTimer()
        timer2 = StageTimer()
        assert timer1 is timer2
    
    def test_start_stop_stage(self):
        timer = StageTimer()
        timer.reset()
        
        timer.start_stage("test_stage")
        assert timer.current_stage == "test_stage"
        
        time.sleep(0.01)
        duration = timer.stop_stage("test_stage")
        
        assert duration > 0
        assert timer.current_stage is None
    
    def test_measure_context(self):
        timer = StageTimer()
        timer.reset()
        
        with timer.measure("context_stage") as record:
            assert timer.current_stage == "context_stage"
            time.sleep(0.01)
        
        assert record.duration_ms > 0
        assert timer.current_stage is None
    
    def test_get_stage_duration(self):
        timer = StageTimer()
        timer.reset()
        
        timer.start_stage("duration_test")
        time.sleep(0.01)
        timer.stop_stage("duration_test")
        
        duration = timer.get_stage_duration("duration_test")
        assert duration > 0
    
    def test_get_stage_duration_nonexistent(self):
        timer = StageTimer()
        timer.reset()
        
        duration = timer.get_stage_duration("nonexistent")
        assert duration == 0.0
    
    def test_get_all_durations(self):
        timer = StageTimer()
        timer.reset()
        
        with timer.measure("stage1"):
            pass
        
        with timer.measure("stage2"):
            pass
        
        durations = timer.get_all_durations()
        assert "stage1" in durations
        assert "stage2" in durations
    
    def test_get_summary(self):
        timer = StageTimer()
        timer.reset()
        
        with timer.measure("analyze"):
            pass
        
        with timer.measure("generate"):
            pass
        
        summary = timer.get_summary()
        assert "total_duration_ms" in summary
        assert "stage_count" in summary
        assert "stages" in summary
        assert summary["stage_count"] == 2
    
    def test_multiple_runs_same_stage(self):
        timer = StageTimer()
        timer.reset()
        
        with timer.measure("repeated"):
            pass
        
        with timer.measure("repeated"):
            pass
        
        summary = timer.get_summary()
        assert summary["stages"]["repeated"]["count"] == 2
    
    def test_metadata(self):
        timer = StageTimer()
        timer.reset()
        
        with timer.measure("metadata_test", {"key": "value", "count": 10}) as record:
            pass
        
        assert record.metadata["key"] == "value"
        assert record.metadata["count"] == 10
    
    def test_reset(self):
        timer = StageTimer()
        
        with timer.measure("test"):
            pass
        
        timer.reset()
        
        assert len(timer._stages) == 0
        assert len(timer._history) == 0
        assert timer.current_stage is None


class TestTimeStageDecorator:
    def setup_method(self):
        stage_timer.reset()
        event_bus.reset()
    
    def test_time_stage_context(self):
        with time_stage("decorated_stage") as record:
            time.sleep(0.01)
        
        assert record.duration_ms > 0


class TestStageTimerEvents:
    def setup_method(self):
        stage_timer.reset()
        event_bus.reset()
    
    def test_events_emitted(self):
        received = []
        
        def handler(event):
            received.append(event)
        
        event_bus.subscribe_all(handler)
        
        with stage_timer.measure("event_test"):
            pass
        
        event_types = [e.event_type for e in received]
        assert EventType.NODE_STARTED in event_types
        assert EventType.NODE_COMPLETED in event_types
        assert EventType.PERFORMANCE_METRIC in event_types
    
    def test_metric_emitted(self):
        received_metrics = []
        
        def handler(event):
            if event.event_type == EventType.PERFORMANCE_METRIC:
                received_metrics.append(event.data)
        
        event_bus.subscribe_all(handler)
        
        with stage_timer.measure("metric_test"):
            pass
        
        assert len(received_metrics) == 1
        assert "metric_test_duration_ms" in received_metrics[0]["metric_name"]
