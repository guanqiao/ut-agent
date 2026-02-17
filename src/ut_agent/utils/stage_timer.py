"""阶段计时器 - 用于性能分析."""

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Generator

from ut_agent.utils.event_bus import event_bus, emit_metric
from ut_agent.utils.events import EventType


@dataclass
class StageRecord:
    stage_name: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def start(self) -> None:
        self.start_time = datetime.now()
    
    def stop(self) -> float:
        self.end_time = datetime.now()
        if self.start_time:
            self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        return self.duration_ms


class StageTimer:
    _instance: Optional['StageTimer'] = None
    
    def __new__(cls) -> 'StageTimer':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._stages: Dict[str, StageRecord] = {}
        self._history: List[StageRecord] = []
        self._current_stage: Optional[str] = None
    
    @classmethod
    def get_instance(cls) -> 'StageTimer':
        return cls()
    
    def start_stage(self, stage_name: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        record = StageRecord(
            stage_name=stage_name,
            metadata=metadata or {},
        )
        record.start()
        self._stages[stage_name] = record
        self._current_stage = stage_name
        
        event_bus.emit_simple(
            EventType.NODE_STARTED,
            {"stage": stage_name, "metadata": metadata},
            source="StageTimer",
        )
    
    def stop_stage(self, stage_name: str) -> float:
        if stage_name not in self._stages:
            return 0.0
        
        record = self._stages[stage_name]
        duration = record.stop()
        
        self._history.append(record)
        
        emit_metric(
            metric_name=f"{stage_name}_duration_ms",
            value=duration,
            unit="ms",
            source="StageTimer",
        )
        
        event_bus.emit_simple(
            EventType.NODE_COMPLETED,
            {"stage": stage_name, "duration_ms": duration},
            source="StageTimer",
        )
        
        if self._current_stage == stage_name:
            self._current_stage = None
        
        return duration
    
    @contextmanager
    def measure(self, stage_name: str, metadata: Optional[Dict[str, Any]] = None) -> Generator[StageRecord, None, None]:
        self.start_stage(stage_name, metadata)
        record = self._stages[stage_name]
        try:
            yield record
        finally:
            self.stop_stage(stage_name)
    
    def get_stage_duration(self, stage_name: str) -> float:
        if stage_name in self._stages:
            return self._stages[stage_name].duration_ms
        
        for record in reversed(self._history):
            if record.stage_name == stage_name:
                return record.duration_ms
        
        return 0.0
    
    def get_all_durations(self) -> Dict[str, float]:
        durations = {}
        for record in self._history:
            if record.stage_name not in durations:
                durations[record.stage_name] = record.duration_ms
        return durations
    
    def get_summary(self) -> Dict[str, Any]:
        total_duration = sum(r.duration_ms for r in self._history)
        
        stage_stats = {}
        for record in self._history:
            if record.stage_name not in stage_stats:
                stage_stats[record.stage_name] = {
                    "count": 0,
                    "total_ms": 0.0,
                    "min_ms": float('inf'),
                    "max_ms": 0.0,
                }
            stats = stage_stats[record.stage_name]
            stats["count"] += 1
            stats["total_ms"] += record.duration_ms
            stats["min_ms"] = min(stats["min_ms"], record.duration_ms)
            stats["max_ms"] = max(stats["max_ms"], record.duration_ms)
        
        for stage_name, stats in stage_stats.items():
            if stats["count"] > 0:
                stats["avg_ms"] = stats["total_ms"] / stats["count"]
            if stats["min_ms"] == float('inf'):
                stats["min_ms"] = 0.0
        
        return {
            "total_duration_ms": total_duration,
            "stage_count": len(stage_stats),
            "stages": stage_stats,
        }
    
    def reset(self) -> None:
        self._stages.clear()
        self._history.clear()
        self._current_stage = None
    
    @property
    def current_stage(self) -> Optional[str]:
        return self._current_stage


stage_timer = StageTimer.get_instance()


def time_stage(stage_name: str, metadata: Optional[Dict[str, Any]] = None):
    return stage_timer.measure(stage_name, metadata)
