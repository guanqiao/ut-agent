"""交互式测试开发模块.

提供测试用例预览、交互式断言编辑和测试数据可视化调整功能。
"""

import re
from dataclasses import dataclass, field
from difflib import unified_diff
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TestPreview:
    """测试预览."""
    test_code: str
    line_count: int
    assertion_count: int
    test_method_count: int
    coverage_estimate: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_code": self.test_code,
            "line_count": self.line_count,
            "assertion_count": self.assertion_count,
            "test_method_count": self.test_method_count,
            "coverage_estimate": self.coverage_estimate,
        }


@dataclass
class EditOperation:
    """编辑操作."""
    operation_type: str
    target: str
    replacement: str
    line_number: int
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_type": self.operation_type,
            "target": self.target,
            "replacement": self.replacement,
            "line_number": self.line_number,
            "description": self.description,
        }


@dataclass
class PreviewResult:
    """预览结果."""
    original_code: str
    modified_code: str
    diff_lines: List[Tuple[int, str]]
    is_valid: bool
    validation_errors: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_code": self.original_code,
            "modified_code": self.modified_code,
            "diff_lines": self.diff_lines,
            "is_valid": self.is_valid,
            "validation_errors": self.validation_errors,
        }


@dataclass
class AdjustmentSuggestion:
    """调整建议."""
    suggestion_type: str
    current_value: str
    suggested_values: List[str]
    reason: str
    priority: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suggestion_type": self.suggestion_type,
            "current_value": self.current_value,
            "suggested_values": self.suggested_values,
            "reason": self.reason,
            "priority": self.priority,
        }


class InteractiveTestEditor:
    """交互式测试编辑器."""

    TEST_METHOD_PATTERN = re.compile(
        r'@Test\s*(?:\([^)]*\))?\s*'
        r'(?:public\s+)?(?:void\s+)?'
        r'(\w+)\s*\([^)]*\)\s*\{',
        re.MULTILINE
    )

    ASSERTION_PATTERNS = [
        re.compile(r'assert(?:Equals|True|False|NotNull|Null|Throws|Same|NotSame|ArrayEquals)\s*\([^)]+\)', re.IGNORECASE),
        re.compile(r'expect\s*\([^)]+\)', re.IGNORECASE),
        re.compile(r'verify\s*\([^)]+\)', re.IGNORECASE),
    ]

    def preview_modification(
        self,
        test_code: str,
        operation: EditOperation,
    ) -> PreviewResult:
        """预览修改效果.

        Args:
            test_code: 原始测试代码
            operation: 编辑操作

        Returns:
            预览结果
        """
        modified_code = self._apply_operation(test_code, operation)
        
        diff_lines = self._compute_diff(test_code, modified_code)
        
        is_valid, validation_errors = self.validate_test_code(modified_code)
        
        return PreviewResult(
            original_code=test_code,
            modified_code=modified_code,
            diff_lines=diff_lines,
            is_valid=is_valid,
            validation_errors=validation_errors,
        )

    def apply_modification(
        self,
        test_code: str,
        operation: EditOperation,
    ) -> str:
        """应用修改.

        Args:
            test_code: 原始测试代码
            operation: 编辑操作

        Returns:
            修改后的代码
        """
        return self._apply_operation(test_code, operation)

    def _apply_operation(
        self,
        test_code: str,
        operation: EditOperation,
    ) -> str:
        """应用编辑操作."""
        lines = test_code.split('\n')
        
        if operation.operation_type == "replace":
            for i, line in enumerate(lines):
                if operation.target in line:
                    lines[i] = line.replace(operation.target, operation.replacement)
                    
        elif operation.operation_type == "insert":
            line_idx = operation.line_number - 1
            if 0 <= line_idx <= len(lines):
                indent = self._get_indent(lines[min(line_idx, len(lines) - 1)])
                lines.insert(line_idx, indent + operation.replacement)
                
        elif operation.operation_type == "delete":
            for i, line in enumerate(lines):
                if operation.target in line:
                    lines[i] = ""
                    
        return '\n'.join(lines)

    def _get_indent(self, line: str) -> str:
        """获取行的缩进."""
        match = re.match(r'^(\s*)', line)
        return match.group(1) if match else ""

    def _compute_diff(
        self,
        original: str,
        modified: str,
    ) -> List[Tuple[int, str]]:
        """计算差异."""
        diff_lines = []
        original_lines = original.split('\n')
        modified_lines = modified.split('\n')
        
        diff = list(unified_diff(
            original_lines,
            modified_lines,
            lineterm='',
        ))
        
        line_num = 0
        for line in diff:
            if line.startswith('@@'):
                match = re.search(r'@@ -(\d+)', line)
                if match:
                    line_num = int(match.group(1))
            elif line.startswith('-') and not line.startswith('---'):
                diff_lines.append((line_num, line))
            elif line.startswith('+') and not line.startswith('+++'):
                diff_lines.append((line_num, line))
                line_num += 1
            elif not line.startswith('\\'):
                line_num += 1
                
        return diff_lines

    def validate_test_code(
        self,
        test_code: str,
    ) -> Tuple[bool, List[str]]:
        """验证测试代码.

        Args:
            test_code: 测试代码

        Returns:
            (是否有效, 错误列表)
        """
        errors = []
        
        if not test_code.strip():
            errors.append("Test code is empty")
            return False, errors
        
        test_methods = self.TEST_METHOD_PATTERN.findall(test_code)
        if not test_methods:
            errors.append("No test methods found")
        
        has_assertion = any(
            pattern.search(test_code)
            for pattern in self.ASSERTION_PATTERNS
        )
        if not has_assertion:
            errors.append("No assertions found in test code")
        
        open_braces = test_code.count('{')
        close_braces = test_code.count('}')
        if open_braces != close_braces:
            errors.append(f"Unbalanced braces: {open_braces} open, {close_braces} close")
        
        return len(errors) == 0, errors

    def generate_preview(self, test_code: str) -> TestPreview:
        """生成测试预览.

        Args:
            test_code: 测试代码

        Returns:
            测试预览
        """
        lines = test_code.split('\n')
        line_count = len(lines)
        
        test_methods = self.TEST_METHOD_PATTERN.findall(test_code)
        test_method_count = len(test_methods)
        
        assertion_count = 0
        for pattern in self.ASSERTION_PATTERNS:
            assertion_count += len(pattern.findall(test_code))
        
        coverage_estimate = min(1.0, assertion_count * 0.2 + test_method_count * 0.1)
        
        return TestPreview(
            test_code=test_code,
            line_count=line_count,
            assertion_count=assertion_count,
            test_method_count=test_method_count,
            coverage_estimate=coverage_estimate,
        )


class AssertionEditor:
    """断言编辑器."""

    ASSERTION_PATTERN = re.compile(
        r'(assert(?:Equals|True|False|NotNull|Null|Throws|Same|NotSame|ArrayEquals))'
        r'\s*\(\s*([^,]+)?\s*(?:,\s*([^)]+))?\s*\)',
        re.IGNORECASE
    )

    def parse_assertions(self, test_code: str) -> List[Dict[str, Any]]:
        """解析断言.

        Args:
            test_code: 测试代码

        Returns:
            断言列表
        """
        assertions = []
        
        for i, line in enumerate(test_code.split('\n'), 1):
            for match in self.ASSERTION_PATTERN.finditer(line):
                assertion_type = match.group(1)
                expected = match.group(2) if match.group(2) else None
                actual = match.group(3) if match.group(3) else match.group(2)
                
                assertions.append({
                    "type": assertion_type,
                    "expected": expected.strip() if expected else None,
                    "actual": actual.strip() if actual else None,
                    "line": i,
                    "full_match": match.group(0),
                })
        
        return assertions

    def modify_expected_value(
        self,
        assertion: Dict[str, Any],
        new_value: str,
    ) -> Dict[str, Any]:
        """修改断言期望值.

        Args:
            assertion: 断言信息
            new_value: 新的期望值

        Returns:
            修改后的断言信息
        """
        modified = assertion.copy()
        modified["expected"] = new_value
        return modified

    def add_assertion(
        self,
        test_code: str,
        assertion: Dict[str, Any],
        line: int,
    ) -> str:
        """添加断言.

        Args:
            test_code: 测试代码
            assertion: 断言信息
            line: 插入行号

        Returns:
            修改后的代码
        """
        lines = test_code.split('\n')
        
        assertion_type = assertion.get("type", "assertNotNull")
        actual = assertion.get("actual", "result")
        
        if assertion_type == "assertEquals":
            expected = assertion.get("expected", "null")
            assertion_code = f"assertEquals({expected}, {actual});"
        elif assertion_type == "assertTrue":
            assertion_code = f"assertTrue({actual});"
        elif assertion_type == "assertFalse":
            assertion_code = f"assertFalse({actual});"
        elif assertion_type == "assertNotNull":
            assertion_code = f"assertNotNull({actual});"
        elif assertion_type == "assertNull":
            assertion_code = f"assertNull({actual});"
        else:
            assertion_code = f"{assertion_type}({actual});"
        
        line_idx = line - 1
        if 0 <= line_idx <= len(lines):
            indent = self._get_indent(lines[min(line_idx, len(lines) - 1)])
            lines.insert(line_idx, indent + assertion_code)
        
        return '\n'.join(lines)

    def _get_indent(self, line: str) -> str:
        """获取行的缩进."""
        match = re.match(r'^(\s*)', line)
        return match.group(1) if match else "    "

    def suggest_assertions(self, test_code: str) -> List[Dict[str, Any]]:
        """建议断言.

        Args:
            test_code: 测试代码

        Returns:
            建议的断言列表
        """
        suggestions = []
        
        result_pattern = re.compile(r'(?:int|Integer|String|Object|var)\s+(\w+)\s*=', re.IGNORECASE)
        for match in result_pattern.finditer(test_code):
            var_name = match.group(1)
            suggestions.append({
                "type": "assertNotNull",
                "actual": var_name,
                "reason": f"Verify {var_name} is not null",
            })
        
        bool_pattern = re.compile(r'boolean\s+(\w+)\s*=', re.IGNORECASE)
        for match in bool_pattern.finditer(test_code):
            var_name = match.group(1)
            suggestions.append({
                "type": "assertTrue",
                "actual": var_name,
                "reason": f"Verify {var_name} is true",
            })
            suggestions.append({
                "type": "assertFalse",
                "actual": var_name,
                "reason": f"Verify {var_name} is false",
            })
        
        return suggestions

    def convert_assertion_type(
        self,
        assertion: Dict[str, Any],
        new_type: str,
    ) -> Dict[str, Any]:
        """转换断言类型.

        Args:
            assertion: 断言信息
            new_type: 新类型

        Returns:
            转换后的断言信息
        """
        converted = assertion.copy()
        converted["type"] = new_type
        
        if new_type in ["assertTrue", "assertFalse", "assertNotNull", "assertNull"]:
            converted["expected"] = None
        
        return converted


class TestDataAdjuster:
    """测试数据调整器."""

    VALUE_PATTERN = re.compile(
        r'(?:assertEquals|assertSame)\s*\(\s*([^,]+)\s*,',
        re.IGNORECASE
    )

    def extract_test_data(self, test_code: str) -> List[Dict[str, Any]]:
        """提取测试数据.

        Args:
            test_code: 测试代码

        Returns:
            测试数据列表
        """
        data = []
        
        for i, line in enumerate(test_code.split('\n'), 1):
            for match in self.VALUE_PATTERN.finditer(line):
                expected = match.group(1).strip()
                data.append({
                    "expected": expected,
                    "line": i,
                    "context": line.strip(),
                })
        
        return data

    def suggest_boundary_values(
        self,
        current_value: str,
        data_type: str,
    ) -> List[str]:
        """建议边界值.

        Args:
            current_value: 当前值
            data_type: 数据类型

        Returns:
            建议的边界值列表
        """
        suggestions = []
        
        if data_type == "int" or data_type == "integer":
            suggestions = ["0", "-1", "1", "Integer.MAX_VALUE", "Integer.MIN_VALUE"]
        elif data_type == "long":
            suggestions = ["0L", "-1L", "1L", "Long.MAX_VALUE", "Long.MIN_VALUE"]
        elif data_type == "double" or data_type == "float":
            suggestions = ["0.0", "-1.0", "1.0", "Double.MAX_VALUE", "Double.MIN_VALUE"]
        elif data_type == "string":
            suggestions = ["", " ", "a", "null"]
        elif data_type == "boolean":
            suggestions = ["true", "false"]
        elif data_type == "object":
            suggestions = ["null"]
        else:
            suggestions = ["null", ""]
        
        if current_value not in suggestions:
            suggestions.insert(0, current_value)
        
        return suggestions

    def adjust_test_data(
        self,
        test_code: str,
        adjustments: List[Dict[str, Any]],
    ) -> str:
        """调整测试数据.

        Args:
            test_code: 测试代码
            adjustments: 调整列表

        Returns:
            修改后的代码
        """
        lines = test_code.split('\n')
        
        for adj in adjustments:
            line_idx = adj.get("line", 0) - 1
            old_value = adj.get("old_value", "")
            new_value = adj.get("new_value", "")
            
            if 0 <= line_idx < len(lines):
                lines[line_idx] = lines[line_idx].replace(old_value, new_value)
        
        return '\n'.join(lines)

    def generate_variations(
        self,
        test_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """生成数据变体.

        Args:
            test_data: 原始测试数据

        Returns:
            变体列表
        """
        variations = [test_data.copy()]
        
        for key, value in test_data.items():
            if isinstance(value, int):
                for v in [0, -1, 1, 100, -100]:
                    new_data = test_data.copy()
                    new_data[key] = v
                    if new_data not in variations:
                        variations.append(new_data)
            elif isinstance(value, str):
                for v in ["", " ", "test", "null"]:
                    new_data = test_data.copy()
                    new_data[key] = v
                    if new_data not in variations:
                        variations.append(new_data)
        
        return variations

    def analyze_data_coverage(
        self,
        test_cases: List[Dict[str, Any]],
        field: str,
    ) -> Dict[str, bool]:
        """分析数据覆盖.

        Args:
            test_cases: 测试用例列表
            field: 字段名

        Returns:
            覆盖分析结果
        """
        values = [tc.get(field) for tc in test_cases if field in tc]
        
        return {
            "has_positive": any(isinstance(v, (int, float)) and v > 0 for v in values),
            "has_negative": any(isinstance(v, (int, float)) and v < 0 for v in values),
            "has_zero": any(v == 0 for v in values),
            "has_null": any(v is None or v == "null" for v in values),
            "has_empty": any(v == "" for v in values),
            "total_cases": len(values),
        }
