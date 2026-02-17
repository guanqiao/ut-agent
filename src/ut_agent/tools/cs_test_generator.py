"""C# 测试生成器."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Template

from ut_agent.tools.cs_analyzer import CsAnalyzer, CsMethod, CsClass


@dataclass
class CsTestTemplate:
    """C# 测试模板."""
    
    name: str
    content: str
    description: Optional[str] = None
    
    def render(self, context: Dict[str, Any]) -> str:
        """渲染模板."""
        template = Template(self.content)
        return template.render(**context)


class CsTestGenerator:
    """C# 测试生成器."""
    
    def __init__(self):
        """初始化生成器."""
        self.analyzer = CsAnalyzer()
        self._templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, CsTestTemplate]:
        """加载测试模板."""
        return {
            "xunit": CsTestTemplate(
                name="xunit",
                description="xUnit 测试模板",
                content="""[Fact]
public {% if is_async %}async Task{% else %}void{% endif %} Test{{ method_name }}()
{
    // Arrange
    {{ arrange_code }}
    
    // Act
    {{ act_code }}
    
    // Assert
    {{ assert_code }}
}"""
            ),
            "nunit": CsTestTemplate(
                name="nunit",
                description="NUnit 测试模板",
                content="""[Test]
public {% if is_async %}async Task{% else %}void{% endif %} Test{{ method_name }}()
{
    // Arrange
    {{ arrange_code }}
    
    // Act
    {{ act_code }}
    
    // Assert
    {{ assert_code }}
}"""
            ),
            "mstest": CsTestTemplate(
                name="mstest",
                description="MSTest 测试模板",
                content="""[TestMethod]
public {% if is_async %}async Task{% else %}void{% endif %} Test{{ method_name }}()
{
    // Arrange
    {{ arrange_code }}
    
    // Act
    {{ act_code }}
    
    // Assert
    {{ assert_code }}
}"""
            ),
            "moq": CsTestTemplate(
                name="moq",
                description="使用 Moq 的测试模板",
                content="""[Fact]
public {% if is_async %}async Task{% else %}void{% endif %} Test{{ method_name }}()
{
    // Arrange
    {{ mock_setup }}
    {{ arrange_code }}
    
    // Act
    {{ act_code }}
    
    // Assert
    {{ assert_code }}
    {{ mock_verify }}
}"""
            )
        }
    
    def generate_test(self, method: CsMethod, template: str = "xunit",
                     class_name: Optional[str] = None) -> str:
        """为方法生成测试.
        
        Args:
            method: 要测试的方法
            template: 模板名称
            class_name: 类名（如果是实例方法）
            
        Returns:
            str: 生成的测试代码
        """
        tmpl = self._templates.get(template, self._templates["xunit"])
        
        context = {
            "method_name": method.name,
            "class_name": class_name or "",
            "is_async": method.is_async,
            "is_static": method.is_static,
            "arrange_code": self._build_arrange_code(method, class_name),
            "act_code": self._build_act_code(method, class_name),
            "assert_code": self._build_assert_code(method),
            "mock_setup": self._build_mock_setup(),
            "mock_verify": self._build_mock_verify()
        }
        
        return tmpl.render(context)
    
    def _build_arrange_code(self, method: CsMethod, class_name: Optional[str]) -> str:
        """构建 Arrange 代码."""
        lines = []
        
        # 生成参数
        for param in method.parameters:
            param_name = param.get("name", "")
            param_type = param.get("type", "")
            test_value = self._get_default_test_value(param_type)
            lines.append(f"var {param_name} = {test_value};")
        
        # 如果是实例方法，创建实例
        if class_name and not method.is_static:
            var_name = class_name.lower()
            lines.append(f"var {var_name} = new {class_name}();")
        
        return "\n    ".join(lines) if lines else "// TODO: Arrange"
    
    def _build_act_code(self, method: CsMethod, class_name: Optional[str]) -> str:
        """构建 Act 代码."""
        param_values = ", ".join([p.get("name", "") for p in method.parameters])
        
        if class_name and not method.is_static:
            instance = class_name.lower()
            call = f"var result = {instance}.{method.name}({param_values});"
        elif method.is_static:
            call = f"var result = {class_name}.{method.name}({param_values});"
        else:
            call = f"var result = {method.name}({param_values});"
        
        if method.is_async:
            call = call.replace("var result = ", "var result = await ")
        
        return call if method.return_type != "void" else f"{call.replace('var result = ', '')}"
    
    def _build_assert_code(self, method: CsMethod) -> str:
        """构建 Assert 代码."""
        if method.return_type == "void":
            return "// No return value to assert"
        
        return_type = method.return_type
        
        if "Task<" in return_type:
            # 提取 Task 中的类型
            inner_type = return_type.replace("Task<", "").rstrip(">")
            if inner_type == "bool":
                return "Assert.True(result);"
            else:
                return "Assert.NotNull(result);"
        elif return_type == "bool":
            return "Assert.True(result);"
        elif return_type in ["int", "long", "double", "float"]:
            return "Assert.Equal(expected, result);"
        elif return_type == "string":
            return 'Assert.Equal("expected", result);'
        else:
            return "Assert.NotNull(result);"
    
    def _build_mock_setup(self) -> str:
        """构建 Mock 设置代码."""
        return "// TODO: Setup mocks"
    
    def _build_mock_verify(self) -> str:
        """构建 Mock 验证代码."""
        return "// TODO: Verify mocks"
    
    def _get_default_test_value(self, type_name: str) -> str:
        """获取类型的默认测试值."""
        type_defaults = {
            "int": "42",
            "long": "42L",
            "float": "3.14f",
            "double": "3.14",
            "decimal": "42.0m",
            "bool": "true",
            "string": '"test"',
            "char": "'a'",
            "byte": "0x42",
            "DateTime": "DateTime.Now",
            "Guid": "Guid.NewGuid()"
        }
        
        for key, value in type_defaults.items():
            if key.lower() in type_name.lower():
                return value
        
        return "default"
    
    def generate_file_header(self, namespace: str, usings: List[str]) -> str:
        """生成测试文件头.
        
        Args:
            namespace: 命名空间
            usings: using 列表
            
        Returns:
            str: 文件头代码
        """
        lines = []
        
        # 添加 usings
        for using in usings:
            lines.append(f"using {using};")
        
        lines.append("")
        lines.append(f"namespace {namespace}")
        lines.append("{")
        
        return "\n".join(lines)
    
    def generate_test_data(self, type_name: str, strategy: str = "boundary") -> List[Any]:
        """生成测试数据.
        
        Args:
            type_name: 类型名称
            strategy: 生成策略 (boundary, random, valid)
            
        Returns:
            List[Any]: 测试数据列表
        """
        type_name = type_name.lower()
        
        if "int" in type_name:
            if strategy == "boundary":
                return [0, 1, -1, int(1e9), -int(1e9)]
            return [0, 1, 42]
        
        elif "long" in type_name:
            if strategy == "boundary":
                return [0, 1, -1, 9999999999, -9999999999]
            return [0, 1, 42]
        
        elif "float" in type_name or "double" in type_name:
            if strategy == "boundary":
                return [0.0, 1.0, -1.0, float('inf'), float('-inf')]
            return [0.0, 1.5, 3.14]
        
        elif "string" in type_name:
            if strategy == "boundary":
                return [
                    '""',
                    '"a"',
                    '"test string"',
                    '"special!@#$%"',
                    '"unicode 中文测试"'
                ]
            return ['"test"', '"example"']
        
        elif "bool" in type_name:
            return ["true", "false"]
        
        return ["default"]
    
    def generate_assertion(self, method: CsMethod) -> str:
        """生成断言代码.
        
        Args:
            method: 方法定义
            
        Returns:
            str: 断言代码
        """
        if method.return_type == "void":
            return "// No return value to assert"
        
        return_type = method.return_type
        
        if "Task<" in return_type:
            inner_type = return_type.replace("Task<", "").rstrip(">")
            if inner_type == "bool":
                return "Assert.True(result);"
            else:
                return "Assert.NotNull(result);"
        elif return_type == "bool":
            return "Assert.True(result);"
        else:
            return "Assert.NotNull(result);"
    
    def generate_tests_for_class(self, cls: CsClass) -> str:
        """为类生成完整测试文件.
        
        Args:
            cls: 类定义
            
        Returns:
            str: 完整测试文件内容
        """
        namespace = cls.namespace or "MyApp"
        test_namespace = f"{namespace}.Tests"
        
        lines = [
            "using Xunit;",
            f"using {namespace};",
            "",
            f"namespace {test_namespace}",
            "{",
            f"    public class {cls.name}Tests",
            "    {",
            f"        private readonly {cls.name} _sut;",
            "",
            f"        public {cls.name}Tests()",
            "        {",
            f"            _sut = new {cls.name}();",
            "        }",
            ""
        ]
        
        # 为每个方法生成测试
        for method_name in cls.methods:
            lines.append("        [Fact]")
            lines.append(f"        public void Test{method_name}()")
            lines.append("        {")
            lines.append(f"            // TODO: Test {method_name}")
            lines.append("        }")
            lines.append("")
        
        lines.append("    }")
        lines.append("}")
        
        return "\n".join(lines)
    
    def generate_theory_test(self, method: CsMethod) -> str:
        """生成 Theory 测试（参数化测试）.
        
        Args:
            method: 方法定义
            
        Returns:
            str: Theory 测试代码
        """
        param_types = [p.get("type", "") for p in method.parameters]
        param_names = [p.get("name", "") for p in method.parameters]
        
        # 生成 InlineData
        inline_data = []
        if "int" in str(param_types):
            inline_data.append("[InlineData(1, 2, 3)]")
            inline_data.append("[InlineData(0, 0, 0)]")
            inline_data.append("[InlineData(-1, 1, 0)]")
        
        lines = [
            "[Theory]"
        ]
        lines.extend(inline_data)
        
        params_str = ", ".join([f"{t} {n}" for t, n in zip(param_types, param_names)])
        lines.append(f"public void Test{method.name}Theory({params_str})")
        lines.append("{")
        lines.append("    // Arrange & Act")
        lines.append(f"    var result = _sut.{method.name}({', '.join(param_names)});")
        lines.append("")
        lines.append("    // Assert")
        lines.append("    // TODO: Add assertions")
        lines.append("}")
        
        return "\n".join(lines)
    
    def generate_benchmark(self, method: CsMethod) -> str:
        """生成基准测试.
        
        Args:
            method: 方法定义
            
        Returns:
            str: 基准测试代码
        """
        param_values = ", ".join([self._get_default_test_value(p.get("type", "")) for p in method.parameters])
        
        return f"""[Benchmark]
public void Benchmark{method.name}()
{{
    // Arrange
    {f"var sut = new ClassName();" if not method.is_static else ""}
    
    // Benchmark
    for (int i = 0; i < 1000; i++)
    {{
        {(f"sut.{method.name}({param_values});" if not method.is_static else f"{method.name}({param_values});")}
    }}
}}"""
    
    def generate_from_file(self, file_path: Path) -> str:
        """从 C# 文件生成测试.
        
        Args:
            file_path: C# 文件路径
            
        Returns:
            str: 生成的测试代码
        """
        result = self.analyzer.analyze_file(file_path)
        
        if not result.classes:
            return "// No classes found to test"
        
        # 为第一个类生成测试
        class_name = list(result.classes.keys())[0]
        cls = result.classes[class_name]
        
        return self.generate_tests_for_class(cls)
    
    def save_test(self, test_code: str, output_path: Path) -> None:
        """保存生成的测试文件.
        
        Args:
            test_code: 测试代码
            output_path: 输出路径
        """
        output_path.write_text(test_code, encoding="utf-8")
