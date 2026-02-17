"""Go 测试生成器."""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Template

from ut_agent.tools.go_analyzer import GoAnalyzer, GoMethod, GoStruct


@dataclass
class GoTestTemplate:
    """Go 测试模板."""
    
    name: str
    content: str
    description: Optional[str] = None
    
    def render(self, context: Dict[str, Any]) -> str:
        """渲染模板."""
        template = Template(self.content)
        return template.render(**context)


class GoTestGenerator:
    """Go 测试生成器."""
    
    def __init__(self):
        """初始化生成器."""
        self.analyzer = GoAnalyzer()
        self._templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, GoTestTemplate]:
        """加载测试模板."""
        return {
            "simple": GoTestTemplate(
                name="simple",
                description="简单测试模板",
                content="""func Test{{ method_name }}(t *testing.T) {
    // Arrange
    {{ receiver_var }} := &{{ receiver_type }}{}
    
    // Act
    {% if return_type %}got := {% endif %}{{ receiver_var }}.{{ method_name }}({{ param_values }})
    
    // Assert
    {% if return_type %}if got != expected {
        t.Errorf("{{ method_name }}() = %v, want %v", got, expected)
    }{% else %}// TODO: Add assertions{% endif %}
}"""
            ),
            "table_driven": GoTestTemplate(
                name="table_driven",
                description="表格驱动测试模板 (Go 惯用写法)",
                content="""func Test{{ method_name }}(t *testing.T) {
    type args struct {
        {% for param in params %}{{ param.name }} {{ param.type }}
        {% endfor %}
    }
    tests := []struct {
        name    string
        args    args
        {% for ret in returns %}want{{ loop.index }} {{ ret.type }}
        {% endfor %}
        wantErr bool
    }{
        // TODO: Add test cases
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            {{ receiver_var }} := &{{ receiver_type }}{}
            {% if returns %}{% for ret in returns %}got{{ loop.index }}{% if not loop.last %}, {% endif %}{% endfor %} := {{ receiver_var }}.{{ method_name }}({% for param in params %}tt.args.{{ param.name }}{% if not loop.last %}, {% endif %}{% endfor %})
            {% if returns %}{% for ret in returns %}
            {% if ret.type == 'error' %}if (got{{ loop.index }} != nil) != tt.wantErr {
                t.Errorf("{{ method_name }}() error = %v, wantErr %v", got{{ loop.index }}, tt.wantErr)
                return
            }{% else %}if got{{ loop.index }} != tt.want{{ loop.index }} {
                t.Errorf("{{ method_name }}() = %v, want %v", got{{ loop.index }}, tt.want{{ loop.index }})
            }{% endif %}
            {% endfor %}{% endif %}{% else %}{{ receiver_var }}.{{ method_name }}({% for param in params %}tt.args.{{ param.name }}{% if not loop.last %}, {% endif %}{% endfor %})
            {% endif %}
        })
    }
}"""
            ),
            "gomock": GoTestTemplate(
                name="gomock",
                description="使用 gomock 的测试模板",
                content="""func Test{{ method_name }}(t *testing.T) {
    ctrl := gomock.NewController(t)
    defer ctrl.Finish()
    
    // Create mocks
    {% for mock in mocks %}{{ mock.var }} := mock_{{ mock.package }}.NewMock{{ mock.type }}(ctrl)
    {% endfor %}
    
    {{ receiver_var }} := New{{ receiver_type }}({% for mock in mocks %}{{ mock.var }}{% if not loop.last %}, {% endif %}{% endfor %})
    
    type args struct {
        {% for param in params %}{{ param.name }} {{ param.type }}
        {% endfor %}
    }
    tests := []struct {
        name    string
        args    args
        {% for mock in mocks %}mockSetup func(*mock_{{ mock.package }}.Mock{{ mock.type }})
        {% endfor %}
        {% for ret in returns %}want{{ loop.index }} {{ ret.type }}
        {% endfor %}
        wantErr bool
    }{
        // TODO: Add test cases
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            // Setup mocks
            {% for mock in mocks %}if tt.mockSetup != nil {
                tt.mockSetup({{ mock.var }})
            }
            {% endfor %}
            
            {% if returns %}{% for ret in returns %}got{{ loop.index }}{% if not loop.last %}, {% endif %}{% endfor %} := {{ receiver_var }}.{{ method_name }}({% for param in params %}tt.args.{{ param.name }}{% if not loop.last %}, {% endif %}{% endfor %})
            {% if returns %}{% for ret in returns %}
            {% if ret.type == 'error' %}if (got{{ loop.index }} != nil) != tt.wantErr {
                t.Errorf("{{ method_name }}() error = %v, wantErr %v", got{{ loop.index }}, tt.wantErr)
                return
            }{% else %}if got{{ loop.index }} != tt.want{{ loop.index }} {
                t.Errorf("{{ method_name }}() = %v, want %v", got{{ loop.index }}, tt.want{{ loop.index }})
            }{% endif %}
            {% endfor %}{% endif %}{% else %}{{ receiver_var }}.{{ method_name }}({% for param in params %}tt.args.{{ param.name }}{% if not loop.last %}, {% endif %}{% endfor %})
            {% endif %}
        })
    }
}"""
            )
        }
    
    def generate_test(self, method: GoMethod, template: str = "table_driven") -> str:
        """为方法生成测试.
        
        Args:
            method: 要测试的方法
            template: 模板名称
            
        Returns:
            str: 生成的测试代码
        """
        tmpl = self._templates.get(template, self._templates["table_driven"])
        
        context = {
            "method_name": method.name,
            "receiver_type": method.receiver or "",
            "receiver_var": method.receiver.lower() if method.receiver else "s",
            "params": method.params,
            "returns": method.returns,
            "param_values": ", ".join([p.get("name", "") for p in method.params]),
            "return_type": method.returns[0].get("type", "") if method.returns else "",
            "mocks": []
        }
        
        return tmpl.render(context)
    
    def generate_mock_setup(self, struct: GoStruct) -> str:
        """生成 Mock 设置代码.
        
        Args:
            struct: 结构体定义
            
        Returns:
            str: Mock 设置代码
        """
        deps = struct.get_interface_dependencies()
        if not deps:
            return ""
        
        lines = ["// Setup mocks", "ctrl := gomock.NewController(t)", "defer ctrl.Finish()", ""]
        
        for dep in deps:
            var_name = dep.lower()
            lines.append(f'{var_name} := mock.NewMock{dep}(ctrl)')
        
        return "\n".join(lines)
    
    def generate_file_header(self, package: str, imports: List[str]) -> str:
        """生成测试文件头.
        
        Args:
            package: 包名
            imports: 导入列表
            
        Returns:
            str: 文件头代码
        """
        header = f"package {package}\n\n"
        
        if imports:
            header += "import (\n"
            for imp in imports:
                header += f'    "{imp}"\n'
            header += ")\n"
        
        return header
    
    def generate_test_data(self, type_name: str, strategy: str = "boundary") -> List[Any]:
        """生成测试数据.
        
        Args:
            type_name: 类型名称
            strategy: 生成策略 (boundary, random, valid)
            
        Returns:
            List[Any]: 测试数据列表
        """
        if type_name in ["int", "int32", "int64"]:
            if strategy == "boundary":
                return [0, 1, -1, 2147483647, -2147483648]
            return [0, 1, 42]
        
        elif type_name in ["float32", "float64"]:
            if strategy == "boundary":
                return [0.0, 1.0, -1.0, 3.14159, -3.14159]
            return [0.0, 1.5, 3.14]
        
        elif type_name == "string":
            if strategy == "boundary":
                return [
                    "",
                    "a",
                    "normal string",
                    "a" * 1000,  # 超长字符串
                    "special!@#$%",
                    "unicode: 中文测试 🎉"
                ]
            return ["test", "example", ""]
        
        elif type_name == "bool":
            return [True, False]
        
        return ["test_data"]
    
    def generate_assertion(self, method: GoMethod) -> str:
        """生成断言代码.
        
        Args:
            method: 方法定义
            
        Returns:
            str: 断言代码
        """
        if not method.returns:
            return "// No return values to assert"
        
        assertions = []
        for i, ret in enumerate(method.returns, 1):
            ret_type = ret.get("type", "")
            if ret_type == "error":
                assertions.append(f"if (err != nil) != tt.wantErr {{")
                assertions.append(f'    t.Errorf("{method.name}() error = %v, wantErr %v", err, tt.wantErr)')
                assertions.append("    return")
                assertions.append("}")
            else:
                assertions.append(f"if got{i} != tt.want{i} {{")
                assertions.append(f'    t.Errorf("{method.name}() = %v, want %v", got{i}, tt.want{i})')
                assertions.append("}")
        
        return "\n".join(assertions)
    
    def generate_tests_for_struct(self, struct: GoStruct) -> str:
        """为结构体生成完整测试文件.
        
        Args:
            struct: 结构体定义
            
        Returns:
            str: 完整测试文件内容
        """
        lines = [
            f"package {struct.name.lower()}",
            "",
            "import (",
            '    "testing"',
            ")",
            "",
        ]
        
        # 为每个方法生成测试
        for method_name in struct.methods:
            lines.append(f"// Test{method_name} tests {method_name} method")
            lines.append(f"func Test{method_name}(t *testing.T) {{")
            lines.append("    t.Parallel()")
            lines.append("    // TODO: Implement test")
            lines.append("}")
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_benchmark(self, method: GoMethod) -> str:
        """生成基准测试.
        
        Args:
            method: 方法定义
            
        Returns:
            str: 基准测试代码
        """
        receiver_var = method.receiver.lower() if method.receiver else "s"
        param_values = ", ".join([p.get("name", "") for p in method.params])
        
        struct_name = method.receiver or 'Struct'
        return f"""func Benchmark{method.name}(b *testing.B) {{
    {receiver_var} := &{struct_name}{{}}
    
    b.ResetTimer()
    for i := 0; i < b.N; i++ {{
        {receiver_var}.{method.name}({param_values})
    }}
}}"""
    
    def generate_fuzz_test(self, method: GoMethod) -> str:
        """生成模糊测试.
        
        Args:
            method: 方法定义
            
        Returns:
            str: 模糊测试代码
        """
        receiver_var = method.receiver.lower() if method.receiver else "s"
        
        fuzz_params = []
        for param in method.params:
            param_type = param.get("type", "")
            if param_type == "string":
                fuzz_params.append(f'f.Fuzz(func(t *testing.T, {param.get("name", "s")} string)')
            elif param_type in ["int", "int64"]:
                fuzz_params.append(f'f.Fuzz(func(t *testing.T, {param.get("name", "n")} int64)')
        
        struct_name = method.receiver or 'Struct'
        return f"""func Fuzz{method.name}(f *testing.F) {{
    // Add seed corpus
    f.Add("seed data")
    
    f.Fuzz(func(t *testing.T, data []byte) {{
        {receiver_var} := &{struct_name}{{}}
        // TODO: Parse data and call method
        _ = {receiver_var}
    }})
}}"""
    
    def generate_example(self, method: GoMethod) -> str:
        """生成示例代码.
        
        Args:
            method: 方法定义
            
        Returns:
            str: 示例代码
        """
        receiver_var = method.receiver.lower() if method.receiver else "s"
        param_values = ", ".join([p.get("name", "") for p in method.params])
        
        struct_name = method.receiver or 'Struct'
        receiver_name = method.receiver or ''
        return f"""func Example{receiver_name}_{method.name}() {{
    {receiver_var} := &{struct_name}{{}}
    
    result := {receiver_var}.{method.name}({param_values})
    fmt.Println(result)
    
    // Output:
    // expected output
}}"""
    
    def generate_from_file(self, file_path: Path) -> str:
        """从 Go 文件生成测试.
        
        Args:
            file_path: Go 文件路径
            
        Returns:
            str: 生成的测试代码
        """
        result = self.analyzer.analyze_file(file_path)
        
        lines = [
            f"package {result.package or 'main'}_test",
            "",
            "import (",
            '    "testing"',
            ")",
            "",
        ]
        
        # 为每个导出方法生成测试
        for method in result.get_testable_methods():
            test_code = self.generate_test(method, template="table_driven")
            lines.append(test_code)
            lines.append("")
        
        return "\n".join(lines)
    
    def save_test(self, test_code: str, output_path: Path) -> None:
        """保存生成的测试文件.
        
        Args:
            test_code: 测试代码
            output_path: 输出路径
        """
        output_path.write_text(test_code, encoding="utf-8")
