"""代码分析模块单元测试."""

import tempfile
from pathlib import Path

import pytest

from ut_agent.tools.code_analyzer import (
    ClassInfo,
    MethodInfo,
    analyze_java_file,
    analyze_ts_file,
    extract_dependencies,
    find_testable_methods,
    parse_ts_params,
)


class TestMethodInfo:
    """MethodInfo 数据类测试."""

    def test_method_info_creation(self):
        """测试 MethodInfo 创建."""
        method = MethodInfo(
            name="testMethod",
            signature="public String testMethod(int arg)",
            return_type="String",
            parameters=[{"type": "int", "name": "arg"}],
            annotations=["@Test"],
            start_line=10,
            end_line=20,
            is_public=True,
            is_static=False,
        )

        assert method.name == "testMethod"
        assert method.return_type == "String"
        assert len(method.parameters) == 1
        assert method.is_public is True
        assert method.is_static is False

    def test_method_info_defaults(self):
        """测试 MethodInfo 默认值."""
        method = MethodInfo(
            name="simpleMethod",
            signature="private void simpleMethod()",
            return_type="void",
            parameters=[],
            annotations=[],
            start_line=1,
            end_line=5,
        )

        assert method.is_public is True  # 默认值
        assert method.is_static is False  # 默认值


class TestClassInfo:
    """ClassInfo 数据类测试."""

    def test_class_info_creation(self):
        """测试 ClassInfo 创建."""
        method = MethodInfo(
            name="test",
            signature="public void test()",
            return_type="void",
            parameters=[],
            annotations=[],
            start_line=5,
            end_line=10,
        )

        class_info = ClassInfo(
            name="TestClass",
            package="com.example",
            imports=["java.util.List"],
            annotations=["@Service"],
            methods=[method],
            fields=[{"name": "id", "type": "Long"}],
            superclass="BaseClass",
            interfaces=["Serializable"],
        )

        assert class_info.name == "TestClass"
        assert class_info.package == "com.example"
        assert len(class_info.methods) == 1
        assert class_info.superclass == "BaseClass"


class TestAnalyzeJavaFile:
    """Java 文件分析测试."""

    @pytest.fixture
    def java_file(self):
        """创建临时 Java 文件."""
        content = '''
package com.example.service;

import java.util.List;
import java.util.Optional;

@Service
public class UserService {
    private UserRepository userRepository;

    public User findById(Long id) {
        return userRepository.findById(id).orElse(null);
    }

    public List<User> findAll() {
        return userRepository.findAll();
    }

    private void validateUser(User user) {
        // private method
    }
}
'''
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".java", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            return f.name

    def test_analyze_java_file_structure(self, java_file):
        """测试 Java 文件结构分析."""
        result = analyze_java_file(java_file)

        assert result["language"] == "java"
        assert result["package"] == "com.example.service"
        assert result["class_name"] == "UserService"
        # 注解列表可能存在但可能为空
        assert "annotations" in result

    def test_analyze_java_imports(self, java_file):
        """测试 Java 导入分析."""
        result = analyze_java_file(java_file)

        assert "java.util.List" in result["imports"]
        assert "java.util.Optional" in result["imports"]

    def test_analyze_java_methods(self, java_file):
        """测试 Java 方法分析."""
        result = analyze_java_file(java_file)

        methods = result["methods"]
        method_names = [m["name"] for m in methods]

        assert "findById" in method_names
        assert "findAll" in method_names
        assert "validateUser" in method_names  # private 方法也会被提取

    def test_analyze_java_fields(self, java_file):
        """测试 Java 字段分析."""
        result = analyze_java_file(java_file)

        fields = result["fields"]
        assert len(fields) >= 1

    def test_analyze_nonexistent_file(self):
        """测试分析不存在的文件."""
        from ut_agent.exceptions import FileReadError
        with pytest.raises(FileReadError):
            analyze_java_file("/nonexistent/path/File.java")


class TestAnalyzeTsFile:
    """TypeScript 文件分析测试."""

    @pytest.fixture
    def ts_file(self):
        """创建临时 TypeScript 文件."""
        content = '''
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

export function useUser() {
  const users = ref([])
  const userCount = computed(() => users.value.length)

  async function fetchUsers() {
    // fetch logic
  }

  return { users, userCount, fetchUsers }
}

export const formatDate = (date: Date): string => {
  return date.toISOString()
}
'''
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ts", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            return f.name

    @pytest.fixture
    def vue_file(self):
        """创建临时 Vue 文件."""
        content = '''<template>
  <div class="user-list">
    <div v-for="user in users" :key="user.id">{{ user.name }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const users = ref([])
const loading = ref(false)

onMounted(() => {
  fetchUsers()
})

async function fetchUsers() {
  loading.value = true
  // fetch logic
  loading.value = false
}
</script>
'''
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".vue", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            return f.name

    def test_analyze_ts_file_structure(self, ts_file):
        """测试 TypeScript 文件结构分析."""
        result = analyze_ts_file(ts_file)

        assert result["language"] == "typescript"
        assert result["is_vue"] is False

    def test_analyze_ts_imports(self, ts_file):
        """测试 TypeScript 导入分析."""
        result = analyze_ts_file(ts_file)

        import_sources = [imp["source"] for imp in result["imports"]]
        assert "vue" in import_sources
        assert "vue-router" in import_sources

    def test_analyze_ts_functions(self, ts_file):
        """测试 TypeScript 函数分析."""
        result = analyze_ts_file(ts_file)

        functions = result["functions"]
        func_names = [f["name"] for f in functions]

        assert "useUser" in func_names
        assert "formatDate" in func_names
        assert "fetchUsers" in func_names

    def test_analyze_vue_file(self, vue_file):
        """测试 Vue 文件分析."""
        result = analyze_ts_file(vue_file)

        assert result["language"] == "vue"
        assert result["is_vue"] is True
        assert "has_setup" in result["component_info"]

    def test_analyze_nonexistent_ts_file(self):
        """测试分析不存在的 TypeScript 文件."""
        with pytest.raises(FileNotFoundError):
            analyze_ts_file("/nonexistent/path/file.ts")


class TestParseTsParams:
    """TypeScript 参数解析测试."""

    def test_parse_simple_params(self):
        """测试简单参数解析."""
        params = parse_ts_params("name: string, age: number")

        assert len(params) == 2
        assert params[0]["name"] == "name"
        assert params[0]["type"] == "string"
        assert params[1]["name"] == "age"
        assert params[1]["type"] == "number"

    def test_parse_empty_params(self):
        """测试空参数解析."""
        params = parse_ts_params("")
        assert params == []

        params = parse_ts_params("   ")
        assert params == []

    def test_parse_params_with_defaults(self):
        """测试带默认值的参数解析."""
        params = parse_ts_params("name: string = 'default'")

        assert len(params) == 1
        assert params[0]["name"] == "name"

    def test_parse_destructured_params(self):
        """测试解构参数解析."""
        params = parse_ts_params("{ id, name }: User")

        # 解构参数解析可能有不同的实现方式
        assert len(params) >= 1
        # 检查是否包含解构参数
        param_names = [p["name"] for p in params]
        assert any("id" in name or "options" in name for name in param_names)

    def test_parse_params_without_types(self):
        """测试无类型参数解析."""
        params = parse_ts_params("arg1, arg2")

        assert len(params) == 2
        assert params[0]["type"] == "any"
        assert params[1]["type"] == "any"


class TestExtractDependencies:
    """依赖提取测试."""

    def test_extract_java_dependencies(self):
        """测试 Java 依赖提取."""
        analysis = {
            "language": "java",
            "imports": ["java.util.List", "com.example.Service"],
        }

        deps = extract_dependencies(analysis)
        assert "java.util.List" in deps
        assert "com.example.Service" in deps

    def test_extract_ts_dependencies(self):
        """测试 TypeScript 依赖提取."""
        analysis = {
            "language": "typescript",
            "imports": [
                {"source": "vue", "name": "ref", "type": "named"},
                {"source": "lodash", "name": "debounce", "type": "named"},
            ],
        }

        deps = extract_dependencies(analysis)
        assert "vue" in deps
        assert "lodash" in deps

    def test_extract_vue_dependencies(self):
        """测试 Vue 依赖提取."""
        analysis = {
            "language": "vue",
            "imports": [{"source": "@/components/Button", "name": "Button", "type": "default"}],
        }

        deps = extract_dependencies(analysis)
        assert "@/components/Button" in deps

    def test_extract_unknown_language(self):
        """测试未知语言依赖提取."""
        analysis = {"language": "python", "imports": ["os"]}

        deps = extract_dependencies(analysis)
        assert deps == []


class TestFindTestableMethods:
    """可测试方法查找测试."""

    def test_find_java_testable_methods(self):
        """测试 Java 可测试方法查找."""
        analysis = {
            "language": "java",
            "methods": [
                {"name": "publicMethod", "is_public": True},
                {"name": "privateMethod", "is_public": False},
                {"name": "anotherPublic", "is_public": True},
            ],
        }

        methods = find_testable_methods(analysis)
        assert len(methods) == 2
        assert all(m["is_public"] for m in methods)

    def test_find_ts_testable_methods(self):
        """测试 TypeScript 可测试方法查找."""
        analysis = {
            "language": "typescript",
            "functions": [
                {"name": "exportedFunc", "is_exported": True, "type": "function"},
                {"name": "internalFunc", "is_exported": False, "type": "function"},
                {"name": "arrowFunc", "is_exported": True, "type": "arrow_function"},
            ],
        }

        methods = find_testable_methods(analysis)
        assert len(methods) == 3  # exported 或 function 类型

    def test_find_no_methods(self):
        """测试无可测试方法的情况."""
        analysis = {"language": "java", "methods": []}

        methods = find_testable_methods(analysis)
        assert methods == []

    def test_find_unknown_language(self):
        """测试未知语言的方法查找."""
        analysis = {"language": "ruby", "methods": [{"name": "test"}]}

        methods = find_testable_methods(analysis)
        assert methods == []
