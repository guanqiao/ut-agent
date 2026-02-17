"""代码分析模块重构版测试."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from ut_agent.tools.code_analyzer_refactored import (
    FileReader,
    JavaASTParser,
    JavaInfoExtractor,
    JavaMethodParser,
    JavaFieldParser,
    JavaParamParser,
    analyze_java_file_refactored,
    MethodInfo,
)
from ut_agent.exceptions import FileReadError


class TestFileReader:
    """文件读取器测试."""

    def test_read_file_success(self, tmp_path):
        """测试成功读取文件."""
        test_file = tmp_path / "Test.java"
        test_file.write_text("public class Test {}", encoding="utf-8")
        
        content = FileReader.read_file(str(test_file))
        
        assert content == "public class Test {}"

    def test_read_file_not_found(self):
        """测试文件不存在."""
        with pytest.raises(FileReadError) as exc_info:
            FileReader.read_file("/nonexistent/file.java")
        
        assert exc_info.value.details.get("reason") == "not_found"

    def test_read_file_permission_error(self, tmp_path):
        """测试权限错误."""
        import os
        test_file = tmp_path / "readonly.java"
        test_file.write_text("content", encoding="utf-8")
        
        # Windows 上权限测试可能不生效，跳过
        if os.name == 'nt':
            pytest.skip("Permission test skipped on Windows")
        
        test_file.chmod(0o000)
        
        try:
            with pytest.raises(FileReadError) as exc_info:
                FileReader.read_file(str(test_file))
            assert exc_info.value.details.get("reason") == "permission"
        finally:
            test_file.chmod(0o644)


class TestJavaASTParser:
    """Java AST 解析器测试."""

    def test_parse_with_cache_disabled(self):
        """测试禁用缓存."""
        result = JavaASTParser.parse("/test/File.java", use_cache=False)
        assert result is None

    @patch("ut_agent.tools.code_analyzer_refactored.parse_java_ast")
    def test_parse_with_cache_success(self, mock_parse):
        """测试缓存解析成功."""
        mock_ast = {"type": "program", "children": []}
        mock_parse.return_value = mock_ast
        
        result = JavaASTParser.parse("/test/File.java", use_cache=True)
        
        assert result == mock_ast
        mock_parse.assert_called_once()

    @patch("ut_agent.tools.code_analyzer_refactored.parse_java_ast")
    def test_parse_with_cache_error(self, mock_parse):
        """测试缓存解析失败."""
        mock_parse.side_effect = Exception("Parse error")
        
        result = JavaASTParser.parse("/test/File.java", use_cache=True)
        
        assert result is None


class TestJavaInfoExtractor:
    """Java 信息提取器测试."""

    def test_extract_package_regex(self):
        """测试正则提取包名."""
        content = "package com.example.test;\npublic class Test {}"
        package = JavaInfoExtractor._extract_package_regex(content)
        assert package == "com.example.test"

    def test_extract_package_regex_no_package(self):
        """测试无包名."""
        content = "public class Test {}"
        package = JavaInfoExtractor._extract_package_regex(content)
        assert package == ""

    def test_extract_imports_regex(self):
        """测试正则提取导入."""
        content = """
import java.util.List;
import java.util.Map;
public class Test {}
"""
        imports = JavaInfoExtractor._extract_imports_regex(content)
        assert "java.util.List" in imports
        assert "java.util.Map" in imports

    def test_extract_class_info_regex(self):
        """测试正则提取类信息."""
        content = "@Component\npublic class TestClass {}"
        path = Path("/test/TestClass.java")
        
        class_name, annotations = JavaInfoExtractor._extract_class_info_regex(content, path)
        
        assert class_name == "TestClass"
        assert "Component" in annotations

    def test_extract_methods_regex(self):
        """测试正则提取方法."""
        content = """
public class Test {
    public String getName(int id) { return ""; }
    private void helper() {}
}
"""
        methods = JavaInfoExtractor._extract_methods_regex(content)
        
        assert len(methods) == 2
        assert methods[0].name == "getName"
        assert methods[0].is_public is True
        assert methods[1].name == "helper"
        assert methods[1].is_public is False

    def test_extract_fields_regex(self):
        """测试正则提取字段."""
        content = """
public class Test {
    private String name;
    public int age;
}
"""
        fields = JavaInfoExtractor._extract_fields_regex(content)
        
        assert len(fields) == 2
        assert fields[0]["name"] == "name"
        assert fields[0]["type"] == "String"

    def test_extract_from_ast(self):
        """测试从 AST 提取."""
        ast_data = {
            "type": "program",
            "children": [
                {
                    "type": "package_declaration",
                    "children": [
                        {"type": "scoped_identifier", "text": "com.example"}
                    ]
                },
                {
                    "type": "class_declaration",
                    "children": [
                        {"type": "identifier", "text": "TestClass"}
                    ]
                }
            ]
        }
        
        package, imports, class_name, annotations, methods, fields = JavaInfoExtractor._extract_from_ast(
            ast_data, "content"
        )
        
        assert package == "com.example"
        assert class_name == "TestClass"


class TestJavaParamParser:
    """Java 参数解析器测试."""

    def test_parse_ast(self):
        """测试 AST 解析参数."""
        params_node = {
            "children": [
                {
                    "type": "formal_parameter",
                    "children": [
                        {"type": "type_identifier", "text": "String"},
                        {"type": "identifier", "text": "name"}
                    ]
                }
            ]
        }
        
        params = JavaParamParser.parse_ast(params_node)
        
        assert len(params) == 1
        assert params[0]["type"] == "String"
        assert params[0]["name"] == "name"

    def test_parse_regex(self):
        """测试正则解析参数."""
        params_str = "String name, int age"
        
        params = JavaParamParser.parse_regex(params_str)
        
        assert len(params) == 2
        assert params[0]["type"] == "String"
        assert params[0]["name"] == "name"

    def test_parse_regex_empty(self):
        """测试空参数."""
        params = JavaParamParser.parse_regex("")
        assert params == []


class TestJavaFieldParser:
    """Java 字段解析器测试."""

    def test_parse_field(self):
        """测试解析字段."""
        field_node = {
            "children": [
                {"type": "type_identifier", "text": "String"},
                {
                    "type": "variable_declarator",
                    "children": [
                        {"type": "identifier", "text": "userName"}
                    ]
                },
                {
                    "type": "modifiers",
                    "children": [
                        {"type": "private"}
                    ]
                }
            ]
        }
        
        field = JavaFieldParser.parse(field_node)
        
        assert field is not None
        assert field["name"] == "userName"
        assert field["type"] == "String"
        assert field["access"] == "private"

    def test_parse_field_incomplete(self):
        """测试不完整字段."""
        field_node = {"children": []}
        
        field = JavaFieldParser.parse(field_node)
        
        assert field is None


class TestJavaMethodParser:
    """Java 方法解析器测试."""

    def test_parse_method(self):
        """测试解析方法."""
        method_node = {
            "children": [
                {"type": "identifier", "text": "getUser"},
                {"type": "type_identifier", "text": "User"},
                {
                    "type": "formal_parameters",
                    "children": [
                        {
                            "type": "formal_parameter",
                            "children": [
                                {"type": "type_identifier", "text": "int"},
                                {"type": "identifier", "text": "id"}
                            ]
                        }
                    ]
                },
                {
                    "type": "modifiers",
                    "children": [
                        {"type": "public"},
                        {"type": "static"}
                    ]
                }
            ],
            "start_point": {"row": 10},
            "end_point": {"row": 15}
        }
        
        method = JavaMethodParser.parse(method_node, "content")
        
        assert method is not None
        assert method.name == "getUser"
        assert method.return_type == "User"
        assert method.is_public is True
        assert method.is_static is True
        assert method.start_line == 11

    def test_parse_method_no_name(self):
        """测试无名称方法."""
        method_node = {"children": []}
        
        method = JavaMethodParser.parse(method_node, "content")
        
        assert method is None


class TestAnalyzeJavaFileRefactored:
    """重构版 analyze_java_file 测试."""

    def test_analyze_java_file_success(self, tmp_path):
        """测试成功分析 Java 文件."""
        java_file = tmp_path / "TestService.java"
        java_file.write_text("""
package com.example.service;

import java.util.List;

public class TestService {
    private String name;
    
    public String getName(int id) {
        return name;
    }
}
""", encoding="utf-8")
        
        result = analyze_java_file_refactored(str(java_file))
        
        assert result["language"] == "java"
        assert result["package"] == "com.example.service"
        assert result["class_name"] == "TestService"
        assert len(result["methods"]) == 1
        assert result["methods"][0]["name"] == "getName"

    def test_analyze_java_file_not_found(self):
        """测试文件不存在."""
        with pytest.raises(FileReadError):
            analyze_java_file_refactored("/nonexistent/Test.java")

    def test_analyze_java_file_empty_class(self, tmp_path):
        """测试空类."""
        java_file = tmp_path / "Empty.java"
        java_file.write_text("public class Empty {}", encoding="utf-8")
        
        result = analyze_java_file_refactored(str(java_file))
        
        assert result["class_name"] == "Empty"
        assert result["methods"] == []
