"""短期记忆管理器."""

from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import threading

from ut_agent.memory.models import SessionContext


class ShortTermMemoryManager:
    """短期记忆管理器 - 管理会话级上下文."""
    
    def __init__(
        self,
        max_sessions: int = 100,
        session_ttl_minutes: int = 60,
    ):
        self._max_sessions = max_sessions
        self._session_ttl = timedelta(minutes=session_ttl_minutes)
        self._sessions: OrderedDict[str, SessionContext] = OrderedDict()
        self._lock = threading.RLock()
    
    def create_session(
        self,
        project_path: str = "",
        project_type: str = "",
    ) -> str:
        with self._lock:
            if len(self._sessions) >= self._max_sessions:
                self._evict_oldest()
            
            context = SessionContext(
                project_path=project_path,
                project_type=project_type,
            )
            self._sessions[context.session_id] = context
            return context.session_id
    
    def get_session(self, session_id: str) -> Optional[SessionContext]:
        with self._lock:
            context = self._sessions.get(session_id)
            if context:
                if self._is_expired(context):
                    del self._sessions[session_id]
                    return None
                context.touch()
                self._sessions.move_to_end(session_id)
            return context
    
    def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        project_path: str = "",
        project_type: str = "",
    ) -> SessionContext:
        if session_id:
            context = self.get_session(session_id)
            if context:
                return context
        
        return self.create_session_context(project_path, project_type)
    
    def create_session_context(
        self,
        project_path: str = "",
        project_type: str = "",
    ) -> SessionContext:
        session_id = self.create_session(project_path, project_type)
        return self._sessions[session_id]
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Dict[str, Any] = None,
    ) -> bool:
        context = self.get_session(session_id)
        if context:
            context.add_message(role, content, metadata)
            return True
        return False
    
    def get_conversation_history(
        self,
        session_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        context = self.get_session(session_id)
        if context:
            return context.conversation_history[-limit:]
        return []
    
    def set_context(
        self,
        session_id: str,
        key: str,
        value: Any,
    ) -> bool:
        context = self.get_session(session_id)
        if context:
            context.working_context[key] = value
            context.touch()
            return True
        return False
    
    def get_context(
        self,
        session_id: str,
        key: str,
        default: Any = None,
    ) -> Any:
        context = self.get_session(session_id)
        if context:
            return context.working_context.get(key, default)
        return default
    
    def set_temp_result(
        self,
        session_id: str,
        key: str,
        value: Any,
    ) -> bool:
        context = self.get_session(session_id)
        if context:
            context.temp_results[key] = {
                "value": value,
                "timestamp": datetime.now().isoformat(),
            }
            context.touch()
            return True
        return False
    
    def get_temp_result(
        self,
        session_id: str,
        key: str,
    ) -> Optional[Any]:
        context = self.get_session(session_id)
        if context and key in context.temp_results:
            return context.temp_results[key]["value"]
        return None
    
    def clear_session(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False
    
    def clear_all(self) -> None:
        with self._lock:
            self._sessions.clear()
    
    def cleanup_expired(self) -> int:
        with self._lock:
            expired = [
                sid for sid, ctx in self._sessions.items()
                if self._is_expired(ctx)
            ]
            for sid in expired:
                del self._sessions[sid]
            return len(expired)
    
    def get_active_session_count(self) -> int:
        return len(self._sessions)
    
    def _is_expired(self, context: SessionContext) -> bool:
        return datetime.now() - context.last_accessed > self._session_ttl
    
    def _evict_oldest(self) -> None:
        if self._sessions:
            oldest_id = next(iter(self._sessions))
            del self._sessions[oldest_id]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_sessions": len(self._sessions),
            "max_sessions": self._max_sessions,
            "session_ttl_minutes": self._session_ttl.total_seconds() / 60,
        }
