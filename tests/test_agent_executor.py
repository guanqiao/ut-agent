"""Agent 执行器测试模块."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ut_agent.agents.base import (
    AgentCapability,
    AgentContext,
    AgentResult,
    AgentStatus,
    BaseAgent,
)
from ut_agent.agents.executor import (
    AgentExecutor,
    ExecutionConfig,
    ExecutionResult,
    ExecutionStatus,
)


class MockAgent(BaseAgent):
    """测试用 Mock Agent."""

    name = "mock_agent"
    description = "Mock Agent for Testing"
    capabilities = [AgentCapability.AST_PARSE, AgentCapability.DEPENDENCY_ANALYSIS]

    def __init__(
        self,
        memory: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
        should_fail: bool = False,
        execution_delay: float = 0.1,
    ):
        super().__init__(memory, config)
        self._should_fail = should_fail
        self._execution_delay = execution_delay
        self._execute_called = False
        self._execute_count = 0

    async def execute(self, context: AgentContext) -> AgentResult:
        self._execute_called = True
        self._execute_count += 1

        if self._execution_delay > 0:
            await asyncio.sleep(self._execution_delay)

        if self._should_fail:
            return AgentResult(
                success=False,
                agent_name=self.name,
                task_id=context.task_id,
                errors=["Mock execution failed"],
            )

        return AgentResult(
            success=True,
            agent_name=self.name,
            task_id=context.task_id,
            data={"result": "mock_result", "file_path": context.source_file},
            metrics={"execution_time_ms": 100},
        )


class TestExecutionConfig:
    """ExecutionConfig 测试."""

    def test_default_config(self):
        """测试默认配置."""
        config = ExecutionConfig()
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.timeout == 300
        assert config.parallel_execution is True
        assert config.max_parallel_agents == 4

    def test_custom_config(self):
        """测试自定义配置."""
        config = ExecutionConfig(
            max_retries=5,
            retry_delay=2.0,
            timeout=600,
            parallel_execution=False,
            max_parallel_agents=8,
        )
        assert config.max_retries == 5
        assert config.retry_delay == 2.0
        assert config.timeout == 600
        assert config.parallel_execution is False
        assert config.max_parallel_agents == 8


class TestExecutionResult:
    """ExecutionResult 测试."""

    def test_success_result(self):
        """测试成功结果."""
        result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            agent_name="test_agent",
            task_id="task-123",
            data={"key": "value"},
        )
        assert result.status == ExecutionStatus.SUCCESS
        assert result.agent_name == "test_agent"
        assert result.success is True
        assert result.errors == []

    def test_failed_result(self):
        """测试失败结果."""
        result = ExecutionResult(
            status=ExecutionStatus.FAILED,
            agent_name="test_agent",
            task_id="task-123",
            errors=["Error 1", "Error 2"],
        )
        assert result.status == ExecutionStatus.FAILED
        assert result.success is False
        assert len(result.errors) == 2

    def test_timeout_result(self):
        """测试超时结果."""
        result = ExecutionResult(
            status=ExecutionStatus.TIMEOUT,
            agent_name="test_agent",
            task_id="task-123",
        )
        assert result.status == ExecutionStatus.TIMEOUT
        assert result.success is False


class TestAgentExecutor:
    """AgentExecutor 测试."""

    @pytest.fixture
    def executor(self):
        """创建执行器实例."""
        return AgentExecutor()

    @pytest.fixture
    def mock_context(self):
        """创建测试上下文."""
        return AgentContext(
            task_id="test-task-001",
            project_path="/test/project",
            source_file="/test/project/src/Main.java",
            source_content="public class Main {}",
        )

    def test_executor_initialization(self, executor):
        """测试执行器初始化."""
        assert executor._agents == {}
        assert executor._execution_history == []
        assert executor._config is not None

    def test_register_agent(self, executor):
        """测试注册 Agent."""
        agent = MockAgent()
        executor.register_agent(agent)

        assert "mock_agent" in executor._agents
        assert executor._agents["mock_agent"] == agent

    def test_register_multiple_agents(self, executor):
        """测试注册多个 Agent."""
        agent1 = MockAgent()
        agent1.name = "agent1"
        agent2 = MockAgent()
        agent2.name = "agent2"

        executor.register_agent(agent1)
        executor.register_agent(agent2)

        assert len(executor._agents) == 2
        assert "agent1" in executor._agents
        assert "agent2" in executor._agents

    def test_get_agent(self, executor):
        """测试获取 Agent."""
        agent = MockAgent()
        executor.register_agent(agent)

        retrieved = executor.get_agent("mock_agent")
        assert retrieved == agent

    def test_get_nonexistent_agent(self, executor):
        """测试获取不存在的 Agent."""
        retrieved = executor.get_agent("nonexistent")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_execute_single_agent(self, executor, mock_context):
        """测试执行单个 Agent."""
        agent = MockAgent()
        executor.register_agent(agent)

        result = await executor.execute_agent("mock_agent", mock_context)

        assert result.status == ExecutionStatus.SUCCESS
        assert result.agent_name == "mock_agent"
        assert result.success is True
        assert agent._execute_called is True

    @pytest.mark.asyncio
    async def test_execute_agent_with_failure(self, executor, mock_context):
        """测试执行失败的 Agent."""
        agent = MockAgent(should_fail=True)
        executor.register_agent(agent)

        result = await executor.execute_agent("mock_agent", mock_context)

        assert result.status == ExecutionStatus.FAILED
        assert result.success is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_execute_nonexistent_agent(self, executor, mock_context):
        """测试执行不存在的 Agent."""
        result = await executor.execute_agent("nonexistent", mock_context)

        assert result.status == ExecutionStatus.FAILED
        assert "not found" in result.errors[0].lower()

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, executor, mock_context):
        """测试执行超时."""
        agent = MockAgent(execution_delay=5.0)
        executor.register_agent(agent)

        config = ExecutionConfig(timeout=0.1)
        result = await executor.execute_agent("mock_agent", mock_context, config)

        assert result.status == ExecutionStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_execute_with_retry(self, executor, mock_context):
        """测试重试机制."""
        fail_count = 0

        class FlakeyAgent(BaseAgent):
            name = "flakey_agent"
            description = "Flakey Agent"
            capabilities = []

            async def execute(self, context: AgentContext) -> AgentResult:
                nonlocal fail_count
                fail_count += 1
                if fail_count < 3:
                    return AgentResult(
                        success=False,
                        agent_name=self.name,
                        task_id=context.task_id,
                        errors=[f"Attempt {fail_count} failed"],
                    )
                return AgentResult(
                    success=True,
                    agent_name=self.name,
                    task_id=context.task_id,
                )

        agent = FlakeyAgent()
        executor.register_agent(agent)

        config = ExecutionConfig(max_retries=3, retry_delay=0.1)
        result = await executor.execute_agent("flakey_agent", mock_context, config)

        assert result.status == ExecutionStatus.SUCCESS
        assert fail_count == 3

    @pytest.mark.asyncio
    async def test_execute_parallel_agents(self, executor, mock_context):
        """测试并行执行多个 Agent."""
        agent1 = MockAgent(execution_delay=0.1)
        agent1.name = "agent1"
        agent2 = MockAgent(execution_delay=0.1)
        agent2.name = "agent2"
        agent3 = MockAgent(execution_delay=0.1)
        agent3.name = "agent3"

        executor.register_agent(agent1)
        executor.register_agent(agent2)
        executor.register_agent(agent3)

        start_time = datetime.now()
        results = await executor.execute_parallel(
            ["agent1", "agent2", "agent3"],
            mock_context,
        )
        end_time = datetime.now()

        assert len(results) == 3
        assert all(r.success for r in results)

        execution_time = (end_time - start_time).total_seconds()
        assert execution_time < 0.5

    @pytest.mark.asyncio
    async def test_execute_sequential_agents(self, executor, mock_context):
        """测试顺序执行多个 Agent."""
        agent1 = MockAgent(execution_delay=0.1)
        agent1.name = "agent1"
        agent2 = MockAgent(execution_delay=0.1)
        agent2.name = "agent2"

        executor.register_agent(agent1)
        executor.register_agent(agent2)

        config = ExecutionConfig(parallel_execution=False)
        results = await executor.execute_parallel(
            ["agent1", "agent2"],
            mock_context,
            config,
        )

        assert len(results) == 2
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_execution_history(self, executor, mock_context):
        """测试执行历史记录."""
        agent = MockAgent()
        executor.register_agent(agent)

        await executor.execute_agent("mock_agent", mock_context)

        history = executor.get_execution_history()
        assert len(history) == 1
        assert history[0].agent_name == "mock_agent"

    @pytest.mark.asyncio
    async def test_execution_history_limit(self, executor, mock_context):
        """测试执行历史记录限制."""
        agent = MockAgent(execution_delay=0)
        executor.register_agent(agent)

        for i in range(150):
            await executor.execute_agent("mock_agent", mock_context)

        history = executor.get_execution_history()
        assert len(history) == 100

    def test_clear_history(self, executor):
        """测试清除历史记录."""
        executor._execution_history = [
            ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                agent_name="test",
                task_id="task-1",
            )
        ]

        executor.clear_history()
        assert len(executor._execution_history) == 0

    @pytest.mark.asyncio
    async def test_execute_with_capability_check(self, executor, mock_context):
        """测试能力检查."""
        agent = MockAgent()
        executor.register_agent(agent)

        result = await executor.execute_agent(
            "mock_agent",
            mock_context,
            required_capability=AgentCapability.AST_PARSE,
        )

        assert result.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_execute_with_missing_capability(self, executor, mock_context):
        """测试缺少能力时的执行."""
        agent = MockAgent()
        executor.register_agent(agent)

        result = await executor.execute_agent(
            "mock_agent",
            mock_context,
            required_capability=AgentCapability.MOCK_GENERATION,
        )

        assert result.status == ExecutionStatus.FAILED
        assert "capability" in result.errors[0].lower()

    @pytest.mark.asyncio
    async def test_execute_with_context_update(self, executor):
        """测试上下文更新."""
        agent = MockAgent()
        executor.register_agent(agent)

        context = AgentContext(task_id="test-task")
        result = await executor.execute_agent("mock_agent", context)

        assert result.task_id == "test-task"


class TestAgentExecutorIntegration:
    """AgentExecutor 集成测试."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """测试完整工作流."""
        executor = AgentExecutor()

        analyzer = MockAgent()
        analyzer.name = "analyzer"
        analyzer.capabilities = [AgentCapability.AST_PARSE]

        generator = MockAgent()
        generator.name = "generator"
        generator.capabilities = [AgentCapability.TEST_STRATEGY]

        executor.register_agent(analyzer)
        executor.register_agent(generator)

        context = AgentContext(
            task_id="workflow-001",
            project_path="/test/project",
            source_file="/test/project/src/Main.java",
        )

        analyzer_result = await executor.execute_agent("analyzer", context)
        assert analyzer_result.success

        context.file_analysis = {"methods": ["method1", "method2"]}
        generator_result = await executor.execute_agent("generator", context)
        assert generator_result.success

        history = executor.get_execution_history()
        assert len(history) == 2
