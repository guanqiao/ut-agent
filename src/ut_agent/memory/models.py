"""记忆数据模型."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class MemoryEntry:
    """记忆条目基类."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    agent_name: str = ""
    content: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "agent_name": self.agent_name,
            "content": self.content,
            "metadata": self.metadata,
        }


@dataclass
class GenerationRecord(MemoryEntry):
    """测试生成记录."""
    
    source_file: str = ""
    test_file: str = ""
    test_code: str = ""
    coverage_achieved: float = 0.0
    patterns_used: List[str] = field(default_factory=list)
    user_feedback: Optional[str] = None
    user_rating: Optional[int] = None
    generation_time_ms: int = 0
    llm_provider: str = ""
    template_used: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "source_file": self.source_file,
            "test_file": self.test_file,
            "coverage_achieved": self.coverage_achieved,
            "patterns_used": self.patterns_used,
            "user_feedback": self.user_feedback,
            "user_rating": self.user_rating,
            "generation_time_ms": self.generation_time_ms,
            "llm_provider": self.llm_provider,
            "template_used": self.template_used,
        })
        return data


@dataclass
class FixRecord(MemoryEntry):
    """修复记录."""
    
    source_file: str = ""
    test_file: str = ""
    error_type: str = ""
    error_message: str = ""
    fix_applied: str = ""
    fix_successful: bool = False
    original_code: str = ""
    fixed_code: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "source_file": self.source_file,
            "test_file": self.test_file,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "fix_applied": self.fix_applied,
            "fix_successful": self.fix_successful,
        })
        return data


@dataclass
class CodeTestPattern(MemoryEntry):
    """测试模式."""
    
    pattern_name: str = ""
    pattern_type: str = ""
    language: str = ""
    description: str = ""
    code_template: str = ""
    use_cases: List[str] = field(default_factory=list)
    success_rate: float = 0.0
    usage_count: int = 0
    
    def to_text(self) -> str:
        return f"""
Pattern: {self.pattern_name}
Type: {self.pattern_type}
Language: {self.language}
Description: {self.description}
Use Cases: {', '.join(self.use_cases)}
Template:
{self.code_template}
"""
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "pattern_name": self.pattern_name,
            "pattern_type": self.pattern_type,
            "language": self.language,
            "description": self.description,
            "code_template": self.code_template,
            "use_cases": self.use_cases,
            "success_rate": self.success_rate,
            "usage_count": self.usage_count,
        })
        return data


@dataclass
class UserPreference(MemoryEntry):
    """用户偏好."""
    
    preference_key: str = ""
    preference_value: Any = None
    confidence: float = 0.0
    source: str = ""
    sample_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "preference_key": self.preference_key,
            "preference_value": self.preference_value,
            "confidence": self.confidence,
            "source": self.source,
            "sample_count": self.sample_count,
        })
        return data


@dataclass
class SessionContext:
    """会话上下文."""
    
    session_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    project_path: str = ""
    project_type: str = ""
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    working_context: Dict[str, Any] = field(default_factory=dict)
    temp_results: Dict[str, Any] = field(default_factory=dict)
    
    def touch(self) -> None:
        self.last_accessed = datetime.now()
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        })
        self.touch()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "project_path": self.project_path,
            "project_type": self.project_type,
            "conversation_history": self.conversation_history,
            "working_context": self.working_context,
        }
