"""代码分析器重构版测试模块."""

import tempfile
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import MagicMock, patch

import pytest

from ut_agent.tools.code_analyzer_refactored import (
    FileReader,
    JavaAnalyzer,
    TypeScriptAnalyzer,
    AnalysisResult,
    MethodInfo,
    ClassInfo,
)


class TestFileReader:
    """FileReader 测试."""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_read_file_success(self, temp_dir):
        """测试成功读取文件."""
        test_file = temp_dir / "Test.java"
        test_file.write_text("public class Test {}", encoding="utf-8")

        content = FileReader.read_file(str(test_file))

        assert content == "public class Test {}"

    def test_read_file_not_found(self):
        """测试文件不存在."""
        from ut_agent.exceptions import FileReadError

        with pytest.raises(FileReadError) as exc_info:
            FileReader.read_file("/nonexistent/path/Test.java")

        assert exc_info.value.file_path == "/nonexistent/path/Test.java"

    def test_read_file_encoding_error(self, temp_dir):
        """测试编码错误."""
        from ut_agent.exceptions import FileReadError

        test_file = temp_dir / "Test.java"
        test_file.write_bytes(b"\xff\xfe Invalid UTF-8")

        with pytest.raises(FileReadError) as exc_info:
            FileReader.read_file(str(test_file))

        assert exc_info.value.reason == "encoding"

    def test_read_file_permission_error(self, temp_dir):
        """测试权限错误."""
        from ut_agent.exceptions import FileReadError

        test_file = temp_dir / "Test.java"
        test_file.write_text("content", encoding="utf-8")

        with patch("pathlib.Path.read_text", side_effect=PermissionError("Permission denied")):
            with pytest.raises(FileReadError) as exc_info:
                FileReader.read_file(str(test_file))

            assert exc_info.value.reason == "permission"


class TestMethodInfo:
    """MethodInfo 测试."""

    def test_method_info_creation(self):
        """测试方法信息创建."""
        method = MethodInfo(
            name="getUser",
            signature="public User getUser(Long id)",
            return_type="User",
            parameters=[{"type": "Long", "name": "id"}],
            annotations=["Override"],
            start_line=10,
            end_line=20,
            is_public=True,
            is_static=False,
        )

        assert method.name == "getUser"
        assert method.return_type == "User"
        assert len(method.parameters) == 1
        assert method.is_public is True

    def test_method_info_to_dict(self):
        """测试方法信息转字典."""
        method = MethodInfo(
            name="save",
            signature="public void save()",
            return_type="void",
            parameters=[],
            annotations=[],
            start_line=5,
            end_line=10,
        )

        result = method.to_dict()

        assert result["name"] == "save"
        assert result["return_type"] == "void"
        assert result["is_public"] is True


class TestClassInfo:
    """ClassInfo 测试."""

    def test_class_info_creation(self):
        """测试类信息创建."""
        class_info = ClassInfo(
            name="UserService",
            package="com.example.service",
            imports=["java.util.List", "org.springframework.stereotype.Service"],
            annotations=["Service"],
            methods=[],
            fields=[],
        )

        assert class_info.name == "UserService"
        assert class_info.package == "com.example.service"
        assert len(class_info.imports) == 2

    def test_class_info_with_inheritance(self):
        """测试带继承的类信息."""
        class_info = ClassInfo(
            name="UserServiceImpl",
            package="com.example.service",
            imports=[],
            annotations=[],
            methods=[],
            fields=[],
            superclass="BaseService",
            interfaces=["UserService", "Serializable"],
        )

        assert class_info.superclass == "BaseService"
        assert len(class_info.interfaces) == 2


class TestJavaAnalyzer:
    """JavaAnalyzer 测试."""

    @pytest.fixture
    def analyzer(self):
        """创建分析器实例."""
        return JavaAnalyzer()

    @pytest.fixture
    def sample_java_content(self):
        """示例 Java 代码."""
        return """
package com.example.service;

import java.util.List;
import org.springframework.stereotype.Service;

@Service
public class UserService {
    private UserRepository userRepository;
    
    public User getUser(Long id) {
        return userRepository.findById(id);
    }
    
    public void saveUser(User user) {
        userRepository.save(user);
    }
    
    private void internalMethod() {
        // private method
    }
}
"""

    def test_extract_package(self, analyzer, sample_java_content):
        """测试提取包名."""
        package = analyzer.extract_package(sample_java_content)

        assert package == "com.example.service"

    def test_extract_imports(self, analyzer, sample_java_content):
        """测试提取导入."""
        imports = analyzer.extract_imports(sample_java_content)

        assert len(imports) == 2
        assert "java.util.List" in imports
        assert "org.springframework.stereotype.Service" in imports

    def test_extract_class_name(self, analyzer, sample_java_content):
        """测试提取类名."""
        class_name = analyzer.extract_class_name(sample_java_content)

        assert class_name == "UserService"

    def test_extract_class_annotations(self, analyzer, sample_java_content):
        """测试提取类注解."""
        annotations = analyzer.extract_class_annotations(sample_java_content)

        assert "Service" in annotations

    def test_extract_methods(self, analyzer, sample_java_content):
        """测试提取方法."""
        methods = analyzer.extract_methods(sample_java_content)

        assert len(methods) >= 2
        method_names = [m.name for m in methods]
        assert "getUser" in method_names
        assert "saveUser" in method_names

    def test_extract_fields(self, analyzer, sample_java_content):
        """测试提取字段."""
        fields = analyzer.extract_fields(sample_java_content)

        assert len(fields) == 1
        assert fields[0]["name"] == "userRepository"

    def test_analyze_full(self, analyzer, sample_java_content):
        """测试完整分析."""
        result = analyzer.analyze(sample_java_content, "/src/UserService.java")

        assert result.class_name == "UserService"
        assert result.package == "com.example.service"
        assert len(result.methods) >= 2


class TestTypeScriptAnalyzer:
    """TypeScriptAnalyzer 测试."""

    @pytest.fixture
    def analyzer(self):
        """创建分析器实例."""
        return TypeScriptAnalyzer()

    @pytest.fixture
    def sample_ts_content(self):
        """示例 TypeScript 代码."""
        return """
import { ref, computed } from 'vue';
import type { User } from './types';

export function getUser(id: number): Promise<User> {
    return fetch(`/api/users/${id}`).then(r => r.json());
}

export const formatDate = (date: Date): string => {
    return date.toISOString().split('T')[0];
};

async function internalHelper() {
    // helper
}
"""

    def test_extract_imports(self, analyzer, sample_ts_content):
        """测试提取导入."""
        imports = analyzer.extract_imports(sample_ts_content)

        assert len(imports) >= 1

    def test_extract_functions(self, analyzer, sample_ts_content):
        """测试提取函数."""
        functions = analyzer.extract_functions(sample_ts_content)

        func_names = [f["name"] for f in functions]
        assert "getUser" in func_names
        assert "formatDate" in func_names

    def test_extract_arrow_functions(self, analyzer, sample_ts_content):
        """测试提取箭头函数."""
        functions = analyzer.extract_functions(sample_ts_content)

        arrow_funcs = [f for f in functions if f["type"] == "arrow_function"]
        assert len(arrow_funcs) >= 1

    def test_analyze_full(self, analyzer, sample_ts_content):
        """测试完整分析."""
        result = analyzer.analyze(sample_ts_content, "/src/user.ts")

        assert result.file_name == "user.ts"
        assert len(result.functions) >= 2


class TestAnalysisResult:
    """AnalysisResult 测试."""

    def test_java_analysis_result(self):
        """测试 Java 分析结果."""
        result = AnalysisResult(
            file_path="/src/Test.java",
            file_name="Test.java",
            language="java",
            package="com.example",
            class_name="Test",
            imports=["java.util.List"],
            methods=[],
            fields=[],
            content="public class Test {}",
            line_count=1,
        )

        assert result.language == "java"
        assert result.class_name == "Test"

    def test_typescript_analysis_result(self):
        """测试 TypeScript 分析结果."""
        result = AnalysisResult(
            file_path="/src/utils.ts",
            file_name="utils.ts",
            language="typescript",
            imports=[],
            functions=[{"name": "helper", "type": "function"}],
            content="export function helper() {}",
            line_count=1,
        )

        assert result.language == "typescript"
        assert len(result.functions) == 1

    def test_to_dict(self):
        """测试转字典."""
        result = AnalysisResult(
            file_path="/src/Test.java",
            file_name="Test.java",
            language="java",
            package="com.example",
            class_name="Test",
            imports=[],
            methods=[],
            fields=[],
            content="",
            line_count=0,
        )

        result_dict = result.to_dict()

        assert result_dict["file_path"] == "/src/Test.java"
        assert result_dict["language"] == "java"


class TestIntegration:
    """集成测试."""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_analyze_java_file_integration(self, temp_dir):
        """测试 Java 文件分析集成."""
        java_file = temp_dir / "Calculator.java"
        java_file.write_text("""
package com.example.math;

public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }
    
    public int subtract(int a, int b) {
        return a - b;
    }
}
""", encoding="utf-8")

        analyzer = JavaAnalyzer()
        result = analyzer.analyze(java_file.read_text(encoding="utf-8"), str(java_file))

        assert result.class_name == "Calculator"
        assert result.package == "com.example.math"
        assert len(result.methods) == 2

    def test_analyze_typescript_file_integration(self, temp_dir):
        """测试 TypeScript 文件分析集成."""
        ts_file = temp_dir / "helpers.ts"
        ts_file.write_text("""
export function greet(name: string): string {
    return `Hello, ${name}!`;
}

export const double = (x: number): number => x * 2;
""", encoding="utf-8")

        analyzer = TypeScriptAnalyzer()
        result = analyzer.analyze(ts_file.read_text(encoding="utf-8"), str(ts_file))

        assert len(result.functions) >= 2
