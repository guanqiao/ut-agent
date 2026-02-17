"""测试进度监控模块."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from ut_agent.utils.progress_monitor import (
    StageProgress, WorkflowProgress, ProgressMonitor, create_progress_monitor,
)
from ut_agent.utils.events import Event, EventType
from ut_agent.utils.event_bus import event_bus


class TestStageProgress:
    def test_stage_progress_creation(self):
        stage = StageProgress(stage_name="test_stage")
        assert stage.stage_name == "test_stage"
        assert stage.current == 0
        assert stage.total == 0
        assert stage.status == "pending"
    
    def test_stage_progress_update(self):
        stage = StageProgress(stage_name="test")
        stage.update(5, 10, "file.py", "Processing")
        
        assert stage.current == 5
        assert stage.total == 10
        assert stage.percentage == 50.0
        assert stage.current_file == "file.py"
        assert stage.message == "Processing"
        assert stage.status == "running"
    
    def test_stage_progress_duration(self):
        stage = StageProgress(stage_name="test")
        stage.start_time = datetime.now()
        stage.end_time = datetime.now()
        
        assert stage.duration_ms >= 0


class TestWorkflowProgress:
    def test_workflow_progress_creation(self):
        progress = WorkflowProgress()
        assert progress.current_stage == ""
        assert "analyze_code" in progress.stages
        assert "generate_tests" in progress.stages
    
    def test_overall_percentage_empty(self):
        progress = WorkflowProgress()
        assert progress.overall_percentage == 0.0
    
    def test_overall_percentage_with_completed(self):
        progress = WorkflowProgress()
        progress.stages["analyze_code"].status = "completed"
        
        percentage = progress.overall_percentage
        assert percentage > 0
    
    def test_overall_percentage_with_running(self):
        progress = WorkflowProgress()
        progress.current_stage = "analyze_code"
        progress.stages["analyze_code"].status = "running"
        progress.stages["analyze_code"].update(5, 10)
        
        percentage = progress.overall_percentage
        assert percentage > 0
    
    def test_duration_str(self):
        progress = WorkflowProgress()
        progress.start_time = datetime.now()
        
        duration = progress.duration_str
        assert ":" in duration


class TestProgressMonitor:
    def setup_method(self):
        event_bus.reset()
    
    def test_monitor_creation(self):
        monitor = create_progress_monitor()
        assert monitor.progress is not None
    
    def test_monitor_start_stop(self):
        monitor = ProgressMonitor()
        monitor.start()
        assert monitor.progress.start_time is not None
        
        monitor.stop()
        assert monitor.progress.end_time is not None
    
    def test_handle_file_analysis_event(self):
        monitor = ProgressMonitor()
        monitor.start()
        
        event = Event(
            event_type=EventType.FILE_ANALYSIS_STARTED,
            data={"total_files": 10},
        )
        monitor._handle_event(event)
        
        assert monitor.progress.current_stage == "analyze_code"
        assert monitor.progress.stages["analyze_code"].status == "running"
        assert monitor.progress.stages["analyze_code"].total == 10
        
        monitor.stop()
    
    def test_handle_test_generation_event(self):
        monitor = ProgressMonitor()
        monitor.start()
        
        event = Event(
            event_type=EventType.TEST_GENERATION_STARTED,
            data={"total_files": 5},
        )
        monitor._handle_event(event)
        
        assert monitor.progress.current_stage == "generate_tests"
        assert monitor.progress.stages["generate_tests"].status == "running"
        
        monitor.stop()
    
    def test_handle_progress_event(self):
        monitor = ProgressMonitor()
        monitor.start()
        
        event = Event(
            event_type=EventType.NODE_PROGRESS,
            data={
                "stage": "generate_tests",
                "current": 3,
                "total": 10,
                "current_file": "test.py",
                "message": "Processing",
            },
        )
        monitor._handle_event(event)
        
        stage = monitor.progress.stages["generate_tests"]
        assert stage.current == 3
        assert stage.total == 10
        assert stage.percentage == 30.0
        
        monitor.stop()
    
    def test_handle_error_event(self):
        monitor = ProgressMonitor()
        monitor.start()
        
        event = Event(
            event_type=EventType.ERROR_OCCURRED,
            data={"error_message": "Test error"},
        )
        monitor._handle_event(event)
        
        assert len(monitor.progress.event_log) == 1
        assert monitor.progress.event_log[0]["type"] == "error"
        
        monitor.stop()
    
    def test_get_summary(self):
        monitor = ProgressMonitor()
        monitor.start()
        monitor.stop()
        
        summary = monitor.get_summary()
        assert "duration_ms" in summary
        assert "stages" in summary
        assert "event_count" in summary
    
    def test_generate_layout(self):
        monitor = ProgressMonitor()
        monitor.start()
        
        layout = monitor._generate_layout()
        assert layout is not None
        
        monitor.stop()
    
    def test_create_progress_bar(self):
        monitor = ProgressMonitor()
        monitor.progress.stages["analyze_code"].status = "completed"
        
        bar = monitor._create_progress_bar()
        assert "进度:" in str(bar)
    
    def test_create_stages_table(self):
        monitor = ProgressMonitor()
        table = monitor._create_stages_table()
        assert table is not None
    
    def test_create_current_info_running(self):
        monitor = ProgressMonitor()
        monitor.progress.current_stage = "generate_tests"
        monitor.progress.stages["generate_tests"].status = "running"
        monitor.progress.stages["generate_tests"].current_file = "test.py"
        
        info = monitor._create_current_info()
        assert "test.py" in str(info)
    
    def test_create_current_info_idle(self):
        monitor = ProgressMonitor()
        info = monitor._create_current_info()
        assert "就绪" in str(info)
