"""Agent 执行器模块 - 统一管理和执行 Agent."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type

from ut_agent.agents.base import (
    AgentCapability,
    AgentContext,
    AgentResult,
    BaseAgent,
)
from ut_agent.utils import get_logger

logger = get_logger("agent_executor")


class ExecutionStatus(Enum):
    """执行状态枚举."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ExecutionConfig:
    """执行配置."""

    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: int = 300
    parallel_execution: bool = True
    max_parallel_agents: int = 4
    history_limit: int = 100


@dataclass
class ExecutionResult:
    """执行结果."""

    status: ExecutionStatus
    agent_name: str
    task_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: int = 0

    @property
    def success(self) -> bool:
        """是否成功."""
        return self.status == ExecutionStatus.SUCCESS


class AgentExecutor:
    """Agent 执行器 - 统一管理和执行 Agent.

    功能:
    - Agent 注册和管理
    - 执行单个 Agent
    - 并行/顺序执行多个 Agent
    - 超时控制
    - 重试机制
    - 执行历史记录
    - 能力检查
    """

    def __init__(self, config: Optional[ExecutionConfig] = None):
        """初始化执行器.

        Args:
            config: 执行配置
        """
        self._agents: Dict[str, BaseAgent] = {}
        self._execution_history: List[ExecutionResult] = []
        self._config = config or ExecutionConfig()

    def register_agent(self, agent: BaseAgent) -> None:
        """注册 Agent.

        Args:
            agent: Agent 实例
        """
        self._agents[agent.name] = agent
        logger.debug(f"Registered agent: {agent.name}")

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """获取 Agent.

        Args:
            name: Agent 名称

        Returns:
            Agent 实例，不存在则返回 None
        """
        return self._agents.get(name)

    def get_registered_agents(self) -> List[str]:
        """获取所有已注册的 Agent 名称."""
        return list(self._agents.keys())

    async def execute_agent(
        self,
        agent_name: str,
        context: AgentContext,
        config: Optional[ExecutionConfig] = None,
        required_capability: Optional[AgentCapability] = None,
    ) -> ExecutionResult:
        """执行单个 Agent.

        Args:
            agent_name: Agent 名称
            context: 执行上下文
            config: 执行配置（覆盖默认配置）
            required_capability: 必需的能力

        Returns:
            ExecutionResult: 执行结果
        """
        exec_config = config or self._config
        agent = self._agents.get(agent_name)

        if not agent:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                agent_name=agent_name,
                task_id=context.task_id,
                errors=[f"Agent '{agent_name}' not found"],
            )

        if required_capability:
            if not agent.has_capability(required_capability.value):
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    agent_name=agent_name,
                    task_id=context.task_id,
                    errors=[
                        f"Agent '{agent_name}' does not have required capability: {required_capability.value}"
                    ],
                )

        return await self._execute_with_retry(agent, context, exec_config)

    async def _execute_with_retry(
        self,
        agent: BaseAgent,
        context: AgentContext,
        config: ExecutionConfig,
    ) -> ExecutionResult:
        """带重试机制的执行.

        Args:
            agent: Agent 实例
            context: 执行上下文
            config: 执行配置

        Returns:
            ExecutionResult: 执行结果
        """
        last_result: Optional[AgentResult] = None
        start_time = datetime.now()

        for attempt in range(config.max_retries):
            try:
                agent._status = agent._status.__class__.RUNNING

                result = await asyncio.wait_for(
                    agent.execute(context),
                    timeout=config.timeout,
                )

                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

                if result.success:
                    execution_result = ExecutionResult(
                        status=ExecutionStatus.SUCCESS,
                        agent_name=agent.name,
                        task_id=context.task_id,
                        data=result.data,
                        errors=result.errors,
                        warnings=result.warnings,
                        metrics=result.metrics,
                        duration_ms=duration_ms,
                    )
                    self._record_execution(execution_result)
                    agent._status = agent._status.__class__.SUCCESS
                    return execution_result

                last_result = result
                logger.warning(
                    f"Agent {agent.name} execution failed (attempt {attempt + 1}/{config.max_retries}): {result.errors}"
                )

                if attempt < config.max_retries - 1:
                    await asyncio.sleep(config.retry_delay * (attempt + 1))

            except asyncio.TimeoutError:
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                execution_result = ExecutionResult(
                    status=ExecutionStatus.TIMEOUT,
                    agent_name=agent.name,
                    task_id=context.task_id,
                    errors=[f"Execution timed out after {config.timeout} seconds"],
                    duration_ms=duration_ms,
                )
                self._record_execution(execution_result)
                agent._status = agent._status.__class__.FAILED
                return execution_result

            except Exception as e:
                logger.error(f"Agent {agent.name} execution error: {e}")
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                execution_result = ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    agent_name=agent.name,
                    task_id=context.task_id,
                    errors=[str(e)],
                    duration_ms=duration_ms,
                )
                self._record_execution(execution_result)
                agent._status = agent._status.__class__.FAILED
                return execution_result

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        execution_result = ExecutionResult(
            status=ExecutionStatus.FAILED,
            agent_name=agent.name,
            task_id=context.task_id,
            errors=last_result.errors if last_result else ["Unknown error"],
            warnings=last_result.warnings if last_result else [],
            duration_ms=duration_ms,
        )
        self._record_execution(execution_result)
        agent._status = agent._status.__class__.FAILED
        return execution_result

    async def execute_parallel(
        self,
        agent_names: List[str],
        context: AgentContext,
        config: Optional[ExecutionConfig] = None,
    ) -> List[ExecutionResult]:
        """并行或顺序执行多个 Agent.

        Args:
            agent_names: Agent 名称列表
            context: 执行上下文
            config: 执行配置

        Returns:
            List[ExecutionResult]: 执行结果列表
        """
        exec_config = config or self._config

        if exec_config.parallel_execution:
            semaphore = asyncio.Semaphore(exec_config.max_parallel_agents)

            async def execute_with_semaphore(agent_name: str) -> ExecutionResult:
                async with semaphore:
                    return await self.execute_agent(agent_name, context, exec_config)

            results = await asyncio.gather(
                *[execute_with_semaphore(name) for name in agent_names],
                return_exceptions=True,
            )

            return [
                r if isinstance(r, ExecutionResult) else ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    agent_name=agent_names[i],
                    task_id=context.task_id,
                    errors=[str(r)],
                )
                for i, r in enumerate(results)
            ]
        else:
            results = []
            for agent_name in agent_names:
                result = await self.execute_agent(agent_name, context, exec_config)
                results.append(result)
            return results

    def _record_execution(self, result: ExecutionResult) -> None:
        """记录执行结果.

        Args:
            result: 执行结果
        """
        self._execution_history.append(result)

        if len(self._execution_history) > self._config.history_limit:
            self._execution_history = self._execution_history[-self._config.history_limit :]

    def get_execution_history(self, limit: int = 100) -> List[ExecutionResult]:
        """获取执行历史.

        Args:
            limit: 返回数量限制

        Returns:
            List[ExecutionResult]: 执行历史列表
        """
        return self._execution_history[-limit:]

    def clear_history(self) -> None:
        """清除执行历史."""
        self._execution_history = []

    def get_stats(self) -> Dict[str, Any]:
        """获取执行统计信息.

        Returns:
            Dict[str, Any]: 统计信息
        """
        if not self._execution_history:
            return {
                "total_executions": 0,
                "success_count": 0,
                "failed_count": 0,
                "success_rate": 0.0,
            }

        success_count = sum(1 for r in self._execution_history if r.success)
        failed_count = len(self._execution_history) - success_count

        return {
            "total_executions": len(self._execution_history),
            "success_count": success_count,
            "failed_count": failed_count,
            "success_rate": success_count / len(self._execution_history),
            "registered_agents": list(self._agents.keys()),
        }
