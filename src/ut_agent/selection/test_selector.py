"""测试选择器."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ut_agent.selection.change_detector import ChangeType
from ut_agent.selection.impact_analyzer import ImpactReport


class TaskType(Enum):
    """任务类型."""
    GENERATE_NEW = "generate_new"
    UPDATE_EXISTING = "update_existing"
    DEPRECATE = "deprecate"
    VERIFY = "verify"


class SelectionStrategy(Enum):
    """选择策略."""
    CONSERVATIVE = "conservative"
    AGGRESSIVE = "aggressive"
    SMART = "smart"


@dataclass
class TestTask:
    """测试任务."""
    source_file: str
    task_type: TaskType
    test_file: Optional[str] = None
    methods: List[str] = field(default_factory=list)
    priority: int = 0
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SelectionResult:
    """选择结果."""
    to_generate: List[TestTask] = field(default_factory=list)
    to_update: List[TestTask] = field(default_factory=list)
    to_deprecate: List[TestTask] = field(default_factory=list)
    to_verify: List[TestTask] = field(default_factory=list)
    
    @property
    def all_tasks(self) -> List[TestTask]:
        return (
            self.to_generate +
            self.to_update +
            self.to_deprecate +
            self.to_verify
        )
    
    @property
    def total_count(self) -> int:
        return len(self.all_tasks)
    
    def add_task(self, task: TestTask) -> None:
        if task.task_type == TaskType.GENERATE_NEW:
            self.to_generate.append(task)
        elif task.task_type == TaskType.UPDATE_EXISTING:
            self.to_update.append(task)
        elif task.task_type == TaskType.DEPRECATE:
            self.to_deprecate.append(task)
        elif task.task_type == TaskType.VERIFY:
            self.to_verify.append(task)


class TestSelector:
    """测试选择器 - 根据影响分析选择需要执行的测试."""
    
    def __init__(
        self,
        strategy: SelectionStrategy = SelectionStrategy.SMART,
        priority_calculator=None,
    ):
        self._strategy = strategy
        self._priority_calculator = priority_calculator
    
    def select_tests(self, impact: ImpactReport) -> SelectionResult:
        result = SelectionResult()
        
        for direct in impact.direct_impacts:
            if direct.change_type == ChangeType.ADDED:
                task = TestTask(
                    source_file=direct.file_path,
                    task_type=TaskType.GENERATE_NEW,
                    methods=[m.name for m in direct.method_changes],
                    reason="新增源文件，需要生成新测试",
                )
                result.add_task(task)
            
            elif direct.change_type == ChangeType.MODIFIED:
                if direct.test_file:
                    task = TestTask(
                        source_file=direct.file_path,
                        task_type=TaskType.UPDATE_EXISTING,
                        test_file=direct.test_file,
                        methods=[m.name for m in direct.method_changes if m.change_type != ChangeType.DELETED],
                        reason="源文件已修改，需要更新测试",
                    )
                else:
                    task = TestTask(
                        source_file=direct.file_path,
                        task_type=TaskType.GENERATE_NEW,
                        methods=[m.name for m in direct.method_changes],
                        reason="源文件已修改但无对应测试，需要生成新测试",
                    )
                result.add_task(task)
            
            elif direct.change_type == ChangeType.DELETED:
                if direct.test_file:
                    task = TestTask(
                        source_file=direct.file_path,
                        task_type=TaskType.DEPRECATE,
                        test_file=direct.test_file,
                        reason="源文件已删除，测试应标记为废弃",
                    )
                    result.add_task(task)
        
        for indirect in impact.indirect_impacts:
            if self._strategy == SelectionStrategy.CONSERVATIVE:
                task = TestTask(
                    source_file=indirect.file_path,
                    task_type=TaskType.VERIFY,
                    test_file=indirect.test_file,
                    reason=f"间接影响: {indirect.reason}",
                )
                result.add_task(task)
            
            elif self._strategy == SelectionStrategy.SMART:
                if indirect.test_file:
                    task = TestTask(
                        source_file=indirect.file_path,
                        task_type=TaskType.VERIFY,
                        test_file=indirect.test_file,
                        reason=f"间接影响: {indirect.reason}",
                    )
                    result.add_task(task)
        
        for test_impact in impact.test_impacts:
            existing = next(
                (t for t in result.to_update if t.test_file == test_impact.test_file),
                None
            )
            
            if not existing and test_impact.test_method:
                task = TestTask(
                    source_file="",
                    task_type=TaskType.UPDATE_EXISTING,
                    test_file=test_impact.test_file,
                    methods=[test_impact.test_method],
                    reason=test_impact.reason,
                    priority=test_impact.priority,
                )
                result.add_task(task)
        
        return result
    
    def prioritize(
        self,
        selection: SelectionResult,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[TestTask]:
        all_tasks = selection.all_tasks
        
        for task in all_tasks:
            task.priority = self._calculate_priority(task, context)
        
        sorted_tasks = sorted(
            all_tasks,
            key=lambda t: (t.priority, t.task_type.value),
            reverse=True,
        )
        
        return sorted_tasks
    
    def _calculate_priority(
        self,
        task: TestTask,
        context: Optional[Dict[str, Any]] = None,
    ) -> int:
        score = task.priority
        
        if task.task_type == TaskType.GENERATE_NEW:
            score += 30
        elif task.task_type == TaskType.UPDATE_EXISTING:
            score += 20
        elif task.task_type == TaskType.VERIFY:
            score += 10
        elif task.task_type == TaskType.DEPRECATE:
            score += 5
        
        if context:
            if self._is_core_module(task.source_file, context):
                score += 25
            
            if context.get("low_coverage_files", {}).get(task.source_file, 1) < 0.5:
                score += 20
            
            if task.source_file in context.get("recently_modified", []):
                score += 15
            
            if task.source_file in context.get("failure_history", []):
                score += 10
        
        return score
    
    def _is_core_module(
        self,
        file_path: str,
        context: Dict[str, Any],
    ) -> bool:
        core_patterns = context.get("core_patterns", [
            "service", "controller", "repository", "manager",
        ])
        
        file_lower = file_path.lower()
        return any(pattern in file_lower for pattern in core_patterns)
    
    def get_summary(self, selection: SelectionResult) -> Dict[str, Any]:
        return {
            "total_tasks": selection.total_count,
            "generate_new": len(selection.to_generate),
            "update_existing": len(selection.to_update),
            "deprecate": len(selection.to_deprecate),
            "verify": len(selection.to_verify),
            "strategy": self._strategy.value,
        }
