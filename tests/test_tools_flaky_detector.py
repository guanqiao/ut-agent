"""Flaky Test 检测器模块测试."""

import pytest
from datetime import datetime, timedelta
from ut_agent.tools.flaky_detector import (
    FlakyTestDetector,
    FlakyTest,
    FlakyCause,
    TestStatus,
    TestExecution,
    StabilityAnalyzer,
    StabilityReport,
    TestQuarantine,
)


class TestTestExecution:
    
    def test_execution_creation(self):
        execution = TestExecution(
            test_id="test_001",
            test_class="TestClass",
            test_method="testMethod",
            status=TestStatus.PASSED,
            duration_ms=150.5,
            timestamp=datetime.now(),
        )
        
        assert execution.test_id == "test_001"
        assert execution.status == TestStatus.PASSED
    
    def test_execution_to_dict(self):
        execution = TestExecution(
            test_id="test_002",
            test_class="TestClass",
            test_method="testMethod",
            status=TestStatus.FAILED,
            duration_ms=200.0,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            error_message="Assertion failed",
        )
        
        result = execution.to_dict()
        
        assert result["status"] == "failed"
        assert result["error_message"] == "Assertion failed"


class TestFlakyTest:
    
    def test_flaky_test_creation(self):
        flaky = FlakyTest(
            test_id="test_001",
            test_class="TestClass",
            test_method="testFlaky",
            flaky_score=0.5,
            pass_count=5,
            fail_count=3,
            total_runs=8,
            detected_causes=[FlakyCause.TIME_DEPENDENCY],
            first_detected=datetime.now(),
            last_flaky=datetime.now(),
            recent_executions=[],
            suggested_fixes=["Inject Clock"],
        )
        
        assert flaky.flaky_score == 0.5
        assert flaky.flaky_rate == 3 / 8
    
    def test_flaky_test_to_dict(self):
        flaky = FlakyTest(
            test_id="test_002",
            test_class="TestClass",
            test_method="testFlaky",
            flaky_score=0.3,
            pass_count=7,
            fail_count=3,
            total_runs=10,
            detected_causes=[FlakyCause.RANDOM_VALUE],
            first_detected=datetime(2024, 1, 1),
            last_flaky=datetime(2024, 1, 2),
            recent_executions=[],
            suggested_fixes=[],
        )
        
        result = flaky.to_dict()
        
        assert result["flaky_rate"] == 0.3
        assert result["detected_causes"] == ["random_value"]


class TestFlakyTestDetector:
    
    def test_record_execution(self):
        detector = FlakyTestDetector()
        
        execution = TestExecution(
            test_id="test_001",
            test_class="TestClass",
            test_method="testMethod",
            status=TestStatus.PASSED,
            duration_ms=100.0,
            timestamp=datetime.now(),
        )
        
        detector.record_execution(execution)
        
        assert "test_001" in detector.execution_history
        assert len(detector.execution_history["test_001"]) == 1
    
    def test_detect_flaky_tests_no_flaky(self):
        detector = FlakyTestDetector()
        
        for i in range(10):
            execution = TestExecution(
                test_id="test_stable",
                test_class="TestClass",
                test_method="testStable",
                status=TestStatus.PASSED,
                duration_ms=100.0,
                timestamp=datetime.now() + timedelta(minutes=i),
            )
            detector.record_execution(execution)
        
        flaky_tests = detector.detect_flaky_tests()
        
        stable_tests = [t for t in flaky_tests if t.test_id == "test_stable"]
        assert len(stable_tests) == 0
    
    def test_detect_flaky_tests_with_flaky(self):
        detector = FlakyTestDetector()
        
        statuses = [
            TestStatus.PASSED, TestStatus.FAILED,
            TestStatus.PASSED, TestStatus.FAILED,
            TestStatus.PASSED, TestStatus.FAILED,
            TestStatus.PASSED, TestStatus.FAILED,
            TestStatus.PASSED, TestStatus.FAILED,
        ]
        
        for i, status in enumerate(statuses):
            execution = TestExecution(
                test_id="test_flaky",
                test_class="TestClass",
                test_method="testFlaky",
                status=status,
                duration_ms=100.0 + (i * 10),
                timestamp=datetime.now() + timedelta(minutes=i),
            )
            detector.record_execution(execution)
        
        flaky_tests = detector.detect_flaky_tests()
        
        flaky_found = [t for t in flaky_tests if t.test_id == "test_flaky"]
        assert len(flaky_found) > 0
    
    def test_analyze_causes_time_dependency(self):
        detector = FlakyTestDetector()
        
        test_code = """
@Test
void testTime() {
    long time = System.currentTimeMillis();
    assertTrue(service.isExpired(time));
}
"""
        
        flaky = FlakyTest(
            test_id="test_001",
            test_class="TestClass",
            test_method="testTime",
            flaky_score=0.5,
            pass_count=5,
            fail_count=5,
            total_runs=10,
            detected_causes=[],
            first_detected=datetime.now(),
            last_flaky=datetime.now(),
            recent_executions=[],
            suggested_fixes=[],
        )
        
        causes = detector.analyze_causes(flaky, test_code)
        
        assert FlakyCause.TIME_DEPENDENCY in causes
    
    def test_analyze_causes_random(self):
        detector = FlakyTestDetector()
        
        test_code = """
@Test
void testRandom() {
    Random random = new Random();
    int value = random.nextInt(100);
    assertTrue(value < 100);
}
"""
        
        flaky = FlakyTest(
            test_id="test_002",
            test_class="TestClass",
            test_method="testRandom",
            flaky_score=0.3,
            pass_count=7,
            fail_count=3,
            total_runs=10,
            detected_causes=[],
            first_detected=datetime.now(),
            last_flaky=datetime.now(),
            recent_executions=[],
            suggested_fixes=[],
        )
        
        causes = detector.analyze_causes(flaky, test_code)
        
        assert FlakyCause.RANDOM_VALUE in causes
    
    def test_generate_fix_suggestions(self):
        detector = FlakyTestDetector()
        
        flaky = FlakyTest(
            test_id="test_003",
            test_class="TestClass",
            test_method="testFlaky",
            flaky_score=0.5,
            pass_count=5,
            fail_count=5,
            total_runs=10,
            detected_causes=[FlakyCause.TIME_DEPENDENCY],
            first_detected=datetime.now(),
            last_flaky=datetime.now(),
            recent_executions=[],
            suggested_fixes=[],
        )
        
        suggestions = detector.generate_fix_suggestions(
            flaky,
            "System.currentTimeMillis()",
            [FlakyCause.TIME_DEPENDENCY],
        )
        
        assert len(suggestions) > 0
        assert any("Clock" in s or "time" in s.lower() for s in suggestions)


class TestStabilityAnalyzer:
    
    def test_analyze_stability(self):
        analyzer = StabilityAnalyzer("/tmp")
        
        for i in range(10):
            execution = TestExecution(
                test_id="test_001",
                test_class="TestClass",
                test_method="testMethod",
                status=TestStatus.PASSED if i % 2 == 0 else TestStatus.FAILED,
                duration_ms=100.0,
                timestamp=datetime.now() + timedelta(minutes=i),
            )
            analyzer.detector.record_execution(execution)
        
        test_files = {"TestClass.testMethod": "test code"}
        report = analyzer.analyze_stability(test_files)
        
        assert report.total_tests > 0
        assert report.overall_stability_score >= 0
    
    def test_stability_report_to_dict(self):
        report = StabilityReport(
            project_path="/tmp",
            total_tests=10,
            stable_tests=8,
            flaky_tests=2,
            overall_stability_score=80.0,
            flaky_test_list=[],
            cause_distribution={"time_dependency": 1},
            recommendations=["Fix time-dependent tests"],
        )
        
        result = report.to_dict()
        
        assert result["total_tests"] == 10
        assert result["flaky_tests"] == 2


class TestTestQuarantine:
    
    def test_add_to_quarantine(self):
        quarantine = TestQuarantine()
        
        quarantine.add_to_quarantine(
            "test_001",
            "Flaky test detected",
            0.5,
        )
        
        assert quarantine.is_quarantined("test_001")
    
    def test_remove_from_quarantine(self):
        quarantine = TestQuarantine()
        
        quarantine.add_to_quarantine("test_002", "Flaky", 0.3)
        assert quarantine.is_quarantined("test_002")
        
        quarantine.remove_from_quarantine("test_002")
        assert not quarantine.is_quarantined("test_002")
    
    def test_record_attempt_passed(self):
        quarantine = TestQuarantine()
        
        quarantine.add_to_quarantine("test_003", "Flaky", 0.5)
        
        for _ in range(3):
            quarantine.record_attempt("test_003", passed=True)
        
        assert not quarantine.is_quarantined("test_003")
    
    def test_record_attempt_failed(self):
        quarantine = TestQuarantine()
        
        quarantine.add_to_quarantine("test_004", "Flaky", 0.5)
        quarantine.record_attempt("test_004", passed=False)
        
        assert quarantine.is_quarantined("test_004")
    
    def test_get_quarantine_report(self):
        quarantine = TestQuarantine()
        
        quarantine.add_to_quarantine("test_005", "Flaky 1", 0.3)
        quarantine.add_to_quarantine("test_006", "Flaky 2", 0.5)
        
        report = quarantine.get_quarantine_report()
        
        assert report["total_quarantined"] == 2
