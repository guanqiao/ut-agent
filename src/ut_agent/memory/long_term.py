"""长期记忆管理器."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import threading

from ut_agent.memory.models import (
    MemoryEntry,
    GenerationRecord,
    FixRecord,
    CodeTestPattern,
    UserPreference,
)


class LongTermMemoryManager:
    """长期记忆管理器 - 持久化存储历史经验和偏好."""
    
    def __init__(self, storage_path: Optional[Path] = None):
        self._storage_path = storage_path or Path.home() / ".ut-agent" / "memory"
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        self._db_path = self._storage_path / "memory.db"
        self._lock = threading.RLock()
        
        self._init_db()
    
    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS generation_records (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    agent_name TEXT,
                    source_file TEXT NOT NULL,
                    test_file TEXT,
                    test_code TEXT,
                    coverage_achieved REAL,
                    patterns_used TEXT,
                    user_feedback TEXT,
                    user_rating INTEGER,
                    generation_time_ms INTEGER,
                    llm_provider TEXT,
                    template_used TEXT,
                    metadata TEXT
                );
                
                CREATE TABLE IF NOT EXISTS fix_records (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    agent_name TEXT,
                    source_file TEXT,
                    test_file TEXT,
                    error_type TEXT,
                    error_message TEXT,
                    fix_applied TEXT,
                    fix_successful INTEGER,
                    metadata TEXT
                );
                
                CREATE TABLE IF NOT EXISTS test_patterns (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    pattern_name TEXT NOT NULL,
                    pattern_type TEXT,
                    language TEXT,
                    description TEXT,
                    code_template TEXT,
                    use_cases TEXT,
                    success_rate REAL,
                    usage_count INTEGER,
                    metadata TEXT
                );
                
                CREATE TABLE IF NOT EXISTS user_preferences (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    preference_key TEXT NOT NULL UNIQUE,
                    preference_value TEXT,
                    confidence REAL,
                    source TEXT,
                    sample_count INTEGER,
                    metadata TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_generation_source ON generation_records(source_file);
                CREATE INDEX IF NOT EXISTS idx_generation_timestamp ON generation_records(timestamp);
                CREATE INDEX IF NOT EXISTS idx_fix_error_type ON fix_records(error_type);
                CREATE INDEX IF NOT EXISTS idx_pattern_language ON test_patterns(language);
                CREATE INDEX IF NOT EXISTS idx_preference_key ON user_preferences(preference_key);
            """)
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def save_generation(self, record: GenerationRecord) -> str:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO generation_records
                    (id, timestamp, agent_name, source_file, test_file, test_code,
                     coverage_achieved, patterns_used, user_feedback, user_rating,
                     generation_time_ms, llm_provider, template_used, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.id,
                    record.timestamp.isoformat(),
                    record.agent_name,
                    record.source_file,
                    record.test_file,
                    record.test_code,
                    record.coverage_achieved,
                    json.dumps(record.patterns_used),
                    record.user_feedback,
                    record.user_rating,
                    record.generation_time_ms,
                    record.llm_provider,
                    record.template_used,
                    json.dumps(record.metadata),
                ))
                return record.id
    
    def get_generation(self, record_id: str) -> Optional[GenerationRecord]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM generation_records WHERE id = ?",
                (record_id,)
            ).fetchone()
            if row:
                return self._row_to_generation_record(row)
        return None
    
    def get_generations_by_source(
        self,
        source_file: str,
        limit: int = 10,
    ) -> List[GenerationRecord]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM generation_records
                WHERE source_file = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (source_file, limit)).fetchall()
            return [self._row_to_generation_record(row) for row in rows]
    
    def get_recent_generations(self, limit: int = 20) -> List[GenerationRecord]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM generation_records
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [self._row_to_generation_record(row) for row in rows]
    
    def save_fix(self, record: FixRecord) -> str:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO fix_records
                    (id, timestamp, agent_name, source_file, test_file,
                     error_type, error_message, fix_applied, fix_successful, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.id,
                    record.timestamp.isoformat(),
                    record.agent_name,
                    record.source_file,
                    record.test_file,
                    record.error_type,
                    record.error_message,
                    record.fix_applied,
                    1 if record.fix_successful else 0,
                    json.dumps(record.metadata),
                ))
                return record.id
    
    def get_fixes_by_error_type(
        self,
        error_type: str,
        limit: int = 20,
    ) -> List[FixRecord]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM fix_records
                WHERE error_type = ? AND fix_successful = 1
                ORDER BY timestamp DESC
                LIMIT ?
            """, (error_type, limit)).fetchall()
            return [self._row_to_fix_record(row) for row in rows]
    
    def save_pattern(self, pattern: CodeTestPattern) -> str:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO test_patterns
                    (id, timestamp, pattern_name, pattern_type, language,
                     description, code_template, use_cases, success_rate,
                     usage_count, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pattern.id,
                    pattern.timestamp.isoformat(),
                    pattern.pattern_name,
                    pattern.pattern_type,
                    pattern.language,
                    pattern.description,
                    pattern.code_template,
                    json.dumps(pattern.use_cases),
                    pattern.success_rate,
                    pattern.usage_count,
                    json.dumps(pattern.metadata),
                ))
                return pattern.id
    
    def get_patterns_by_language(
        self,
        language: str,
        limit: int = 20,
    ) -> List[CodeTestPattern]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM test_patterns
                WHERE language = ?
                ORDER BY success_rate DESC, usage_count DESC
                LIMIT ?
            """, (language, limit)).fetchall()
            return [self._row_to_test_pattern(row) for row in rows]
    
    def update_pattern_usage(self, pattern_id: str, success: bool) -> None:
        with self._lock:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT usage_count, success_rate FROM test_patterns WHERE id = ?",
                    (pattern_id,)
                ).fetchone()
                if row:
                    usage_count = row["usage_count"] + 1
                    old_rate = row["success_rate"]
                    new_rate = (
                        (old_rate * (usage_count - 1) + (1 if success else 0))
                        / usage_count
                    )
                    conn.execute("""
                        UPDATE test_patterns
                        SET usage_count = ?, success_rate = ?
                        WHERE id = ?
                    """, (usage_count, new_rate, pattern_id))
    
    def save_preference(self, preference: UserPreference) -> str:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO user_preferences
                    (id, timestamp, preference_key, preference_value,
                     confidence, source, sample_count, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    preference.id,
                    preference.timestamp.isoformat(),
                    preference.preference_key,
                    json.dumps(preference.preference_value),
                    preference.confidence,
                    preference.source,
                    preference.sample_count,
                    json.dumps(preference.metadata),
                ))
                return preference.id
    
    def get_preference(self, key: str) -> Optional[UserPreference]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM user_preferences WHERE preference_key = ?",
                (key,)
            ).fetchone()
            if row:
                return self._row_to_user_preference(row)
        return None
    
    def get_all_preferences(self) -> List[UserPreference]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM user_preferences ORDER BY confidence DESC"
            ).fetchall()
            return [self._row_to_user_preference(row) for row in rows]
    
    def update_preference(
        self,
        key: str,
        value: Any,
        source: str = "implicit",
    ) -> None:
        existing = self.get_preference(key)
        if existing:
            new_count = existing.sample_count + 1
            new_confidence = min(1.0, existing.confidence + 0.1)
            existing.preference_value = value
            existing.sample_count = new_count
            existing.confidence = new_confidence
            existing.source = source
            self.save_preference(existing)
        else:
            self.save_preference(UserPreference(
                preference_key=key,
                preference_value=value,
                confidence=0.5,
                source=source,
                sample_count=1,
            ))
    
    def _row_to_generation_record(self, row: sqlite3.Row) -> GenerationRecord:
        return GenerationRecord(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            agent_name=row["agent_name"] or "",
            source_file=row["source_file"],
            test_file=row["test_file"] or "",
            test_code=row["test_code"] or "",
            coverage_achieved=row["coverage_achieved"] or 0.0,
            patterns_used=json.loads(row["patterns_used"] or "[]"),
            user_feedback=row["user_feedback"],
            user_rating=row["user_rating"],
            generation_time_ms=row["generation_time_ms"] or 0,
            llm_provider=row["llm_provider"] or "",
            template_used=row["template_used"] or "",
            metadata=json.loads(row["metadata"] or "{}"),
        )
    
    def _row_to_fix_record(self, row: sqlite3.Row) -> FixRecord:
        return FixRecord(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            agent_name=row["agent_name"] or "",
            source_file=row["source_file"] or "",
            test_file=row["test_file"] or "",
            error_type=row["error_type"] or "",
            error_message=row["error_message"] or "",
            fix_applied=row["fix_applied"] or "",
            fix_successful=bool(row["fix_successful"]),
            metadata=json.loads(row["metadata"] or "{}"),
        )
    
    def _row_to_test_pattern(self, row: sqlite3.Row) -> CodeTestPattern:
        return CodeTestPattern(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            pattern_name=row["pattern_name"],
            pattern_type=row["pattern_type"] or "",
            language=row["language"] or "",
            description=row["description"] or "",
            code_template=row["code_template"] or "",
            use_cases=json.loads(row["use_cases"] or "[]"),
            success_rate=row["success_rate"] or 0.0,
            usage_count=row["usage_count"] or 0,
            metadata=json.loads(row["metadata"] or "{}"),
        )
    
    def _row_to_user_preference(self, row: sqlite3.Row) -> UserPreference:
        return UserPreference(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            preference_key=row["preference_key"],
            preference_value=json.loads(row["preference_value"] or "null"),
            confidence=row["confidence"] or 0.0,
            source=row["source"] or "",
            sample_count=row["sample_count"] or 0,
            metadata=json.loads(row["metadata"] or "{}"),
        )
    
    def get_stats(self) -> Dict[str, int]:
        with self._get_connection() as conn:
            return {
                "generation_records": conn.execute(
                    "SELECT COUNT(*) FROM generation_records"
                ).fetchone()[0],
                "fix_records": conn.execute(
                    "SELECT COUNT(*) FROM fix_records"
                ).fetchone()[0],
                "test_patterns": conn.execute(
                    "SELECT COUNT(*) FROM test_patterns"
                ).fetchone()[0],
                "user_preferences": conn.execute(
                    "SELECT COUNT(*) FROM user_preferences"
                ).fetchone()[0],
            }
