"""事件总线实现 - 统一的事件发射/订阅机制."""

import asyncio
import logging
from collections import defaultdict
from contextlib import contextmanager
from typing import Callable, Dict, List, Any, Optional, Set
from datetime import datetime
from threading import Lock

from ut_agent.utils.events import Event, EventType

logger = logging.getLogger(__name__)


EventHandler = Callable[[Event], None]
AsyncEventHandler = Callable[[Event], Any]


class EventBus:
    _instance: Optional['EventBus'] = None
    _lock = Lock()
    
    def __new__(cls) -> 'EventBus':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._sync_handlers: Dict[EventType, List[EventHandler]] = defaultdict(list)
        self._async_handlers: Dict[EventType, List[AsyncEventHandler]] = defaultdict(list)
        self._wildcard_handlers: List[EventHandler] = []
        self._event_history: List[Event] = []
        self._max_history: int = 1000
        self._enabled: bool = True
        self._event_counts: Dict[EventType, int] = defaultdict(int)
    
    @classmethod
    def get_instance(cls) -> 'EventBus':
        return cls()
    
    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
    ) -> None:
        self._sync_handlers[event_type].append(handler)
        logger.debug(f"Subscribed handler to event type: {event_type.value}")
    
    def subscribe_async(
        self,
        event_type: EventType,
        handler: AsyncEventHandler,
    ) -> None:
        self._async_handlers[event_type].append(handler)
        logger.debug(f"Subscribed async handler to event type: {event_type.value}")
    
    def subscribe_all(self, handler: EventHandler) -> None:
        self._wildcard_handlers.append(handler)
        logger.debug("Subscribed wildcard handler to all events")
    
    def unsubscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
    ) -> bool:
        if handler in self._sync_handlers[event_type]:
            self._sync_handlers[event_type].remove(handler)
            return True
        return False
    
    def emit(self, event: Event) -> None:
        if not self._enabled:
            return
        
        self._event_counts[event.event_type] += 1
        
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
        
        for handler in self._wildcard_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in wildcard handler: {e}")
        
        for handler in self._sync_handlers[event.event_type]:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in sync handler for {event.event_type.value}: {e}")
    
    async def emit_async(self, event: Event) -> None:
        self.emit(event)
        
        for handler in self._async_handlers[event.event_type]:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Error in async handler for {event.event_type.value}: {e}")
    
    def emit_simple(
        self,
        event_type: EventType,
        data: Optional[Dict[str, Any]] = None,
        source: str = "",
    ) -> None:
        event = Event(
            event_type=event_type,
            data=data or {},
            source=source,
        )
        self.emit(event)
    
    @contextmanager
    def track_event(
        self,
        event_type: EventType,
        source: str = "",
        **data
    ):
        start_time = datetime.now()
        self.emit_simple(
            event_type,
            {"status": "started", **data},
            source
        )
        try:
            yield
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.emit_simple(
                event_type,
                {"status": "completed", "duration_ms": duration_ms, **data},
                source
            )
        except Exception as e:
            self.emit_simple(
                EventType.ERROR_OCCURRED,
                {"error": str(e), "source_event": event_type.value, **data},
                source
            )
            raise
    
    def get_history(
        self,
        event_type: Optional[EventType] = None,
        limit: int = 100,
    ) -> List[Event]:
        events = self._event_history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]
    
    def get_event_counts(self) -> Dict[str, int]:
        return {et.value: count for et, count in self._event_counts.items()}
    
    def clear_history(self) -> None:
        self._event_history.clear()
    
    def enable(self) -> None:
        self._enabled = True
    
    def disable(self) -> None:
        self._enabled = False
    
    def reset(self) -> None:
        self._sync_handlers.clear()
        self._async_handlers.clear()
        self._wildcard_handlers.clear()
        self._event_history.clear()
        self._event_counts.clear()


event_bus = EventBus.get_instance()


def emit_progress(
    stage: str,
    current: int,
    total: int,
    message: str = "",
    current_file: Optional[str] = None,
    source: str = "",
) -> None:
    from ut_agent.utils.events import ProgressEvent
    event = ProgressEvent(
        stage=stage,
        current=current,
        total=total,
        message=message,
        current_file=current_file,
        source=source,
    )
    event_bus.emit(event)


def emit_error(
    error_type: str,
    error_message: str,
    stack_trace: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    source: str = "",
) -> None:
    from ut_agent.utils.events import ErrorEvent
    event = ErrorEvent(
        error_type=error_type,
        error_message=error_message,
        stack_trace=stack_trace,
        context=context,
        source=source,
    )
    event_bus.emit(event)


def emit_metric(
    metric_name: str,
    value: float,
    unit: str = "",
    tags: Optional[Dict[str, str]] = None,
    source: str = "",
) -> None:
    from ut_agent.utils.events import PerformanceMetricEvent
    event = PerformanceMetricEvent(
        metric_name=metric_name,
        value=value,
        unit=unit,
        tags=tags,
        source=source,
    )
    event_bus.emit(event)
