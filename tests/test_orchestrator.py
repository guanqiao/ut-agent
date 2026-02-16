"""Orchestrator 单元测试."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ut_agent.agents.orchestrator import (
    Orchestrator,
    OrchestratorResult,
    Task,
    WorkflowStage,
    WorkflowState,
    WorkflowGraph,
)
from ut_agent.agents.base import (
    AgentContext,
    AgentResult,
    AgentStatus,
)


class TestWorkflowGraph:
    """WorkflowGraph 测试."""

    def test_add_node(self):
        graph = WorkflowGraph()
        handler = MagicMock()
        graph.add_node("test_node", handler)
        assert "test_node" in graph.nodes
        assert graph.nodes["test_node"] == handler

    def test_add_edge(self):
        graph = WorkflowGraph()
        graph.add_edge("node_a", "node_b")
        assert "node_a" in graph.edges
        assert "node_b" in graph.edges["node_a"]

    def test_add_conditional_edge(self):
        graph = WorkflowGraph()
        condition = lambda state: "path_a"
        graph.add_conditional_edge(
            "node_a",
            condition,
            {"path_a": "node_b", "path_b": "node_c"},
        )
        assert "node_a" in graph.conditionals

    def test_get_next_node_simple(self):
        graph = WorkflowGraph()
        graph.add_edge("node_a", "node_b")
        state = MagicMock()
        result = graph.get_next_node("node_a", state)
        assert result == "node_b"

    def test_get_next_node_conditional(self):
        graph = WorkflowGraph()
        graph.add_conditional_edge(
            "node_a",
            lambda state: "fix",
            {"fix": "node_b", "finalize": "node_c"},
        )
        state = MagicMock()
        result = graph.get_next_node("node_a", state)
        assert result == "node_b"

    def test_get_next_node_no_edges(self):
        graph = WorkflowGraph()
        state = MagicMock()
        result = graph.get_next_node("unknown_node", state)
        assert result is None


class TestTask:
    """Task 测试."""

    def test_task_creation(self):
        task = Task(
            source_file="/path/to/file.java",
            project_path="/project",
            project_type="java",
        )
        assert task.source_file == "/path/to/file.java"
        assert task.project_path == "/project"
        assert task.project_type == "java"
        assert task.id is not None
        assert task.priority == 0

    def test_task_with_config(self):
        task = Task(
            source_file="/path/to/file.java",
            config={"max_iterations": 5},
        )
        assert task.config == {"max_iterations": 5}


class TestWorkflowState:
    """WorkflowState 测试."""

    def test_workflow_state_creation(self):
        state = WorkflowState(task_id="test-task-id")
        assert state.task_id == "test-task-id"
        assert state.stage == WorkflowStage.INIT
        assert state.iteration == 0
        assert state.errors == []

    def test_workflow_state_with_context(self):
        context = AgentContext(task_id="test-task-id")
        state = WorkflowState(
            task_id="test-task-id",
            context=context,
        )
        assert state.context == context


class TestOrchestratorResult:
    """OrchestratorResult 测试."""

    def test_success_result(self):
        result = OrchestratorResult(
            success=True,
            task_id="test-task-id",
            iterations=2,
            duration_ms=1000,
        )
        assert result.success is True
        assert result.task_id == "test-task-id"
        assert result.iterations == 2
        assert result.test_file is None

    def test_failure_result(self):
        result = OrchestratorResult(
            success=False,
            task_id="test-task-id",
            errors=["Error message"],
        )
        assert result.success is False
        assert len(result.errors) == 1


class TestOrchestrator:
    """Orchestrator 测试."""

    @pytest.fixture
    def orchestrator(self):
        with patch("ut_agent.agents.orchestrator.AnalyzerAgent"), \
             patch("ut_agent.agents.orchestrator.GeneratorAgent"), \
             patch("ut_agent.agents.orchestrator.ReviewerAgent"), \
             patch("ut_agent.agents.orchestrator.FixerAgent"):
            return Orchestrator()

    def test_orchestrator_initialization(self, orchestrator):
        assert orchestrator is not None
        assert "analyzer" in orchestrator._agents
        assert "generator" in orchestrator._agents
        assert "reviewer" in orchestrator._agents
        assert "fixer" in orchestrator._agents

    def test_register_agent(self, orchestrator):
        mock_agent = MagicMock()
        mock_agent.name = "custom_agent"
        orchestrator.register_agent("custom", mock_agent)
        assert "custom" in orchestrator._agents

    def test_get_agent(self, orchestrator):
        agent = orchestrator.get_agent("analyzer")
        assert agent is not None

    def test_get_nonexistent_agent(self, orchestrator):
        agent = orchestrator.get_agent("nonexistent")
        assert agent is None

    @pytest.mark.asyncio
    async def test_run_task_success(self, orchestrator):
        task = Task(
            source_file="/test/file.java",
            project_path="/project",
            project_type="java",
        )

        mock_analyzer = orchestrator._agents["analyzer"]
        mock_analyzer.execute = AsyncMock(return_value=AgentResult(
            success=True,
            agent_name="analyzer",
            task_id=task.id,
            data={"file_analysis": {"methods": []}},
        ))

        mock_generator = orchestrator._agents["generator"]
        mock_generator.execute = AsyncMock(return_value=AgentResult(
            success=True,
            agent_name="generator",
            task_id=task.id,
            data={"test_file": MagicMock(test_code="test code", test_file_path="/test/Test.java", language="java")},
        ))

        mock_reviewer = orchestrator._agents["reviewer"]
        mock_reviewer.execute = AsyncMock(return_value=AgentResult(
            success=True,
            agent_name="reviewer",
            task_id=task.id,
            data={"review_result": {"score": 0.9, "needs_fix": False}},
        ))

        result = await orchestrator.run(task)

        assert result.success is True
        assert result.task_id == task.id

    @pytest.mark.asyncio
    async def test_run_task_analyzer_failure(self, orchestrator):
        task = Task(
            source_file="/test/file.java",
            project_path="/project",
            project_type="java",
        )

        mock_analyzer = orchestrator._agents["analyzer"]
        mock_analyzer.execute = AsyncMock(return_value=AgentResult(
            success=False,
            agent_name="analyzer",
            task_id=task.id,
            errors=["Analysis failed"],
        ))

        result = await orchestrator.run(task)

        assert len(result.errors) > 0
        assert "Analysis failed" in result.errors

    @pytest.mark.asyncio
    async def test_run_batch(self, orchestrator):
        tasks = [
            Task(source_file=f"/test/file{i}.java", project_path="/project", project_type="java")
            for i in range(3)
        ]

        for agent_name in ["analyzer", "generator", "reviewer"]:
            mock_agent = orchestrator._agents[agent_name]
            mock_agent.execute = AsyncMock(return_value=AgentResult(
                success=True,
                agent_name=agent_name,
                task_id="test",
            ))

        results = await orchestrator.run_batch(tasks)

        assert len(results) == 3

    def test_get_task_status_not_found(self, orchestrator):
        status = orchestrator.get_task_status("nonexistent-task")
        assert status is None

    def test_get_agent_status(self, orchestrator):
        status = orchestrator.get_agent_status()
        assert "analyzer" in status
        assert "generator" in status

    def test_to_dict(self, orchestrator):
        data = orchestrator.to_dict()
        assert "agents" in data
        assert "active_tasks" in data
        assert "config" in data
