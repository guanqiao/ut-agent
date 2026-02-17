"""标准化事件类型定义."""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional


class EventType(Enum):
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    
    NODE_STARTED = "node_started"
    NODE_PROGRESS = "node_progress"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    
    FILE_ANALYSIS_STARTED = "file_analysis_started"
    FILE_ANALYSIS_COMPLETED = "file_analysis_completed"
    
    TEST_GENERATION_STARTED = "test_generation_started"
    TEST_GENERATION_PROGRESS = "test_generation_progress"
    TEST_GENERATION_COMPLETED = "test_generation_completed"
    
    TEST_EXECUTION_STARTED = "test_execution_started"
    TEST_EXECUTION_PROGRESS = "test_execution_progress"
    TEST_EXECUTION_COMPLETED = "test_execution_completed"
    
    COVERAGE_ANALYSIS_STARTED = "coverage_analysis_started"
    COVERAGE_ANALYSIS_COMPLETED = "coverage_analysis_completed"
    
    LLM_CALL_STARTED = "llm_call_started"
    LLM_CALL_STREAMING = "llm_call_streaming"
    LLM_CALL_COMPLETED = "llm_call_completed"
    LLM_CALL_FAILED = "llm_call_failed"
    
    ERROR_OCCURRED = "error_occurred"
    WARNING_OCCURRED = "warning_occurred"
    
    PERFORMANCE_METRIC = "performance_metric"


@dataclass
class Event:
    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "data": self.data,
            "metadata": self.metadata,
        }


@dataclass
class ProgressEvent(Event):
    def __init__(
        self,
        stage: str,
        current: int,
        total: int,
        message: str = "",
        current_file: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            event_type=EventType.NODE_PROGRESS,
            data={
                "stage": stage,
                "current": current,
                "total": total,
                "percentage": round(current / total * 100, 1) if total > 0 else 0,
                "message": message,
                "current_file": current_file,
            },
            **kwargs
        )


@dataclass
class LLMStreamingEvent(Event):
    def __init__(
        self,
        provider: str,
        model: str,
        chunk: str,
        tokens_generated: int = 0,
        **kwargs
    ):
        super().__init__(
            event_type=EventType.LLM_CALL_STREAMING,
            data={
                "provider": provider,
                "model": model,
                "chunk": chunk,
                "tokens_generated": tokens_generated,
            },
            **kwargs
        )


@dataclass
class PerformanceMetricEvent(Event):
    def __init__(
        self,
        metric_name: str,
        value: float,
        unit: str = "",
        tags: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        super().__init__(
            event_type=EventType.PERFORMANCE_METRIC,
            data={
                "metric_name": metric_name,
                "value": value,
                "unit": unit,
                "tags": tags or {},
            },
            **kwargs
        )


@dataclass
class ErrorEvent(Event):
    def __init__(
        self,
        error_type: str,
        error_message: str,
        stack_trace: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(
            event_type=EventType.ERROR_OCCURRED,
            data={
                "error_type": error_type,
                "error_message": error_message,
                "stack_trace": stack_trace,
                "context": context or {},
            },
            **kwargs
        )
