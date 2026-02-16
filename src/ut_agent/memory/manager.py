"""记忆管理器 - 统一管理所有记忆类型."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ut_agent.memory.models import (
    GenerationRecord,
    FixRecord,
    CodeTestPattern,
    UserPreference,
)
from ut_agent.memory.short_term import ShortTermMemoryManager
from ut_agent.memory.long_term import LongTermMemoryManager
from ut_agent.memory.semantic import SemanticMemoryManager


class MemoryManager:
    """统一记忆管理器."""
    
    def __init__(
        self,
        storage_path: Optional[Path] = None,
        max_sessions: int = 100,
        session_ttl_minutes: int = 60,
        embedding_model: str = "text-embedding-3-small",
    ):
        self._storage_path = storage_path
        
        self._short_term = ShortTermMemoryManager(
            max_sessions=max_sessions,
            session_ttl_minutes=session_ttl_minutes,
        )
        
        self._long_term = LongTermMemoryManager(storage_path)
        
        self._semantic = SemanticMemoryManager(
            storage_path=storage_path / "vectors" if storage_path else None,
            embedding_model=embedding_model,
        )
    
    @property
    def short_term(self) -> ShortTermMemoryManager:
        return self._short_term
    
    @property
    def long_term(self) -> LongTermMemoryManager:
        return self._long_term
    
    @property
    def semantic(self) -> SemanticMemoryManager:
        return self._semantic
    
    def create_session(
        self,
        project_path: str = "",
        project_type: str = "",
    ) -> str:
        return self._short_term.create_session(project_path, project_type)
    
    def get_session(self, session_id: str):
        return self._short_term.get_session(session_id)
    
    def remember(
        self,
        agent_name: str,
        key: str,
        value: Any,
        session_id: Optional[str] = None,
    ) -> None:
        if session_id:
            self._short_term.set_context(
                session_id,
                f"{agent_name}:{key}",
                value,
            )
    
    def recall(
        self,
        agent_name: str,
        key: str,
        session_id: Optional[str] = None,
    ) -> Optional[Any]:
        if session_id:
            return self._short_term.get_context(
                session_id,
                f"{agent_name}:{key}",
            )
        return None
    
    def save_generation(
        self,
        agent_name: str,
        source_file: str,
        test_file: str,
        test_code: str,
        coverage: float = 0.0,
        patterns: List[str] = None,
        template: str = "",
        llm_provider: str = "",
        generation_time_ms: int = 0,
    ) -> str:
        record = GenerationRecord(
            agent_name=agent_name,
            source_file=source_file,
            test_file=test_file,
            test_code=test_code,
            coverage_achieved=coverage,
            patterns_used=patterns or [],
            template_used=template,
            llm_provider=llm_provider,
            generation_time_ms=generation_time_ms,
        )
        
        record_id = self._long_term.save_generation(record)
        
        self._semantic.add_pattern(
            pattern_id=record_id,
            content=f"{source_file}\n{test_code}",
            metadata={
                "type": "generation",
                "agent": agent_name,
                "source_file": source_file,
                "coverage": coverage,
                "template": template,
            },
        )
        
        return record_id
    
    def get_similar_generations(
        self,
        source_file: str,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        return self._semantic.find_similar(
            query=source_file,
            k=k,
        )
    
    def save_fix(
        self,
        agent_name: str,
        source_file: str,
        test_file: str,
        error_type: str,
        error_message: str,
        fix_applied: str,
        success: bool,
    ) -> str:
        record = FixRecord(
            agent_name=agent_name,
            source_file=source_file,
            test_file=test_file,
            error_type=error_type,
            error_message=error_message,
            fix_applied=fix_applied,
            fix_successful=success,
        )
        
        return self._long_term.save_fix(record)
    
    def get_fix_suggestions(
        self,
        error_type: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        records = self._long_term.get_fixes_by_error_type(error_type, limit)
        return [
            {
                "error_type": r.error_type,
                "fix_applied": r.fix_applied,
                "success": r.fix_successful,
            }
            for r in records
        ]
    
    def save_pattern(
        self,
        pattern_name: str,
        pattern_type: str,
        language: str,
        description: str,
        code_template: str,
        use_cases: List[str] = None,
    ) -> str:
        pattern = CodeTestPattern(
            pattern_name=pattern_name,
            pattern_type=pattern_type,
            language=language,
            description=description,
            code_template=code_template,
            use_cases=use_cases or [],
        )
        
        pattern_id = self._long_term.save_pattern(pattern)
        
        self._semantic.add_pattern(
            pattern_id=pattern_id,
            content=f"{pattern_name}\n{description}\n{code_template}",
            metadata={
                "type": "pattern",
                "pattern_type": pattern_type,
                "language": language,
            },
        )
        
        return pattern_id
    
    def find_patterns(
        self,
        query: str,
        language: Optional[str] = None,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        return self._semantic.find_similar(
            query=query,
            k=k,
            language=language,
        )
    
    def learn(
        self,
        agent_name: str,
        feedback: Dict[str, Any],
    ) -> None:
        feedback_type = feedback.get("type", "")
        
        if feedback_type == "user_rating":
            key = f"rating:{feedback.get('source_file', 'default')}"
            rating = feedback.get("rating", 3)
            self._long_term.update_preference(
                key,
                rating,
                source="user_feedback",
            )
        
        elif feedback_type == "template_success":
            template = feedback.get("template", "")
            success = feedback.get("success", False)
            key = f"template:{template}"
            
            existing = self._long_term.get_preference(key)
            if existing:
                new_count = existing.sample_count + 1
                old_rate = existing.confidence
                new_rate = (
                    (old_rate * (new_count - 1) + (1 if success else 0))
                    / new_count
                )
                existing.preference_value = {"success_rate": new_rate}
                existing.sample_count = new_count
                existing.confidence = new_rate
                self._long_term.save_preference(existing)
            else:
                self._long_term.save_preference(UserPreference(
                    preference_key=key,
                    preference_value={"success_rate": 1 if success else 0},
                    confidence=0.5,
                    source="template_usage",
                    sample_count=1,
                ))
        
        elif feedback_type == "pattern_usage":
            pattern_id = feedback.get("pattern_id", "")
            success = feedback.get("success", False)
            if pattern_id:
                self._long_term.update_pattern_usage(pattern_id, success)
    
    def get_preferences(self) -> Dict[str, Any]:
        preferences = self._long_term.get_all_preferences()
        return {
            p.preference_key: {
                "value": p.preference_value,
                "confidence": p.confidence,
                "samples": p.sample_count,
            }
            for p in preferences
        }
    
    def get_recommended_templates(self, language: str) -> List[str]:
        templates = []
        prefs = self.get_preferences()
        
        for key, pref in prefs.items():
            if key.startswith("template:"):
                template_name = key.replace("template:", "")
                success_rate = pref.get("value", {}).get("success_rate", 0)
                if success_rate > 0.7:
                    templates.append(template_name)
        
        return templates
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "short_term": {
                "active_sessions": self._short_term.get_active_session_count(),
            },
            "long_term": self._long_term.get_stats(),
            "semantic": {
                "pattern_count": self._semantic.get_pattern_count(),
            },
        }
    
    def cleanup(self) -> Dict[str, int]:
        expired_sessions = self._short_term.cleanup_expired()
        
        return {
            "expired_sessions": expired_sessions,
        }
