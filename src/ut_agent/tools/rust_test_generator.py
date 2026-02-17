"""Rust 测试生成器."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Template

from ut_agent.tools.rust_analyzer import RustAnalyzer, RustFunction, RustStruct


@dataclass
class RustTestTemplate:
    """Rust 测试模板."""
    
    name: str
    content: str
    description: Optional[str] = None
    
    def render(self, context: Dict[str, Any]) -> str:
        """渲染模板."""
        template = Template(self.content)
        return template.render(**context)


class RustTestGenerator:
    """Rust 测试生成器."""
    
    def __init__(self):
        """初始化生成器."""
        self.analyzer = RustAnalyzer()
        self._templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, RustTestTemplate]:
        """加载测试模板."""
        return {
            "standard": RustTestTemplate(
                name="standard",
                description="标准 Rust 测试模板",
                content="""{% if is_async %}#[tokio::test]
async {% else %}#[test]
{% endif %}fn test_{{ function_name }}() {
    // Arrange
    {% for line in arrange_lines %}{{ line }}
    {% endfor %}
    
    // Act
    {% if has_return %}let result = {% endif %}{{ function_call }};
    
    // Assert
    {% for assertion in assertions %}{{ assertion }}
    {% endfor %}
}"""
            ),
            "mockall": RustTestTemplate(
                name="mockall",
                description="使用 mockall 的测试模板",
                content="""#[test]
fn test_{{ function_name }}() {
    // Create mock
    {% for mock in mocks %}
    let mut {{ mock.var }} = Mock{{ mock.type }}::new();
    {{ mock.var }}.expect_{{ mock.method }}()
        .times(1)
        .returning({{ mock.return_value }});
    {% endfor %}
    
    // Create instance with mocks
    let {{ instance_var }} = {{ struct_name }}::new({% for mock in mocks %}{{ mock.var }}{% if not loop.last %}, {% endif %}{% endfor %});
    
    // Act
    {% if has_return %}let result = {% endif %}{{ instance_var }}.{{ function_name }}({{ param_values }});
    
    // Assert
    {% for assertion in assertions %}{{ assertion }}
    {% endfor %}
}"""
            ),
            "table_driven": RustTestTemplate(
                name="table_driven",
                description="表格驱动测试模板",
                content="""#[test]
fn test_{{ function_name }}() {
    let test_cases = vec![
        {% for case in test_cases %}
        ({{ case.input }}, {{ case.expected }}),
        {% endfor %}
    ];
    
    for (input, expected) in test_cases {
        {% if has_receiver %}let instance = {{ struct_name }}::new();{% endif %}
        {% if has_return %}let result = {% endif %}{% if has_receiver %}instance.{% endif %}{{ function_name }}(input);
        {% if has_return %}assert_eq!(result, expected);{% endif %}
    }
}"""
            )
        }
    
    def generate_test(self, function: RustFunction, template: str = "standard", 
                     struct_name: Optional[str] = None) -> str:
        """为函数生成测试.
        
        Args:
            function: 要测试的函数
            template: 模板名称
            struct_name: 结构体名称（如果是方法）
            
        Returns:
            str: 生成的测试代码
        """
        tmpl = self._templates.get(template, self._templates["standard"])
        
        has_receiver = struct_name is not None
        param_values = ", ".join([p.get("name", "_") for p in function.params])
        
        context = {
            "function_name": function.name,
            "struct_name": struct_name or "",
            "instance_var": struct_name.lower() if struct_name else "instance",
            "is_async": function.is_async,
            "has_return": function.return_type is not None,
            "has_receiver": has_receiver,
            "param_values": param_values,
            "function_call": self._build_function_call(function, struct_name),
            "arrange_lines": self._build_arrange_lines(function, struct_name),
            "assertions": self._build_assertions(function),
            "mocks": [],
            "test_cases": self._generate_test_cases(function)
        }
        
        return tmpl.render(context)
    
    def _build_function_call(self, function: RustFunction, struct_name: Optional[str]) -> str:
        """构建函数调用代码."""
        param_values = ", ".join([p.get("name", "_") for p in function.params])
        
        if struct_name:
            instance = struct_name.lower()
            call = f"{instance}.{function.name}({param_values})"
        else:
            call = f"{function.name}({param_values})"
        
        if function.is_async:
            call += ".await"
        
        return call
    
    def _build_arrange_lines(self, function: RustFunction, struct_name: Optional[str]) -> List[str]:
        """构建 Arrange 部分的代码行."""
        lines = []
        
        # 为参数生成测试数据
        for param in function.params:
            param_name = param.get("name", "")
            param_type = param.get("type", "")
            test_value = self._get_default_test_value(param_type)
            lines.append(f"let {param_name} = {test_value};")
        
        # 如果是方法，创建实例
        if struct_name:
            lines.append(f"let {struct_name.lower()} = {struct_name}::new();")
        
        return lines
    
    def _build_assertions(self, function: RustFunction) -> List[str]:
        """构建断言代码."""
        assertions = []
        
        if not function.return_type:
            return ["// No return value to assert"]
        
        return_type = function.return_type
        
        if "Result" in return_type:
            assertions.append("assert!(result.is_ok());")
        elif "Option" in return_type:
            assertions.append("assert!(result.is_some());")
        elif return_type == "bool":
            assertions.append("assert!(result);")
        elif return_type in ["i32", "i64", "u32", "u64", "f32", "f64"]:
            assertions.append("assert_eq!(result, expected);")
        elif return_type == "String":
            assertions.append('assert_eq!(result, "expected".to_string());')
        else:
            assertions.append("// TODO: Add assertion for return value")
        
        return assertions
    
    def _generate_test_cases(self, function: RustFunction) -> List[Dict[str, str]]:
        """生成测试用例."""
        cases = []
        
        # 根据返回类型生成测试用例
        if function.return_type in ["i32", "i64"]:
            cases = [
                {"input": "1", "expected": "1"},
                {"input": "0", "expected": "0"},
                {"input": "-1", "expected": "-1"}
            ]
        elif function.return_type == "bool":
            cases = [
                {"input": "true", "expected": "true"},
                {"input": "false", "expected": "false"}
            ]
        
        return cases
    
    def _get_default_test_value(self, type_name: str) -> str:
        """获取类型的默认测试值."""
        type_defaults = {
            "i32": "42",
            "i64": "42i64",
            "u32": "42u32",
            "u64": "42u64",
            "f32": "3.14f32",
            "f64": "3.14",
            "bool": "true",
            "String": '"test".to_string()',
            "&str": '"test"',
            "Vec": "vec![]",
            "Option": "Some(42)",
            "Result": "Ok(42)"
        }
        
        for key, value in type_defaults.items():
            if key in type_name:
                return value
        
        return "Default::default()"
    
    def generate_file_header(self, module: str, imports: List[str]) -> str:
        """生成测试文件头.
        
        Args:
            module: 模块名
            imports: 导入列表
            
        Returns:
            str: 文件头代码
        """
        lines = []
        
        # 添加 imports
        if imports:
            for imp in imports:
                lines.append(f"use {imp};")
            lines.append("")
        
        # 添加被测模块
        lines.append(f"use super::*;")
        lines.append("")
        
        return "\n".join(lines)
    
    def generate_test_data(self, type_name: str, strategy: str = "boundary") -> List[Any]:
        """生成测试数据.
        
        Args:
            type_name: 类型名称
            strategy: 生成策略 (boundary, random, valid)
            
        Returns:
            List[Any]: 测试数据列表
        """
        if "i32" in type_name or "i64" in type_name:
            if strategy == "boundary":
                return [0, 1, -1, "i32::MAX", "i32::MIN"]
            return [0, 1, 42]
        
        elif "f32" in type_name or "f64" in type_name:
            if strategy == "boundary":
                return [0.0, 1.0, -1.0, "f64::MAX", "f64::MIN"]
            return [0.0, 1.5, 3.14]
        
        elif "String" in type_name or "str" in type_name:
            if strategy == "boundary":
                return [
                    '""',
                    '"a".to_string()',
                    '"normal string".to_string()',
                    '"a".repeat(1000)',
                    '"special!@#$%".to_string()',
                    '"unicode: 中文测试".to_string()'
                ]
            return ['"test".to_string()', '"example".to_string()']
        
        elif "Result" in type_name:
            return ["Ok(42)", 'Err("error".to_string())']
        
        elif "Option" in type_name:
            return ["Some(42)", "None"]
        
        elif "bool" in type_name:
            return ["true", "false"]
        
        return ["Default::default()"]
    
    def generate_assertion(self, function: RustFunction) -> str:
        """生成断言代码.
        
        Args:
            function: 函数定义
            
        Returns:
            str: 断言代码
        """
        if not function.return_type:
            return "// No return value to assert"
        
        return_type = function.return_type
        
        if "Result" in return_type:
            return "assert!(result.is_ok());"
        elif "Option" in return_type:
            return "assert!(result.is_some());"
        elif return_type == "bool":
            return "assert!(result);"
        else:
            return "assert_eq!(result, expected);"
    
    def generate_tests_for_struct(self, struct: RustStruct, methods: List[str]) -> str:
        """为结构体生成完整测试文件.
        
        Args:
            struct: 结构体定义
            methods: 方法列表
            
        Returns:
            str: 完整测试文件内容
        """
        lines = [
            "#[cfg(test)]",
            "mod tests {",
            "    use super::*;",
            "",
        ]
        
        # 为每个方法生成测试
        for method_name in methods:
            lines.append(f"    #[test]")
            lines.append(f"    fn test_{method_name}() {{")
            lines.append(f"        // TODO: Implement test for {method_name}")
            lines.append("    }")
            lines.append("")
        
        lines.append("}")
        
        return "\n".join(lines)
    
    def generate_benchmark(self, function: RustFunction) -> str:
        """生成基准测试.
        
        Args:
            function: 函数定义
            
        Returns:
            str: 基准测试代码
        """
        param_values = ", ".join([p.get("name", "_") for p in function.params])
        
        # 生成参数准备代码
        param_setup = []
        for param in function.params:
            param_name = param.get("name", "")
            param_type = param.get("type", "")
            test_value = self._get_default_test_value(param_type)
            param_setup.append(f"let {param_name} = {test_value};")
        
        setup_code = "\n        ".join(param_setup)
        
        return f"""#[cfg(test)]
mod benches {{
    use super::*;
    use criterion::{{black_box, criterion_group, criterion_main, Criterion}};
    
    fn bench_{function.name}(c: &mut Criterion) {{
        {setup_code}
        
        c.bench_function("{function.name}", |b| {{
            b.iter(|| {function.name}({param_values}))
        }});
    }}
    
    criterion_group!(benches, bench_{function.name});
    criterion_main!(benches);
}}"""
    
    def generate_doc_test(self, function: RustFunction) -> str:
        """生成文档测试.
        
        Args:
            function: 函数定义
            
        Returns:
            str: 文档测试代码
        """
        param_values = ", ".join([p.get("name", "_") for p in function.params])
        
        # 生成示例参数值
        example_params = []
        for param in function.params:
            param_type = param.get("type", "")
            example_params.append(self._get_default_test_value(param_type))
        
        example_values = ", ".join(example_params)
        
        return f"""/// # Examples
///
/// ```
/// use your_crate::{function.name};
///
/// let result = {function.name}({example_values});
/// ```
pub fn {function.name}({{ /* ... */ }}) {{ /* ... */ }}"""
    
    def generate_property_test(self, function: RustFunction) -> str:
        """生成属性测试.
        
        Args:
            function: 函数定义
            
        Returns:
            str: 属性测试代码
        """
        return f"""#[cfg(test)]
mod property_tests {{
    use super::*;
    use proptest::prelude::*;
    
    proptest! {{
        #[test]
        fn test_{function.name}_properties(
            // TODO: Define property test parameters
        ) {{
            // TODO: Implement property test
        }}
    }}
}}"""
    
    def generate_integration_test(self, function: RustFunction) -> str:
        """生成集成测试.
        
        Args:
            function: 函数定义
            
        Returns:
            str: 集成测试代码
        """
        async_attr = "#[tokio::test]\n    " if function.is_async else "#[test]\n    "
        async_kw = "async " if function.is_async else ""
        await_kw = ".await" if function.is_async else ""
        
        param_values = ", ".join([p.get("name", "_") for p in function.params])
        
        # 生成参数准备
        param_setup = []
        for param in function.params:
            param_name = param.get("name", "")
            param_type = param.get("type", "")
            test_value = self._get_default_test_value(param_type)
            param_setup.append(f"let {param_name} = {test_value};")
        
        setup_code = "\n        ".join(param_setup)
        
        return f"""{async_attr}{async_kw}fn test_{function.name}_integration() {{
    // Arrange
    {setup_code}
    
    // Act
    let result = {function.name}({param_values}){await_kw};
    
    // Assert
    assert!(result.is_ok());
}}"""
    
    def generate_from_file(self, file_path: Path) -> str:
        """从 Rust 文件生成测试.
        
        Args:
            file_path: Rust 文件路径
            
        Returns:
            str: 生成的测试代码
        """
        result = self.analyzer.analyze_file(file_path)
        
        lines = [
            "#[cfg(test)]",
            "mod tests {",
            "    use super::*;",
            "",
        ]
        
        # 为每个公开函数生成测试
        for func in result.get_testable_functions():
            # 查找函数所属的结构体
            struct_name = None
            for impl in result.impls:
                if func.name in impl.methods:
                    struct_name = impl.struct_name
                    break
            
            test_code = self.generate_test(func, template="standard", struct_name=struct_name)
            # 缩进测试代码
            indented_test = "\n".join("    " + line if line.strip() else line for line in test_code.split("\n"))
            lines.append(indented_test)
            lines.append("")
        
        lines.append("}")
        
        return "\n".join(lines)
    
    def save_test(self, test_code: str, output_path: Path) -> None:
        """保存生成的测试文件.
        
        Args:
            test_code: 测试代码
            output_path: 输出路径
        """
        output_path.write_text(test_code, encoding="utf-8")
