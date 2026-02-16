"""可测试性分析器模块测试."""

import pytest
from ut_agent.tools.testability_analyzer import (
    TestabilityAnalyzer,
    TestabilityScore,
    TestabilityIssue,
    TestabilityIssueType,
    Severity,
    RefactoringAdvisor,
    RefactoringSuggestion,
)


class TestTestabilityIssue:
    
    def test_issue_creation(self):
        issue = TestabilityIssue(
            issue_type=TestabilityIssueType.SINGLETON,
            severity=Severity.HIGH,
            file_path="src/main/java/Service.java",
            line_number=10,
            code_snippet="private static Service instance;",
            description="Singleton pattern detected",
            refactoring_suggestion="Use dependency injection",
        )
        
        assert issue.issue_type == TestabilityIssueType.SINGLETON
        assert issue.severity == Severity.HIGH
        assert issue.auto_fixable == False
    
    def test_issue_to_dict(self):
        issue = TestabilityIssue(
            issue_type=TestabilityIssueType.STATIC_METHOD,
            severity=Severity.MEDIUM,
            file_path="test.java",
            line_number=5,
            code_snippet="public static void method()",
            description="Static method",
            refactoring_suggestion="Convert to instance method",
            auto_fixable=True,
        )
        
        result = issue.to_dict()
        
        assert result["issue_type"] == "static_method"
        assert result["severity"] == "medium"
        assert result["auto_fixable"] == True


class TestTestabilityScore:
    
    def test_score_creation(self):
        score = TestabilityScore(
            overall_score=75.0,
            dependency_score=80.0,
            coupling_score=70.0,
            complexity_score=75.0,
            design_score=70.0,
        )
        
        assert score.overall_score == 75.0
        assert len(score.issues) == 0
    
    def test_score_to_dict(self):
        score = TestabilityScore(
            overall_score=80.0,
            dependency_score=85.0,
            coupling_score=75.0,
            complexity_score=80.0,
            design_score=80.0,
            issues=[
                TestabilityIssue(
                    issue_type=TestabilityIssueType.HARD_CODED_DEPENDENCY,
                    severity=Severity.MEDIUM,
                    file_path="test.java",
                    line_number=10,
                    code_snippet="new Service()",
                    description="Hard-coded dependency",
                    refactoring_suggestion="Inject dependency",
                )
            ],
        )
        
        result = score.to_dict()
        
        assert result["overall_score"] == 80.0
        assert result["issue_count"] == 1


class TestTestabilityAnalyzer:
    
    def test_analyze_file_no_issues(self):
        analyzer = TestabilityAnalyzer("/tmp")
        
        simple_code = """
public class SimpleClass {
    private String name;
    
    public String getName() {
        return name;
    }
    
    public void setName(String name) {
        this.name = name;
    }
}
"""
        
        score = analyzer.analyze_file("SimpleClass.java", simple_code)
        
        assert score.overall_score >= 50
    
    def test_detect_singleton(self):
        analyzer = TestabilityAnalyzer("/tmp")
        
        singleton_code = """
public class SingletonService {
    private static SingletonService instance;
    
    private SingletonService() {}
    
    public static SingletonService getInstance() {
        if (instance == null) {
            instance = new SingletonService();
        }
        return instance;
    }
}
"""
        
        score = analyzer.analyze_file("SingletonService.java", singleton_code)
        
        singleton_issues = [
            i for i in score.issues
            if i.issue_type == TestabilityIssueType.SINGLETON
        ]
        
        assert len(singleton_issues) > 0
    
    def test_detect_static_methods(self):
        analyzer = TestabilityAnalyzer("/tmp")
        
        static_code = """
public class Utils {
    public static String format(String input) {
        return input.toUpperCase();
    }
    
    public static int calculate(int a, int b) {
        return a + b;
    }
}
"""
        
        score = analyzer.analyze_file("Utils.java", static_code)
        
        static_issues = [
            i for i in score.issues
            if i.issue_type == TestabilityIssueType.STATIC_METHOD
        ]
        
        assert len(static_issues) > 0
    
    def test_detect_time_dependency(self):
        analyzer = TestabilityAnalyzer("/tmp")
        
        time_code = """
public class TimeService {
    public boolean isExpired() {
        return System.currentTimeMillis() > deadline;
    }
    
    public String getCurrentDate() {
        return LocalDate.now().toString();
    }
}
"""
        
        score = analyzer.analyze_file("TimeService.java", time_code)
        
        time_issues = [
            i for i in score.issues
            if i.issue_type == TestabilityIssueType.TIME_DEPENDENCY
        ]
        
        assert len(time_issues) > 0
    
    def test_detect_hard_coded_dependency(self):
        analyzer = TestabilityAnalyzer("/tmp")
        
        dependency_code = """
public class OrderService {
    public void processOrder(Order order) {
        EmailSender sender = new EmailSender();
        sender.send(order.getEmail());
    }
}
"""
        
        score = analyzer.analyze_file("OrderService.java", dependency_code)
        
        dependency_issues = [
            i for i in score.issues
            if i.issue_type == TestabilityIssueType.HARD_CODED_DEPENDENCY
        ]
        
        assert len(dependency_issues) > 0
    
    def test_detect_long_method(self):
        analyzer = TestabilityAnalyzer("/tmp")
        
        lines = ["    int x = 0;"] * 60
        long_method_code = f"""
public class LongMethod {{
    public void longMethod() {{
{chr(10).join(lines)}
    }}
}}
"""
        
        score = analyzer.analyze_file("LongMethod.java", long_method_code)
        
        long_method_issues = [
            i for i in score.issues
            if i.issue_type == TestabilityIssueType.LONG_METHOD
        ]
        
        assert len(long_method_issues) > 0


class TestRefactoringAdvisor:
    
    def test_get_refactoring_suggestion_singleton(self):
        advisor = RefactoringAdvisor()
        
        issue = TestabilityIssue(
            issue_type=TestabilityIssueType.SINGLETON,
            severity=Severity.HIGH,
            file_path="test.java",
            line_number=10,
            code_snippet="private static Instance instance;",
            description="Singleton",
            refactoring_suggestion="Use DI",
        )
        
        suggestion = advisor.get_refactoring_suggestion(issue)
        
        assert suggestion.description != ""
        assert len(suggestion.benefits) > 0
    
    def test_get_refactoring_suggestion_time_dependency(self):
        advisor = RefactoringAdvisor()
        
        issue = TestabilityIssue(
            issue_type=TestabilityIssueType.TIME_DEPENDENCY,
            severity=Severity.MEDIUM,
            file_path="test.java",
            line_number=5,
            code_snippet="System.currentTimeMillis()",
            description="Time dependency",
            refactoring_suggestion="Inject Clock",
        )
        
        suggestion = advisor.get_refactoring_suggestion(issue)
        
        assert "Clock" in suggestion.refactored_code or "clock" in suggestion.description.lower()
    
    def test_generate_refactoring_report(self):
        advisor = RefactoringAdvisor()
        
        issues = [
            TestabilityIssue(
                issue_type=TestabilityIssueType.SINGLETON,
                severity=Severity.HIGH,
                file_path="a.java",
                line_number=1,
                code_snippet="singleton",
                description="Singleton",
                refactoring_suggestion="Use DI",
            ),
            TestabilityIssue(
                issue_type=TestabilityIssueType.STATIC_METHOD,
                severity=Severity.MEDIUM,
                file_path="b.java",
                line_number=2,
                code_snippet="static",
                description="Static",
                refactoring_suggestion="Instance method",
            ),
        ]
        
        report = advisor.generate_refactoring_report(issues)
        
        assert report["summary"]["total_issues"] == 2
        assert len(report["refactorings"]) == 2
        assert len(report["priority_order"]) == 2
