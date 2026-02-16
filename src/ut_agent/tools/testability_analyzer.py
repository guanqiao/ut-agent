"""可测试性分析器.

分析代码的可测试性，检测反模式，并提供重构建议。
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from pathlib import Path


class TestabilityIssueType(Enum):
    HARD_CODED_DEPENDENCY = "hard_coded_dependency"
    GLOBAL_STATE = "global_state"
    SINGLETON = "singleton"
    STATIC_METHOD = "static_method"
    TIGHT_COUPLING = "tight_coupling"
    LAW_OF_DEMETER = "law_of_demeter"
    CONSTRUCTOR_OVER_INJECTION = "constructor_over_injection"
    PRIVATE_METHOD_ACCESS = "private_method_access"
    FILE_SYSTEM_DEPENDENCY = "file_system_dependency"
    NETWORK_DEPENDENCY = "network_dependency"
    DATABASE_DEPENDENCY = "database_dependency"
    TIME_DEPENDENCY = "time_dependency"
    RANDOM_DEPENDENCY = "random_dependency"
    IMMUTABLE_VIOLATION = "immutable_violation"
    LARGE_CLASS = "large_class"
    LONG_METHOD = "long_method"
    DEEP_INHERITANCE = "deep_inheritance"


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class TestabilityIssue:
    issue_type: TestabilityIssueType
    severity: Severity
    file_path: str
    line_number: int
    code_snippet: str
    description: str
    refactoring_suggestion: str
    auto_fixable: bool = False
    fix_code: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_type": self.issue_type.value,
            "severity": self.severity.value,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "code_snippet": self.code_snippet,
            "description": self.description,
            "refactoring_suggestion": self.refactoring_suggestion,
            "auto_fixable": self.auto_fixable,
            "fix_code": self.fix_code,
        }


@dataclass
class TestabilityScore:
    overall_score: float
    dependency_score: float
    coupling_score: float
    complexity_score: float
    design_score: float
    issues: List[TestabilityIssue] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 2),
            "dependency_score": round(self.dependency_score, 2),
            "coupling_score": round(self.coupling_score, 2),
            "complexity_score": round(self.complexity_score, 2),
            "design_score": round(self.design_score, 2),
            "issues": [i.to_dict() for i in self.issues],
            "issue_count": len(self.issues),
            "critical_count": sum(1 for i in self.issues if i.severity == Severity.CRITICAL),
            "high_count": sum(1 for i in self.issues if i.severity == Severity.HIGH),
        }


@dataclass
class RefactoringSuggestion:
    original_code: str
    refactored_code: str
    description: str
    benefits: List[str]
    applies_to: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_code": self.original_code,
            "refactored_code": self.refactored_code,
            "description": self.description,
            "benefits": self.benefits,
            "applies_to": self.applies_to,
        }


class TestabilityAnalyzer:
    
    SINGLETON_PATTERN = re.compile(
        r'(?:private\s+static\s+\w+\s+instance\s*;|'
        r'public\s+static\s+\w+\s+getInstance\s*\(|'
        r'private\s+\w+\s*\(\s*\)\s*\{[^}]*\})',
        re.MULTILINE
    )
    
    STATIC_METHOD_PATTERN = re.compile(
        r'public\s+static\s+(?!void\s+main\b)(\w+(?:<[^>]+>)?)\s+(\w+)\s*\(',
        re.MULTILINE
    )
    
    NEW_KEYWORD_PATTERN = re.compile(
        r'new\s+(\w+)\s*\(',
        re.MULTILINE
    )
    
    GLOBAL_STATE_PATTERN = re.compile(
        r'(?:public\s+static\s+(?!final\s+\w+\s+\w+\s*=)[^;]*;|'
        r'static\s+\{[^}]*\}|'
        r'private\s+static\s+(?!final)[^;]*;)'
    )
    
    FILE_SYSTEM_PATTERN = re.compile(
        r'(?:new\s+File\s*\(|FileInputStream|FileOutputStream|'
        r'Files\.|Paths\.|FileReader|FileWriter|RandomAccessFile)',
        re.MULTILINE
    )
    
    NETWORK_PATTERN = re.compile(
        r'(?:HttpURLConnection|URL\s*\(|HttpClient|RestTemplate|'
        r'WebClient|Socket\s*\(|ServerSocket)',
        re.MULTILINE
    )
    
    DATABASE_PATTERN = re.compile(
        r'(?:DataSource|Connection\s+|Statement\s+|ResultSet|'
        r'@Repository|@Entity|JdbcTemplate|EntityManager)',
        re.MULTILINE
    )
    
    TIME_DEPENDENCY_PATTERN = re.compile(
        r'(?:System\.currentTimeMillis\(\)|System\.nanoTime\(\)|'
        r'new\s+Date\s*\(|LocalDate\.now\(\)|LocalDateTime\.now\(\)|'
        r'Instant\.now\(\)|Thread\.sleep\()',
        re.MULTILINE
    )
    
    RANDOM_PATTERN = re.compile(
        r'(?:new\s+Random\s*\(|Math\.random\(\)|Random\.|'
        r'SecureRandom|UUID\.randomUUID\(\))',
        re.MULTILINE
    )
    
    PRIVATE_METHOD_PATTERN = re.compile(
        r'private\s+(?:static\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*\(',
        re.MULTILINE
    )
    
    LONG_METHOD_THRESHOLD = 50
    LARGE_CLASS_THRESHOLD = 500
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.issues: List[TestabilityIssue] = []
    
    def analyze_file(self, file_path: str, source_code: str) -> TestabilityScore:
        self.issues = []
        
        self._detect_singletons(file_path, source_code)
        self._detect_static_methods(file_path, source_code)
        self._detect_hard_coded_dependencies(file_path, source_code)
        self._detect_global_state(file_path, source_code)
        self._detect_file_system_dependencies(file_path, source_code)
        self._detect_network_dependencies(file_path, source_code)
        self._detect_database_dependencies(file_path, source_code)
        self._detect_time_dependencies(file_path, source_code)
        self._detect_random_dependencies(file_path, source_code)
        self._detect_long_methods(file_path, source_code)
        self._detect_large_classes(file_path, source_code)
        self._detect_constructor_injection_issues(file_path, source_code)
        
        return self._calculate_score()
    
    def _detect_singletons(self, file_path: str, source_code: str) -> None:
        matches = self.SINGLETON_PATTERN.findall(source_code)
        
        if matches:
            line_num = source_code[:source_code.find(matches[0])].count('\n') + 1
            
            self.issues.append(TestabilityIssue(
                issue_type=TestabilityIssueType.SINGLETON,
                severity=Severity.HIGH,
                file_path=file_path,
                line_number=line_num,
                code_snippet=matches[0][:100],
                description="Singleton pattern detected. Singletons make testing difficult as they maintain global state.",
                refactoring_suggestion="Consider using dependency injection instead of singleton pattern. "
                                     "Make the class a regular service and inject it where needed.",
                auto_fixable=False,
            ))
    
    def _detect_static_methods(self, file_path: str, source_code: str) -> None:
        for match in self.STATIC_METHOD_PATTERN.finditer(source_code):
            method_name = match.group(2)
            
            if method_name.startswith(('get', 'set', 'is', 'has')):
                continue
            
            line_num = source_code[:match.start()].count('\n') + 1
            
            self.issues.append(TestabilityIssue(
                issue_type=TestabilityIssueType.STATIC_METHOD,
                severity=Severity.MEDIUM,
                file_path=file_path,
                line_number=line_num,
                code_snippet=match.group(0),
                description=f"Static method '{method_name}' detected. Static methods are difficult to mock.",
                refactoring_suggestion="Convert to instance method and use dependency injection, "
                                     "or extract to a separate utility class that can be mocked.",
                auto_fixable=False,
            ))
    
    def _detect_hard_coded_dependencies(self, file_path: str, source_code: str) -> None:
        new_keywords = self.NEW_KEYWORD_PATTERN.findall(source_code)
        
        dependency_types = set()
        for type_name in new_keywords:
            if type_name not in ('String', 'Integer', 'Long', 'Double', 'Float',
                                'Boolean', 'Character', 'Byte', 'Short',
                                'ArrayList', 'HashMap', 'HashSet', 'LinkedList',
                                'StringBuilder', 'Object', 'Optional'):
                dependency_types.add(type_name)
        
        for dep_type in dependency_types:
            pattern = re.compile(rf'new\s+{re.escape(dep_type)}\s*\(')
            match = pattern.search(source_code)
            
            if match:
                line_num = source_code[:match.start()].count('\n') + 1
                
                self.issues.append(TestabilityIssue(
                    issue_type=TestabilityIssueType.HARD_CODED_DEPENDENCY,
                    severity=Severity.HIGH,
                    file_path=file_path,
                    line_number=line_num,
                    code_snippet=match.group(0),
                    description=f"Hard-coded dependency on '{dep_type}'. This makes unit testing difficult.",
                    refactoring_suggestion=f"Inject {dep_type} through constructor or setter. "
                                         f"Use interface/abstraction for better testability.",
                    auto_fixable=False,
                ))
    
    def _detect_global_state(self, file_path: str, source_code: str) -> None:
        for match in self.GLOBAL_STATE_PATTERN.finditer(source_code):
            line_num = source_code[:match.start()].count('\n') + 1
            
            self.issues.append(TestabilityIssue(
                issue_type=TestabilityIssueType.GLOBAL_STATE,
                severity=Severity.HIGH,
                file_path=file_path,
                line_number=line_num,
                code_snippet=match.group(0)[:100],
                description="Global mutable state detected. This can cause test interference and make tests unreliable.",
                refactoring_suggestion="Convert static mutable fields to instance fields. "
                                     "Use dependency injection to manage state.",
                auto_fixable=False,
            ))
    
    def _detect_file_system_dependencies(self, file_path: str, source_code: str) -> None:
        for match in self.FILE_SYSTEM_PATTERN.finditer(source_code):
            line_num = source_code[:match.start()].count('\n') + 1
            
            self.issues.append(TestabilityIssue(
                issue_type=TestabilityIssueType.FILE_SYSTEM_DEPENDENCY,
                severity=Severity.MEDIUM,
                file_path=file_path,
                line_number=line_num,
                code_snippet=match.group(0),
                description="File system dependency detected. File operations are slow and hard to test.",
                refactoring_suggestion="Use an abstraction layer for file operations. "
                                     "Consider using in-memory file systems for tests.",
                auto_fixable=False,
            ))
    
    def _detect_network_dependencies(self, file_path: str, source_code: str) -> None:
        for match in self.NETWORK_PATTERN.finditer(source_code):
            line_num = source_code[:match.start()].count('\n') + 1
            
            self.issues.append(TestabilityIssue(
                issue_type=TestabilityIssueType.NETWORK_DEPENDENCY,
                severity=Severity.HIGH,
                file_path=file_path,
                line_number=line_num,
                code_snippet=match.group(0),
                description="Network dependency detected. Network calls are slow and unreliable in tests.",
                refactoring_suggestion="Use HTTP client abstraction that can be mocked. "
                                     "Consider using WireMock or similar for integration tests.",
                auto_fixable=False,
            ))
    
    def _detect_database_dependencies(self, file_path: str, source_code: str) -> None:
        for match in self.DATABASE_PATTERN.finditer(source_code):
            line_num = source_code[:match.start()].count('\n') + 1
            
            self.issues.append(TestabilityIssue(
                issue_type=TestabilityIssueType.DATABASE_DEPENDENCY,
                severity=Severity.MEDIUM,
                file_path=file_path,
                line_number=line_num,
                code_snippet=match.group(0),
                description="Database dependency detected. Database operations require test data setup.",
                refactoring_suggestion="Use repository pattern with interface. "
                                     "Consider using in-memory database or testcontainers for tests.",
                auto_fixable=False,
            ))
    
    def _detect_time_dependencies(self, file_path: str, source_code: str) -> None:
        for match in self.TIME_DEPENDENCY_PATTERN.finditer(source_code):
            line_num = source_code[:match.start()].count('\n') + 1
            
            self.issues.append(TestabilityIssue(
                issue_type=TestabilityIssueType.TIME_DEPENDENCY,
                severity=Severity.MEDIUM,
                file_path=file_path,
                line_number=line_num,
                code_snippet=match.group(0),
                description="Time dependency detected. Time-based code is non-deterministic in tests.",
                refactoring_suggestion="Inject a Clock or TimeProvider interface. "
                                     "This allows controlling time in tests.",
                auto_fixable=True,
                fix_code=self._generate_time_fix(match.group(0)),
            ))
    
    def _detect_random_dependencies(self, file_path: str, source_code: str) -> None:
        for match in self.RANDOM_PATTERN.finditer(source_code):
            line_num = source_code[:match.start()].count('\n') + 1
            
            self.issues.append(TestabilityIssue(
                issue_type=TestabilityIssueType.RANDOM_DEPENDENCY,
                severity=Severity.MEDIUM,
                file_path=file_path,
                line_number=line_num,
                code_snippet=match.group(0),
                description="Random dependency detected. Random values make tests non-deterministic.",
                refactoring_suggestion="Inject a RandomProvider or use seeded random for tests. "
                                     "Consider deterministic test data generation.",
                auto_fixable=False,
            ))
    
    def _detect_long_methods(self, file_path: str, source_code: str) -> None:
        method_pattern = re.compile(
            r'(?:public|private|protected)?\s*'
            r'(?:static\s+)?'
            r'(\w+(?:<[^>]+>)?)\s+(\w+)\s*\([^)]*\)\s*\{',
            re.MULTILINE
        )
        
        for match in method_pattern.finditer(source_code):
            method_start = match.end() - 1
            brace_count = 1
            method_end = method_start + 1
            
            for i, char in enumerate(source_code[method_start + 1:], method_start + 1):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        method_end = i + 1
                        break
            
            method_lines = source_code[method_start:method_end].count('\n')
            
            if method_lines > self.LONG_METHOD_THRESHOLD:
                line_num = source_code[:match.start()].count('\n') + 1
                
                self.issues.append(TestabilityIssue(
                    issue_type=TestabilityIssueType.LONG_METHOD,
                    severity=Severity.MEDIUM,
                    file_path=file_path,
                    line_number=line_num,
                    code_snippet=f"{match.group(0)}... ({method_lines} lines)",
                    description=f"Long method detected ({method_lines} lines). Long methods are hard to test comprehensively.",
                    refactoring_suggestion="Extract smaller, focused methods. "
                                         "Each method should do one thing and be easily testable.",
                    auto_fixable=False,
                ))
    
    def _detect_large_classes(self, file_path: str, source_code: str) -> None:
        class_pattern = re.compile(r'class\s+(\w+)', re.MULTILINE)
        
        for match in class_pattern.finditer(source_code):
            class_name = match.group(1)
            class_start = match.start()
            
            brace_count = 0
            class_end = class_start
            
            for i, char in enumerate(source_code[class_start:], class_start):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        class_end = i + 1
                        break
            
            class_lines = source_code[class_start:class_end].count('\n')
            
            if class_lines > self.LARGE_CLASS_THRESHOLD:
                line_num = source_code[:match.start()].count('\n') + 1
                
                self.issues.append(TestabilityIssue(
                    issue_type=TestabilityIssueType.LARGE_CLASS,
                    severity=Severity.LOW,
                    file_path=file_path,
                    line_number=line_num,
                    code_snippet=f"class {class_name}... ({class_lines} lines)",
                    description=f"Large class detected ({class_lines} lines). Large classes violate Single Responsibility Principle.",
                    refactoring_suggestion="Split into smaller, focused classes. "
                                         "Identify distinct responsibilities and extract them.",
                    auto_fixable=False,
                ))
    
    def _detect_constructor_injection_issues(self, file_path: str, source_code: str) -> None:
        constructor_pattern = re.compile(
            r'(?:public|protected)\s+\w+\s*\(([^)]+)\)\s*\{',
            re.MULTILINE
        )
        
        for match in constructor_pattern.finditer(source_code):
            params = match.group(1)
            param_count = len([p.strip() for p in params.split(',') if p.strip()])
            
            if param_count > 5:
                line_num = source_code[:match.start()].count('\n') + 1
                
                self.issues.append(TestabilityIssue(
                    issue_type=TestabilityIssueType.CONSTRUCTOR_OVER_INJECTION,
                    severity=Severity.MEDIUM,
                    file_path=file_path,
                    line_number=line_num,
                    code_snippet=match.group(0)[:100],
                    description=f"Constructor with {param_count} parameters detected. "
                               f"This suggests the class has too many responsibilities.",
                    refactoring_suggestion="Consider using Facade or Service pattern to reduce dependencies. "
                                         "Group related dependencies into a Parameter Object.",
                    auto_fixable=False,
                ))
    
    def _generate_time_fix(self, original_code: str) -> str:
        if 'System.currentTimeMillis' in original_code:
            return 'clock.millis()'
        elif 'System.nanoTime' in original_code:
            return 'clock.getZone().getRules().getOffset(Instant.now(clock)).getTotalSeconds() * 1_000_000_000L'
        elif 'new Date' in original_code:
            return 'Date.from(clock.instant())'
        elif 'LocalDate.now' in original_code:
            return 'LocalDate.now(clock)'
        elif 'LocalDateTime.now' in original_code:
            return 'LocalDateTime.now(clock)'
        elif 'Instant.now' in original_code:
            return 'Instant.now(clock)'
        return original_code
    
    def _calculate_score(self) -> TestabilityScore:
        if not self.issues:
            return TestabilityScore(
                overall_score=100.0,
                dependency_score=100.0,
                coupling_score=100.0,
                complexity_score=100.0,
                design_score=100.0,
                issues=[],
            )
        
        severity_weights = {
            Severity.CRITICAL: 20,
            Severity.HIGH: 10,
            Severity.MEDIUM: 5,
            Severity.LOW: 2,
            Severity.INFO: 0,
        }
        
        dependency_types = {
            TestabilityIssueType.HARD_CODED_DEPENDENCY,
            TestabilityIssueType.SINGLETON,
            TestabilityIssueType.STATIC_METHOD,
            TestabilityIssueType.FILE_SYSTEM_DEPENDENCY,
            TestabilityIssueType.NETWORK_DEPENDENCY,
            TestabilityIssueType.DATABASE_DEPENDENCY,
            TestabilityIssueType.TIME_DEPENDENCY,
            TestabilityIssueType.RANDOM_DEPENDENCY,
        }
        
        coupling_types = {
            TestabilityIssueType.TIGHT_COUPLING,
            TestabilityIssueType.LAW_OF_DEMETER,
        }
        
        complexity_types = {
            TestabilityIssueType.LONG_METHOD,
            TestabilityIssueType.LARGE_CLASS,
            TestabilityIssueType.CONSTRUCTOR_OVER_INJECTION,
        }
        
        design_types = {
            TestabilityIssueType.GLOBAL_STATE,
            TestabilityIssueType.DEEP_INHERITANCE,
            TestabilityIssueType.IMMUTABLE_VIOLATION,
        }
        
        def calculate_category_score(issue_types: Set[TestabilityIssueType]) -> float:
            category_issues = [i for i in self.issues if i.issue_type in issue_types]
            penalty = sum(severity_weights[i.severity] for i in category_issues)
            return max(0, 100 - penalty)
        
        dependency_score = calculate_category_score(dependency_types)
        coupling_score = calculate_category_score(coupling_types)
        complexity_score = calculate_category_score(complexity_types)
        design_score = calculate_category_score(design_types)
        
        overall_score = (
            dependency_score * 0.35 +
            coupling_score * 0.20 +
            complexity_score * 0.25 +
            design_score * 0.20
        )
        
        return TestabilityScore(
            overall_score=overall_score,
            dependency_score=dependency_score,
            coupling_score=coupling_score,
            complexity_score=complexity_score,
            design_score=design_score,
            issues=self.issues,
        )


class RefactoringAdvisor:
    
    REFACTORING_PATTERNS = {
        TestabilityIssueType.SINGLETON: {
            "name": "Replace Singleton with Dependency Injection",
            "steps": [
                "1. Remove private static instance field",
                "2. Remove private constructor",
                "3. Remove getInstance() method",
                "4. Make class a regular Spring bean or injectable service",
                "5. Update all callers to receive the dependency via injection",
            ],
            "example_before": """public class DatabaseManager {
    private static DatabaseManager instance;
    
    private DatabaseManager() {}
    
    public static DatabaseManager getInstance() {
        if (instance == null) {
            instance = new DatabaseManager();
        }
        return instance;
    }
}""",
            "example_after": """@Service
public class DatabaseManager {
    // Regular service class with dependency injection
    private final DataSource dataSource;
    
    public DatabaseManager(DataSource dataSource) {
        this.dataSource = dataSource;
    }
}""",
        },
        
        TestabilityIssueType.STATIC_METHOD: {
            "name": "Convert Static Method to Instance Method",
            "steps": [
                "1. Remove static modifier from method",
                "2. If method uses static fields, convert them to instance fields",
                "3. Create interface for the class if needed",
                "4. Inject the class where the method is called",
            ],
            "example_before": """public class DateUtils {
    public static String formatDate(Date date) {
        return new SimpleDateFormat("yyyy-MM-dd").format(date);
    }
}""",
            "example_after": """@Service
public class DateFormatter {
    public String formatDate(Date date) {
        return new SimpleDateFormat("yyyy-MM-dd").format(date);
    }
}

// Usage:
@Service
public class ReportService {
    private final DateFormatter dateFormatter;
    
    public ReportService(DateFormatter dateFormatter) {
        this.dateFormatter = dateFormatter;
    }
}""",
        },
        
        TestabilityIssueType.HARD_CODED_DEPENDENCY: {
            "name": "Extract and Inject Dependency",
            "steps": [
                "1. Create interface for the dependency if it doesn't exist",
                "2. Add dependency as a constructor parameter",
                "3. Store dependency in instance field",
                "4. Use the field instead of creating new instance",
            ],
            "example_before": """public class OrderService {
    public void processOrder(Order order) {
        EmailSender sender = new EmailSender();
        sender.send(order.getEmail(), "Order confirmed");
    }
}""",
            "example_after": """public interface NotificationService {
    void send(String to, String message);
}

@Service
public class OrderService {
    private final NotificationService notificationService;
    
    public OrderService(NotificationService notificationService) {
        this.notificationService = notificationService;
    }
    
    public void processOrder(Order order) {
        notificationService.send(order.getEmail(), "Order confirmed");
    }
}""",
        },
        
        TestabilityIssueType.TIME_DEPENDENCY: {
            "name": "Inject Clock for Time Operations",
            "steps": [
                "1. Add Clock parameter to constructor",
                "2. Replace direct time calls with clock methods",
                "3. In tests, use fixed Clock for deterministic behavior",
            ],
            "example_before": """public class TimeService {
    public boolean isExpired(Instant expirationTime) {
        return Instant.now().isAfter(expirationTime);
    }
}""",
            "example_after": """@Service
public class TimeService {
    private final Clock clock;
    
    public TimeService(Clock clock) {
        this.clock = clock;
    }
    
    public boolean isExpired(Instant expirationTime) {
        return Instant.now(clock).isAfter(expirationTime);
    }
}

// Test:
@Test
void testExpiration() {
    Clock fixedClock = Clock.fixed(Instant.parse("2024-01-01T00:00:00Z"), ZoneOffset.UTC);
    TimeService service = new TimeService(fixedClock);
    // Now time is deterministic
}""",
        },
    }
    
    def get_refactoring_suggestion(
        self,
        issue: TestabilityIssue,
    ) -> RefactoringSuggestion:
        pattern = self.REFACTORING_PATTERNS.get(issue.issue_type)
        
        if pattern:
            return RefactoringSuggestion(
                original_code=pattern.get("example_before", ""),
                refactored_code=pattern.get("example_after", ""),
                description=pattern.get("name", ""),
                benefits=self._get_benefits(issue.issue_type),
                applies_to=pattern.get("steps", []),
            )
        
        return RefactoringSuggestion(
            original_code=issue.code_snippet,
            refactored_code="// Refactoring needed",
            description=issue.refactoring_suggestion,
            benefits=[],
            applies_to=[],
        )
    
    def _get_benefits(self, issue_type: TestabilityIssueType) -> List[str]:
        benefits_map = {
            TestabilityIssueType.SINGLETON: [
                "Enables easy mocking in tests",
                "Supports multiple instances when needed",
                "Follows dependency injection principle",
                "Improves code flexibility",
            ],
            TestabilityIssueType.STATIC_METHOD: [
                "Can be mocked for testing",
                "Supports polymorphism",
                "Better test isolation",
                "Easier to extend and override",
            ],
            TestabilityIssueType.HARD_CODED_DEPENDENCY: [
                "Enables dependency injection",
                "Supports mock implementations",
                "Improves code testability",
                "Follows SOLID principles",
            ],
            TestabilityIssueType.TIME_DEPENDENCY: [
                "Deterministic time in tests",
                "Easy to test time-based logic",
                "Supports time travel in tests",
                "Better control over test scenarios",
            ],
        }
        
        return benefits_map.get(issue_type, [
            "Improved testability",
            "Better code maintainability",
        ])
    
    def generate_refactoring_report(
        self,
        issues: List[TestabilityIssue],
    ) -> Dict[str, Any]:
        report = {
            "summary": {
                "total_issues": len(issues),
                "by_severity": {},
                "by_type": {},
            },
            "refactorings": [],
            "priority_order": [],
        }
        
        for severity in Severity:
            count = sum(1 for i in issues if i.severity == severity)
            if count > 0:
                report["summary"]["by_severity"][severity.value] = count
        
        for issue_type in TestabilityIssueType:
            count = sum(1 for i in issues if i.issue_type == issue_type)
            if count > 0:
                report["summary"]["by_type"][issue_type.value] = count
        
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
            Severity.INFO: 4,
        }
        
        sorted_issues = sorted(
            issues,
            key=lambda i: severity_order.get(i.severity, 5),
        )
        
        for issue in sorted_issues:
            suggestion = self.get_refactoring_suggestion(issue)
            report["refactorings"].append({
                "issue": issue.to_dict(),
                "suggestion": suggestion.to_dict(),
            })
            report["priority_order"].append({
                "file": issue.file_path,
                "line": issue.line_number,
                "type": issue.issue_type.value,
                "severity": issue.severity.value,
            })
        
        return report
