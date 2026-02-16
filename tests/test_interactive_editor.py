"""交互式测试开发单元测试.

测试测试用例预览、交互式断言编辑和测试数据可视化调整功能。
"""

from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import pytest

from ut_agent.tools.interactive_editor import (
    InteractiveTestEditor,
    TestPreview,
    AssertionEditor,
    TestDataAdjuster,
    EditOperation,
    PreviewResult,
    AdjustmentSuggestion,
)


class TestTestPreview:
    """测试预览测试."""

    def test_preview_creation(self):
        """测试创建预览对象."""
        preview = TestPreview(
            test_code="void testAdd() { assertEquals(5, calc.add(2, 3)); }",
            line_count=1,
            assertion_count=1,
            test_method_count=1,
            coverage_estimate=0.8,
        )

        assert preview.test_code == "void testAdd() { assertEquals(5, calc.add(2, 3)); }"
        assert preview.line_count == 1
        assert preview.assertion_count == 1

    def test_preview_to_dict(self):
        """测试转换为字典."""
        preview = TestPreview(
            test_code="void testMethod() {}",
            line_count=1,
            assertion_count=0,
            test_method_count=1,
            coverage_estimate=0.5,
        )

        result = preview.to_dict()

        assert result["line_count"] == 1
        assert result["assertion_count"] == 0


class TestEditOperation:
    """编辑操作测试."""

    def test_edit_operation_creation(self):
        """测试创建编辑操作."""
        operation = EditOperation(
            operation_type="replace",
            target="assertEquals(5, result)",
            replacement="assertEquals(6, result)",
            line_number=10,
            description="Update expected value",
        )

        assert operation.operation_type == "replace"
        assert operation.target == "assertEquals(5, result)"
        assert operation.line_number == 10

    def test_edit_operation_to_dict(self):
        """测试转换为字典."""
        operation = EditOperation(
            operation_type="insert",
            target="",
            replacement="assertNotNull(result);",
            line_number=15,
            description="Add null check",
        )

        result = operation.to_dict()

        assert result["operation_type"] == "insert"
        assert result["line_number"] == 15


class TestPreviewResult:
    """预览结果测试."""

    def test_preview_result_creation(self):
        """测试创建预览结果."""
        result = PreviewResult(
            original_code="assertEquals(5, result);",
            modified_code="assertEquals(6, result);",
            diff_lines=[(10, "- assertEquals(5, result);"), (10, "+ assertEquals(6, result);")],
            is_valid=True,
            validation_errors=[],
        )

        assert result.is_valid is True
        assert len(result.diff_lines) == 2

    def test_preview_result_with_errors(self):
        """测试带错误的预览结果."""
        result = PreviewResult(
            original_code="assertEqua(5, result);",
            modified_code="assertEqua(6, result);",
            diff_lines=[],
            is_valid=False,
            validation_errors=["Unknown assertion: assertEqua"],
        )

        assert result.is_valid is False
        assert len(result.validation_errors) == 1


class TestAdjustmentSuggestion:
    """调整建议测试."""

    def test_adjustment_suggestion_creation(self):
        """测试创建调整建议."""
        suggestion = AdjustmentSuggestion(
            suggestion_type="boundary_value",
            current_value="5",
            suggested_values=["0", "-1", "Integer.MAX_VALUE", "Integer.MIN_VALUE"],
            reason="Add boundary test coverage",
            priority="high",
        )

        assert suggestion.suggestion_type == "boundary_value"
        assert len(suggestion.suggested_values) == 4
        assert suggestion.priority == "high"

    def test_adjustment_suggestion_to_dict(self):
        """测试转换为字典."""
        suggestion = AdjustmentSuggestion(
            suggestion_type="null_check",
            current_value="new User()",
            suggested_values=["null"],
            reason="Add null input test",
            priority="medium",
        )

        result = suggestion.to_dict()

        assert result["suggestion_type"] == "null_check"
        assert result["priority"] == "medium"


class TestInteractiveTestEditor:
    """交互式测试编辑器测试."""

    def test_preview_test_modification(self):
        """测试预览测试修改."""
        editor = InteractiveTestEditor()
        
        test_code = '''
@Test
void testAdd() {
    Calculator calc = new Calculator();
    int result = calc.add(2, 3);
    assertEquals(5, result);
}
'''
        operation = EditOperation(
            operation_type="replace",
            target="assertEquals(5, result)",
            replacement="assertEquals(6, result)",
            line_number=5,
            description="Update expected value",
        )
        
        preview = editor.preview_modification(test_code, operation)
        
        assert isinstance(preview, PreviewResult)
        assert "assertEquals(6, result)" in preview.modified_code

    def test_preview_insert_operation(self):
        """测试预览插入操作."""
        editor = InteractiveTestEditor()
        
        test_code = '''
@Test
void testMethod() {
    Object result = service.method();
}
'''
        operation = EditOperation(
            operation_type="insert",
            target="",
            replacement="assertNotNull(result);",
            line_number=4,
            description="Add assertion",
        )
        
        preview = editor.preview_modification(test_code, operation)
        
        assert "assertNotNull(result);" in preview.modified_code

    def test_preview_delete_operation(self):
        """测试预览删除操作."""
        editor = InteractiveTestEditor()
        
        test_code = '''
@Test
void testMethod() {
    Object result = service.method();
    System.out.println("debug");
    assertNotNull(result);
}
'''
        operation = EditOperation(
            operation_type="delete",
            target='System.out.println("debug");',
            replacement="",
            line_number=4,
            description="Remove debug statement",
        )
        
        preview = editor.preview_modification(test_code, operation)
        
        assert 'System.out.println("debug");' not in preview.modified_code

    def test_apply_modification(self):
        """测试应用修改."""
        editor = InteractiveTestEditor()
        
        test_code = "assertEquals(5, result);"
        operation = EditOperation(
            operation_type="replace",
            target="assertEquals(5, result)",
            replacement="assertEquals(6, result)",
            line_number=1,
            description="Update value",
        )
        
        modified = editor.apply_modification(test_code, operation)
        
        assert "assertEquals(6, result)" in modified

    def test_validate_test_code_valid(self):
        """测试验证有效的测试代码."""
        editor = InteractiveTestEditor()
        
        test_code = '''
@Test
void testAdd() {
    Calculator calc = new Calculator();
    assertEquals(5, calc.add(2, 3));
}
'''
        is_valid, errors = editor.validate_test_code(test_code)
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_test_code_missing_assertion(self):
        """测试验证缺少断言的测试代码."""
        editor = InteractiveTestEditor()
        
        test_code = '''
@Test
void testMethod() {
    service.method();
}
'''
        is_valid, errors = editor.validate_test_code(test_code)
        
        assert is_valid is False
        assert any("assertion" in e.lower() for e in errors)

    def test_generate_test_preview(self):
        """测试生成测试预览."""
        editor = InteractiveTestEditor()
        
        test_code = '''
@Test
void testAdd() {
    assertEquals(5, calc.add(2, 3));
}

@Test
void testSubtract() {
    assertEquals(1, calc.subtract(3, 2));
}
'''
        preview = editor.generate_preview(test_code)
        
        assert isinstance(preview, TestPreview)
        assert preview.test_method_count == 2
        assert preview.assertion_count == 2


class TestAssertionEditor:
    """断言编辑器测试."""

    def test_parse_assertions(self):
        """测试解析断言."""
        editor = AssertionEditor()
        
        test_code = '''
@Test
void testMethod() {
    assertEquals(5, result);
    assertTrue(condition);
    assertNotNull(object);
}
'''
        assertions = editor.parse_assertions(test_code)
        
        assert len(assertions) == 3
        assert assertions[0]["type"] == "assertEquals"
        assert assertions[0]["expected"] == "5"

    def test_modify_assertion_expected_value(self):
        """测试修改断言期望值."""
        editor = AssertionEditor()
        
        assertion = {
            "type": "assertEquals",
            "expected": "5",
            "actual": "result",
            "line": 3,
        }
        
        modified = editor.modify_expected_value(assertion, "10")
        
        assert modified["expected"] == "10"

    def test_add_assertion(self):
        """测试添加断言."""
        editor = AssertionEditor()
        
        test_code = '''
@Test
void testMethod() {
    Object result = service.method();
}
'''
        new_assertion = {
            "type": "assertNotNull",
            "actual": "result",
        }
        
        modified = editor.add_assertion(test_code, new_assertion, line=4)
        
        assert "assertNotNull(result)" in modified

    def test_suggest_assertions(self):
        """测试建议断言."""
        editor = AssertionEditor()
        
        test_code = '''
@Test
void testAdd() {
    int result = calc.add(2, 3);
}
'''
        suggestions = editor.suggest_assertions(test_code)
        
        assert len(suggestions) > 0
        assert any("result" in s.get("actual", "") for s in suggestions)

    def test_convert_assertion_type(self):
        """测试转换断言类型."""
        editor = AssertionEditor()
        
        assertion = {
            "type": "assertEquals",
            "expected": "true",
            "actual": "condition",
            "line": 3,
        }
        
        converted = editor.convert_assertion_type(assertion, "assertTrue")
        
        assert converted["type"] == "assertTrue"
        assert "expected" not in converted or converted.get("expected") is None


class TestTestDataAdjuster:
    """测试数据调整器测试."""

    def test_extract_test_data(self):
        """测试提取测试数据."""
        adjuster = TestDataAdjuster()
        
        test_code = '''
@Test
void testAdd() {
    assertEquals(5, calc.add(2, 3));
    assertEquals(0, calc.add(0, 0));
    assertEquals(-1, calc.add(-2, 1));
}
'''
        data = adjuster.extract_test_data(test_code)
        
        assert len(data) > 0
        assert any(d.get("expected") == "5" for d in data)

    def test_suggest_boundary_values(self):
        """测试建议边界值."""
        adjuster = TestDataAdjuster()
        
        current_value = "5"
        data_type = "int"
        
        suggestions = adjuster.suggest_boundary_values(current_value, data_type)
        
        assert "0" in suggestions
        assert any("MAX" in s or "MIN" in s for s in suggestions)

    def test_suggest_null_value(self):
        """测试建议 null 值."""
        adjuster = TestDataAdjuster()
        
        current_value = "new User()"
        data_type = "object"
        
        suggestions = adjuster.suggest_boundary_values(current_value, data_type)
        
        assert "null" in suggestions

    def test_adjust_test_data(self):
        """测试调整测试数据."""
        adjuster = TestDataAdjuster()
        
        test_code = '''@Test
void testAdd() {
    assertEquals(5, calc.add(2, 3));
}'''
        adjustments = [
            {"line": 3, "old_value": "5", "new_value": "0"},
            {"line": 3, "old_value": "2", "new_value": "0"},
            {"line": 3, "old_value": "3", "new_value": "0"},
        ]
        
        modified = adjuster.adjust_test_data(test_code, adjustments)
        
        assert "0" in modified

    def test_generate_data_variations(self):
        """测试生成数据变体."""
        adjuster = TestDataAdjuster()
        
        test_data = {
            "a": 2,
            "b": 3,
            "expected": 5,
        }
        
        variations = adjuster.generate_variations(test_data)
        
        assert len(variations) > 1
        assert any(v.get("a") == 0 for v in variations)

    def test_analyze_data_coverage(self):
        """测试分析数据覆盖."""
        adjuster = TestDataAdjuster()
        
        test_cases = [
            {"a": 2, "b": 3},
            {"a": 0, "b": 0},
            {"a": -1, "b": 1},
        ]
        
        coverage = adjuster.analyze_data_coverage(test_cases, "a")
        
        assert coverage["has_positive"] is True
        assert coverage["has_zero"] is True
        assert coverage["has_negative"] is True


class TestIntegration:
    """集成测试."""

    def test_full_interactive_workflow(self):
        """测试完整的交互式工作流."""
        test_code = '''
@Test
void testCalculate() {
    Calculator calc = new Calculator();
    int result = calc.add(2, 3);
    assertEquals(5, result);
}
'''
        editor = InteractiveTestEditor()
        
        preview = editor.generate_preview(test_code)
        assert preview.test_method_count == 1
        
        assertion_editor = AssertionEditor()
        assertions = assertion_editor.parse_assertions(test_code)
        assert len(assertions) == 1
        
        modified_assertion = assertion_editor.modify_expected_value(assertions[0], "6")
        
        operation = EditOperation(
            operation_type="replace",
            target="assertEquals(5, result)",
            replacement=f"assertEquals({modified_assertion['expected']}, result)",
            line_number=5,
            description="Update expected value",
        )
        
        preview_result = editor.preview_modification(test_code, operation)
        assert "assertEquals(6, result)" in preview_result.modified_code
        
        data_adjuster = TestDataAdjuster()
        suggestions = data_adjuster.suggest_boundary_values("2", "int")
        assert len(suggestions) > 0

    def test_interactive_assertion_building(self):
        """测试交互式断言构建."""
        test_code = '''
@Test
void testUserService() {
    UserService service = new UserService();
    Object user = service.findById(1L);
}
'''
        assertion_editor = AssertionEditor()
        suggestions = assertion_editor.suggest_assertions(test_code)
        
        assert len(suggestions) > 0
        
        for suggestion in suggestions:
            modified = assertion_editor.add_assertion(test_code, suggestion, line=5)
            assert suggestion["type"] in modified
