"""Orchestrator - Agent 调度器和工作流编排."""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from uuid import uuid4

from ut_agent.agents.base import (
    BaseAgent,
    AgentContext,
    AgentResult,
    AgentStatus,
)
from ut_agent.agents.analyzer import AnalyzerAgent
from ut_agent.agents.generator import GeneratorAgent
from ut_agent.agents.reviewer import ReviewerAgent
from ut_agent.agents.fixer import FixerAgent
from ut_agent.graph.state import GeneratedTestFile


class WorkflowStage(Enum):
    """工作流阶段."""
    INIT = "init"
    ANALYZE = "analyze"
    GENERATE = "generate"
    REVIEW = "review"
    FIX = "fix"
    FINALIZE = "finalize"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class WorkflowState:
    """工作流状态."""
    task_id: str
    stage: WorkflowStage = WorkflowStage.INIT
    context: AgentContext = None
    results: Dict[str, AgentResult] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    iteration: int = 0
    max_iterations: int = 3


@dataclass
class Task:
    """任务定义."""
    id: str = field(default_factory=lambda: str(uuid4()))
    source_file: str = ""
    project_path: str = ""
    project_type: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0


@dataclass
class OrchestratorResult:
    """编排结果."""
    success: bool
    task_id: str
    test_file: Optional[GeneratedTestFile] = None
    analysis: Optional[Dict[str, Any]] = None
    review_score: float = 0.0
    iterations: int = 0
    duration_ms: int = 0
    errors: List[str] = field(default_factory=list)


class WorkflowGraph:
    """工作流图定义."""
    
    def __init__(self):
        self.nodes: Dict[str, Callable] = {}
        self.edges: Dict[str, List[str]] = {}
        self.conditionals: Dict[str, Callable] = {}
    
    def add_node(self, name: str, handler: Callable) -> None:
        self.nodes[name] = handler
    
    def add_edge(self, from_node: str, to_node: str) -> None:
        if from_node not in self.edges:
            self.edges[from_node] = []
        self.edges[from_node].append(to_node)
    
    def add_conditional_edge(
        self,
        from_node: str,
        condition: Callable,
        targets: Dict[str, str],
    ) -> None:
        self.conditionals[from_node] = {
            "condition": condition,
            "targets": targets,
        }
    
    def get_next_node(self, current: str, state: WorkflowState) -> Optional[str]:
        if current in self.conditionals:
            cond_info = self.conditionals[current]
            result = cond_info["condition"](state)
            return cond_info["targets"].get(result)
        
        edges = self.edges.get(current, [])
        return edges[0] if edges else None


class Orchestrator:
    """Agent 编排器."""
    
    def __init__(
        self,
        memory: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self._memory = memory
        self._config = config or {}
        self._agents: Dict[str, BaseAgent] = {}
        self._workflow = self._build_workflow()
        self._active_tasks: Dict[str, WorkflowState] = {}
        
        self._init_agents()
    
    def _init_agents(self) -> None:
        self._agents["analyzer"] = AnalyzerAgent(memory=self._memory, config=self._config)
        self._agents["generator"] = GeneratorAgent(memory=self._memory, config=self._config)
        self._agents["reviewer"] = ReviewerAgent(memory=self._memory, config=self._config)
        self._agents["fixer"] = FixerAgent(memory=self._memory, config=self._config)
    
    def _build_workflow(self) -> WorkflowGraph:
        workflow = WorkflowGraph()
        
        workflow.add_node("analyze", self._run_analyzer)
        workflow.add_node("generate", self._run_generator)
        workflow.add_node("review", self._run_reviewer)
        workflow.add_node("fix", self._run_fixer)
        workflow.add_node("finalize", self._finalize)
        
        workflow.add_edge("analyze", "generate")
        workflow.add_edge("generate", "review")
        
        workflow.add_conditional_edge(
            "review",
            lambda state: "fix" if state.results.get("review", AgentResult(False, "", "")).data.get("review_result", {}).get("needs_fix", False) and state.iteration < state.max_iterations else "finalize",
            {
                "fix": "fix",
                "finalize": "finalize",
            },
        )
        
        workflow.add_edge("fix", "generate")
        
        return workflow
    
    def register_agent(self, name: str, agent: BaseAgent) -> None:
        self._agents[name] = agent
    
    def get_agent(self, name: str) -> Optional[BaseAgent]:
        return self._agents.get(name)
    
    async def run(self, task: Task) -> OrchestratorResult:
        start_time = time.time()
        
        context = AgentContext(
            task_id=task.id,
            project_path=task.project_path,
            project_type=task.project_type,
            source_file=task.source_file,
            config={**self._config, **task.config},
        )
        
        state = WorkflowState(
            task_id=task.id,
            context=context,
            max_iterations=task.config.get("max_iterations", 3),
        )
        
        self._active_tasks[task.id] = state
        
        try:
            current_node = "analyze"
            
            while current_node and current_node not in ["finalize", "completed", "failed"]:
                state.stage = WorkflowStage(current_node)
                
                handler = self._workflow.nodes.get(current_node)
                if handler:
                    result = await handler(state)
                    state.results[current_node] = result
                    
                    if not result.success:
                        state.errors.extend(result.errors)
                        if current_node in ["analyze", "generate"]:
                            state.stage = WorkflowStage.FAILED
                            break
                
                next_node = self._workflow.get_next_node(current_node, state)
                if next_node == "fix":
                    state.iteration += 1
                current_node = next_node
            
            state.end_time = datetime.now()
            state.stage = WorkflowStage.COMPLETED
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            test_file = None
            if "generate" in state.results:
                gen_data = state.results["generate"].data
                if gen_data:
                    test_file = gen_data.get("test_file")
            
            review_score = 0.0
            if "review" in state.results:
                review_data = state.results["review"].data
                if review_data:
                    review_score = review_data.get("review_result", {}).get("score", 0.0)
            
            analysis = None
            if "analyze" in state.results:
                analysis = state.results["analyze"].data
            
            if "fix" in state.results:
                fix_data = state.results["fix"].data
                if fix_data and test_file:
                    test_file.test_code = fix_data.get("fixed_test_code", test_file.test_code)
            
            return OrchestratorResult(
                success=True,
                task_id=task.id,
                test_file=test_file,
                analysis=analysis,
                review_score=review_score,
                iterations=state.iteration,
                duration_ms=duration_ms,
                errors=state.errors,
            )
            
        except Exception as e:
            state.stage = WorkflowStage.FAILED
            state.errors.append(str(e))
            
            return OrchestratorResult(
                success=False,
                task_id=task.id,
                errors=state.errors,
                duration_ms=int((time.time() - start_time) * 1000),
            )
        
        finally:
            if task.id in self._active_tasks:
                del self._active_tasks[task.id]
    
    async def run_batch(self, tasks: List[Task]) -> List[OrchestratorResult]:
        results = await asyncio.gather(
            *[self.run(task) for task in tasks],
            return_exceptions=True,
        )
        
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(OrchestratorResult(
                    success=False,
                    task_id=tasks[i].id,
                    errors=[str(result)],
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _run_analyzer(self, state: WorkflowState) -> AgentResult:
        agent = self._agents.get("analyzer")
        if not agent:
            return AgentResult(
                success=False,
                agent_name="orchestrator",
                task_id=state.task_id,
                errors=["Analyzer agent not found"],
            )
        
        result = await agent.execute(state.context)
        
        if result.success and result.data:
            state.context.file_analysis = result.data.get("file_analysis")
            state.context.memory_context.update({
                "dependencies": result.data.get("dependencies", {}),
                "mock_suggestions": result.data.get("mock_suggestions", []),
                "test_strategy": result.data.get("test_strategy", {}),
            })
        
        return result
    
    async def _run_generator(self, state: WorkflowState) -> AgentResult:
        agent = self._agents.get("generator")
        if not agent:
            return AgentResult(
                success=False,
                agent_name="orchestrator",
                task_id=state.task_id,
                errors=["Generator agent not found"],
            )
        
        result = await agent.execute(state.context)
        
        if result.success and result.data:
            test_file = result.data.get("test_file")
            if test_file:
                state.context.generated_test = {
                    "test_code": test_file.test_code,
                    "test_file_path": test_file.test_file_path,
                    "language": test_file.language,
                }
        
        return result
    
    async def _run_reviewer(self, state: WorkflowState) -> AgentResult:
        agent = self._agents.get("reviewer")
        if not agent:
            return AgentResult(
                success=False,
                agent_name="orchestrator",
                task_id=state.task_id,
                errors=["Reviewer agent not found"],
            )
        
        result = await agent.execute(state.context)
        
        if result.success and result.data:
            state.context.review_result = result.data.get("review_result")
        
        return result
    
    async def _run_fixer(self, state: WorkflowState) -> AgentResult:
        agent = self._agents.get("fixer")
        if not agent:
            return AgentResult(
                success=False,
                agent_name="orchestrator",
                task_id=state.task_id,
                errors=["Fixer agent not found"],
            )
        
        result = await agent.execute(state.context)
        
        if result.success and result.data:
            fixed_code = result.data.get("fixed_test_code")
            if fixed_code and state.context.generated_test:
                state.context.generated_test["test_code"] = fixed_code
        
        return result
    
    async def _finalize(self, state: WorkflowState) -> AgentResult:
        return AgentResult(
            success=True,
            agent_name="orchestrator",
            task_id=state.task_id,
            data={
                "iterations": state.iteration,
                "total_stages": len(state.results),
            },
        )
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        state = self._active_tasks.get(task_id)
        if not state:
            return None
        
        return {
            "task_id": task_id,
            "stage": state.stage.value,
            "iteration": state.iteration,
            "errors": state.errors,
            "results": {k: v.success for k, v in state.results.items()},
        }
    
    def get_agent_status(self) -> Dict[str, Dict[str, Any]]:
        return {
            name: {
                "status": agent.status.value,
                "capabilities": agent.get_capabilities(),
            }
            for name, agent in self._agents.items()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agents": {name: agent.to_dict() for name, agent in self._agents.items()},
            "active_tasks": len(self._active_tasks),
            "config": self._config,
        }
