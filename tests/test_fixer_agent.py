"""Fixer Agent 单元测试."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ut_agent.agents.fixer import (
    FixerAgent,
    ErrorDiagnoser,
    AutoFixer,
    FixType,
    FixAction,
)
from ut_agent.agents.base import (
    AgentContext,
    AgentResult,
    AgentStatus,
)


class TestFixType:
    """FixType 测试."""

    def test_fix_types(self):
        assert FixType.COMPILE_ERROR.value == "compile_error"
        assert FixType.RUNTIME_ERROR.value == "runtime_error"
        assert FixType.ASSERTION_ERROR.value == "assertion_error"
        assert FixType.IMPORT_ERROR.value == "import_error"


class TestFixAction:
    """FixAction 测试."""

    def test_fix_action_creation(self):
        action = FixAction(
            fix_type=FixType.IMPORT_ERROR,
            description="Fix missing import",
            original_code="List list;",
            fixed_code="import java.util.List;\nList list;",
            line_start=1,
            line_end=1,
        )
        assert action.fix_type == FixType.IMPORT_ERROR
        assert "import" in action.fixed_code


class TestErrorDiagnoser:
    """ErrorDiagnoser 测试."""

    @pytest.fixture
    def diagnoser(self):
        return ErrorDiagnoser()

    def test_diagnose_import_error(self, diagnoser):
        error_message = "cannot find symbol: class List"
        test_code = "List<String> list = new ArrayList<>();"
        diagnoses = diagnoser.diagnose(error_message, test_code)
        assert len(diagnoses) > 0
        assert diagnoses[0]["fix_type"] == FixType.IMPORT_ERROR

    def test_diagnose_type_error(self, diagnoser):
        error_message = "incompatible types: String cannot be converted to int"
        test_code = "int x = \"string\";"
        diagnoses = diagnoser.diagnose(error_message, test_code)
        assert len(diagnoses) > 0
        assert diagnoses[0]["fix_type"] == FixType.COMPILE_ERROR

    def test_diagnose_null_pointer(self, diagnoser):
        error_message = "NullPointerException at line 10"
        test_code = "Object obj = null; obj.toString();"
        diagnoses = diagnoser.diagnose(error_message, test_code)
        assert len(diagnoses) > 0
        assert diagnoses[0]["fix_type"] == FixType.RUNTIME_ERROR

    def test_diagnose_assertion_error(self, diagnoser):
        error_message = "AssertionError: Expected 5 but was 3"
        test_code = "assertEquals(5, result);"
        diagnoses = diagnoser.diagnose(error_message, test_code)
        assert len(diagnoses) > 0
        assert diagnoses[0]["fix_type"] == FixType.ASSERTION_ERROR

    def test_diagnose_timeout(self, diagnoser):
        error_message = "test timed out after 30 seconds"
        test_code = "@Test void test() { while(true); }"
        diagnoses = diagnoser.diagnose(error_message, test_code)
        assert len(diagnoses) > 0
        assert diagnoses[0]["fix_type"] == FixType.PERFORMANCE

    def test_diagnose_no_error(self, diagnoser):
        error_message = ""
        test_code = "assertEquals(1, 1);"
        diagnoses = diagnoser.diagnose(error_message, test_code)
        assert len(diagnoses) == 0


class TestAutoFixer:
    """AutoFixer 测试."""

    @pytest.fixture
    def fixer(self):
        return AutoFixer()

    def test_fix_missing_import_java(self, fixer):
        test_code = '''
public class Test {
    @Test
    public void testMethod() {
        assertEquals(1, 1);
    }
}
'''
        fixed_code = fixer.fix_imports(test_code, "java")
        assert "import" in fixed_code

    def test_fix_missing_import_typescript(self, fixer):
        test_code = '''
describe("test", () => {
    it("should work", () => {
        expect(1).toBe(1);
    });
});
'''
        fixed_code = fixer.fix_imports(test_code, "typescript")
        assert fixed_code is not None

    def test_fix_null_checks(self, fixer):
        test_code = '''
@Test
public void test() {
    Object obj = null;
    obj.toString();
}
'''
        fixed_code = fixer.fix_null_checks(test_code)
        assert fixed_code is not None


class TestFixerAgent:
    """FixerAgent 测试."""

    @pytest.fixture
    def agent(self):
        with patch("ut_agent.agents.fixer.get_llm"):
            return FixerAgent()

    def test_agent_initialization(self, agent):
        assert agent.name == "fixer"
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
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="fixed code"))
        agent.set_llm(mock_llm)

        context = AgentContext(
            task_id="test-task",
            source_file="/test/UserService.java",
            generated_test={
                "test_code": "@Test void testMethod() { }",
                "language": "java",
            },
            review_result={
                "issues": [],
                "needs_fix": False,
            },
            file_analysis={
                "language": "java",
            },
        )

        result = await agent.execute(context)

        assert result.agent_name == "fixer"

    def test_to_dict(self, agent):
        data = agent.to_dict()
        assert data["name"] == "fixer"
        assert "capabilities" in data
        assert data["status"] == "idle"
