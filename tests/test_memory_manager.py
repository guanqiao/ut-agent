"""记忆管理器测试"""

import gc
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import pytest

from ut_agent.memory.manager import MemoryManager
from ut_agent.memory.short_term import ShortTermMemoryManager
from ut_agent.memory.long_term import LongTermMemoryManager
from ut_agent.memory.models import (
    SessionContext,
    GenerationRecord,
    FixRecord,
    CodeTestPattern,
    UserPreference,
)


class TestShortTermMemoryManager:
    """测试短期记忆管理器"""
    
    def test_initialization(self):
        """测试初始化"""
        manager = ShortTermMemoryManager(
            max_sessions=50,
            session_ttl_minutes=30,
        )
        assert manager._max_sessions == 50
        assert manager._session_ttl == timedelta(minutes=30)
    
    def test_create_session(self):
        """测试创建会话"""
        manager = ShortTermMemoryManager()
        session_id = manager.create_session(
            project_path="/test/project",
            project_type="java",
        )
        
        assert session_id is not None
        assert len(session_id) > 0
        
        context = manager.get_session(session_id)
        assert context is not None
        assert context.project_path == "/test/project"
        assert context.project_type == "java"
    
    def test_get_session(self):
        """测试获取会话"""
        manager = ShortTermMemoryManager()
        session_id = manager.create_session()
        
        context = manager.get_session(session_id)
        assert context is not None
        assert context.session_id == session_id
    
    def test_get_nonexistent_session(self):
        """测试获取不存在的会话"""
        manager = ShortTermMemoryManager()
        context = manager.get_session("nonexistent")
        assert context is None
    
    def test_get_or_create_session(self):
        """测试获取或创建会话"""
        manager = ShortTermMemoryManager()
        
        # 创建新会话
        context = manager.get_or_create_session(
            session_id=None,
            project_path="/test",
            project_type="java",
        )
        assert context is not None
        assert context.project_path == "/test"
        
        # 获取现有会话
        existing_context = manager.get_or_create_session(
            session_id=context.session_id,
        )
        assert existing_context.session_id == context.session_id
    
    def test_add_message(self):
        """测试添加消息"""
        manager = ShortTermMemoryManager()
        session_id = manager.create_session()
        
        result = manager.add_message(
            session_id=session_id,
            role="user",
            content="Hello",
            metadata={"key": "value"},
        )
        assert result is True
        
        history = manager.get_conversation_history(session_id)
        assert len(history) == 1
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"
    
    def test_get_conversation_history(self):
        """测试获取对话历史"""
        manager = ShortTermMemoryManager()
        session_id = manager.create_session()
        
        manager.add_message(session_id, "user", "Message 1")
        manager.add_message(session_id, "assistant", "Message 2")
        manager.add_message(session_id, "user", "Message 3")
        
        history = manager.get_conversation_history(session_id, limit=2)
        assert len(history) == 2
        assert history[0]["role"] == "assistant"
        assert history[1]["role"] == "user"
    
    def test_set_and_get_context(self):
        """测试设置和获取上下文"""
        manager = ShortTermMemoryManager()
        session_id = manager.create_session()
        
        manager.set_context(session_id, "test_key", "test_value")
        value = manager.get_context(session_id, "test_key")
        assert value == "test_value"
    
    def test_get_context_default(self):
        """测试获取上下文默认值"""
        manager = ShortTermMemoryManager()
        session_id = manager.create_session()
        
        value = manager.get_context(session_id, "nonexistent", default="default")
        assert value == "default"
    
    def test_set_and_get_temp_result(self):
        """测试设置和获取临时结果"""
        manager = ShortTermMemoryManager()
        session_id = manager.create_session()
        
        manager.set_temp_result(session_id, "temp_key", {"data": "value"})
        result = manager.get_temp_result(session_id, "temp_key")
        assert result == {"data": "value"}
    
    def test_clear_session(self):
        """测试清除会话"""
        manager = ShortTermMemoryManager()
        session_id = manager.create_session()
        
        result = manager.clear_session(session_id)
        assert result is True
        
        context = manager.get_session(session_id)
        assert context is None
    
    def test_clear_all(self):
        """测试清除所有会话"""
        manager = ShortTermMemoryManager()
        manager.create_session()
        manager.create_session()
        
        manager.clear_all()
        assert manager.get_active_session_count() == 0
    
    def test_max_sessions_limit(self):
        """测试最大会话数限制"""
        manager = ShortTermMemoryManager(max_sessions=2)
        
        session1 = manager.create_session()
        session2 = manager.create_session()
        session3 = manager.create_session()
        
        # 第一个会话应该被驱逐
        assert manager.get_session(session1) is None
        assert manager.get_session(session2) is not None
        assert manager.get_session(session3) is not None
    
    def test_cleanup_expired(self):
        """测试清理过期会话"""
        manager = ShortTermMemoryManager(session_ttl_minutes=0)
        session_id = manager.create_session()
        
        # 手动设置会话为过期状态
        with manager._lock:
            context = manager._sessions[session_id]
            context.last_accessed = datetime.now() - timedelta(minutes=1)
        
        expired_count = manager.cleanup_expired()
        assert expired_count == 1
        assert manager.get_session(session_id) is None
    
    def test_get_active_session_count(self):
        """测试获取活跃会话数"""
        manager = ShortTermMemoryManager()
        assert manager.get_active_session_count() == 0
        
        manager.create_session()
        assert manager.get_active_session_count() == 1
        
        manager.create_session()
        assert manager.get_active_session_count() == 2
    
    def test_to_dict(self):
        """测试转换为字典"""
        manager = ShortTermMemoryManager(
            max_sessions=50,
            session_ttl_minutes=30,
        )
        
        data = manager.to_dict()
        assert data["active_sessions"] == 0
        assert data["max_sessions"] == 50
        assert data["session_ttl_minutes"] == 30


class TestLongTermMemoryManager:
    """测试长期记忆管理器"""
    
    def setup_method(self):
        """设置测试环境"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_path = Path(self.temp_dir.name)
        self.manager = None
    
    def teardown_method(self):
        """清理测试环境"""
        # 显式释放管理器引用
        if self.manager:
            del self.manager
        # 强制垃圾回收以关闭 SQLite 连接
        gc.collect()
        # 清理临时目录
        self.temp_dir.cleanup()
    
    def test_initialization(self):
        """测试初始化"""
        self.manager = LongTermMemoryManager(self.storage_path)
        assert self.manager._storage_path == self.storage_path
        assert self.manager._db_path.exists()
    
    def test_save_and_get_generation(self):
        """测试保存和获取生成记录"""
        self.manager = LongTermMemoryManager(self.storage_path)
        
        record = GenerationRecord(
            agent_name="test_agent",
            source_file="Test.java",
            test_file="TestTest.java",
            test_code="public class TestTest {}",
            coverage_achieved=0.85,
            patterns_used=["pattern1", "pattern2"],
        )
        
        record_id = self.manager.save_generation(record)
        retrieved = self.manager.get_generation(record_id)
        
        assert retrieved is not None
        assert retrieved.agent_name == "test_agent"
        assert retrieved.source_file == "Test.java"
        assert retrieved.coverage_achieved == 0.85
        assert retrieved.patterns_used == ["pattern1", "pattern2"]
    
    def test_get_generations_by_source(self):
        """测试按源文件获取生成记录"""
        self.manager = LongTermMemoryManager(self.storage_path)
        
        record1 = GenerationRecord(source_file="Test.java")
        record2 = GenerationRecord(source_file="Test.java")
        record3 = GenerationRecord(source_file="Other.java")
        
        self.manager.save_generation(record1)
        self.manager.save_generation(record2)
        self.manager.save_generation(record3)
        
        records = self.manager.get_generations_by_source("Test.java")
        assert len(records) == 2
    
    def test_get_recent_generations(self):
        """测试获取最近的生成记录"""
        self.manager = LongTermMemoryManager(self.storage_path)
        
        for i in range(5):
            record = GenerationRecord(source_file=f"Test{i}.java")
            self.manager.save_generation(record)
        
        records = self.manager.get_recent_generations(limit=3)
        assert len(records) == 3
    
    def test_save_and_get_fix(self):
        """测试保存和获取修复记录"""
        self.manager = LongTermMemoryManager(self.storage_path)
        
        record = FixRecord(
            agent_name="fixer",
            source_file="Test.java",
            test_file="TestTest.java",
            error_type="AssertionError",
            error_message="Expected true but was false",
            fix_applied="Fixed assertion",
            fix_successful=True,
        )
        
        record_id = self.manager.save_fix(record)
        
        fixes = self.manager.get_fixes_by_error_type("AssertionError")
        assert len(fixes) == 1
        assert fixes[0].fix_applied == "Fixed assertion"
        assert fixes[0].fix_successful is True
    
    def test_save_and_get_pattern(self):
        """测试保存和获取测试模式"""
        self.manager = LongTermMemoryManager(self.storage_path)
        
        pattern = CodeTestPattern(
            pattern_name="Singleton Test",
            pattern_type="creational",
            language="java",
            description="Test pattern for singleton classes",
            code_template="@Test public void testSingleton() {}",
            use_cases=["singleton"],
            success_rate=0.9,
        )
        
        pattern_id = self.manager.save_pattern(pattern)
        patterns = self.manager.get_patterns_by_language("java")
        
        assert len(patterns) == 1
        assert patterns[0].pattern_name == "Singleton Test"
        assert patterns[0].success_rate == 0.9
    
    def test_update_pattern_usage(self):
        """测试更新模式使用"""
        self.manager = LongTermMemoryManager(self.storage_path)
        
        pattern = CodeTestPattern(
            pattern_name="Test Pattern",
            language="java",
            success_rate=0.5,
            usage_count=1,
        )
        pattern_id = self.manager.save_pattern(pattern)
        
        self.manager.update_pattern_usage(pattern_id, success=True)
        
        patterns = self.manager.get_patterns_by_language("java")
        assert patterns[0].usage_count == 2
        assert patterns[0].success_rate > 0.5
    
    def test_save_and_get_preference(self):
        """测试保存和获取用户偏好"""
        self.manager = LongTermMemoryManager(self.storage_path)
        
        preference = UserPreference(
            preference_key="template:basic",
            preference_value={"success_rate": 0.8},
            confidence=0.7,
            source="user_feedback",
            sample_count=10,
        )
        
        preference_id = self.manager.save_preference(preference)
        retrieved = self.manager.get_preference("template:basic")
        
        assert retrieved is not None
        assert retrieved.preference_value == {"success_rate": 0.8}
        assert retrieved.confidence == 0.7
    
    def test_get_all_preferences(self):
        """测试获取所有偏好"""
        self.manager = LongTermMemoryManager(self.storage_path)
        
        pref1 = UserPreference(preference_key="key1", confidence=0.5)
        pref2 = UserPreference(preference_key="key2", confidence=0.9)
        
        self.manager.save_preference(pref1)
        self.manager.save_preference(pref2)
        
        preferences = self.manager.get_all_preferences()
        assert len(preferences) == 2
        # 应该按置信度降序排列
        assert preferences[0].confidence >= preferences[1].confidence
    
    def test_update_preference(self):
        """测试更新偏好"""
        self.manager = LongTermMemoryManager(self.storage_path)
        
        # 创建初始偏好
        self.manager.update_preference("test_key", 5, source="test")
        
        # 更新偏好
        self.manager.update_preference("test_key", 10, source="update")
        
        preference = self.manager.get_preference("test_key")
        assert preference.preference_value == 10
        assert preference.sample_count == 2
    
    def test_get_stats(self):
        """测试获取统计信息"""
        self.manager = LongTermMemoryManager(self.storage_path)
        
        # 添加一些记录
        self.manager.save_generation(GenerationRecord(source_file="Test.java"))
        self.manager.save_fix(FixRecord(error_type="TestError"))
        self.manager.save_pattern(CodeTestPattern(pattern_name="Test", language="java"))
        self.manager.save_preference(UserPreference(preference_key="test"))
        
        stats = self.manager.get_stats()
        assert stats["generation_records"] == 1
        assert stats["fix_records"] == 1
        assert stats["test_patterns"] == 1
        assert stats["user_preferences"] == 1


class TestMemoryManager:
    """测试统一记忆管理器"""
    
    def setup_method(self):
        """设置测试环境"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_path = Path(self.temp_dir.name)
        self.manager = None
    
    def teardown_method(self):
        """清理测试环境"""
        # 显式释放管理器引用
        if self.manager:
            del self.manager
        # 强制垃圾回收以关闭 SQLite 连接
        gc.collect()
        # 清理临时目录
        self.temp_dir.cleanup()
    
    def test_initialization(self):
        """测试初始化"""
        manager = MemoryManager(
            storage_path=self.storage_path,
            max_sessions=50,
            session_ttl_minutes=30,
        )
        
        assert manager._storage_path == self.storage_path
        assert manager.short_term is not None
        assert manager.long_term is not None
        assert manager.semantic is not None
    
    def test_create_session(self):
        """测试创建会话"""
        manager = MemoryManager(storage_path=self.storage_path)
        
        session_id = manager.create_session(
            project_path="/test",
            project_type="java",
        )
        
        assert session_id is not None
        context = manager.get_session(session_id)
        assert context is not None
    
    def test_remember_and_recall(self):
        """测试记忆和回忆"""
        manager = MemoryManager(storage_path=self.storage_path)
        session_id = manager.create_session()
        
        manager.remember("agent1", "key1", "value1", session_id=session_id)
        value = manager.recall("agent1", "key1", session_id=session_id)
        
        assert value == "value1"
    
    def test_recall_nonexistent(self):
        """测试回忆不存在的记忆"""
        manager = MemoryManager(storage_path=self.storage_path)
        session_id = manager.create_session()
        
        value = manager.recall("agent1", "nonexistent", session_id=session_id)
        assert value is None
    
    def test_save_generation(self):
        """测试保存生成记录"""
        manager = MemoryManager(storage_path=self.storage_path)
        
        record_id = manager.save_generation(
            agent_name="generator",
            source_file="Test.java",
            test_file="TestTest.java",
            test_code="public class TestTest {}",
            coverage=0.85,
            patterns=["pattern1"],
            template="basic",
            llm_provider="openai",
            generation_time_ms=1000,
        )
        
        assert record_id is not None
        
        # 验证长期存储
        record = manager.long_term.get_generation(record_id)
        assert record is not None
        assert record.source_file == "Test.java"
    
    def test_save_fix(self):
        """测试保存修复记录"""
        manager = MemoryManager(storage_path=self.storage_path)
        
        record_id = manager.save_fix(
            agent_name="fixer",
            source_file="Test.java",
            test_file="TestTest.java",
            error_type="AssertionError",
            error_message="Test failed",
            fix_applied="Fixed the test",
            success=True,
        )
        
        assert record_id is not None
    
    def test_get_fix_suggestions(self):
        """测试获取修复建议"""
        manager = MemoryManager(storage_path=self.storage_path)
        
        # 保存一些修复记录
        manager.save_fix(
            agent_name="fixer",
            source_file="Test.java",
            test_file="TestTest.java",
            error_type="AssertionError",
            error_message="Test failed",
            fix_applied="Fix 1",
            success=True,
        )
        manager.save_fix(
            agent_name="fixer",
            source_file="Test.java",
            test_file="TestTest.java",
            error_type="AssertionError",
            error_message="Test failed",
            fix_applied="Fix 2",
            success=True,
        )
        
        suggestions = manager.get_fix_suggestions("AssertionError")
        assert len(suggestions) == 2
    
    def test_save_pattern(self):
        """测试保存测试模式"""
        manager = MemoryManager(storage_path=self.storage_path)
        
        pattern_id = manager.save_pattern(
            pattern_name="Test Pattern",
            pattern_type="unit",
            language="java",
            description="A test pattern",
            code_template="@Test public void test() {}",
            use_cases=["testing"],
        )
        
        assert pattern_id is not None
    
    def test_learn_user_rating(self):
        """测试学习用户评分"""
        manager = MemoryManager(storage_path=self.storage_path)
        
        manager.learn("agent1", {
            "type": "user_rating",
            "source_file": "Test.java",
            "rating": 5,
        })
        
        preferences = manager.get_preferences()
        assert "rating:Test.java" in preferences
    
    def test_learn_template_success(self):
        """测试学习模板成功"""
        manager = MemoryManager(storage_path=self.storage_path)
        
        manager.learn("agent1", {
            "type": "template_success",
            "template": "basic",
            "success": True,
        })
        
        preferences = manager.get_preferences()
        assert "template:basic" in preferences
        assert preferences["template:basic"]["value"]["success_rate"] == 1
    
    def test_get_recommended_templates(self):
        """测试获取推荐模板"""
        manager = MemoryManager(storage_path=self.storage_path)
        
        # 添加一些模板偏好
        manager.learn("agent1", {
            "type": "template_success",
            "template": "good_template",
            "success": True,
        })
        manager.learn("agent1", {
            "type": "template_success",
            "template": "bad_template",
            "success": False,
        })
        
        # 多次成功以提高成功率
        for _ in range(5):
            manager.learn("agent1", {
                "type": "template_success",
                "template": "good_template",
                "success": True,
            })
        
        templates = manager.get_recommended_templates("java")
        assert "good_template" in templates
    
    def test_get_stats(self):
        """测试获取统计信息"""
        manager = MemoryManager(storage_path=self.storage_path)
        
        manager.create_session()
        manager.save_generation(
            agent_name="test",
            source_file="Test.java",
            test_file="TestTest.java",
            test_code="code",
        )
        
        stats = manager.get_stats()
        assert "short_term" in stats
        assert "long_term" in stats
        assert "semantic" in stats
        assert stats["short_term"]["active_sessions"] == 1
    
    def test_cleanup(self):
        """测试清理"""
        manager = MemoryManager(
            storage_path=self.storage_path,
            session_ttl_minutes=0,
        )
        
        session_id = manager.create_session()
        
        # 手动设置会话为过期状态
        with manager.short_term._lock:
            context = manager.short_term._sessions[session_id]
            context.last_accessed = datetime.now() - timedelta(minutes=1)
        
        result = manager.cleanup()
        assert "expired_sessions" in result
        assert result["expired_sessions"] == 1


if __name__ == "__main__":
    pytest.main([__file__])
