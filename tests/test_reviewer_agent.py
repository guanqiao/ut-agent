"""Reviewer Agent 单元测试."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ut_agent.agents.reviewer import (
    ReviewerAgent,
    AntiPatternDetector,
    CodeIssue,
    ReviewResult,
    IssueSeverity,
)
from ut_agent.agents.base import (
    AgentContext,
    AgentResult,
    AgentStatus,
)


class TestCodeIssue:
    """CodeIssue 测试."""

    def test_code_issue_creation(self):
        issue = CodeIssue(
            rule_id="test-rule",
            message="Test message",
            severity=IssueSeverity.HIGH,
            line=10,
        )
        assert issue.rule_id == "test-rule"
        assert issue.severity == IssueSeverity.HIGH
        assert issue.line == 10


class TestReviewResult:
    """ReviewResult 测试."""

    def test_review_result_creation(self):
        result = ReviewResult(
            score=0.85,
            issues=[],
            suggestions=["Improve coverage"],
        )
        assert result.score == 0.85
        assert result.needs_fix is False

    def test_review_result_needs_fix(self):
        result = ReviewResult(
            score=0.5,
            issues=[CodeIssue("rule", "error", IssueSeverity.HIGH)],
            suggestions=[],
            needs_fix=True,
        )
        assert result.needs_fix is True


class TestAntiPatternDetector:
    """AntiPatternDetector 测试."""

    @pytest.fixture
    def detector(self):
        return AntiPatternDetector()

    def test_detect_empty_test(self, detector):
        code = '''
@Test
public void testSomething() {}
'''
        issues = detector.detect(code)
        empty_issues = [i for i in issues if "empty_test" in i.rule_id]
        assert len(empty_issues) > 0

    def test_detect_sleep_in_test(self, detector):
        code = '''
@Test
public void testAsync() throws Exception {
    Thread.sleep(1000);
}
'''
        issues = detector.detect(code)
        sleep_issues = [i for i in issues if "sleep_in_test" in i.rule_id]
        assert len(sleep_issues) > 0

    def test_detect_system_out(self, detector):
        code = '''
@Test
public void testPrint() {
    System.out.println("debug");
}
'''
        issues = detector.detect(code)
        sysout_issues = [i for i in issues if "system_out" in i.rule_id]
        assert len(sysout_issues) > 0

    def test_detect_ignored_test(self, detector):
        code = '''
@Disabled
@Test
public void testSkipped() {}
'''
        issues = detector.detect(code)
        ignored_issues = [i for i in issues if "ignored_test" in i.rule_id]
        assert len(ignored_issues) > 0

    def test_detect_no_issues(self, detector):
        code = '''
@Test
public void testAddition() {
    int result = calculator.add(2, 3);
    assertEquals(5, result);
}
'''
        issues = detector.detect(code)
        critical_issues = [i for i in issues if i.severity == IssueSeverity.CRITICAL]
        assert len(critical_issues) == 0


class TestReviewerAgent:
    """ReviewerAgent 测试."""

    @pytest.fixture
    def agent(self):
        return ReviewerAgent()

    def test_agent_initialization(self, agent):
        assert agent.name == "reviewer"
        assert agent.status == AgentStatus.IDLE

    def test_agent_capabilities(self, agent):
        capabilities = agent.get_capabilities()
        assert len(capabilities) > 0

    @pytest.mark.asyncio
    async def test_execute_without_generated_test(self, agent):
        context = AgentContext(
            task_id="test-task",
            source_file="/test/file.java",
        )
        result = await agent.execute(context)
        assert result.success is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_execute_with_generated_test(self, agent):
        context = AgentContext(
            task_id="test-task",
            source_file="/test/UserService.java",
            generated_test={
                "test_code": "@Test void testMethod() { assertEquals(1, 1); }",
                "language": "java",
            },
            file_analysis={
                "language": "java",
                "class_name": "UserService",
            },
        )

        result = await agent.execute(context)

        assert result.agent_name == "reviewer"

    def test_to_dict(self, agent):
        data = agent.to_dict()
        assert data["name"] == "reviewer"
        assert "capabilities" in data
        assert data["status"] == "idle"
