"""测试数据生成器单元测试."""

import pytest
from ut_agent.tools.test_data_generator import (
    BoundaryValue,
    TypeBoundaryValues,
    DataType,
    PrimitiveBoundaryGenerator,
    StringBoundaryGenerator,
    CollectionBoundaryGenerator,
    BoundaryValueGenerator,
    format_test_data_for_prompt,
)


class TestBoundaryValue:
    """BoundaryValue 测试."""

    def test_boundary_value_creation(self):
        """测试边界值创建."""
        bv = BoundaryValue(value=0, description="零值", category="normal")
        assert bv.value == 0
        assert bv.description == "零值"
        assert bv.category == "normal"


class TestTypeBoundaryValues:
    """TypeBoundaryValues 测试."""

    def test_get_values_by_category(self):
        """测试按类别获取边界值."""
        values = [
            BoundaryValue(0, "零值", "normal"),
            BoundaryValue(-1, "负数", "normal"),
            BoundaryValue(2147483647, "最大值", "max"),
        ]
        tbv = TypeBoundaryValues(type_name="int", language="java", values=values)

        normal_values = tbv.get_values_by_category("normal")
        assert len(normal_values) == 2

        max_values = tbv.get_values_by_category("max")
        assert len(max_values) == 1
        assert max_values[0].value == 2147483647


class TestPrimitiveBoundaryGenerator:
    """PrimitiveBoundaryGenerator 测试."""

    def test_get_java_int_boundaries(self):
        """测试获取 Java int 边界值."""
        boundaries = PrimitiveBoundaryGenerator.get_java_boundaries("int")
        assert len(boundaries) > 0

        values = [b.value for b in boundaries]
        assert 0 in values
        assert 2147483647 in values
        assert -2147483648 in values

    def test_get_java_integer_boundaries(self):
        """测试获取 Java Integer 边界值（包装类）."""
        boundaries = PrimitiveBoundaryGenerator.get_java_boundaries("Integer")
        assert len(boundaries) > 0

    def test_get_java_float_boundaries(self):
        """测试获取 Java float 边界值."""
        boundaries = PrimitiveBoundaryGenerator.get_java_boundaries("float")
        assert len(boundaries) > 0

        values = [b.value for b in boundaries]
        assert 0.0 in values
        assert any(v != v for v in values if isinstance(v, float))

    def test_get_java_boolean_boundaries(self):
        """测试获取 Java boolean 边界值."""
        boundaries = PrimitiveBoundaryGenerator.get_java_boundaries("boolean")
        assert len(boundaries) == 2

        values = [b.value for b in boundaries]
        assert True in values
        assert False in values

    def test_get_typescript_number_boundaries(self):
        """测试获取 TypeScript number 边界值."""
        boundaries = PrimitiveBoundaryGenerator.get_typescript_boundaries("number")
        assert len(boundaries) > 0

        values = [b.value for b in boundaries]
        assert 0 in values

    def test_get_unknown_type_boundaries(self):
        """测试获取未知类型边界值."""
        boundaries = PrimitiveBoundaryGenerator.get_java_boundaries("UnknownType")
        assert boundaries == []


class TestStringBoundaryGenerator:
    """StringBoundaryGenerator 测试."""

    def test_get_string_boundaries(self):
        """测试获取字符串边界值."""
        boundaries = StringBoundaryGenerator.get_boundaries("java")
        assert len(boundaries) > 0

        values = [b.value for b in boundaries]
        assert "" in values
        assert " " in values

    def test_string_boundary_categories(self):
        """测试字符串边界值类别."""
        boundaries = StringBoundaryGenerator.get_boundaries("java")

        categories = {b.category for b in boundaries}
        assert "empty" in categories
        assert "whitespace" in categories
        assert "normal" in categories


class TestCollectionBoundaryGenerator:
    """CollectionBoundaryGenerator 测试."""

    def test_generate_list_boundaries(self):
        """测试生成 List 边界值."""
        boundaries = CollectionBoundaryGenerator.generate_list_boundaries("int", "java")
        assert len(boundaries) > 0

        values = [b.value for b in boundaries]
        assert [] in values
        assert [1] in values

    def test_generate_set_boundaries(self):
        """测试生成 Set 边界值."""
        boundaries = CollectionBoundaryGenerator.generate_set_boundaries("string", "java")
        assert len(boundaries) > 0

        values = [b.value for b in boundaries]
        assert set() in values

    def test_generate_map_boundaries(self):
        """测试生成 Map 边界值."""
        boundaries = CollectionBoundaryGenerator.generate_map_boundaries("string", "int", "java")
        assert len(boundaries) > 0

        values = [b.value for b in boundaries]
        assert {} in values


class TestBoundaryValueGenerator:
    """BoundaryValueGenerator 测试."""

    def test_init_java(self):
        """测试初始化 Java 生成器."""
        generator = BoundaryValueGenerator(language="java")
        assert generator.language == "java"

    def test_init_typescript(self):
        """测试初始化 TypeScript 生成器."""
        generator = BoundaryValueGenerator(language="typescript")
        assert generator.language == "typescript"

    def test_generate_primitive_boundary_values(self):
        """测试生成基本类型边界值."""
        generator = BoundaryValueGenerator(language="java")

        result = generator.generate_boundary_values({"type_name": "int"})
        assert result.type_name == "int"
        assert len(result.values) > 0

    def test_generate_string_boundary_values(self):
        """测试生成字符串边界值."""
        generator = BoundaryValueGenerator(language="java")

        result = generator.generate_boundary_values({"type_name": "String"})
        assert result.type_name == "String"
        assert len(result.values) > 0

    def test_generate_list_boundary_values(self):
        """测试生成 List 边界值."""
        generator = BoundaryValueGenerator(language="java")

        result = generator.generate_boundary_values({
            "type_name": "List",
            "generic_args": ["String"],
        })
        assert result.type_name == "List"
        assert len(result.values) > 0

    def test_generate_boundary_values_with_category_filter(self):
        """测试带类别过滤的边界值生成."""
        generator = BoundaryValueGenerator(language="java")

        result = generator.generate_boundary_values(
            {"type_name": "int"},
            include_categories=["normal", "max"],
        )

        for v in result.values:
            assert v.category in ["normal", "max"]

    def test_generate_boundary_values_with_exclude_categories(self):
        """测试排除类别的边界值生成."""
        generator = BoundaryValueGenerator(language="java")

        result = generator.generate_boundary_values(
            {"type_name": "int"},
            exclude_categories=["special"],
        )

        for v in result.values:
            assert v.category != "special"

    def test_generate_test_data_for_method(self):
        """测试为方法生成测试数据."""
        generator = BoundaryValueGenerator(language="java")

        method_info = {
            "name": "calculate",
            "parameters": [
                {"name": "value", "type": "int"},
                {"name": "name", "type": "String"},
            ],
        }

        result = generator.generate_test_data_for_method(method_info)

        assert "value" in result
        assert "name" in result
        assert len(result["value"]) > 0
        assert len(result["name"]) > 0

    def test_generate_test_data_for_method_max_values(self):
        """测试限制每个参数的最大边界值数量."""
        generator = BoundaryValueGenerator(language="java")

        method_info = {
            "name": "calculate",
            "parameters": [
                {"name": "value", "type": "int"},
            ],
        }

        result = generator.generate_test_data_for_method(method_info, max_values_per_param=2)

        assert len(result["value"]) <= 2

    def test_generate_combinatorial_test_cases(self):
        """测试生成组合测试用例."""
        generator = BoundaryValueGenerator(language="java")

        method_info = {
            "name": "add",
            "parameters": [
                {"name": "a", "type": "int"},
                {"name": "b", "type": "int"},
            ],
        }

        test_cases = generator.generate_combinatorial_test_cases(method_info, max_cases=10)

        assert len(test_cases) <= 10
        assert len(test_cases) > 0

        for case in test_cases:
            assert "params" in case
            assert "description" in case

    def test_generate_combinatorial_test_cases_no_params(self):
        """测试无参数方法的组合测试用例."""
        generator = BoundaryValueGenerator(language="java")

        method_info = {
            "name": "noop",
            "parameters": [],
        }

        test_cases = generator.generate_combinatorial_test_cases(method_info)

        assert len(test_cases) == 1
        assert test_cases[0]["params"] == {}

    def test_is_primitive_java(self):
        """测试 Java 基本类型判断."""
        generator = BoundaryValueGenerator(language="java")

        assert generator._is_primitive("int")
        assert generator._is_primitive("Integer")
        assert generator._is_primitive("long")
        assert generator._is_primitive("double")
        assert not generator._is_primitive("String")
        assert not generator._is_primitive("List")

    def test_is_primitive_typescript(self):
        """测试 TypeScript 基本类型判断."""
        generator = BoundaryValueGenerator(language="typescript")

        assert generator._is_primitive("number")
        assert generator._is_primitive("Number")
        assert generator._is_primitive("boolean")
        assert not generator._is_primitive("string")
        assert not generator._is_primitive("Array")

    def test_is_string(self):
        """测试字符串类型判断."""
        generator = BoundaryValueGenerator(language="java")

        assert generator._is_string("String")
        assert generator._is_string("string")
        assert not generator._is_string("int")

    def test_is_collection_java(self):
        """测试 Java 集合类型判断."""
        generator = BoundaryValueGenerator(language="java")

        assert generator._is_collection("List")
        assert generator._is_collection("ArrayList")
        assert generator._is_collection("Set")
        assert generator._is_collection("Map")
        assert not generator._is_collection("String")

    def test_is_collection_typescript(self):
        """测试 TypeScript 集合类型判断."""
        generator = BoundaryValueGenerator(language="typescript")

        assert generator._is_collection("Array")
        assert generator._is_collection("Set")
        assert generator._is_collection("Map")
        assert not generator._is_collection("string")


class TestFormatTestDataForPrompt:
    """format_test_data_for_prompt 测试."""

    def test_format_empty_data(self):
        """测试格式化空数据."""
        result = format_test_data_for_prompt({})
        assert "无参数边界值数据" in result

    def test_format_single_param(self):
        """测试格式化单参数数据."""
        test_data = {
            "value": [
                {"value": 0, "description": "零值", "category": "normal"},
                {"value": 1, "description": "正数", "category": "normal"},
            ],
        }

        result = format_test_data_for_prompt(test_data, language="java")

        assert "参数 value:" in result
        assert "零值" in result
        assert "正数" in result

    def test_format_multiple_params(self):
        """测试格式化多参数数据."""
        test_data = {
            "a": [{"value": 0, "description": "零", "category": "normal"}],
            "b": [{"value": "", "description": "空字符串", "category": "empty"}],
        }

        result = format_test_data_for_prompt(test_data, language="java")

        assert "参数 a:" in result
        assert "参数 b:" in result

    def test_format_null_value(self):
        """测试格式化 null 值."""
        test_data = {
            "name": [{"value": None, "description": "null值", "category": "null"}],
        }

        result = format_test_data_for_prompt(test_data, language="java")
        assert "null" in result

    def test_format_boolean_value(self):
        """测试格式化布尔值."""
        test_data = {
            "flag": [
                {"value": True, "description": "真", "category": "normal"},
                {"value": False, "description": "假", "category": "normal"},
            ],
        }

        result = format_test_data_for_prompt(test_data, language="java")
        assert "true" in result or "false" in result

    def test_format_list_value(self):
        """测试格式化列表值."""
        test_data = {
            "items": [{"value": [], "description": "空列表", "category": "empty"}],
        }

        result = format_test_data_for_prompt(test_data, language="java")
        assert "List" in result or "elements" in result

    def test_format_nan_value(self):
        """测试格式化 NaN 值."""
        test_data = {
            "num": [{"value": float('nan'), "description": "NaN", "category": "special"}],
        }

        result = format_test_data_for_prompt(test_data, language="java")
        assert "NaN" in result

    def test_format_infinity_value(self):
        """测试格式化无穷大值."""
        test_data = {
            "num": [
                {"value": float('inf'), "description": "正无穷", "category": "special"},
                {"value": float('-inf'), "description": "负无穷", "category": "special"},
            ],
        }

        result = format_test_data_for_prompt(test_data, language="java")
        assert "Infinity" in result or "无穷" in result
