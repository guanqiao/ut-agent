"""测试债务管理系统.

量化测试债务，追踪质量趋势，提供优先级排序的改进建议。
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict


class DebtType(Enum):
    MISSING_TESTS = "missing_tests"
    LOW_COVERAGE = "low_coverage"
    FLAKY_TESTS = "flaky_tests"
    POOR_QUALITY = "poor_quality"
    OUTDATED_TESTS = "outdated_tests"
    MISSING_ASSERTIONS = "missing_assertions"
    COMPLEX_TESTS = "complex_tests"
    DUPLICATE_TESTS = "duplicate_tests"
    MISSING_EDGE_CASES = "missing_edge_cases"
    MUTATION_WEAKNESS = "mutation_weakness"


class DebtPriority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DebtStatus(Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    IGNORED = "ignored"


@dataclass
class TestDebtItem:
    debt_id: str
    debt_type: DebtType
    priority: DebtPriority
    status: DebtStatus
    file_path: str
    description: str
    impact_score: float
    effort_estimate: int
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    assigned_to: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def debt_score(self) -> float:
        priority_weights = {
            DebtPriority.CRITICAL: 4.0,
            DebtPriority.HIGH: 3.0,
            DebtPriority.MEDIUM: 2.0,
            DebtPriority.LOW: 1.0,
        }
        
        age_days = (datetime.now() - self.created_at).days
        age_factor = min(2.0, 1.0 + age_days / 30)
        
        return self.impact_score * priority_weights[self.priority] * age_factor
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "debt_id": self.debt_id,
            "debt_type": self.debt_type.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "file_path": self.file_path,
            "description": self.description,
            "impact_score": round(self.impact_score, 2),
            "effort_estimate": self.effort_estimate,
            "debt_score": round(self.debt_score, 2),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "assigned_to": self.assigned_to,
            "tags": self.tags,
            "metrics": self.metrics,
        }


@dataclass
class QualityTrend:
    metric_name: str
    values: List[Tuple[datetime, float]]
    trend_direction: str
    change_rate: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "values": [(t.isoformat(), v) for t, v in self.values[-10:]],
            "trend_direction": self.trend_direction,
            "change_rate": round(self.change_rate, 4),
        }


@dataclass
class DebtReport:
    project_path: str
    total_debt_score: float
    total_items: int
    open_items: int
    critical_items: int
    debt_by_type: Dict[str, float]
    debt_by_priority: Dict[str, int]
    trends: List[QualityTrend]
    prioritized_items: List[TestDebtItem]
    recommendations: List[str]
    generated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_path": self.project_path,
            "total_debt_score": round(self.total_debt_score, 2),
            "total_items": self.total_items,
            "open_items": self.open_items,
            "critical_items": self.critical_items,
            "debt_by_type": self.debt_by_type,
            "debt_by_priority": self.debt_by_priority,
            "trends": [t.to_dict() for t in self.trends],
            "prioritized_items": [i.to_dict() for i in self.prioritized_items[:20]],
            "recommendations": self.recommendations,
            "generated_at": self.generated_at.isoformat(),
        }


class TestDebtTracker:
    
    DEBT_THRESHOLDS = {
        "coverage": {"warning": 70, "critical": 50},
        "mutation_score": {"warning": 60, "critical": 40},
        "flaky_rate": {"warning": 0.05, "critical": 0.1},
        "quality_score": {"warning": 60, "critical": 40},
        "assertion_density": {"warning": 0.5, "critical": 0.3},
    }
    
    def __init__(self, project_path: str, storage_path: Optional[str] = None):
        self.project_path = Path(project_path)
        self.storage_path = Path(storage_path) if storage_path else self.project_path / ".ut-agent" / "debt"
        self.debt_items: Dict[str, TestDebtItem] = {}
        self.metrics_history: Dict[str, List[Tuple[datetime, float]]] = defaultdict(list)
        self._debt_counter = 0
        self._load_data()
    
    def _load_data(self) -> None:
        if self.storage_path.exists():
            debt_file = self.storage_path / "debt_items.json"
            if debt_file.exists():
                try:
                    with open(debt_file, 'r') as f:
                        data = json.load(f)
                        for item_data in data.get("items", []):
                            item = TestDebtItem(
                                debt_id=item_data["debt_id"],
                                debt_type=DebtType(item_data["debt_type"]),
                                priority=DebtPriority(item_data["priority"]),
                                status=DebtStatus(item_data["status"]),
                                file_path=item_data["file_path"],
                                description=item_data["description"],
                                impact_score=item_data["impact_score"],
                                effort_estimate=item_data["effort_estimate"],
                                created_at=datetime.fromisoformat(item_data["created_at"]),
                                updated_at=datetime.fromisoformat(item_data["updated_at"]),
                                resolved_at=datetime.fromisoformat(item_data["resolved_at"]) if item_data.get("resolved_at") else None,
                                assigned_to=item_data.get("assigned_to"),
                                tags=item_data.get("tags", []),
                                metrics=item_data.get("metrics", {}),
                            )
                            self.debt_items[item.debt_id] = item
                            if int(item.debt_id.split("_")[-1]) > self._debt_counter:
                                self._debt_counter = int(item.debt_id.split("_")[-1])
                except Exception:
                    pass
            
            metrics_file = self.storage_path / "metrics_history.json"
            if metrics_file.exists():
                try:
                    with open(metrics_file, 'r') as f:
                        data = json.load(f)
                        for metric, values in data.items():
                            self.metrics_history[metric] = [
                                (datetime.fromisoformat(t), v) for t, v in values
                            ]
                except Exception:
                    pass
    
    def _save_data(self) -> None:
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        debt_file = self.storage_path / "debt_items.json"
        with open(debt_file, 'w') as f:
            json.dump({
                "items": [item.to_dict() for item in self.debt_items.values()],
                "updated_at": datetime.now().isoformat(),
            }, f, indent=2)
        
        metrics_file = self.storage_path / "metrics_history.json"
        with open(metrics_file, 'w') as f:
            json.dump({
                metric: [(t.isoformat(), v) for t, v in values]
                for metric, values in self.metrics_history.items()
            }, f, indent=2)
    
    def _generate_debt_id(self) -> str:
        self._debt_counter += 1
        return f"debt_{self._debt_counter:06d}"
    
    def record_metrics(self, metrics: Dict[str, float]) -> None:
        now = datetime.now()
        
        for metric_name, value in metrics.items():
            self.metrics_history[metric_name].append((now, value))
            
            if len(self.metrics_history[metric_name]) > 100:
                self.metrics_history[metric_name] = self.metrics_history[metric_name][-100:]
        
        self._detect_debt_from_metrics(metrics)
        self._save_data()
    
    def _detect_debt_from_metrics(self, metrics: Dict[str, float]) -> None:
        for metric_name, value in metrics.items():
            if metric_name not in self.DEBT_THRESHOLDS:
                continue
            
            thresholds = self.DEBT_THRESHOLDS[metric_name]
            
            if metric_name == "flaky_rate":
                if value >= thresholds["critical"]:
                    self._create_or_update_debt(
                        debt_type=DebtType.FLAKY_TESTS,
                        file_path="project-wide",
                        description=f"Critical flaky test rate: {value:.2%}",
                        impact_score=value * 100,
                        priority=DebtPriority.CRITICAL,
                        metrics={metric_name: value},
                    )
                elif value >= thresholds["warning"]:
                    self._create_or_update_debt(
                        debt_type=DebtType.FLAKY_TESTS,
                        file_path="project-wide",
                        description=f"Warning flaky test rate: {value:.2%}",
                        impact_score=value * 50,
                        priority=DebtPriority.HIGH,
                        metrics={metric_name: value},
                    )
            else:
                if value <= thresholds["critical"]:
                    self._create_or_update_debt(
                        debt_type=DebtType.LOW_COVERAGE if metric_name == "coverage" else DebtType.POOR_QUALITY,
                        file_path="project-wide",
                        description=f"Critical {metric_name}: {value:.2f}",
                        impact_score=(100 - value) / 10,
                        priority=DebtPriority.CRITICAL,
                        metrics={metric_name: value},
                    )
                elif value <= thresholds["warning"]:
                    self._create_or_update_debt(
                        debt_type=DebtType.LOW_COVERAGE if metric_name == "coverage" else DebtType.POOR_QUALITY,
                        file_path="project-wide",
                        description=f"Warning {metric_name}: {value:.2f}",
                        impact_score=(100 - value) / 20,
                        priority=DebtPriority.HIGH,
                        metrics={metric_name: value},
                    )
    
    def _create_or_update_debt(
        self,
        debt_type: DebtType,
        file_path: str,
        description: str,
        impact_score: float,
        priority: DebtPriority,
        metrics: Dict[str, Any],
        effort_estimate: int = 1,
    ) -> TestDebtItem:
        existing = self._find_existing_debt(debt_type, file_path)
        
        if existing:
            existing.impact_score = impact_score
            existing.metrics = metrics
            existing.updated_at = datetime.now()
            if existing.status == DebtStatus.RESOLVED:
                existing.status = DebtStatus.OPEN
                existing.resolved_at = None
            self._save_data()
            return existing
        
        debt_id = self._generate_debt_id()
        now = datetime.now()
        
        item = TestDebtItem(
            debt_id=debt_id,
            debt_type=debt_type,
            priority=priority,
            status=DebtStatus.OPEN,
            file_path=file_path,
            description=description,
            impact_score=impact_score,
            effort_estimate=effort_estimate,
            created_at=now,
            updated_at=now,
            metrics=metrics,
        )
        
        self.debt_items[debt_id] = item
        self._save_data()
        
        return item
    
    def _find_existing_debt(
        self,
        debt_type: DebtType,
        file_path: str,
    ) -> Optional[TestDebtItem]:
        for item in self.debt_items.values():
            if (item.debt_type == debt_type and 
                item.file_path == file_path and 
                item.status in (DebtStatus.OPEN, DebtStatus.IN_PROGRESS)):
                return item
        return None
    
    def add_debt_item(
        self,
        debt_type: DebtType,
        file_path: str,
        description: str,
        impact_score: float,
        priority: DebtPriority = DebtPriority.MEDIUM,
        effort_estimate: int = 1,
        tags: Optional[List[str]] = None,
    ) -> TestDebtItem:
        return self._create_or_update_debt(
            debt_type=debt_type,
            file_path=file_path,
            description=description,
            impact_score=impact_score,
            priority=priority,
            metrics={},
            effort_estimate=effort_estimate,
        )
    
    def resolve_debt(self, debt_id: str) -> bool:
        if debt_id in self.debt_items:
            item = self.debt_items[debt_id]
            item.status = DebtStatus.RESOLVED
            item.resolved_at = datetime.now()
            item.updated_at = datetime.now()
            self._save_data()
            return True
        return False
    
    def get_debt_report(self) -> DebtReport:
        open_items = [i for i in self.debt_items.values() if i.status == DebtStatus.OPEN]
        
        total_debt = sum(i.debt_score for i in open_items)
        
        debt_by_type: Dict[str, float] = defaultdict(float)
        for item in open_items:
            debt_by_type[item.debt_type.value] += item.debt_score
        
        debt_by_priority: Dict[str, int] = defaultdict(int)
        for item in open_items:
            debt_by_priority[item.priority.value] += 1
        
        trends = self._calculate_trends()
        
        prioritized = sorted(open_items, key=lambda i: i.debt_score, reverse=True)
        
        critical_count = sum(1 for i in open_items if i.priority == DebtPriority.CRITICAL)
        
        recommendations = self._generate_recommendations(open_items, trends)
        
        return DebtReport(
            project_path=str(self.project_path),
            total_debt_score=total_debt,
            total_items=len(self.debt_items),
            open_items=len(open_items),
            critical_items=critical_count,
            debt_by_type=dict(debt_by_type),
            debt_by_priority=dict(debt_by_priority),
            trends=trends,
            prioritized_items=prioritized,
            recommendations=recommendations,
            generated_at=datetime.now(),
        )
    
    def _calculate_trends(self) -> List[QualityTrend]:
        trends = []
        
        for metric_name, values in self.metrics_history.items():
            if len(values) < 2:
                continue
            
            recent_values = values[-10:]
            
            if len(recent_values) >= 2:
                first_value = recent_values[0][1]
                last_value = recent_values[-1][1]
                
                if first_value != 0:
                    change_rate = (last_value - first_value) / abs(first_value)
                else:
                    change_rate = 0
                
                if change_rate > 0.05:
                    direction = "improving"
                elif change_rate < -0.05:
                    direction = "declining"
                else:
                    direction = "stable"
                
                trends.append(QualityTrend(
                    metric_name=metric_name,
                    values=recent_values,
                    trend_direction=direction,
                    change_rate=change_rate,
                ))
        
        return trends
    
    def _generate_recommendations(
        self,
        open_items: List[TestDebtItem],
        trends: List[QualityTrend],
    ) -> List[str]:
        recommendations = []
        
        critical_items = [i for i in open_items if i.priority == DebtPriority.CRITICAL]
        if critical_items:
            recommendations.append(
                f"Address {len(critical_items)} critical debt items immediately"
            )
        
        declining_metrics = [t for t in trends if t.trend_direction == "declining"]
        for trend in declining_metrics:
            recommendations.append(
                f"Focus on improving {trend.metric_name} (declining at {trend.change_rate:.1%})"
            )
        
        debt_by_type = defaultdict(list)
        for item in open_items:
            debt_by_type[item.debt_type.value].append(item)
        
        if len(debt_by_type.get(DebtType.FLAKY_TESTS.value, [])) > 3:
            recommendations.append(
                "Consider implementing a test stability improvement sprint"
            )
        
        if len(debt_by_type.get(DebtType.LOW_COVERAGE.value, [])) > 5:
            recommendations.append(
                "Prioritize coverage improvements for high-impact files"
            )
        
        quick_wins = [i for i in open_items if i.effort_estimate <= 2 and i.priority in (DebtPriority.HIGH, DebtPriority.CRITICAL)]
        if quick_wins:
            recommendations.append(
                f"Tackle {len(quick_wins)} quick-win items for immediate impact"
            )
        
        return recommendations[:10]
    
    def get_debt_by_file(self, file_path: str) -> List[TestDebtItem]:
        return [
            item for item in self.debt_items.values()
            if item.file_path == file_path and item.status == DebtStatus.OPEN
        ]
    
    def get_debt_summary(self) -> Dict[str, Any]:
        open_items = [i for i in self.debt_items.values() if i.status == DebtStatus.OPEN]
        
        return {
            "total_debt_score": round(sum(i.debt_score for i in open_items), 2),
            "open_items": len(open_items),
            "by_priority": {
                "critical": sum(1 for i in open_items if i.priority == DebtPriority.CRITICAL),
                "high": sum(1 for i in open_items if i.priority == DebtPriority.HIGH),
                "medium": sum(1 for i in open_items if i.priority == DebtPriority.MEDIUM),
                "low": sum(1 for i in open_items if i.priority == DebtPriority.LOW),
            },
            "by_type": {
                debt_type.value: sum(1 for i in open_items if i.debt_type == debt_type)
                for debt_type in DebtType
            },
        }
    
    def calculate_debt_interest(self) -> float:
        open_items = [i for i in self.debt_items.values() if i.status == DebtStatus.OPEN]
        
        interest = 0.0
        for item in open_items:
            age_days = (datetime.now() - item.created_at).days
            monthly_interest_rate = 0.1
            
            interest += item.impact_score * (monthly_interest_rate ** (age_days / 30))
        
        return interest
