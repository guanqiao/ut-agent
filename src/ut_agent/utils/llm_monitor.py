"""LLM调用监控器 - 实时监控LLM调用状态."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict

from ut_agent.utils.events import Event, EventType
from ut_agent.utils.event_bus import event_bus


@dataclass
class LLMCallInfo:
    call_id: str
    provider: str = ""
    model: str = ""
    status: str = "pending"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    tokens_generated: int = 0
    duration_ms: float = 0.0
    first_token_latency_ms: float = 0.0
    tokens_per_second: float = 0.0
    error: str = ""
    
    @property
    def duration_str(self) -> str:
        if self.duration_ms > 0:
            if self.duration_ms >= 1000:
                return f"{self.duration_ms / 1000:.1f}s"
            return f"{self.duration_ms:.0f}ms"
        return "-"


@dataclass
class LLMStats:
    total_calls: int = 0
    active_calls: int = 0
    completed_calls: int = 0
    failed_calls: int = 0
    total_tokens: int = 0
    total_duration_ms: float = 0.0
    avg_first_token_latency_ms: float = 0.0
    avg_tokens_per_second: float = 0.0
    
    calls_by_provider: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    tokens_by_provider: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.completed_calls / self.total_calls * 100


class LLMMonitor:
    _instance: Optional['LLMMonitor'] = None
    
    def __new__(cls) -> 'LLMMonitor':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._active_calls: Dict[str, LLMCallInfo] = {}
        self._completed_calls: List[LLMCallInfo] = []
        self._stats = LLMStats()
        self._call_counter = 0
        self._subscribed = False
        self._max_history = 100
    
    @classmethod
    def get_instance(cls) -> 'LLMMonitor':
        return cls()
    
    def start(self) -> None:
        if not self._subscribed:
            event_bus.subscribe_all(self._handle_event)
            self._subscribed = True
    
    def stop(self) -> None:
        pass
    
    def _handle_event(self, event: Event) -> None:
        if event.event_type == EventType.LLM_CALL_STARTED:
            self._on_call_started(event)
        elif event.event_type == EventType.LLM_CALL_STREAMING:
            self._on_call_streaming(event)
        elif event.event_type == EventType.LLM_CALL_COMPLETED:
            self._on_call_completed(event)
        elif event.event_type == EventType.LLM_CALL_FAILED:
            self._on_call_failed(event)
    
    def _on_call_started(self, event: Event) -> None:
        self._call_counter += 1
        call_id = f"llm_{self._call_counter}"
        
        call_info = LLMCallInfo(
            call_id=call_id,
            provider=event.data.get("provider", "unknown"),
            model=event.data.get("model", "unknown"),
            status="running",
            start_time=event.timestamp,
        )
        
        self._active_calls[call_id] = call_info
        self._stats.total_calls += 1
        self._stats.active_calls += 1
        self._stats.calls_by_provider[call_info.provider] += 1
    
    def _on_call_streaming(self, event: Event) -> None:
        tokens = event.data.get("tokens_generated", 0)
        for call_info in self._active_calls.values():
            if call_info.status == "running":
                call_info.tokens_generated = tokens
    
    def _on_call_completed(self, event: Event) -> None:
        provider = event.data.get("provider", "unknown")
        tokens = event.data.get("total_tokens", 0)
        duration_ms = event.data.get("duration_ms", 0)
        first_token_latency = event.data.get("first_token_latency_ms", 0)
        tokens_per_second = event.data.get("tokens_per_second", 0)
        
        for call_id, call_info in list(self._active_calls.items()):
            if call_info.provider == provider and call_info.status == "running":
                call_info.status = "completed"
                call_info.end_time = event.timestamp
                call_info.tokens_generated = tokens
                call_info.duration_ms = duration_ms
                call_info.first_token_latency_ms = first_token_latency
                call_info.tokens_per_second = tokens_per_second
                
                self._completed_calls.append(call_info)
                del self._active_calls[call_id]
                
                self._stats.active_calls -= 1
                self._stats.completed_calls += 1
                self._stats.total_tokens += tokens
                self._stats.total_duration_ms += duration_ms
                self._stats.tokens_by_provider[provider] += tokens
                
                if self._stats.completed_calls > 0:
                    self._stats.avg_first_token_latency_ms = (
                        (self._stats.avg_first_token_latency_ms * (self._stats.completed_calls - 1) + first_token_latency)
                        / self._stats.completed_calls
                    )
                    self._stats.avg_tokens_per_second = (
                        (self._stats.avg_tokens_per_second * (self._stats.completed_calls - 1) + tokens_per_second)
                        / self._stats.completed_calls
                    )
                break
        
        if len(self._completed_calls) > self._max_history:
            self._completed_calls = self._completed_calls[-self._max_history:]
    
    def _on_call_failed(self, event: Event) -> None:
        provider = event.data.get("provider", "unknown")
        error = event.data.get("error", "Unknown error")
        
        for call_id, call_info in list(self._active_calls.items()):
            if call_info.provider == provider and call_info.status == "running":
                call_info.status = "failed"
                call_info.end_time = event.timestamp
                call_info.error = error
                call_info.duration_ms = event.data.get("duration_ms", 0)
                
                self._completed_calls.append(call_info)
                del self._active_calls[call_id]
                
                self._stats.active_calls -= 1
                self._stats.failed_calls += 1
                break
    
    def get_active_calls(self) -> List[LLMCallInfo]:
        return list(self._active_calls.values())
    
    def get_recent_calls(self, limit: int = 10) -> List[LLMCallInfo]:
        return self._completed_calls[-limit:]
    
    def get_stats(self) -> LLMStats:
        return self._stats
    
    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_calls": self._stats.total_calls,
            "active_calls": self._stats.active_calls,
            "completed_calls": self._stats.completed_calls,
            "failed_calls": self._stats.failed_calls,
            "success_rate": f"{self._stats.success_rate:.1f}%",
            "total_tokens": self._stats.total_tokens,
            "avg_duration_ms": self._stats.total_duration_ms / max(1, self._stats.completed_calls),
            "avg_first_token_latency_ms": self._stats.avg_first_token_latency_ms,
            "avg_tokens_per_second": self._stats.avg_tokens_per_second,
            "calls_by_provider": dict(self._stats.calls_by_provider),
            "tokens_by_provider": dict(self._stats.tokens_by_provider),
        }
    
    def reset(self) -> None:
        self._active_calls.clear()
        self._completed_calls.clear()
        self._stats = LLMStats()
        self._call_counter = 0


llm_monitor = LLMMonitor.get_instance()


def create_llm_monitor() -> LLMMonitor:
    return LLMMonitor()
