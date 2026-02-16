"""Agent 基类单元测试."""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from ut_agent.agents.base import (
    AgentStatus,
    AgentCapability,
    AgentContext,
    AgentResult,
    Capability,
    BaseAgent,
)


class TestAgentStatus:
    """AgentStatus 枚举测试."""

    def test_agent_status_values(self):
        """测试 AgentStatus 枚举值."""
        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.RUNNING.value == "running"
        assert AgentStatus.SUCCESS.value == "success"
        assert AgentStatus.FAILED.value == "failed"


class TestAgentCapability:
    """AgentCapability 枚举测试."""

    def test_agent_capability_values(self):
        """测试 AgentCapability 枚举值."""
        assert AgentCapability.AST_PARSE.value == "ast_parse"
        assert AgentCapability.DEPENDENCY_ANALYSIS.value == "dependency_analysis"
        assert AgentCapability.TEST_STRATEGY.value == "test_strategy"
        assert AgentCapability.MOCK_GENERATION.value == "mock_generation"

    def test_all_capabilities(self):
        """测试所有能力枚举."""
        capabilities = list(AgentCapability)
        assert len(capabilities) >= 18  # 至少有18个能力


class TestAgentContext:
    """AgentContext 数据类测试."""

    def test_agent_context_creation(self):
        """测试 AgentContext 创建."""
        context = AgentContext(
            project_path="/project",
            project_type="java",
            source_file="/src/Main.java",
            source_content="public class Main {}",
        )

        assert context.project_path == "/project"
        assert context.project_type == "java"
        assert context.source_file == "/src/Main.java"
        assert context.task_id is not None  # 自动生成 UUID

    def test_agent_context_defaults(self):
        """测试 AgentContext 默认值."""
        context = AgentContext()

        assert context.project_path == ""
        assert context.project_type == ""
        assert context.task_id is not None
        assert context.memory_context == {}
        assert context.config == {}
        assert context.metadata == {}


class TestAgentResult:
    """AgentResult 数据类测试."""

    def test_agent_result_creation(self):
        """测试 AgentResult 创建."""
        result = AgentResult(
            success=True,
            agent_name="test_agent",
            task_id="task-123",
            data={"key": "value"},
            errors=[],
            warnings=["warning1"],
            duration_ms=100,
        )

        assert result.success is True
        assert result.agent_name == "test_agent"
        assert result.task_id == "task-123"
        assert result.data["key"] == "value"
        assert len(result.warnings) == 1

    def test_agent_result_defaults(self):
        """测试 AgentResult 默认值."""
        result = AgentResult(
            success=True,
            agent_name="test",
            task_id="123",
        )

        assert result.data == {}
        assert result.errors == []
        assert result.warnings == []
        assert result.suggestions == []
        assert result.metrics == {}
        assert isinstance(result.timestamp, datetime)


class TestCapability:
    """Capability 数据类测试."""

    def test_capability_creation(self):
        """测试 Capability 创建."""
        handler = Mock()
        cap = Capability(
            name="test_cap",
            description="Test capability",
            handler=handler,
            priority=5,
            enabled=True,
        )

        assert cap.name == "test_cap"
        assert cap.description == "Test capability"
        assert cap.handler == handler
        assert cap.priority == 5
        assert cap.enabled is True

    def test_capability_defaults(self):
        """测试 Capability 默认值."""
        cap = Capability(name="test", description="")

        assert cap.description == ""
        assert cap.handler is None
        assert cap.priority == 0
        assert cap.enabled is True


class ConcreteAgent(BaseAgent):
    """测试用的具体 Agent 实现."""

    name = "concrete_agent"
    description = "Concrete Agent for testing"
    capabilities = [AgentCapability.AST_PARSE, AgentCapability.TEST_STRATEGY]

    async def execute(self, context: AgentContext) -> AgentResult:
        self._status = AgentStatus.RUNNING
        # 模拟执行
        result = AgentResult(
            success=True,
            agent_name=self.name,
            task_id=context.task_id,
            data={"executed": True},
        )
        self._status = AgentStatus.SUCCESS
        self.record_execution(result)
        return result


class TestBaseAgent:
    """BaseAgent 测试."""

    def test_base_agent_initialization(self):
        """测试 BaseAgent 初始化."""
        agent = ConcreteAgent()

        assert agent.name == "concrete_agent"
        assert agent.description == "Concrete Agent for testing"
        assert agent.status == AgentStatus.IDLE
        assert agent.memory is None

    def test_base_agent_with_memory(self):
        """测试带内存的 BaseAgent 初始化."""
        mock_memory = Mock()
        agent = ConcreteAgent(memory=mock_memory)

        assert agent.memory == mock_memory

    def test_base_agent_with_config(self):
        """测试带配置的 BaseAgent 初始化."""
        config = {"key": "value"}
        agent = ConcreteAgent(config=config)

        assert agent._config == config

    def test_status_property(self):
        """测试 status 属性."""
        agent = ConcreteAgent()

        assert agent.status == AgentStatus.IDLE

    def test_memory_setter(self):
        """测试 memory setter."""
        agent = ConcreteAgent()
        mock_memory = Mock()

        agent.memory = mock_memory

        assert agent.memory == mock_memory

    def test_has_capability(self):
        """测试 has_capability 方法."""
        agent = ConcreteAgent()

        assert agent.has_capability("ast_parse") is True
        assert agent.has_capability("test_strategy") is True
        assert agent.has_capability("nonexistent") is False

    def test_get_capabilities(self):
        """测试 get_capabilities 方法."""
        agent = ConcreteAgent()

        caps = agent.get_capabilities()

        assert "ast_parse" in caps
        assert "test_strategy" in caps
        assert len(caps) == 2

    def test_register_capability(self):
        """测试 register_capability 方法."""
        agent = ConcreteAgent()
        handler = Mock()

        agent.register_capability(
            name="new_cap",
            handler=handler,
            description="New capability",
            priority=10,
        )

        assert agent.has_capability("new_cap") is True
        caps = agent.get_capabilities()
        assert "new_cap" in caps

    def test_register_default_capability(self):
        """测试默认能力注册."""
        agent = ConcreteAgent()

        # 初始化时应该已经注册了默认能力
        assert agent.has_capability("ast_parse") is True
        assert agent.has_capability("test_strategy") is True

    @pytest.mark.asyncio
    async def test_invoke_capability(self):
        """测试 invoke_capability 方法."""
        agent = ConcreteAgent()
        handler = AsyncMock(return_value="result")

        agent.register_capability("test_cap", handler)
        result = await agent.invoke_capability("test_cap", "arg1", kwarg="value")

        assert result == "result"
        handler.assert_called_once_with("arg1", kwarg="value")

    @pytest.mark.asyncio
    async def test_invoke_capability_not_found(self):
        """测试调用不存在的能力."""
        agent = ConcreteAgent()

        with pytest.raises(ValueError, match="does not have capability"):
            await agent.invoke_capability("nonexistent")

    @pytest.mark.asyncio
    async def test_invoke_capability_disabled(self):
        """测试调用禁用的能力."""
        agent = ConcreteAgent()
        handler = Mock()

        agent.register_capability("disabled_cap", handler)
        agent._capability_handlers["disabled_cap"].enabled = False

        with pytest.raises(ValueError, match="is not available"):
            await agent.invoke_capability("disabled_cap")

    @pytest.mark.asyncio
    async def test_execute(self):
        """测试 execute 方法."""
        agent = ConcreteAgent()
        context = AgentContext(source_file="/test.java")

        result = await agent.execute(context)

        assert result.success is True
        assert result.agent_name == "concrete_agent"
        assert result.data["executed"] is True
        assert agent.status == AgentStatus.SUCCESS

    def test_record_execution(self):
        """测试 record_execution 方法."""
        agent = ConcreteAgent()
        result = AgentResult(
            success=True,
            agent_name="test",
            task_id="123",
        )

        agent.record_execution(result)

        history = agent.get_execution_history()
        assert len(history) == 1
        assert history[0] == result

    def test_record_execution_limit(self):
        """测试 record_execution 历史限制."""
        agent = ConcreteAgent()

        # 添加超过100条记录
        for i in range(150):
            result = AgentResult(
                success=True,
                agent_name="test",
                task_id=f"task-{i}",
            )
            agent.record_execution(result)

        history = agent.get_execution_history(limit=200)
        assert len(history) == 100  # 限制为100条

    def test_get_execution_history(self):
        """测试 get_execution_history 方法."""
        agent = ConcreteAgent()

        for i in range(5):
            result = AgentResult(
                success=True,
                agent_name="test",
                task_id=f"task-{i}",
            )
            agent.record_execution(result)

        history = agent.get_execution_history(limit=3)
        assert len(history) == 3
        # 应该返回最近的3条
        assert history[0].task_id == "task-2"
        assert history[2].task_id == "task-4"

    def test_remember(self):
        """测试 remember 方法."""
        mock_memory = Mock()
        agent = ConcreteAgent(memory=mock_memory)

        agent.remember("key", "value")

        mock_memory.remember.assert_called_once_with("concrete_agent", "key", "value")

    def test_remember_no_memory(self):
        """测试无内存时的 remember."""
        agent = ConcreteAgent(memory=None)

        # 不应该抛出异常
        agent.remember("key", "value")

    def test_recall(self):
        """测试 recall 方法."""
        mock_memory = Mock()
        mock_memory.recall.return_value = "recalled_value"
        agent = ConcreteAgent(memory=mock_memory)

        result = agent.recall("key")

        assert result == "recalled_value"
        mock_memory.recall.assert_called_once_with("concrete_agent", "key")

    def test_recall_no_memory(self):
        """测试无内存时的 recall."""
        agent = ConcreteAgent(memory=None)

        result = agent.recall("key")

        assert result is None

    def test_learn(self):
        """测试 learn 方法."""
        mock_memory = Mock()
        agent = ConcreteAgent(memory=mock_memory)
        feedback = {"score": 5, "comment": "good"}

        agent.learn(feedback)

        mock_memory.learn.assert_called_once_with("concrete_agent", feedback)

    def test_learn_no_memory(self):
        """测试无内存时的 learn."""
        agent = ConcreteAgent(memory=None)

        # 不应该抛出异常
        agent.learn({"score": 5})

    def test_to_dict(self):
        """测试 to_dict 方法."""
        agent = ConcreteAgent()

        data = agent.to_dict()

        assert data["name"] == "concrete_agent"
        assert data["description"] == "Concrete Agent for testing"
        assert "ast_parse" in data["capabilities"]
        assert "test_strategy" in data["capabilities"]
        assert data["status"] == "idle"
