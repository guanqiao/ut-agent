"""测试数据生成器 - 基于类型自动生成边界值."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import random
import string


class DataType(Enum):
    """数据类型枚举."""
    INT = "int"
    LONG = "long"
    FLOAT = "float"
    DOUBLE = "double"
    BOOLEAN = "boolean"
    STRING = "string"
    CHAR = "char"
    BYTE = "byte"
    SHORT = "short"
    LIST = "list"
    SET = "set"
    MAP = "map"
    OBJECT = "object"
    OPTIONAL = "optional"
    NULL = "null"
    ANY = "any"


@dataclass
class BoundaryValue:
    """边界值数据结构."""
    value: Any
    description: str
    category: str


@dataclass
class TypeBoundaryValues:
    """类型边界值集合."""
    type_name: str
    language: str
    values: List[BoundaryValue] = field(default_factory=list)

    def get_values_by_category(self, category: str) -> List[BoundaryValue]:
        """按类别获取边界值."""
        return [v for v in self.values if v.category == category]


class PrimitiveBoundaryGenerator:
    """基本类型边界值生成器."""

    JAVA_INT_BOUNDARIES: List[BoundaryValue] = [
        BoundaryValue(0, "零值", "normal"),
        BoundaryValue(1, "正数最小值", "normal"),
        BoundaryValue(-1, "负数最小值", "normal"),
        BoundaryValue(2147483647, "int最大值", "max"),
        BoundaryValue(-2147483648, "int最小值", "min"),
        BoundaryValue(100, "常规正数", "normal"),
        BoundaryValue(-100, "常规负数", "normal"),
    ]

    JAVA_LONG_BOUNDARIES: List[BoundaryValue] = [
        BoundaryValue(0, "零值", "normal"),
        BoundaryValue(1, "正数最小值", "normal"),
        BoundaryValue(-1, "负数最小值", "normal"),
        BoundaryValue(9223372036854775807, "long最大值", "max"),
        BoundaryValue(-9223372036854775808, "long最小值", "min"),
    ]

    JAVA_FLOAT_BOUNDARIES: List[BoundaryValue] = [
        BoundaryValue(0.0, "零值", "normal"),
        BoundaryValue(1.0, "正常正数", "normal"),
        BoundaryValue(-1.0, "正常负数", "normal"),
        BoundaryValue(3.4028235E38, "float最大值", "max"),
        BoundaryValue(-3.4028235E38, "float最小值", "min"),
        BoundaryValue(1.4E-45, "float最小正数", "min_positive"),
        BoundaryValue(float('inf'), "正无穷", "special"),
        BoundaryValue(float('-inf'), "负无穷", "special"),
        BoundaryValue(float('nan'), "NaN", "special"),
    ]

    JAVA_DOUBLE_BOUNDARIES: List[BoundaryValue] = [
        BoundaryValue(0.0, "零值", "normal"),
        BoundaryValue(1.0, "正常正数", "normal"),
        BoundaryValue(-1.0, "正常负数", "normal"),
        BoundaryValue(1.7976931348623157E308, "double最大值", "max"),
        BoundaryValue(-1.7976931348623157E308, "double最小值", "min"),
        BoundaryValue(4.9E-324, "double最小正数", "min_positive"),
        BoundaryValue(float('inf'), "正无穷", "special"),
        BoundaryValue(float('-inf'), "负无穷", "special"),
        BoundaryValue(float('nan'), "NaN", "special"),
    ]

    JAVA_BOOLEAN_BOUNDARIES: List[BoundaryValue] = [
        BoundaryValue(True, "真值", "normal"),
        BoundaryValue(False, "假值", "normal"),
    ]

    JAVA_CHAR_BOUNDARIES: List[BoundaryValue] = [
        BoundaryValue('a', "小写字母", "normal"),
        BoundaryValue('A', "大写字母", "normal"),
        BoundaryValue('0', "数字字符", "normal"),
        BoundaryValue(' ', "空格字符", "whitespace"),
        BoundaryValue('\n', "换行符", "whitespace"),
        BoundaryValue('\t', "制表符", "whitespace"),
        BoundaryValue('\0', "空字符", "special"),
        BoundaryValue(chr(65535), "char最大值", "max"),
        BoundaryValue(chr(0), "char最小值", "min"),
    ]

    JAVA_BYTE_BOUNDARIES: List[BoundaryValue] = [
        BoundaryValue(0, "零值", "normal"),
        BoundaryValue(1, "正数最小值", "normal"),
        BoundaryValue(-1, "负数最小值", "normal"),
        BoundaryValue(127, "byte最大值", "max"),
        BoundaryValue(-128, "byte最小值", "min"),
    ]

    JAVA_SHORT_BOUNDARIES: List[BoundaryValue] = [
        BoundaryValue(0, "零值", "normal"),
        BoundaryValue(1, "正数最小值", "normal"),
        BoundaryValue(-1, "负数最小值", "normal"),
        BoundaryValue(32767, "short最大值", "max"),
        BoundaryValue(-32768, "short最小值", "min"),
    ]

    TYPESCRIPT_NUMBER_BOUNDARIES: List[BoundaryValue] = [
        BoundaryValue(0, "零值", "normal"),
        BoundaryValue(1, "正数最小值", "normal"),
        BoundaryValue(-1, "负数最小值", "normal"),
        BoundaryValue(9007199254740991, "安全整数最大值", "max"),
        BoundaryValue(-9007199254740991, "安全整数最小值", "min"),
        BoundaryValue(1.7976931348623157E308, "number最大值", "max"),
        BoundaryValue(5E-324, "number最小正值", "min_positive"),
        BoundaryValue(float('inf'), "正无穷", "special"),
        BoundaryValue(float('-inf'), "负无穷", "special"),
        BoundaryValue(float('nan'), "NaN", "special"),
    ]

    TYPESCRIPT_BOOLEAN_BOUNDARIES: List[BoundaryValue] = [
        BoundaryValue(True, "真值", "normal"),
        BoundaryValue(False, "假值", "normal"),
    ]

    @classmethod
    def get_java_boundaries(cls, type_name: str) -> List[BoundaryValue]:
        """获取Java类型的边界值."""
        type_map = {
            "int": cls.JAVA_INT_BOUNDARIES,
            "Integer": cls.JAVA_INT_BOUNDARIES,
            "long": cls.JAVA_LONG_BOUNDARIES,
            "Long": cls.JAVA_LONG_BOUNDARIES,
            "float": cls.JAVA_FLOAT_BOUNDARIES,
            "Float": cls.JAVA_FLOAT_BOUNDARIES,
            "double": cls.JAVA_DOUBLE_BOUNDARIES,
            "Double": cls.JAVA_DOUBLE_BOUNDARIES,
            "boolean": cls.JAVA_BOOLEAN_BOUNDARIES,
            "Boolean": cls.JAVA_BOOLEAN_BOUNDARIES,
            "char": cls.JAVA_CHAR_BOUNDARIES,
            "Character": cls.JAVA_CHAR_BOUNDARIES,
            "byte": cls.JAVA_BYTE_BOUNDARIES,
            "Byte": cls.JAVA_BYTE_BOUNDARIES,
            "short": cls.JAVA_SHORT_BOUNDARIES,
            "Short": cls.JAVA_SHORT_BOUNDARIES,
        }
        return type_map.get(type_name, [])

    @classmethod
    def get_typescript_boundaries(cls, type_name: str) -> List[BoundaryValue]:
        """获取TypeScript类型的边界值."""
        type_map = {
            "number": cls.TYPESCRIPT_NUMBER_BOUNDARIES,
            "Number": cls.TYPESCRIPT_NUMBER_BOUNDARIES,
            "boolean": cls.TYPESCRIPT_BOOLEAN_BOUNDARIES,
            "Boolean": cls.TYPESCRIPT_BOOLEAN_BOUNDARIES,
        }
        return type_map.get(type_name, [])


class StringBoundaryGenerator:
    """字符串边界值生成器."""

    JAVA_STRING_BOUNDARIES: List[BoundaryValue] = [
        BoundaryValue("", "空字符串", "empty"),
        BoundaryValue(" ", "单个空格", "whitespace"),
        BoundaryValue("  ", "多个空格", "whitespace"),
        BoundaryValue("\t", "制表符", "whitespace"),
        BoundaryValue("\n", "换行符", "whitespace"),
        BoundaryValue("\r\n", "Windows换行", "whitespace"),
        BoundaryValue("a", "单字符", "normal"),
        BoundaryValue("abc", "短字符串", "normal"),
        BoundaryValue("a" * 1000, "长字符串", "long"),
        BoundaryValue("a" * 10000, "超长字符串", "very_long"),
        BoundaryValue("中文测试", "中文字符", "unicode"),
        BoundaryValue("日本語テスト", "日文字符", "unicode"),
        BoundaryValue("🎉🎊🎁", "Emoji表情", "unicode"),
        BoundaryValue("<script>alert('xss')</script>", "XSS攻击字符串", "security"),
        BoundaryValue("'; DROP TABLE users; --", "SQL注入字符串", "security"),
        BoundaryValue("test\x00null", "包含空字符", "special"),
        BoundaryValue("test\\n\\t\\r", "转义字符", "special"),
    ]

    TYPESCRIPT_STRING_BOUNDARIES: List[BoundaryValue] = JAVA_STRING_BOUNDARIES

    @classmethod
    def get_boundaries(cls, language: str = "java") -> List[BoundaryValue]:
        """获取字符串边界值."""
        return cls.JAVA_STRING_BOUNDARIES


class CollectionBoundaryGenerator:
    """集合类型边界值生成器."""

    @staticmethod
    def generate_list_boundaries(element_type: str = "any", language: str = "java") -> List[BoundaryValue]:
        """生成List边界值."""
        return [
            BoundaryValue([], "空列表", "empty"),
            BoundaryValue([None], "包含null的列表", "null"),
            BoundaryValue([1], "单元素列表", "single"),
            BoundaryValue([1, 2, 3], "多元素列表", "normal"),
            BoundaryValue(list(range(100)), "大列表", "large"),
            BoundaryValue([1, 1, 1], "重复元素列表", "duplicate"),
            BoundaryValue([1, 2, 1], "部分重复列表", "partial_duplicate"),
        ]

    @staticmethod
    def generate_set_boundaries(element_type: str = "any", language: str = "java") -> List[BoundaryValue]:
        """生成Set边界值."""
        return [
            BoundaryValue(set(), "空集合", "empty"),
            BoundaryValue({None}, "包含null的集合", "null"),
            BoundaryValue({1}, "单元素集合", "single"),
            BoundaryValue({1, 2, 3}, "多元素集合", "normal"),
        ]

    @staticmethod
    def generate_map_boundaries(key_type: str = "string", value_type: str = "any", language: str = "java") -> List[BoundaryValue]:
        """生成Map边界值."""
        return [
            BoundaryValue({}, "空Map", "empty"),
            BoundaryValue({"key": None}, "包含null值的Map", "null"),
            BoundaryValue({"key": "value"}, "单键值对Map", "single"),
            BoundaryValue({"k1": "v1", "k2": "v2"}, "多键值对Map", "normal"),
            BoundaryValue({"": "empty_key"}, "空键Map", "special"),
            BoundaryValue({"key": ""}, "空值Map", "special"),
        ]


class BoundaryValueGenerator:
    """边界值数据生成器主类."""

    def __init__(self, language: str = "java"):
        """初始化生成器.

        Args:
            language: 目标语言 (java/typescript)
        """
        self.language = language
        self._primitive_gen = PrimitiveBoundaryGenerator()
        self._string_gen = StringBoundaryGenerator()
        self._collection_gen = CollectionBoundaryGenerator()

    def generate_boundary_values(
        self,
        type_info: Dict[str, Any],
        include_categories: Optional[List[str]] = None,
        exclude_categories: Optional[List[str]] = None,
    ) -> TypeBoundaryValues:
        """根据类型信息生成边界值.

        Args:
            type_info: 类型信息字典，包含 type_name, generic_args 等
            include_categories: 只包含的类别
            exclude_categories: 排除的类别

        Returns:
            TypeBoundaryValues: 类型边界值集合
        """
        type_name = type_info.get("type_name", "any")
        generic_args = type_info.get("generic_args", [])

        if self._is_primitive(type_name):
            values = self._generate_primitive_boundaries(type_name)
        elif self._is_string(type_name):
            values = self._string_gen.get_boundaries(self.language)
        elif self._is_collection(type_name):
            values = self._generate_collection_boundaries(type_name, generic_args)
        elif self._is_optional(type_name):
            values = self._generate_optional_boundaries(generic_args)
        else:
            values = self._generate_object_boundaries(type_name)

        if include_categories:
            values = [v for v in values if v.category in include_categories]
        if exclude_categories:
            values = [v for v in values if v.category not in exclude_categories]

        return TypeBoundaryValues(
            type_name=type_name,
            language=self.language,
            values=values,
        )

    def generate_test_data_for_method(
        self,
        method_info: Dict[str, Any],
        max_values_per_param: int = 3,
    ) -> Dict[str, List[Any]]:
        """为方法参数生成测试数据.

        Args:
            method_info: 方法信息
            max_values_per_param: 每个参数最多生成的边界值数量

        Returns:
            Dict[str, List[Any]]: 参数名到测试数据列表的映射
        """
        result = {}
        parameters = method_info.get("parameters", [])

        for param in parameters:
            param_name = param.get("name", "unknown")
            param_type = param.get("type", "any")

            type_info = {"type_name": param_type}
            boundary_values = self.generate_boundary_values(type_info)

            selected_values = self._select_representative_values(
                boundary_values.values,
                max_values_per_param,
            )

            result[param_name] = [
                {"value": v.value, "description": v.description, "category": v.category}
                for v in selected_values
            ]

        return result

    def generate_combinatorial_test_cases(
        self,
        method_info: Dict[str, Any],
        max_cases: int = 50,
    ) -> List[Dict[str, Any]]:
        """生成组合测试用例.

        Args:
            method_info: 方法信息
            max_cases: 最大测试用例数量

        Returns:
            List[Dict[str, Any]]: 测试用例列表
        """
        param_data = self.generate_test_data_for_method(method_info)
        parameters = method_info.get("parameters", [])

        if not parameters:
            return [{"params": {}, "description": "无参数调用"}]

        test_cases = []
        param_names = [p.get("name") for p in parameters]

        def generate_combinations(current_idx: int, current_params: Dict[str, Any]):
            if current_idx >= len(param_names):
                test_cases.append({
                    "params": current_params.copy(),
                    "description": self._generate_case_description(current_params),
                })
                return

            param_name = param_names[current_idx]
            values = param_data.get(param_name, [{"value": None, "description": "默认值"}])

            for v in values[:3]:
                current_params[param_name] = v["value"]
                generate_combinations(current_idx + 1, current_params)

                if len(test_cases) >= max_cases:
                    return

        generate_combinations(0, {})
        return test_cases[:max_cases]

    def _is_primitive(self, type_name: str) -> bool:
        """判断是否为基本类型."""
        java_primitives = {"int", "long", "float", "double", "boolean", "char", "byte", "short"}
        java_wrappers = {"Integer", "Long", "Float", "Double", "Boolean", "Character", "Byte", "Short"}
        ts_primitives = {"number", "boolean", "Number", "Boolean"}

        if self.language == "java":
            return type_name in java_primitives or type_name in java_wrappers
        else:
            return type_name in ts_primitives

    def _is_string(self, type_name: str) -> bool:
        """判断是否为字符串类型."""
        string_types = {"String", "string", "str"}
        return type_name in string_types

    def _is_collection(self, type_name: str) -> bool:
        """判断是否为集合类型."""
        java_collections = {"List", "ArrayList", "LinkedList", "Set", "HashSet", "TreeSet", "Map", "HashMap", "Collection"}
        ts_collections = {"Array", "array", "Set", "Map", "Record"}

        if self.language == "java":
            return type_name in java_collections
        else:
            return type_name in ts_collections

    def _is_optional(self, type_name: str) -> bool:
        """判断是否为Optional类型."""
        optional_types = {"Optional", "OptionalInt", "OptionalLong", "OptionalDouble"}
        return type_name in optional_types

    def _generate_primitive_boundaries(self, type_name: str) -> List[BoundaryValue]:
        """生成基本类型边界值."""
        if self.language == "java":
            return self._primitive_gen.get_java_boundaries(type_name)
        else:
            return self._primitive_gen.get_typescript_boundaries(type_name)

    def _generate_collection_boundaries(
        self, type_name: str, generic_args: List[str]
    ) -> List[BoundaryValue]:
        """生成集合类型边界值."""
        element_type = generic_args[0] if generic_args else "any"

        if type_name in {"Map", "HashMap", "map", "Record"}:
            value_type = generic_args[1] if len(generic_args) > 1 else "any"
            return self._collection_gen.generate_map_boundaries(
                element_type, value_type, self.language
            )
        elif type_name in {"Set", "HashSet", "set"}:
            return self._collection_gen.generate_set_boundaries(element_type, self.language)
        else:
            return self._collection_gen.generate_list_boundaries(element_type, self.language)

    def _generate_optional_boundaries(self, generic_args: List[str]) -> List[BoundaryValue]:
        """生成Optional边界值."""
        return [
            BoundaryValue(None, "空Optional", "empty"),
            BoundaryValue("value", "有值Optional", "present"),
        ]

    def _generate_object_boundaries(self, type_name: str) -> List[BoundaryValue]:
        """生成对象类型边界值."""
        return [
            BoundaryValue(None, "null对象", "null"),
            BoundaryValue({}, "空对象", "empty"),
            BoundaryValue({"field": "value"}, "有值对象", "normal"),
        ]

    def _select_representative_values(
        self,
        values: List[BoundaryValue],
        max_count: int,
    ) -> List[BoundaryValue]:
        """选择代表性的边界值."""
        if len(values) <= max_count:
            return values

        categories = {}
        for v in values:
            if v.category not in categories:
                categories[v.category] = []
            categories[v.category].append(v)

        selected = []
        priority_categories = ["empty", "null", "min", "max", "special", "normal"]

        for category in priority_categories:
            if category in categories and len(selected) < max_count:
                selected.append(categories[category][0])

        remaining = max_count - len(selected)
        if remaining > 0:
            for v in values:
                if v not in selected:
                    selected.append(v)
                    remaining -= 1
                    if remaining <= 0:
                        break

        return selected[:max_count]

    def _generate_case_description(self, params: Dict[str, Any]) -> str:
        """生成测试用例描述."""
        if not params:
            return "无参数调用"

        descriptions = []
        for name, value in params.items():
            if value is None:
                descriptions.append(f"{name}=null")
            elif isinstance(value, str):
                if len(value) > 20:
                    descriptions.append(f"{name}='长字符串'")
                else:
                    descriptions.append(f"{name}='{value}'")
            elif isinstance(value, (list, dict)):
                descriptions.append(f"{name}={type(value).__name__}({len(value)})")
            else:
                descriptions.append(f"{name}={value}")

        return ", ".join(descriptions)


def format_test_data_for_prompt(test_data: Dict[str, List[Any]], language: str = "java") -> str:
    """格式化测试数据为Prompt格式.

    Args:
        test_data: 测试数据字典
        language: 目标语言

    Returns:
        str: 格式化后的字符串
    """
    if not test_data:
        return "无参数边界值数据"

    lines = ["测试数据边界值建议:"]
    for param_name, values in test_data.items():
        lines.append(f"\n参数 {param_name}:")
        for v in values:
            value_repr = _format_value(v["value"], language)
            lines.append(f"  - {value_repr} ({v['description']}, {v['category']})")

    return "\n".join(lines)


def _format_value(value: Any, language: str) -> str:
    """格式化值为代码表示."""
    if value is None:
        return "null" if language == "java" else "null"
    elif isinstance(value, bool):
        if language == "java":
            return "true" if value else "false"
        else:
            return "true" if value else "false"
    elif isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        if len(escaped) > 30:
            escaped = escaped[:30] + "..."
        return f'"{escaped}"'
    elif isinstance(value, float):
        if value != value:
            return "Float.NaN" if language == "java" else "NaN"
        elif value == float('inf'):
            return "Float.POSITIVE_INFINITY" if language == "java" else "Infinity"
        elif value == float('-inf'):
            return "Float.NEGATIVE_INFINITY" if language == "java" else "-Infinity"
        return str(value)
    elif isinstance(value, list):
        if language == "java":
            return f"List.of({len(value)} elements)"
        else:
            return f"[{len(value)} elements]"
    elif isinstance(value, dict):
        if language == "java":
            return f"Map.of({len(value)} entries)"
        else:
            return f"{{{len(value)} entries}}"
    elif isinstance(value, set):
        return f"Set({len(value)} elements)"
    else:
        return str(value)
