"""测试生成器模块单元测试."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from ut_agent.tools.test_generator import (
    generate_java_test,
    generate_frontend_test,
    generate_incremental_java_test,
    generate_incremental_frontend_test,
    format_java_methods,
    format_java_fields,
    format_ts_functions,
    format_vue_component_info,
    clean_code_blocks,
    wrap_additional_test,
)
from ut_agent.graph.state import CoverageGap, GeneratedTestFile


class TestFormatFunctions:
    """格式化函数测试."""

    def test_format_java_methods_empty(self):
        """测试格式化空的 Java 方法列表."""
        result = format_java_methods([])
        assert result == "无"

    def test_format_java_methods(self):
        """测试格式化 Java 方法."""
        methods = [
            {
                "signature": "public void test()",
                "return_type": "void",
            },
            {
                "signature": "public int add(int a, int b)",
                "return_type": "int",
            },
        ]

        result = format_java_methods(methods)
        assert "public void test() (返回: void)" in result
        assert "public int add(int a, int b) (返回: int)" in result

    def test_format_java_fields_empty(self):
        """测试格式化空的 Java 字段列表."""
        result = format_java_fields([])
        assert result == "无"

    def test_format_java_fields(self):
        """测试格式化 Java 字段."""
        fields = [
            {"access": "private", "type": "int", "name": "id"},
            {"access": "public", "type": "String", "name": "name"},
        ]

        result = format_java_fields(fields)
        assert "private int id" in result
        assert "public String name" in result

    def test_format_ts_functions_empty(self):
        """测试格式化空的 TypeScript 函数列表."""
        result = format_ts_functions([])
        assert result == "无"

    def test_format_ts_functions(self):
        """测试格式化 TypeScript 函数."""
        functions = [
            {
                "is_exported": True,
                "is_async": False,
                "name": "add",
                "parameters": [
                    {"name": "a", "type": "number"},
                    {"name": "b", "type": "number"},
                ],
                "return_type": "number",
            },
            {
                "is_exported": False,
                "is_async": True,
                "name": "fetchData",
                "parameters": [],
                "return_type": "Promise<any>",
            },
        ]

        result = format_ts_functions(functions)
        assert "export add(a: number, b: number): number" in result
        assert "async fetchData(): Promise<any>" in result

    def test_format_vue_component_info_empty(self):
        """测试格式化空的 Vue 组件信息."""
        result = format_vue_component_info({})
        assert result == "- 基础组件"

    def test_format_vue_component_info(self):
        """测试格式化 Vue 组件信息."""
        component_info = {
            "has_props": True,
            "has_emits": True,
            "has_setup": True,
            "has_data": False,
        }

        result = format_vue_component_info(component_info)
        assert "- 有 Props 定义" in result
        assert "- 有 Emits 定义" in result
        assert "- 使用 Composition API (setup)" in result


class TestCleanCodeBlocks:
    """clean_code_blocks 函数测试."""

    def test_clean_code_blocks_with_markdown(self):
        """测试清理 Markdown 代码块标记."""
        code = """```java
public class Test {
    public void test() {
    }
}
```"""

        result = clean_code_blocks(code)
        assert result == "public class Test {\n    public void test() {\n    }\n}"

    def test_clean_code_blocks_without_markdown(self):
        """测试清理没有 Markdown 代码块标记的代码."""
        code = "public class Test {\n    public void test() {\n    }\n}"

        result = clean_code_blocks(code)
        assert result == code

    def test_clean_code_blocks_empty(self):
        """测试清理空代码."""
        result = clean_code_blocks("")
        assert result == ""

    def test_clean_code_blocks_only_markdown(self):
        """测试清理只有 Markdown 标记的代码."""
        code = "```java\n```"
        result = clean_code_blocks(code)
        assert result == ""


class TestWrapAdditionalTest:
    """wrap_additional_test 函数测试."""

    def test_wrap_additional_test(self):
        """测试包装补充测试."""
        test_code = "    @Test\n    void testMethod() {\n    }"
        class_name = "TestClass"
        package = "com.example"
        file_analysis = {
            "imports": ["java.util.List", "java.util.Map"],
        }

        result = wrap_additional_test(test_code, class_name, package, file_analysis)

        assert "package com.example;" in result
        assert "import org.junit.jupiter.api.Test;" in result
        assert "import java.util.List;" in result
        assert "import java.util.Map;" in result
        assert "public class TestClassTest {" in result
        assert "@Test" in result
        assert "void testMethod()" in result

    def test_wrap_additional_test_no_imports(self):
        """测试包装无导入的补充测试."""
        test_code = "    @Test\n    void testMethod() {\n    }"
        class_name = "TestClass"
        package = "com.example"
        file_analysis = {}

        result = wrap_additional_test(test_code, class_name, package, file_analysis)

        assert "package com.example;" in result
        assert "public class TestClassTest {" in result


class TestGenerateJavaTest:
    """generate_java_test 函数测试."""

    @patch("ut_agent.tools.test_generator.BoundaryValueGenerator")
    @patch("ut_agent.tools.test_generator.format_test_data_for_prompt")
    def test_generate_java_test(self, mock_format, mock_generator):
        """测试生成 Java 测试."""
        mock_llm = Mock()
        mock_response = Mock(content="public class TestTest {\n    @Test\n    void test() {\n    }\n}")
        mock_llm.invoke.return_value = mock_response

        mock_data_generator = Mock()
        mock_data_generator.generate_test_data_for_method.return_value = None
        mock_generator.return_value = mock_data_generator

        mock_format.return_value = ""

        file_analysis = {
            "class_name": "Test",
            "package": "com.example",
            "methods": [
                {"name": "test", "is_public": True},
            ],
            "fields": [],
            "file_path": "/src/main/java/com/example/Test.java",
        }

        result = generate_java_test(file_analysis, mock_llm)

        assert isinstance(result, GeneratedTestFile)
        assert result.source_file == "/src/main/java/com/example/Test.java"
        assert "TestTest.java" in result.test_file_path
        assert "public class TestTest" in result.test_code
        mock_llm.invoke.assert_called_once()

    @patch("ut_agent.tools.test_generator.BoundaryValueGenerator")
    @patch("ut_agent.tools.test_generator.format_test_data_for_prompt")
    def test_generate_java_test_with_gap(self, mock_format, mock_generator):
        """测试生成带覆盖率缺口的 Java 测试."""
        mock_llm = Mock()
        mock_response = Mock(content="    @Test\n    void testGap() {\n    }")
        mock_llm.invoke.return_value = mock_response

        mock_data_generator = Mock()
        mock_data_generator.generate_test_data_for_method.return_value = None
        mock_generator.return_value = mock_data_generator

        mock_format.return_value = ""

        gap_info = CoverageGap(
            file_path="/src/main/java/com/example/Test.java",
            line_number=10,
            line_content="if (x > 0) {",
            gap_type="condition",
        )

        file_analysis = {
            "class_name": "Test",
            "package": "com.example",
            "methods": [],
            "fields": [],
            "file_path": "/src/main/java/com/example/Test.java",
        }

        result = generate_java_test(
            file_analysis, mock_llm, gap_info=gap_info, plan="覆盖条件分支"
        )

        assert isinstance(result, GeneratedTestFile)
        assert "testGap" in result.test_code

    def test_generate_java_test_no_methods(self):
        """测试生成无方法的 Java 测试."""
        mock_llm = Mock()
        mock_response = Mock(content="public class TestTest {\n}")
        mock_llm.invoke.return_value = mock_response

        file_analysis = {
            "class_name": "Test",
            "package": "com.example",
            "methods": [],
            "fields": [],
            "file_path": "/src/main/java/com/example/Test.java",
        }

        result = generate_java_test(file_analysis, mock_llm, use_boundary_values=False)

        assert isinstance(result, GeneratedTestFile)
        assert "public class TestTest" in result.test_code


class TestGenerateFrontendTest:
    """generate_frontend_test 函数测试."""

    @patch("ut_agent.tools.test_generator.BoundaryValueGenerator")
    @patch("ut_agent.tools.test_generator.format_test_data_for_prompt")
    def test_generate_frontend_test(self, mock_format, mock_generator):
        """测试生成前端测试."""
        mock_llm = Mock()
        mock_response = Mock(content="import { describe, it, expect } from 'vitest';\n\ndescribe('test', () => {\n    it('should work', () => {\n    });\n});")
        mock_llm.invoke.return_value = mock_response

        mock_data_generator = Mock()
        mock_data_generator.generate_test_data_for_method.return_value = None
        mock_generator.return_value = mock_data_generator

        mock_format.return_value = ""

        file_analysis = {
            "file_path": "/src/App.ts",
            "functions": [
                {"name": "add", "is_exported": True, "type": "function"},
            ],
            "is_vue": False,
        }

        result = generate_frontend_test(file_analysis, "typescript", mock_llm)

        assert isinstance(result, GeneratedTestFile)
        assert result.source_file == "/src/App.ts"
        assert "App.spec.ts" in result.test_file_path
        assert "import { describe, it, expect } from 'vitest'" in result.test_code

    @patch("ut_agent.tools.test_generator.BoundaryValueGenerator")
    @patch("ut_agent.tools.test_generator.format_test_data_for_prompt")
    def test_generate_frontend_test_vue(self, mock_format, mock_generator):
        """测试生成 Vue 前端测试."""
        mock_llm = Mock()
        mock_response = Mock(content="import { describe, it, expect } from 'vitest';\nimport { mount } from '@vue/test-utils';\n\ndescribe('App', () => {\n});")
        mock_llm.invoke.return_value = mock_response

        mock_data_generator = Mock()
        mock_data_generator.generate_test_data_for_method.return_value = None
        mock_generator.return_value = mock_data_generator

        mock_format.return_value = ""

        file_analysis = {
            "file_path": "/src/App.vue",
            "functions": [],
            "is_vue": True,
            "component_info": {
                "has_props": True,
            },
        }

        result = generate_frontend_test(file_analysis, "vue", mock_llm)

        assert isinstance(result, GeneratedTestFile)
        assert "App.spec.ts" in result.test_file_path
        assert "@vue/test-utils" in result.test_code

    @patch("ut_agent.tools.test_generator.BoundaryValueGenerator")
    @patch("ut_agent.tools.test_generator.format_test_data_for_prompt")
    def test_generate_frontend_test_with_gap(self, mock_format, mock_generator):
        """测试生成带覆盖率缺口的前端测试."""
        mock_llm = Mock()
        mock_response = Mock(content="it('should cover gap', () => {\n});")
        mock_llm.invoke.return_value = mock_response

        mock_data_generator = Mock()
        mock_data_generator.generate_test_data_for_method.return_value = None
        mock_generator.return_value = mock_data_generator

        mock_format.return_value = ""

        gap_info = CoverageGap(
            file_path="/src/App.ts",
            line_number=10,
            line_content="if (x > 0) {",
            gap_type="condition",
        )

        file_analysis = {
            "file_path": "/src/App.ts",
            "functions": [],
            "is_vue": False,
        }

        result = generate_frontend_test(
            file_analysis, "typescript", mock_llm, gap_info=gap_info, plan="覆盖条件分支"
        )

        assert isinstance(result, GeneratedTestFile)
        assert "should cover gap" in result.test_code


class TestGenerateIncrementalJavaTest:
    """generate_incremental_java_test 函数测试."""

    @patch("ut_agent.tools.test_generator.TestAnalyzer")
    @patch("ut_agent.tools.test_generator.format_existing_tests_for_prompt")
    def test_generate_incremental_java_test_new_methods(self, mock_format, mock_analyzer_class):
        """测试增量生成 Java 测试 - 新增方法."""
        mock_llm = Mock()
        mock_response = Mock(content="@Test\nvoid testNewMethod() {\n}")
        mock_llm.invoke.return_value = mock_response

        mock_analyzer = Mock()
        mock_analyzer.analyze_existing_tests.return_value = Mock(
            tested_methods={},
            untested_methods=["newMethod"],
            manual_tests=[],
        )
        mock_analyzer.extract_test_patterns.return_value = {"naming_convention": "test_prefix"}
        mock_analyzer_class.return_value = mock_analyzer

        mock_format.return_value = "无已有测试"

        file_analysis = {
            "class_name": "Test",
            "package": "com.example",
            "methods": [
                {"name": "existingMethod", "is_public": True},
                {"name": "newMethod", "is_public": True},
            ],
            "fields": [],
            "file_path": "/src/main/java/com/example/Test.java",
        }

        result = generate_incremental_java_test(
            file_analysis,
            mock_llm,
            existing_test_path=None,
            added_methods=["newMethod"],
            modified_methods=[],
            use_boundary_values=False,
        )

        assert isinstance(result, GeneratedTestFile)
        assert "testNewMethod" in result.test_code
        mock_llm.invoke.assert_called_once()

    @patch("ut_agent.tools.test_generator.TestAnalyzer")
    @patch("ut_agent.tools.test_generator.format_existing_tests_for_prompt")
    def test_generate_incremental_java_test_with_existing(self, mock_format, mock_analyzer_class):
        """测试增量生成 Java 测试 - 有已有测试."""
        mock_llm = Mock()
        mock_response = Mock(content="@Test\nvoid testModifiedMethod() {\n}")
        mock_llm.invoke.return_value = mock_response

        mock_analyzer = Mock()
        mock_analyzer.analyze_existing_tests.return_value = Mock(
            tested_methods={"existingMethod": ["testExistingMethod"]},
            untested_methods=[],
            manual_tests=[],
        )
        mock_analyzer.extract_test_patterns.return_value = {"naming_convention": "given_when_then"}
        mock_analyzer_class.return_value = mock_analyzer

        mock_format.return_value = "已覆盖的方法:\n  - existingMethod"

        with tempfile.TemporaryDirectory() as temp_dir:
            existing_test = Path(temp_dir) / "TestTest.java"
            existing_test.write_text("public class TestTest { @Test void testExistingMethod() {} }")

            file_analysis = {
                "class_name": "Test",
                "package": "com.example",
                "methods": [
                    {"name": "existingMethod", "is_public": True},
                    {"name": "modifiedMethod", "is_public": True},
                ],
                "fields": [],
                "file_path": "/src/main/java/com/example/Test.java",
            }

            result = generate_incremental_java_test(
                file_analysis,
                mock_llm,
                existing_test_path=str(existing_test),
                added_methods=[],
                modified_methods=["modifiedMethod"],
                use_boundary_values=False,
            )

            assert isinstance(result, GeneratedTestFile)


class TestGenerateIncrementalFrontendTest:
    """generate_incremental_frontend_test 函数测试."""

    @patch("ut_agent.tools.test_generator.TestAnalyzer")
    @patch("ut_agent.tools.test_generator.format_existing_tests_for_prompt")
    def test_generate_incremental_frontend_test(self, mock_format, mock_analyzer_class):
        """测试增量生成前端测试."""
        mock_llm = Mock()
        mock_response = Mock(content="it('should work for newFunc', () => {});")
        mock_llm.invoke.return_value = mock_response

        mock_analyzer = Mock()
        mock_analyzer.analyze_existing_tests.return_value = Mock(
            tested_methods={},
            untested_methods=["newFunc"],
            manual_tests=[],
        )
        mock_analyzer.extract_test_patterns.return_value = {"naming_convention": "should_style"}
        mock_analyzer_class.return_value = mock_analyzer

        mock_format.return_value = "无已有测试"

        file_analysis = {
            "file_path": "/src/utils.ts",
            "functions": [
                {"name": "existingFunc", "is_exported": True},
                {"name": "newFunc", "is_exported": True},
            ],
            "is_vue": False,
        }

        result = generate_incremental_frontend_test(
            file_analysis,
            "typescript",
            mock_llm,
            existing_test_path=None,
            added_functions=["newFunc"],
            modified_functions=[],
            use_boundary_values=False,
        )

        assert isinstance(result, GeneratedTestFile)
        assert "should work for newFunc" in result.test_code

    @patch("ut_agent.tools.test_generator.TestAnalyzer")
    @patch("ut_agent.tools.test_generator.format_existing_tests_for_prompt")
    def test_generate_incremental_frontend_test_vue(self, mock_format, mock_analyzer_class):
        """测试增量生成 Vue 组件测试."""
        mock_llm = Mock()
        mock_response = Mock(content="it('should handle newMethod', () => {});")
        mock_llm.invoke.return_value = mock_response

        mock_analyzer = Mock()
        mock_analyzer.analyze_existing_tests.return_value = Mock(
            tested_methods={},
            untested_methods=["newMethod"],
            manual_tests=[],
        )
        mock_analyzer.extract_test_patterns.return_value = {"naming_convention": "should_style"}
        mock_analyzer_class.return_value = mock_analyzer

        mock_format.return_value = "无已有测试"

        file_analysis = {
            "file_path": "/src/Component.vue",
            "functions": [
                {"name": "newMethod", "is_exported": True},
            ],
            "is_vue": True,
            "component_info": {"has_props": True},
        }

        result = generate_incremental_frontend_test(
            file_analysis,
            "vue",
            mock_llm,
            existing_test_path=None,
            added_functions=["newMethod"],
            modified_functions=[],
            use_boundary_values=False,
        )

        assert isinstance(result, GeneratedTestFile)


if __name__ == "__main__":
    pytest.main([__file__])
