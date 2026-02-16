"""Flaky Test 检测与稳定性保障模块.

检测不稳定的测试，分析原因，并提供修复建议。
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict


class FlakyCause(Enum):
    RACE_CONDITION = "race_condition"
    TIME_DEPENDENCY = "time_dependency"
    RANDOM_VALUE = "random_value"
    NETWORK_DEPENDENCY = "network_dependency"
    FILE_SYSTEM = "file_system"
    DATABASE_STATE = "database_state"
    GLOBAL_STATE = "global_state"
    THREAD_UNSAFE = "thread_unsafe"
    RESOURCE_LEAK = "resource_leak"
    ORDER_DEPENDENCY = "order_dependency"
    ASYNC_OPERATION = "async_operation"
    EXTERNAL_SERVICE = "external_service"
    UNKNOWN = "unknown"


class TestStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestExecution:
    test_id: str
    test_class: str
    test_method: str
    status: TestStatus
    duration_ms: float
    timestamp: datetime
    error_message: Optional[str] = None
    error_stack_trace: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "test_class": self.test_class,
            "test_method": self.test_method,
            "status": self.status.value,
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp.isoformat(),
            "error_message": self.error_message,
            "error_stack_trace": self.error_stack_trace,
        }


@dataclass
class FlakyTest:
    test_id: str
    test_class: str
    test_method: str
    flaky_score: float
    pass_count: int
    fail_count: int
    total_runs: int
    detected_causes: List[FlakyCause]
    first_detected: datetime
    last_flaky: datetime
    recent_executions: List[TestExecution]
    suggested_fixes: List[str]
    
    @property
    def flaky_rate(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.fail_count / self.total_runs
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "test_class": self.test_class,
            "test_method": self.test_method,
            "flaky_score": round(self.flaky_score, 4),
            "flaky_rate": round(self.flaky_rate, 4),
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "total_runs": self.total_runs,
            "detected_causes": [c.value for c in self.detected_causes],
            "first_detected": self.first_detected.isoformat(),
            "last_flaky": self.last_flaky.isoformat(),
            "recent_executions": [e.to_dict() for e in self.recent_executions[-10:]],
            "suggested_fixes": self.suggested_fixes,
        }


@dataclass
class StabilityReport:
    project_path: str
    total_tests: int
    stable_tests: int
    flaky_tests: int
    overall_stability_score: float
    flaky_test_list: List[FlakyTest]
    cause_distribution: Dict[str, int]
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_path": self.project_path,
            "total_tests": self.total_tests,
            "stable_tests": self.stable_tests,
            "flaky_tests": self.flaky_tests,
            "overall_stability_score": round(self.overall_stability_score, 2),
            "flaky_test_list": [t.to_dict() for t in self.flaky_test_list],
            "cause_distribution": self.cause_distribution,
            "recommendations": self.recommendations,
        }


class FlakyTestDetector:
    
    FLAKY_THRESHOLD = 0.1
    MIN_RUNS_FOR_DETECTION = 5
    
    PATTERNS = {
        FlakyCause.TIME_DEPENDENCY: [
            re.compile(r'(?:System\.currentTimeMillis|System\.nanoTime|new Date\s*\(|LocalDate\.now|LocalDateTime\.now|Instant\.now)', re.IGNORECASE),
            re.compile(r'Thread\.sleep\s*\(', re.IGNORECASE),
            re.compile(r'(?:wait\s*\(|notify\s*\(|notifyAll\s*\()', re.IGNORECASE),
        ],
        FlakyCause.RANDOM_VALUE: [
            re.compile(r'(?:new Random\s*\(|Math\.random\s*\(|Random\.|UUID\.randomUUID)', re.IGNORECASE),
            re.compile(r'(?:shuffle|Collections\.shuffle)', re.IGNORECASE),
        ],
        FlakyCause.RACE_CONDITION: [
            re.compile(r'(?:synchronized\s*\(|volatile\s+|AtomicInteger|AtomicLong|AtomicBoolean|ConcurrentHashMap|CountDownLatch|CyclicBarrier|Semaphore)', re.IGNORECASE),
            re.compile(r'(?:\.start\s*\(\)|\.join\s*\(\)|ExecutorService|ThreadPool|CompletableFuture)', re.IGNORECASE),
        ],
        FlakyCause.NETWORK_DEPENDENCY: [
            re.compile(r'(?:HttpURLConnection|URL\s*\(|HttpClient|RestTemplate|WebClient|Socket)', re.IGNORECASE),
            re.compile(r'(?:@MockBean|@Mock|WireMock)', re.IGNORECASE),
        ],
        FlakyCause.FILE_SYSTEM: [
            re.compile(r'(?:new File\s*\(|FileInputStream|FileOutputStream|Files\.|Paths\.)', re.IGNORECASE),
            re.compile(r'(?:@TempDir|temporaryFolder)', re.IGNORECASE),
        ],
        FlakyCause.DATABASE_STATE: [
            re.compile(r'(?:@DataJpaTest|@DataMongoTest|@JdbcTest|@Sql)', re.IGNORECASE),
            re.compile(r'(?:@DirtiesContext|@Transactional)', re.IGNORECASE),
        ],
        FlakyCause.GLOBAL_STATE: [
            re.compile(r'(?:static\s+\w+\s+\w+\s*=(?!\s*final|=\s*null\s*;))', re.MULTILINE),
            re.compile(r'(?:System\.setProperty|System\.getProperty|Environment\.)', re.IGNORECASE),
        ],
        FlakyCause.ASYNC_OPERATION: [
            re.compile(r'(?:@Async|CompletableFuture|Mono|Flux|Publisher)', re.IGNORECASE),
            re.compile(r'(?:await\(\)|\.block\(\)|subscribe\()', re.IGNORECASE),
        ],
    }
    
    def __init__(self, history_file: Optional[str] = None):
        self.history_file = Path(history_file) if history_file else None
        self.execution_history: Dict[str, List[TestExecution]] = defaultdict(list)
        self._load_history()
    
    def _load_history(self) -> None:
        if self.history_file and self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                    for test_id, executions in data.items():
                        self.execution_history[test_id] = [
                            TestExecution(
                                test_id=e["test_id"],
                                test_class=e["test_class"],
                                test_method=e["test_method"],
                                status=TestStatus(e["status"]),
                                duration_ms=e["duration_ms"],
                                timestamp=datetime.fromisoformat(e["timestamp"]),
                                error_message=e.get("error_message"),
                                error_stack_trace=e.get("error_stack_trace"),
                            )
                            for e in executions
                        ]
            except Exception:
                pass
    
    def _save_history(self) -> None:
        if self.history_file:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                test_id: [e.to_dict() for e in executions]
                for test_id, executions in self.execution_history.items()
            }
            with open(self.history_file, 'w') as f:
                json.dump(data, f, indent=2)
    
    def record_execution(self, execution: TestExecution) -> None:
        self.execution_history[execution.test_id].append(execution)
        self._save_history()
    
    def detect_flaky_tests(self) -> List[FlakyTest]:
        flaky_tests = []
        
        for test_id, executions in self.execution_history.items():
            if len(executions) < self.MIN_RUNS_FOR_DETECTION:
                continue
            
            pass_count = sum(1 for e in executions if e.status == TestStatus.PASSED)
            fail_count = sum(1 for e in executions if e.status in (TestStatus.FAILED, TestStatus.ERROR))
            total_runs = len(executions)
            
            flaky_rate = fail_count / total_runs if total_runs > 0 else 0
            
            if flaky_rate > 0 and flaky_rate < 1:
                flaky_score = self._calculate_flaky_score(executions)
                
                if flaky_score >= self.FLAKY_THRESHOLD:
                    failed_executions = [e for e in executions if e.status in (TestStatus.FAILED, TestStatus.ERROR)]
                    
                    flaky_test = FlakyTest(
                        test_id=test_id,
                        test_class=executions[0].test_class,
                        test_method=executions[0].test_method,
                        flaky_score=flaky_score,
                        pass_count=pass_count,
                        fail_count=fail_count,
                        total_runs=total_runs,
                        detected_causes=[],
                        first_detected=failed_executions[0].timestamp if failed_executions else executions[0].timestamp,
                        last_flaky=failed_executions[-1].timestamp if failed_executions else executions[-1].timestamp,
                        recent_executions=executions[-10:],
                        suggested_fixes=[],
                    )
                    
                    flaky_tests.append(flaky_test)
        
        return flaky_tests
    
    def _calculate_flaky_score(self, executions: List[TestExecution]) -> float:
        if not executions:
            return 0.0
        
        statuses = [e.status for e in executions]
        
        transitions = 0
        for i in range(1, len(statuses)):
            if statuses[i] != statuses[i-1]:
                transitions += 1
        
        transition_score = transitions / (len(statuses) - 1) if len(statuses) > 1 else 0
        
        fail_count = sum(1 for s in statuses if s in (TestStatus.FAILED, TestStatus.ERROR))
        fail_rate = fail_count / len(statuses)
        
        variance_score = min(1.0, fail_rate * (1 - fail_rate) * 4)
        
        durations = [e.duration_ms for e in executions]
        if len(durations) > 1:
            avg_duration = sum(durations) / len(durations)
            variance = sum((d - avg_duration) ** 2 for d in durations) / len(durations)
            cv = (variance ** 0.5) / avg_duration if avg_duration > 0 else 0
            duration_score = min(1.0, cv / 2)
        else:
            duration_score = 0
        
        return (
            transition_score * 0.5 +
            variance_score * 0.3 +
            duration_score * 0.2
        )
    
    def analyze_causes(
        self,
        flaky_test: FlakyTest,
        test_code: str,
    ) -> List[FlakyCause]:
        causes = []
        
        for cause, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if pattern.search(test_code):
                    if cause not in causes:
                        causes.append(cause)
        
        error_messages = [
            e.error_message for e in flaky_test.recent_executions
            if e.error_message
        ]
        
        if error_messages:
            error_text = ' '.join(error_messages).lower()
            
            if any(word in error_text for word in ['timeout', 'timed out', 'deadline']):
                if FlakyCause.TIME_DEPENDENCY not in causes:
                    causes.append(FlakyCause.TIME_DEPENDENCY)
            
            if any(word in error_text for word in ['concurrent', 'race', 'deadlock', 'thread']):
                if FlakyCause.RACE_CONDITION not in causes:
                    causes.append(FlakyCause.RACE_CONDITION)
            
            if any(word in error_text for word in ['connection', 'socket', 'network', 'http']):
                if FlakyCause.NETWORK_DEPENDENCY not in causes:
                    causes.append(FlakyCause.NETWORK_DEPENDENCY)
        
        if not causes:
            causes.append(FlakyCause.UNKNOWN)
        
        return causes
    
    def generate_fix_suggestions(
        self,
        flaky_test: FlakyTest,
        test_code: str,
        causes: List[FlakyCause],
    ) -> List[str]:
        suggestions = []
        
        for cause in causes:
            if cause == FlakyCause.TIME_DEPENDENCY:
                suggestions.extend([
                    "Inject a Clock or TimeProvider for deterministic time handling",
                    "Use Awaitility for async assertions instead of Thread.sleep",
                    "Mock time-dependent operations in tests",
                ])
            
            elif cause == FlakyCause.RANDOM_VALUE:
                suggestions.extend([
                    "Use seeded Random for reproducible tests",
                    "Inject a RandomProvider that can be controlled in tests",
                    "Replace random values with fixed test data",
                ])
            
            elif cause == FlakyCause.RACE_CONDITION:
                suggestions.extend([
                    "Use proper synchronization mechanisms",
                    "Consider using CountDownLatch or Barrier for coordination",
                    "Add explicit waits with timeout instead of relying on timing",
                ])
            
            elif cause == FlakyCause.NETWORK_DEPENDENCY:
                suggestions.extend([
                    "Use WireMock or MockWebServer for HTTP mocking",
                    "Abstract network calls behind an interface",
                    "Use @MockBean for Spring applications",
                ])
            
            elif cause == FlakyCause.FILE_SYSTEM:
                suggestions.extend([
                    "Use @TempDir or in-memory file systems",
                    "Abstract file operations behind an interface",
                    "Clean up test files in @AfterEach",
                ])
            
            elif cause == FlakyCause.DATABASE_STATE:
                suggestions.extend([
                    "Use @Transactional with proper rollback",
                    "Clean database state between tests",
                    "Use dedicated test database or testcontainers",
                ])
            
            elif cause == FlakyCause.GLOBAL_STATE:
                suggestions.extend([
                    "Reset static state in @Before/@After methods",
                    "Avoid mutable static fields",
                    "Use instance fields instead of static fields",
                ])
            
            elif cause == FlakyCause.ASYNC_OPERATION:
                suggestions.extend([
                    "Use Awaitility for async assertions",
                    "Add proper timeout handling",
                    "Ensure async operations complete before assertions",
                ])
            
            elif cause == FlakyCause.ORDER_DEPENDENCY:
                suggestions.extend([
                    "Make tests independent of execution order",
                    "Reset shared state between tests",
                    "Use @TestMethodOrder with deterministic ordering if needed",
                ])
        
        return list(set(suggestions))


class StabilityAnalyzer:
    
    def __init__(self, project_path: str, history_file: Optional[str] = None):
        self.project_path = project_path
        self.detector = FlakyTestDetector(history_file)
    
    def analyze_stability(
        self,
        test_files: Dict[str, str],
    ) -> StabilityReport:
        flaky_tests = self.detector.detect_flaky_tests()
        
        for flaky in flaky_tests:
            test_key = f"{flaky.test_class}.{flaky.test_method}"
            if test_key in test_files:
                test_code = test_files[test_key]
                causes = self.detector.analyze_causes(flaky, test_code)
                flaky.detected_causes = causes
                flaky.suggested_fixes = self.detector.generate_fix_suggestions(
                    flaky, test_code, causes
                )
        
        total_tests = len(self.detector.execution_history)
        flaky_count = len(flaky_tests)
        stable_count = total_tests - flaky_count
        
        if total_tests > 0:
            stability_score = (stable_count / total_tests) * 100
        else:
            stability_score = 100.0
        
        cause_distribution: Dict[str, int] = defaultdict(int)
        for flaky in flaky_tests:
            for cause in flaky.detected_causes:
                cause_distribution[cause.value] += 1
        
        recommendations = self._generate_recommendations(flaky_tests, cause_distribution)
        
        return StabilityReport(
            project_path=self.project_path,
            total_tests=total_tests,
            stable_tests=stable_count,
            flaky_tests=flaky_count,
            overall_stability_score=stability_score,
            flaky_test_list=flaky_tests,
            cause_distribution=dict(cause_distribution),
            recommendations=recommendations,
        )
    
    def _generate_recommendations(
        self,
        flaky_tests: List[FlakyTest],
        cause_distribution: Dict[str, int],
    ) -> List[str]:
        recommendations = []
        
        if not flaky_tests:
            recommendations.append("No flaky tests detected. Continue monitoring test stability.")
            return recommendations
        
        sorted_causes = sorted(
            cause_distribution.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        
        if sorted_causes:
            top_cause = sorted_causes[0][0]
            
            cause_recommendations = {
                FlakyCause.TIME_DEPENDENCY.value: "Consider implementing time abstraction layer across the codebase",
                FlakyCause.RACE_CONDITION.value: "Review concurrent code for proper synchronization patterns",
                FlakyCause.RANDOM_VALUE.value: "Implement deterministic test data generation strategy",
                FlakyCause.NETWORK_DEPENDENCY.value: "Consider service virtualization for external dependencies",
                FlakyCause.DATABASE_STATE.value: "Implement proper test database isolation strategy",
                FlakyCause.GLOBAL_STATE.value: "Refactor to reduce reliance on global mutable state",
            }
            
            if top_cause in cause_recommendations:
                recommendations.append(cause_recommendations[top_cause])
        
        high_flaky = [t for t in flaky_tests if t.flaky_score > 0.5]
        if high_flaky:
            recommendations.append(
                f"Prioritize fixing {len(high_flaky)} highly unstable tests (flaky score > 0.5)"
            )
        
        recommendations.extend([
            "Set up continuous flaky test detection in CI pipeline",
            "Implement test quarantine mechanism for flaky tests",
            "Add retry mechanism for known flaky tests with proper annotation",
        ])
        
        return recommendations
    
    def run_stability_check(
        self,
        test_executor,
        test_ids: List[str],
        runs: int = 5,
    ) -> Dict[str, Any]:
        results = {
            "runs": [],
            "flaky_detected": [],
        }
        
        for run in range(runs):
            run_results = {}
            
            for test_id in test_ids:
                execution = test_executor.execute_test(test_id)
                self.detector.record_execution(execution)
                run_results[test_id] = execution.status.value
            
            results["runs"].append({
                "run_number": run + 1,
                "results": run_results,
            })
        
        flaky_tests = self.detector.detect_flaky_tests()
        results["flaky_detected"] = [t.to_dict() for t in flaky_tests]
        
        return results


class TestQuarantine:
    
    def __init__(self, quarantine_file: Optional[str] = None):
        self.quarantine_file = Path(quarantine_file) if quarantine_file else None
        self.quarantined_tests: Dict[str, Dict[str, Any]] = {}
        self._load_quarantine()
    
    def _load_quarantine(self) -> None:
        if self.quarantine_file and self.quarantine_file.exists():
            try:
                with open(self.quarantine_file, 'r') as f:
                    self.quarantined_tests = json.load(f)
            except Exception:
                pass
    
    def _save_quarantine(self) -> None:
        if self.quarantine_file:
            self.quarantine_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.quarantine_file, 'w') as f:
                json.dump(self.quarantined_tests, f, indent=2)
    
    def add_to_quarantine(
        self,
        test_id: str,
        reason: str,
        flaky_score: float,
    ) -> None:
        self.quarantined_tests[test_id] = {
            "reason": reason,
            "flaky_score": flaky_score,
            "quarantined_at": datetime.now().isoformat(),
            "attempts": 0,
            "last_attempt": None,
        }
        self._save_quarantine()
    
    def remove_from_quarantine(self, test_id: str) -> None:
        if test_id in self.quarantined_tests:
            del self.quarantined_tests[test_id]
            self._save_quarantine()
    
    def is_quarantined(self, test_id: str) -> bool:
        return test_id in self.quarantined_tests
    
    def record_attempt(self, test_id: str, passed: bool) -> None:
        if test_id in self.quarantined_tests:
            self.quarantined_tests[test_id]["attempts"] += 1
            self.quarantined_tests[test_id]["last_attempt"] = datetime.now().isoformat()
            
            if passed:
                self.quarantined_tests[test_id]["consecutive_passes"] = \
                    self.quarantined_tests[test_id].get("consecutive_passes", 0) + 1
                
                if self.quarantined_tests[test_id]["consecutive_passes"] >= 3:
                    self.remove_from_quarantine(test_id)
            else:
                self.quarantined_tests[test_id]["consecutive_passes"] = 0
            
            self._save_quarantine()
    
    def get_quarantine_report(self) -> Dict[str, Any]:
        return {
            "total_quarantined": len(self.quarantined_tests),
            "tests": self.quarantined_tests,
        }
