"""优先级计算器."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Priority:
    """优先级."""
    score: int
    factors: Dict[str, int] = None
    
    def __lt__(self, other: "Priority") -> bool:
        return self.score < other.score
    
    def __le__(self, other: "Priority") -> bool:
        return self.score <= other.score
    
    def __gt__(self, other: "Priority") -> bool:
        return self.score > other.score
    
    def __ge__(self, other: "Priority") -> bool:
        return self.score >= other.score
    
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Priority):
            return self.score == other.score
        return False


class PriorityCalculator:
    """优先级计算器 - 综合多维度计算测试优先级."""
    
    DEFAULT_WEIGHTS = {
        "complexity": 0.25,
        "coverage": 0.25,
        "change_frequency": 0.20,
        "business_value": 0.15,
        "failure_history": 0.15,
    }
    
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        custom_factors: Optional[Dict[str, Any]] = None,
    ):
        self._weights = weights or self.DEFAULT_WEIGHTS.copy()
        self._custom_factors = custom_factors or {}
    
    def calculate(
        self,
        task_info: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Priority:
        scores = {}
        
        scores["complexity"] = self._complexity_score(task_info, context)
        
        scores["coverage"] = self._coverage_score(task_info, context)
        
        scores["change_frequency"] = self._change_frequency_score(task_info, context)
        
        scores["business_value"] = self._business_value_score(task_info, context)
        
        scores["failure_history"] = self._failure_history_score(task_info, context)
        
        for factor, calculator in self._custom_factors.items():
            scores[factor] = calculator(task_info, context)
        
        total_score = sum(
            scores.get(key, 0) * self._weights.get(key, 0)
            for key in self._weights
        )
        
        normalized_score = int(total_score * 100)
        
        return Priority(
            score=normalized_score,
            factors={k: int(v * 100) for k, v in scores.items()},
        )
    
    def _complexity_score(
        self,
        task_info: Dict[str, Any],
        context: Dict[str, Any],
    ) -> float:
        complexity = task_info.get("complexity", 0)
        
        if complexity > 20:
            return 1.0
        elif complexity > 15:
            return 0.8
        elif complexity > 10:
            return 0.6
        elif complexity > 5:
            return 0.4
        else:
            return 0.2
    
    def _coverage_score(
        self,
        task_info: Dict[str, Any],
        context: Dict[str, Any],
    ) -> float:
        current_coverage = task_info.get("current_coverage", 1.0)
        
        if current_coverage < 0.3:
            return 1.0
        elif current_coverage < 0.5:
            return 0.8
        elif current_coverage < 0.7:
            return 0.5
        elif current_coverage < 0.9:
            return 0.3
        else:
            return 0.1
    
    def _change_frequency_score(
        self,
        task_info: Dict[str, Any],
        context: Dict[str, Any],
    ) -> float:
        change_count = task_info.get("change_count", 0)
        
        if change_count > 10:
            return 1.0
        elif change_count > 5:
            return 0.7
        elif change_count > 2:
            return 0.5
        elif change_count > 0:
            return 0.3
        else:
            return 0.1
    
    def _business_value_score(
        self,
        task_info: Dict[str, Any],
        context: Dict[str, Any],
    ) -> float:
        file_path = task_info.get("source_file", "").lower()
        
        high_value_patterns = [
            "service", "controller", "api", "handler",
            "manager", "processor", "core",
        ]
        
        medium_value_patterns = [
            "repository", "dao", "client", "helper",
            "util", "config",
        ]
        
        for pattern in high_value_patterns:
            if pattern in file_path:
                return 1.0
        
        for pattern in medium_value_patterns:
            if pattern in file_path:
                return 0.6
        
        return 0.3
    
    def _failure_history_score(
        self,
        task_info: Dict[str, Any],
        context: Dict[str, Any],
    ) -> float:
        failure_count = task_info.get("failure_count", 0)
        
        if failure_count > 5:
            return 1.0
        elif failure_count > 3:
            return 0.7
        elif failure_count > 1:
            return 0.5
        elif failure_count > 0:
            return 0.3
        else:
            return 0.0
    
    def set_weight(self, factor: str, weight: float) -> None:
        self._weights[factor] = weight
    
    def add_custom_factor(
        self,
        name: str,
        calculator: callable,
        weight: float = 0.1,
    ) -> None:
        self._custom_factors[name] = calculator
        self._weights[name] = weight
    
    def get_weights(self) -> Dict[str, float]:
        return self._weights.copy()
    
    def rank_tasks(
        self,
        tasks: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        scored_tasks = []
        
        for task in tasks:
            priority = self.calculate(task, context)
            task_with_priority = task.copy()
            task_with_priority["priority_score"] = priority.score
            task_with_priority["priority_factors"] = priority.factors
            scored_tasks.append(task_with_priority)
        
        return sorted(
            scored_tasks,
            key=lambda t: t["priority_score"],
            reverse=True,
        )
