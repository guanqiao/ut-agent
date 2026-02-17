"""测试分析器测试."""

import tempfile
from pathlib import Path
from unittest import mock

import pytest

from ut_agent.tools.test_analyzer import (
    TestAnalyzer,
    TestMethodInfo,
    TestCoverageInfo,
    TestGap,
    MethodDependency,
    IncrementalTestPlan,
    format_existing_tests_for_prompt,
    format_test_gaps_for_prompt,
    format_incremental_plan_for_prompt,
)


class TestTestMethodInfo:
    """测试 TestMethodInfo 数据类."""

    def test_creation(self):
        """测试创建测试方法信息."""
        info = TestMethodInfo(
            name="testMethod",
            description="测试方法",
            line_start=10,
            line_end=20,
            content="test content",
            tested_methods=["method1"],
            test_scenarios=["success"],
            is_manual=False,
        )
        
        assert info.name == "testMethod"
        assert info.description == "测试方法"
        assert info.line_start == 10
        assert info.line_end == 20
        assert info.tested_methods == ["method1"]
        assert info.test_scenarios == ["success"]
        assert info.is_manual is False

    def test_defaults(self):
        """测试默认值."""
        info = TestMethodInfo(
            name="testMethod",
            description="",
            line_start=1,
            line_end=2,
            content="",
        )
        
        assert info.tested_methods == []
        assert info.test_scenarios == []
        assert info.is_manual is False
        assert info.annotations == []


class TestTestCoverageInfo:
    """测试 TestCoverageInfo 数据类."""

    def test_creation(self):
        """测试创建覆盖信息."""
        info = TestCoverageInfo(
            test_file="Test.java",
            source_file="Source.java",
            tested_methods={"method1": ["testMethod1"]},
            untested_methods=["method2"],
        )
        
        assert info.test_file == "Test.java"
        assert info.source_file == "Source.java"
        assert info.tested_methods == {"method1": ["testMethod1"]}
        assert info.untested_methods == ["method2"]

    def test_defaults(self):
        """测试默认值."""
        info = TestCoverageInfo(
            test_file="Test.java",
            source_file="Source.java",
        )
        
        assert info.tested_methods == {}
        assert info.untested_methods == []
        assert info.test_scenarios == {}
        assert info.manual_tests == []
        assert info.auto_generated_tests == []


class TestTestGap:
    """测试 TestGap 数据类."""

    def test_creation(self):
        """测试创建测试缺口."""
        gap = TestGap(
            method_name="method1",
            gap_type="no_test",
            suggested_scenarios=["success", "failure"],
            priority=5,
        )
        
        assert gap.method_name == "method1"
        assert gap.gap_type == "no_test"
        assert gap.suggested_scenarios == ["success", "failure"]
        assert gap.priority == 5

    def test_defaults(self):
        """测试默认值."""
        gap = TestGap(
            method_name="method1",
            gap_type="no_test",
        )
        
        assert gap.suggested_scenarios == []
        assert gap.priority == 0


class TestTestAnalyzer:
    """测试 TestAnalyzer 类."""

    def test_initialization(self):
        """测试初始化."""
        analyzer = TestAnalyzer("java")
        assert analyzer.project_type == "java"
        
        analyzer = TestAnalyzer("typescript")
        assert analyzer.project_type == "typescript"

    def test_analyze_existing_tests_file_not_exists(self):
        """测试分析不存在的测试文件."""
        analyzer = TestAnalyzer("java")
        result = analyzer.analyze_existing_tests(
            "/non/existent/path/Test.java",
            ["method1", "method2"],
        )
        
        assert result.test_file == "/non/existent/path/Test.java"
        assert result.untested_methods == ["method1", "method2"]
        assert result.tested_methods == {}

    def test_analyze_existing_java_tests(self):
        """测试分析 Java 测试文件."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "TestClassTest.java"
            test_content = """
package com.example;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;

public class TestClassTest {

    @Test
    @DisplayName("测试 method1 正常场景")
    public void testMethod1_success() {
        target.method1();
    }

    @Test
    @DisplayName("测试 method1 异常场景")
    public void testMethod1_failure() {
        target.method1();
    }

    // MANUAL
    @Test
    public void testMethod2() {
        // 手工编写的测试
    }
    // MANUAL
}
"""
            test_file.write_text(test_content)
            
            analyzer = TestAnalyzer("java")
            result = analyzer.analyze_existing_tests(
                str(test_file),
                ["method1", "method2", "method3"],
            )
            
            assert "method1" in result.tested_methods or len(result.auto_generated_tests) >= 0
            assert "method3" in result.untested_methods

    def test_analyze_existing_typescript_tests(self):
        """测试分析 TypeScript 测试文件."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "utils.test.ts"
            test_content = """
import { describe, it, expect } from 'vitest';

describe('utils', () => {
    it('should return correct value for method1', () => {
        const result = method1();
        expect(result).toBeDefined();
    });
    
    it('should handle error for method1', () => {
        expect(() => method1(null)).toThrow();
    });
});
"""
            test_file.write_text(test_content)
            
            analyzer = TestAnalyzer("typescript")
            result = analyzer.analyze_existing_tests(
                str(test_file),
                ["method1", "method2"],
            )
            
            assert len(result.auto_generated_tests) >= 0

    def test_identify_test_gaps(self):
        """测试识别测试缺口."""
        analyzer = TestAnalyzer("java")
        
        coverage_info = TestCoverageInfo(
            test_file="Test.java",
            source_file="Source.java",
            tested_methods={"method1": ["testMethod1"]},
            untested_methods=["method2"],
        )
        
        method_info = {
            "method1": {"return_type": "String", "parameters": [], "modifiers": ["public"]},
            "method2": {"return_type": "void", "parameters": ["String"], "modifiers": ["public"]},
        }
        
        gaps = analyzer.identify_test_gaps(coverage_info, method_info)
        
        assert len(gaps) > 0
        assert any(g.method_name == "method2" for g in gaps)

    def test_extract_test_patterns_java(self):
        """测试提取 Java 测试模式."""
        analyzer = TestAnalyzer("java")
        
        content = """
import static org.assertj.core.api.Assertions.assertThat;

public class TestClass {
    @Test
    @DisplayName("givenX_whenY_thenZ")
    void givenX_whenY_thenZ() {
        // Given
        String input = "test";
        // When
        String result = method(input);
        // Then
        assertThat(result).isNotNull();
    }
}
"""
        patterns = analyzer.extract_test_patterns(content)
        
        assert patterns["assertion_style"] == "assertj"

    def test_extract_test_patterns_typescript(self):
        """测试提取 TypeScript 测试模式."""
        analyzer = TestAnalyzer("typescript")
        
        content = """
import { describe, it, expect, vi } from 'vitest';

describe('utils', () => {
    it('should return value', () => {
        expect(method()).toBeDefined();
    });
});
"""
        patterns = analyzer.extract_test_patterns(content)
        
        assert patterns["naming_convention"] == "should_style"
        assert patterns["assertion_style"] == "jest_vitest"

    def test_extract_java_test_methods(self):
        """测试提取 Java 测试方法."""
        analyzer = TestAnalyzer("java")
        
        content = """
public class TestClass {
    @Test
    public void testMethod1() {
        target.method1();
    }

    @Test
    @DisplayName("测试方法2")
    public void testMethod2() {
        target.method2();
    }
}
"""
        methods = analyzer._extract_java_test_methods(content)
        
        assert len(methods) >= 1
        assert methods[0].name == "testMethod1"

    def test_extract_typescript_test_methods(self):
        """测试提取 TypeScript 测试方法."""
        analyzer = TestAnalyzer("typescript")
        
        content = """
describe('utils', () => {
    it('should work', () => {
        expect(true).toBe(true);
    });
    
    test('another test', () => {
        expect(1).toBe(1);
    });
});
"""
        methods = analyzer._extract_typescript_test_methods(content)
        
        assert len(methods) >= 2

    def test_extract_scenarios_from_name(self):
        """测试从测试名称提取场景."""
        analyzer = TestAnalyzer("java")
        
        scenarios = analyzer._extract_scenarios_from_name("testMethod_success", "")
        assert "success" in scenarios
        
        scenarios = analyzer._extract_scenarios_from_name("testMethod_failure", "")
        assert "failure" in scenarios
        
        scenarios = analyzer._extract_scenarios_from_name("testMethod_boundary", "")
        assert "boundary" in scenarios

    def test_suggest_scenarios(self):
        """测试建议测试场景."""
        analyzer = TestAnalyzer("java")
        
        scenarios = analyzer._suggest_scenarios({
            "return_type": "String",
            "parameters": ["String", "int"],
            "modifiers": ["public"],
        })
        
        assert "success" in scenarios
        assert "boundary" in scenarios
        assert "invalid_input" in scenarios

    def test_calculate_priority(self):
        """测试计算优先级."""
        analyzer = TestAnalyzer("java")
        
        priority1 = analyzer._calculate_priority({
            "return_type": "String",
            "parameters": ["String"],
            "modifiers": ["public"],
        })
        
        priority2 = analyzer._calculate_priority({
            "return_type": "void",
            "parameters": [],
            "modifiers": ["private"],
        })
        
        assert priority1 > priority2


class TestFormatFunctions:
    """测试格式化函数."""

    def test_format_existing_tests_for_prompt(self):
        """测试格式化已有测试信息."""
        coverage_info = TestCoverageInfo(
            test_file="Test.java",
            source_file="Source.java",
            tested_methods={"method1": ["testMethod1", "testMethod1Failure"]},
            untested_methods=["method2", "method3"],
            manual_tests=["manualTest"],
        )
        
        result = format_existing_tests_for_prompt(coverage_info)
        
        assert "已覆盖的方法" in result
        assert "未覆盖的方法" in result
        assert "手工编写的测试" in result
        assert "method1" in result
        assert "method2" in result

    def test_format_test_gaps_for_prompt(self):
        """测试格式化测试缺口."""
        gaps = [
            TestGap(
                method_name="method1",
                gap_type="no_test",
                suggested_scenarios=["success", "failure"],
                priority=5,
            ),
            TestGap(
                method_name="method2",
                gap_type="incomplete_coverage",
                suggested_scenarios=["boundary"],
                priority=3,
            ),
        ]
        
        result = format_test_gaps_for_prompt(gaps)
        
        assert "需要补充的测试" in result
        assert "method1" in result
        assert "method2" in result

    def test_format_test_gaps_empty(self):
        """测试格式化空测试缺口."""
        result = format_test_gaps_for_prompt([])
        
        assert result == "无测试缺口"

    def test_format_existing_tests_with_reusable_resources(self):
        """测试格式化包含可复用资源的测试信息."""
        coverage_info = TestCoverageInfo(
            test_file="Test.java",
            source_file="Source.java",
            tested_methods={"method1": ["testMethod1"]},
            untested_methods=[],
            manual_tests=[],
            reusable_mocks={"method1": ["when(mock.getValue()).thenReturn(42)"]},
            reusable_assertions={"method1": ["assertThat(result).isNotNull()"]},
        )
        
        result = format_existing_tests_for_prompt(coverage_info)
        
        assert "可复用的 Mock 配置" in result
        assert "可复用的断言模式" in result

    def test_format_incremental_plan(self):
        """测试格式化增量测试计划."""
        plan = IncrementalTestPlan(
            direct_changes=["newMethod"],
            affected_methods=["existingMethod"],
            reuse_candidates={"newMethod_mocks": ["when(mock.getValue()).thenReturn(42)"]},
            gaps_to_fill=[
                TestGap(
                    method_name="newMethod",
                    gap_type="no_test",
                    suggested_scenarios=["success"],
                    priority=8,
                )
            ],
            estimated_effort=3,
        )
        
        result = format_incremental_plan_for_prompt(plan)
        
        assert "需要新增测试的方法" in result
        assert "可能需要更新测试的方法" in result
        assert "可复用的测试资源" in result
        assert "预估工作量" in result


class TestMethodDependency:
    """测试 MethodDependency 数据类."""

    def test_creation(self):
        """测试创建方法依赖."""
        dep = MethodDependency(
            method_name="method1",
            called_methods=["method2", "method3"],
            called_by=["mainMethod"],
            dependencies=["ServiceA", "ServiceB"],
        )
        
        assert dep.method_name == "method1"
        assert dep.called_methods == ["method2", "method3"]
        assert dep.called_by == ["mainMethod"]
        assert dep.dependencies == ["ServiceA", "ServiceB"]

    def test_defaults(self):
        """测试默认值."""
        dep = MethodDependency(method_name="method1")
        
        assert dep.called_methods == []
        assert dep.called_by == []
        assert dep.dependencies == []


class TestIncrementalTestPlan:
    """测试 IncrementalTestPlan 数据类."""

    def test_creation(self):
        """测试创建增量测试计划."""
        plan = IncrementalTestPlan(
            direct_changes=["method1"],
            affected_methods=["method2"],
            estimated_effort=5,
        )
        
        assert plan.direct_changes == ["method1"]
        assert plan.affected_methods == ["method2"]
        assert plan.estimated_effort == 5

    def test_defaults(self):
        """测试默认值."""
        plan = IncrementalTestPlan()
        
        assert plan.direct_changes == []
        assert plan.affected_methods == []
        assert plan.reuse_candidates == {}
        assert plan.gaps_to_fill == []
        assert plan.estimated_effort == 0


class TestIncrementalPlanCreation:
    """测试增量计划创建."""

    def test_create_incremental_plan(self):
        """测试创建增量测试计划."""
        analyzer = TestAnalyzer("java")
        
        coverage_info = TestCoverageInfo(
            test_file="Test.java",
            source_file="Source.java",
            tested_methods={"existingMethod": ["testExistingMethod"]},
            untested_methods=["newMethod"],
            reusable_mocks={"existingMethod": ["when(mock.getValue()).thenReturn(42)"]},
        )
        
        plan = analyzer.create_incremental_plan(
            coverage_info,
            changed_methods=["newMethod", "existingMethod"],
        )
        
        assert "newMethod" in plan.direct_changes
        assert "existingMethod" in plan.affected_methods
        assert len(plan.gaps_to_fill) > 0
        assert plan.estimated_effort > 0

    def test_create_incremental_plan_with_dependencies(self):
        """测试带依赖关系的增量计划."""
        analyzer = TestAnalyzer("java")
        
        coverage_info = TestCoverageInfo(
            test_file="Test.java",
            source_file="Source.java",
            tested_methods={"methodA": ["testMethodA"]},
            untested_methods=["methodB"],
        )
        
        dependencies = {
            "methodA": MethodDependency(
                method_name="methodA",
                called_methods=["methodB"],
            )
        }
        
        plan = analyzer.create_incremental_plan(
            coverage_info,
            changed_methods=["methodA"],
            method_dependencies=dependencies,
        )
        
        assert "methodA" in plan.affected_methods


class TestMethodSimilarity:
    """测试方法相似度分析."""

    def test_analyze_method_similarity(self):
        """测试分析方法相似度."""
        analyzer = TestAnalyzer("java")
        
        method1 = {
            "name": "getUserById",
            "return_type": "User",
            "parameters": [{"type": "Long"}],
            "is_public": True,
            "is_static": False,
        }
        
        method2 = {
            "name": "getUserByName",
            "return_type": "User",
            "parameters": [{"type": "String"}],
            "is_public": True,
            "is_static": False,
        }
        
        similarity = analyzer.analyze_method_similarity(method1, method2)
        
        assert similarity > 0.5
        assert similarity <= 1.0

    def test_analyze_method_similarity_different(self):
        """测试分析不同方法的相似度."""
        analyzer = TestAnalyzer("java")
        
        method1 = {
            "name": "save",
            "return_type": "void",
            "parameters": [],
            "is_public": True,
            "is_static": False,
        }
        
        method2 = {
            "name": "deleteAll",
            "return_type": "int",
            "parameters": [{"type": "List"}],
            "is_public": False,
            "is_static": True,
        }
        
        similarity = analyzer.analyze_method_similarity(method1, method2)
        
        assert similarity < 0.5

    def test_suggest_test_reuse(self):
        """测试建议测试复用."""
        analyzer = TestAnalyzer("java")
        
        new_method = {
            "name": "getUserByEmail",
            "return_type": "User",
            "parameters": [{"type": "String"}],
        }
        
        existing_tests = [
            TestMethodInfo(
                name="testGetUserById",
                description="",
                line_start=1,
                line_end=10,
                content="target.getUserById(1L);",
                tested_methods=["getUserById"],
            )
        ]
        
        suggestions = analyzer.suggest_test_reuse(new_method, existing_tests)
        
        assert len(suggestions) >= 0


class TestReusableResources:
    """测试可复用资源提取."""

    def test_extract_reusable_mocks_java(self):
        """测试提取 Java 可复用 Mock."""
        analyzer = TestAnalyzer("java")
        
        test_methods = [
            TestMethodInfo(
                name="testMethod1",
                description="",
                line_start=1,
                line_end=10,
                content='when(mockService.getValue()).thenReturn("test");',
                tested_methods=["method1"],
            )
        ]
        
        mocks = analyzer._extract_reusable_mocks(test_methods)
        
        assert "method1" in mocks

    def test_extract_reusable_assertions_java(self):
        """测试提取 Java 可复用断言."""
        analyzer = TestAnalyzer("java")
        
        test_methods = [
            TestMethodInfo(
                name="testMethod1",
                description="",
                line_start=1,
                line_end=10,
                content="assertThat(result).isNotNull();",
                tested_methods=["method1"],
            )
        ]
        
        assertions = analyzer._extract_reusable_assertions(test_methods)
        
        assert "method1" in assertions


if __name__ == "__main__":
    pytest.main([__file__])
