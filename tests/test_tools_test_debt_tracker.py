"""测试债务管理系统模块测试."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from ut_agent.tools.test_debt_tracker import (
    TestDebtTracker,
    TestDebtItem,
    DebtReport,
    DebtType,
    DebtPriority,
    DebtStatus,
)


class TestTestDebtItem:
    
    def test_debt_item_creation(self):
        item = TestDebtItem(
            debt_id="debt_001",
            debt_type=DebtType.LOW_COVERAGE,
            priority=DebtPriority.HIGH,
            status=DebtStatus.OPEN,
            file_path="src/main/java/Service.java",
            description="Low test coverage",
            impact_score=5.0,
            effort_estimate=2,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        
        assert item.debt_id == "debt_001"
        assert item.debt_type == DebtType.LOW_COVERAGE
        assert item.status == DebtStatus.OPEN
    
    def test_debt_score_calculation(self):
        item = TestDebtItem(
            debt_id="debt_002",
            debt_type=DebtType.FLAKY_TESTS,
            priority=DebtPriority.CRITICAL,
            status=DebtStatus.OPEN,
            file_path="test.java",
            description="Flaky test",
            impact_score=10.0,
            effort_estimate=1,
            created_at=datetime.now() - timedelta(days=30),
            updated_at=datetime.now(),
        )
        
        score = item.debt_score
        
        assert score > 0
        assert score >= item.impact_score * 4.0
    
    def test_debt_item_to_dict(self):
        item = TestDebtItem(
            debt_id="debt_003",
            debt_type=DebtType.MISSING_TESTS,
            priority=DebtPriority.MEDIUM,
            status=DebtStatus.OPEN,
            file_path="test.java",
            description="Missing tests",
            impact_score=3.0,
            effort_estimate=1,
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
        )
        
        result = item.to_dict()
        
        assert result["debt_id"] == "debt_003"
        assert result["debt_type"] == "missing_tests"
        assert result["priority"] == "medium"


class TestTestDebtTracker:
    
    def test_tracker_initialization(self):
        tracker = TestDebtTracker("/tmp/test_project_init")
        
        assert tracker.project_path == Path("/tmp/test_project_init")
        assert len(tracker.debt_items) == 0
    
    def test_record_metrics(self):
        import uuid
        unique_path = f"/tmp/test_project_metrics_{uuid.uuid4().hex[:8]}"
        tracker = TestDebtTracker(unique_path)
        
        tracker.record_metrics({
            "coverage": 65.0,
            "mutation_score": 55.0,
            "flaky_rate": 0.08,
        })
        
        assert "coverage" in tracker.metrics_history
        assert len(tracker.metrics_history["coverage"]) >= 1
    
    def test_add_debt_item(self):
        tracker = TestDebtTracker("/tmp/test_project_add")
        
        item = tracker.add_debt_item(
            debt_type=DebtType.MISSING_ASSERTIONS,
            file_path="src/test/java/Test.java",
            description="Test lacks assertions",
            impact_score=5.0,
            priority=DebtPriority.HIGH,
        )
        
        assert item.debt_id in tracker.debt_items
        assert item.status == DebtStatus.OPEN
    
    def test_resolve_debt(self):
        tracker = TestDebtTracker("/tmp/test_project_resolve")
        
        item = tracker.add_debt_item(
            debt_type=DebtType.LOW_COVERAGE,
            file_path="test.java",
            description="Low coverage",
            impact_score=3.0,
        )
        
        result = tracker.resolve_debt(item.debt_id)
        
        assert result == True
        assert tracker.debt_items[item.debt_id].status == DebtStatus.RESOLVED
    
    def test_resolve_nonexistent_debt(self):
        tracker = TestDebtTracker("/tmp/test_project_nonexist")
        
        result = tracker.resolve_debt("nonexistent_id")
        
        assert result == False
    
    def test_get_debt_report(self):
        tracker = TestDebtTracker("/tmp/test_project_report")
        
        tracker.add_debt_item(
            debt_type=DebtType.FLAKY_TESTS,
            file_path="test1.java",
            description="Flaky test 1",
            impact_score=5.0,
            priority=DebtPriority.HIGH,
        )
        
        tracker.add_debt_item(
            debt_type=DebtType.LOW_COVERAGE,
            file_path="test2.java",
            description="Low coverage",
            impact_score=3.0,
            priority=DebtPriority.MEDIUM,
        )
        
        report = tracker.get_debt_report()
        
        assert report.total_items == 2
        assert report.open_items == 2
    
    def test_get_debt_by_file(self):
        tracker = TestDebtTracker("/tmp/test_project_byfile")
        
        tracker.add_debt_item(
            debt_type=DebtType.MISSING_TESTS,
            file_path="src/Service.java",
            description="Missing tests",
            impact_score=5.0,
        )
        
        tracker.add_debt_item(
            debt_type=DebtType.LOW_COVERAGE,
            file_path="src/Other.java",
            description="Low coverage",
            impact_score=3.0,
        )
        
        items = tracker.get_debt_by_file("src/Service.java")
        
        assert len(items) == 1
        assert items[0].debt_type == DebtType.MISSING_TESTS
    
    def test_get_debt_summary(self):
        tracker = TestDebtTracker("/tmp/test_project_summary")
        
        tracker.add_debt_item(
            debt_type=DebtType.FLAKY_TESTS,
            file_path="test.java",
            description="Flaky",
            impact_score=5.0,
            priority=DebtPriority.CRITICAL,
        )
        
        tracker.add_debt_item(
            debt_type=DebtType.POOR_QUALITY,
            file_path="test2.java",
            description="Poor quality",
            impact_score=3.0,
            priority=DebtPriority.LOW,
        )
        
        summary = tracker.get_debt_summary()
        
        assert summary["open_items"] == 2
        assert summary["by_priority"]["critical"] == 1
        assert summary["by_priority"]["low"] == 1
    
    def test_calculate_debt_interest(self):
        tracker = TestDebtTracker("/tmp/test_project_interest")
        
        tracker.add_debt_item(
            debt_type=DebtType.MUTATION_WEAKNESS,
            file_path="test.java",
            description="Mutation weakness",
            impact_score=10.0,
        )
        
        interest = tracker.calculate_debt_interest()
        
        assert interest >= 0


class TestDebtReport:
    
    def test_report_creation(self):
        report = DebtReport(
            project_path="/tmp/project",
            total_debt_score=50.0,
            total_items=5,
            open_items=3,
            critical_items=1,
            debt_by_type={"low_coverage": 20.0, "flaky_tests": 30.0},
            debt_by_priority={"high": 2, "medium": 3},
            trends=[],
            prioritized_items=[],
            recommendations=["Fix critical issues"],
            generated_at=datetime.now(),
        )
        
        assert report.total_debt_score == 50.0
        assert report.total_items == 5
    
    def test_report_to_dict(self):
        report = DebtReport(
            project_path="/tmp/project",
            total_debt_score=30.0,
            total_items=3,
            open_items=2,
            critical_items=0,
            debt_by_type={},
            debt_by_priority={},
            trends=[],
            prioritized_items=[],
            recommendations=[],
            generated_at=datetime(2024, 1, 1, 12, 0, 0),
        )
        
        result = report.to_dict()
        
        assert result["total_debt_score"] == 30.0
        assert result["total_items"] == 3


class TestDebtTypes:
    
    def test_debt_type_values(self):
        assert DebtType.MISSING_TESTS.value == "missing_tests"
        assert DebtType.LOW_COVERAGE.value == "low_coverage"
        assert DebtType.FLAKY_TESTS.value == "flaky_tests"
        assert DebtType.POOR_QUALITY.value == "poor_quality"
    
    def test_debt_priority_values(self):
        assert DebtPriority.CRITICAL.value == "critical"
        assert DebtPriority.HIGH.value == "high"
        assert DebtPriority.MEDIUM.value == "medium"
        assert DebtPriority.LOW.value == "low"
    
    def test_debt_status_values(self):
        assert DebtStatus.OPEN.value == "open"
        assert DebtStatus.IN_PROGRESS.value == "in_progress"
        assert DebtStatus.RESOLVED.value == "resolved"
        assert DebtStatus.IGNORED.value == "ignored"
