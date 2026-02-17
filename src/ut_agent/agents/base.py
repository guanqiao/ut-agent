"""Agent 基类定义."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from uuid import uuid4


class AgentStatus(Enum):
    """Agent 状态."""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class AgentCapability(Enum):
    """Agent 能力枚举."""
    AST_PARSE = "ast_parse"
    DEPENDENCY_ANALYSIS = "dependency_analysis"
    COMPLEXITY_ANALYSIS = "complexity_analysis"
    RISK_IDENTIFICATION = "risk_identification"
    TEST_STRATEGY = "test_strategy"
    TEMPLATE_SELECTION = "template_selection"
    MOCK_GENERATION = "mock_generation"
    TEST_DATA_GENERATION = "test_data_generation"
    ASSERTION_GENERATION = "assertion_generation"
    SCENARIO_COVERAGE = "scenario_coverage"
    CODE_QUALITY_CHECK = "code_quality_check"
    COVERAGE_VERIFICATION = "coverage_verification"
    ANTI_PATTERN_DETECTION = "anti_pattern_detection"
    BEST_PRACTICE_SUGGESTION = "best_practice_suggestion"
    COMPILE_ERROR_FIX = "compile_error_fix"
    RUNTIME_ERROR_FIX = "runtime_error_fix"
    ASSERTION_FIX = "assertion_fix"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    CONFLICT_MERGE = "conflict_merge"


@dataclass
class AgentContext:
    """Agent 执行上下文."""
    task_id: str = field(default_factory=lambda: str(uuid4()))
    session_id: Optional[str] = None
    project_path: str = ""
    project_type: str = ""
    source_file: str = ""
    source_content: str = ""
    file_analysis: Optional[Dict[str, Any]] = None
    generated_test: Optional[Dict[str, Any]] = None
    review_result: Optional[Dict[str, Any]] = None
    execution_result: Optional[Dict[str, Any]] = None
    coverage_report: Optional[Dict[str, Any]] = None
    memory_context: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Agent 执行结果."""
    success: bool
    agent_name: str
    task_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: int = 0


@dataclass
class Capability:
    """能力定义."""
    name: str
    description: str
    handler: Optional[Callable] = None
    priority: int = 0
    enabled: bool = True


class BaseAgent(ABC):
    """Agent 基类."""
    
    name: str = "base_agent"
    description: str = "Base Agent"
    capabilities: List[AgentCapability] = []
    
    def __init__(
        self,
        memory: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self._memory = memory
        self._config = config or {}
        self._status = AgentStatus.IDLE
        self._capability_handlers: Dict[str, Capability] = {}
        self._execution_history: List[AgentResult] = []
        
        for cap in self.capabilities:
            self._register_default_capability(cap)
    
    @property
    def status(self) -> AgentStatus:
        return self._status
    
    @property
    def memory(self) -> Optional[Any]:
        return self._memory
    
    @memory.setter
    def memory(self, value: Optional[Any]) -> None:
        self._memory = value
    
    def _register_default_capability(self, capability: AgentCapability) -> None:
        self._capability_handlers[capability.value] = Capability(
            name=capability.value,
            description=capability.value.replace("_", " ").title(),
        )
    
    def register_capability(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        priority: int = 0,
    ) -> None:
        self._capability_handlers[name] = Capability(
            name=name,
            description=description,
            handler=handler,
            priority=priority,
        )
    
    def has_capability(self, capability: str) -> bool:
        return capability in self._capability_handlers
    
    def get_capabilities(self) -> List[str]:
        return list(self._capability_handlers.keys())
    
    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        pass
    
    async def invoke_capability(
        self,
        capability: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if capability not in self._capability_handlers:
            raise ValueError(f"Agent {self.name} does not have capability: {capability}")
        
        cap = self._capability_handlers[capability]
        if not cap.enabled or cap.handler is None:
            raise ValueError(f"Capability {capability} is not available")
        
        return await cap.handler(*args, **kwargs)
    
    def record_execution(self, result: AgentResult) -> None:
        self._execution_history.append(result)
        if len(self._execution_history) > 100:
            self._execution_history = self._execution_history[-100:]
    
    def get_execution_history(self, limit: int = 10) -> List[AgentResult]:
        return self._execution_history[-limit:]
    
    def remember(self, key: str, value: Any) -> None:
        if self._memory is not None:
            self._memory.remember(self.name, key, value)
    
    def recall(self, key: str) -> Optional[Any]:
        if self._memory is not None:
            return self._memory.recall(self.name, key)
        return None
    
    def learn(self, feedback: Dict[str, Any]) -> None:
        if self._memory is not None:
            self._memory.learn(self.name, feedback)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": self.get_capabilities(),
            "status": self._status.value,
        }
