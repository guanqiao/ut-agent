"""Memory 数据模型单元测试."""

import pytest
from datetime import datetime
from typing import List

from ut_agent.memory.models import (
    MemoryEntry,
    GenerationRecord,
    FixRecord,
    CodeTestPattern,
    UserPreference,
    SessionContext,
)


class TestMemoryEntry:
    """MemoryEntry 数据类测试."""

    def test_memory_entry_creation(self):
        """测试 MemoryEntry 创建."""
        entry = MemoryEntry(
            agent_name="test_agent",
            content="test content",
            metadata={"key": "value"},
        )

        assert entry.agent_name == "test_agent"
        assert entry.content == "test content"
        assert entry.metadata["key"] == "value"
        assert entry.id is not None
        assert isinstance(entry.timestamp, datetime)

    def test_memory_entry_defaults(self):
        """测试 MemoryEntry 默认值."""
        entry = MemoryEntry()

        assert entry.id is not None
        assert isinstance(entry.timestamp, datetime)
        assert entry.agent_name == ""
        assert entry.content is None
        assert entry.metadata == {}
        assert entry.embedding is None

    def test_memory_entry_to_dict(self):
        """测试 to_dict 方法."""
        entry = MemoryEntry(
            agent_name="test_agent",
            content="test content",
            metadata={"key": "value"},
        )

        data = entry.to_dict()

        assert data["agent_name"] == "test_agent"
        assert data["content"] == "test content"
        assert data["metadata"]["key"] == "value"
        assert "id" in data
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)  # ISO format


class TestGenerationRecord:
    """GenerationRecord 数据类测试."""

    def test_generation_record_creation(self):
        """测试 GenerationRecord 创建."""
        record = GenerationRecord(
            agent_name="generator",
            source_file="/src/Main.java",
            test_file="/test/MainTest.java",
            test_code="public class MainTest {}",
            coverage_achieved=85.5,
            patterns_used=["mockito", "junit5"],
            user_rating=5,
            generation_time_ms=1500,
            llm_provider="openai",
            template_used="java-controller",
        )

        assert record.source_file == "/src/Main.java"
        assert record.test_file == "/test/MainTest.java"
        assert record.coverage_achieved == 85.5
        assert len(record.patterns_used) == 2
        assert record.user_rating == 5
        assert record.generation_time_ms == 1500

    def test_generation_record_defaults(self):
        """测试 GenerationRecord 默认值."""
        record = GenerationRecord()

        assert record.source_file == ""
        assert record.test_file == ""
        assert record.test_code == ""
        assert record.coverage_achieved == 0.0
        assert record.patterns_used == []
        assert record.user_feedback is None
        assert record.user_rating is None
        assert record.generation_time_ms == 0
        assert record.llm_provider == ""
        assert record.template_used == ""

    def test_generation_record_to_dict(self):
        """测试 to_dict 方法."""
        record = GenerationRecord(
            agent_name="generator",
            source_file="/src/Main.java",
            test_file="/test/MainTest.java",
            coverage_achieved=85.5,
            patterns_used=["mockito"],
        )

        data = record.to_dict()

        assert data["source_file"] == "/src/Main.java"
        assert data["test_file"] == "/test/MainTest.java"
        assert data["coverage_achieved"] == 85.5
        assert data["patterns_used"] == ["mockito"]
        assert "id" in data
        assert "timestamp" in data


class TestFixRecord:
    """FixRecord 数据类测试."""

    def test_fix_record_creation(self):
        """测试 FixRecord 创建."""
        record = FixRecord(
            agent_name="fixer",
            source_file="/src/Main.java",
            test_file="/test/MainTest.java",
            error_type="compilation",
            error_message="cannot find symbol",
            fix_applied="add_import",
            fix_successful=True,
            original_code="class Test {}",
            fixed_code="import java.util.List;\nclass Test {}",
        )

        assert record.source_file == "/src/Main.java"
        assert record.error_type == "compilation"
        assert record.error_message == "cannot find symbol"
        assert record.fix_applied == "add_import"
        assert record.fix_successful is True
        assert record.original_code == "class Test {}"

    def test_fix_record_defaults(self):
        """测试 FixRecord 默认值."""
        record = FixRecord()

        assert record.source_file == ""
        assert record.test_file == ""
        assert record.error_type == ""
        assert record.error_message == ""
        assert record.fix_applied == ""
        assert record.fix_successful is False
        assert record.original_code == ""
        assert record.fixed_code == ""

    def test_fix_record_to_dict(self):
        """测试 to_dict 方法."""
        record = FixRecord(
            agent_name="fixer",
            source_file="/src/Main.java",
            error_type="compilation",
            fix_successful=True,
        )

        data = record.to_dict()

        assert data["source_file"] == "/src/Main.java"
        assert data["error_type"] == "compilation"
        assert data["fix_successful"] is True
        assert "id" in data
        assert "timestamp" in data


class TestCodeTestPattern:
    """CodeTestPattern 数据类测试."""

    def test_code_test_pattern_creation(self):
        """测试 CodeTestPattern 创建."""
        pattern = CodeTestPattern(
            agent_name="analyzer",
            pattern_name="controller_test",
            pattern_type="spring",
            language="java",
            description="Test pattern for Spring controllers",
            code_template="@Test\nvoid test() {}",
            use_cases=["rest_api", "mvc"],
            success_rate=0.95,
            usage_count=100,
        )

        assert pattern.pattern_name == "controller_test"
        assert pattern.pattern_type == "spring"
        assert pattern.language == "java"
        assert pattern.description == "Test pattern for Spring controllers"
        assert pattern.code_template == "@Test\nvoid test() {}"
        assert len(pattern.use_cases) == 2
        assert pattern.success_rate == 0.95
        assert pattern.usage_count == 100

    def test_code_test_pattern_defaults(self):
        """测试 CodeTestPattern 默认值."""
        pattern = CodeTestPattern()

        assert pattern.pattern_name == ""
        assert pattern.pattern_type == ""
        assert pattern.language == ""
        assert pattern.description == ""
        assert pattern.code_template == ""
        assert pattern.use_cases == []
        assert pattern.success_rate == 0.0
        assert pattern.usage_count == 0

    def test_code_test_pattern_to_text(self):
        """测试 to_text 方法."""
        pattern = CodeTestPattern(
            pattern_name="controller_test",
            pattern_type="spring",
            language="java",
            description="Test pattern for Spring controllers",
            code_template="@Test\nvoid test() {}",
        )

        text = pattern.to_text()

        assert "controller_test" in text
        assert "spring" in text
        assert "java" in text
        assert "Test pattern for Spring controllers" in text
        assert "@Test" in text

    def test_code_test_pattern_to_dict(self):
        """测试 to_dict 方法."""
        pattern = CodeTestPattern(
            agent_name="analyzer",
            pattern_name="controller_test",
            pattern_type="spring",
            success_rate=0.95,
        )

        data = pattern.to_dict()

        assert data["pattern_name"] == "controller_test"
        assert data["pattern_type"] == "spring"
        assert data["success_rate"] == 0.95
        assert "id" in data
        assert "timestamp" in data


class TestUserPreference:
    """UserPreference 数据类测试."""

    def test_user_preference_creation(self):
        """测试 UserPreference 创建."""
        pref = UserPreference(
            agent_name="user",
            preference_key="theme",
            preference_value="dark",
            confidence=0.9,
            source="user_input",
            sample_count=10,
        )

        assert pref.preference_key == "theme"
        assert pref.preference_value == "dark"
        assert pref.confidence == 0.9
        assert pref.source == "user_input"
        assert pref.sample_count == 10

    def test_user_preference_defaults(self):
        """测试 UserPreference 默认值."""
        pref = UserPreference()

        assert pref.preference_key == ""
        assert pref.preference_value is None
        assert pref.confidence == 0.0
        assert pref.source == ""
        assert pref.sample_count == 0

    def test_user_preference_to_dict(self):
        """测试 to_dict 方法."""
        pref = UserPreference(
            agent_name="user",
            preference_key="language",
            preference_value="java",
            confidence=0.8,
        )

        data = pref.to_dict()

        assert data["preference_key"] == "language"
        assert data["preference_value"] == "java"
        assert data["confidence"] == 0.8
        assert "id" in data
        assert "timestamp" in data


class TestSessionContext:
    """SessionContext 数据类测试."""

    def test_session_context_creation(self):
        """测试 SessionContext 创建."""
        context = SessionContext(
            session_id="session-123",
            project_path="/project",
            project_type="java",
            conversation_history=[{"role": "user", "content": "hello"}],
            working_context={"file": "/src/Main.java"},
        )

        assert context.session_id == "session-123"
        assert context.project_path == "/project"
        assert context.project_type == "java"
        assert len(context.conversation_history) == 1
        assert context.working_context["file"] == "/src/Main.java"

    def test_session_context_defaults(self):
        """测试 SessionContext 默认值."""
        context = SessionContext()

        assert context.session_id is not None
        assert context.project_path == ""
        assert context.project_type == ""
        assert context.conversation_history == []
        assert context.working_context == {}
        assert context.temp_results == {}
        assert isinstance(context.created_at, datetime)
        assert isinstance(context.last_accessed, datetime)

    def test_session_context_to_dict(self):
        """测试 to_dict 方法."""
        context = SessionContext(
            session_id="session-123",
            project_path="/project",
            project_type="java",
        )

        data = context.to_dict()

        assert data["session_id"] == "session-123"
        assert data["project_path"] == "/project"
        assert data["project_type"] == "java"
        assert "created_at" in data
        assert "last_accessed" in data
        assert "conversation_history" in data

    def test_session_context_touch(self):
        """测试 touch 方法."""
        context = SessionContext()
        old_accessed = context.last_accessed

        import time
        time.sleep(0.01)
        context.touch()

        assert context.last_accessed > old_accessed

    def test_session_context_add_message(self):
        """测试 add_message 方法."""
        context = SessionContext()

        context.add_message("user", "Hello", {"metadata": "value"})

        assert len(context.conversation_history) == 1
        assert context.conversation_history[0]["role"] == "user"
        assert context.conversation_history[0]["content"] == "Hello"
        assert context.conversation_history[0]["metadata"]["metadata"] == "value"
        assert "timestamp" in context.conversation_history[0]
