"""Go 测试生成器测试."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from ut_agent.tools.go_test_generator import GoTestGenerator, GoTestTemplate
from ut_agent.tools.go_analyzer import GoAnalyzer, GoMethod, GoStruct


class TestGoTestTemplate:
    """Go 测试模板测试."""

    def test_template_creation(self):
        """测试模板创建."""
        template = GoTestTemplate(
            name="table_driven",
            description="Table-driven test template",
            content="""
func Test{{.MethodName}}(t *testing.T) {
    tests := []struct {
        name string
        {{range .Params}}
        {{.name}} {{.type}}
        {{end}}
        want {{.ReturnType}}
    }{
        // TODO: Add test cases
    }
    
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            {{if .Receiver}}s := &{{.Receiver}}{}{{end}}
            got := s.{{.MethodName}}({{range .Params}}tt.{{.name}}, {{end}})
            if got != tt.want {
                t.Errorf("{{.MethodName}}() = %v, want %v", got, tt.want)
            }
        })
    }
}
"""
        )
        assert template.name == "table_driven"
        assert "{{.MethodName}}" in template.content

    def test_template_rendering(self):
        """测试模板渲染."""
        template = GoTestTemplate(
            name="simple",
            content="func Test{{ method_name }}(t *testing.T) { {{ receiver_var }}.{{ method_name }}() }"
        )
        
        rendered = template.render({
            "method_name": "Add",
            "receiver_var": "calc"
        })
        
        assert "TestAdd" in rendered
        assert "calc.Add()" in rendered


class TestGoTestGenerator:
    """Go 测试生成器测试."""

    @pytest.fixture
    def generator(self):
        """创建生成器实例."""
        return GoTestGenerator()

    @pytest.fixture
    def sample_struct(self):
        """示例结构体."""
        return GoStruct(
            name="Calculator",
            fields=[],
            methods=["Add", "Subtract"]
        )

    @pytest.fixture
    def sample_method(self):
        """示例方法."""
        return GoMethod(
            name="Add",
            receiver="Calculator",
            params=[{"name": "a", "type": "int"}, {"name": "b", "type": "int"}],
            returns=[{"type": "int"}],
            is_exported=True
        )

    def test_generate_table_driven_test(self, generator, sample_method):
        """测试生成表格驱动测试."""
        test_code = generator.generate_test(sample_method, template="table_driven")
        
        assert "func TestAdd" in test_code
        assert "tests := []struct" in test_code
        assert "for _, tt := range tests" in test_code
        assert "t.Run(tt.name" in test_code

    def test_generate_simple_test(self, generator, sample_method):
        """测试生成简单测试."""
        test_code = generator.generate_test(sample_method, template="simple")
        
        assert "func TestAdd" in test_code
        assert "t *testing.T" in test_code

    def test_generate_mock_setup(self, generator):
        """测试生成 Mock 设置."""
        struct = GoStruct(
            name="UserService",
            fields=[
                {"name": "repo", "type": "UserRepository", "is_interface": True},
                {"name": "cache", "type": "Cache", "is_interface": True}
            ],
            methods=[]
        )
        
        mock_code = generator.generate_mock_setup(struct)
        
        assert "mockRepo" in mock_code or "Repo" in mock_code
        assert "mockCache" in mock_code or "Cache" in mock_code

    def test_generate_test_file_header(self, generator):
        """测试生成测试文件头."""
        header = generator.generate_file_header(
            package="service",
            imports=["testing", "github.com/stretchr/testify/mock"]
        )
        
        assert "package service" in header
        assert "import" in header
        assert "testing" in header

    def test_generate_test_data(self, generator):
        """测试生成测试数据."""
        test_data = generator.generate_test_data("int", "boundary")
        
        assert isinstance(test_data, list)
        assert len(test_data) > 0
        # 边界值应该包含 0, 1, -1, MaxInt, MinInt
        assert any(d in [0, 1, -1] for d in test_data)

    def test_generate_test_data_string(self, generator):
        """测试生成字符串测试数据."""
        test_data = generator.generate_test_data("string", "boundary")
        
        assert isinstance(test_data, list)
        # 应该包含空字符串、普通字符串、超长字符串
        assert any(d == "" for d in test_data)
        assert any(len(d) > 10 for d in test_data if d)

    def test_generate_assertion(self, generator, sample_method):
        """测试生成断言."""
        assertion = generator.generate_assertion(sample_method)
        
        assert "if got" in assertion or "assert" in assertion

    def test_generate_test_for_struct(self, generator, sample_struct):
        """测试为结构体生成完整测试."""
        test_file = generator.generate_tests_for_struct(sample_struct)
        
        assert "package" in test_file
        assert "TestAdd" in test_file or "TestCalculator" in test_file

    def test_generate_gomock_test(self, generator):
        """测试生成 gomock 测试."""
        method = GoMethod(
            name="GetUser",
            receiver="UserService",
            params=[{"name": "id", "type": "int64"}],
            returns=[{"type": "*User"}, {"type": "error"}],
            is_exported=True
        )
        
        test_code = generator.generate_test(method, template="gomock")
        
        assert "gomock" in test_code or "mock" in test_code.lower()
        assert "EXPECT()" in test_code or "mock" in test_code.lower()

    def test_generate_benchmark(self, generator, sample_method):
        """测试生成基准测试."""
        benchmark = generator.generate_benchmark(sample_method)
        
        assert "func Benchmark" in benchmark
        assert "for i := 0; i < b.N; i++" in benchmark

    def test_generate_fuzz_test(self, generator, sample_method):
        """测试生成模糊测试."""
        fuzz_test = generator.generate_fuzz_test(sample_method)
        
        assert "func Fuzz" in fuzz_test or "testing.F" in fuzz_test

    def test_generate_example_test(self, generator, sample_method):
        """测试生成示例测试."""
        example = generator.generate_example(sample_method)
        
        assert "func Example" in example
        assert "// Output:" in example


class TestGoTestGeneratorIntegration:
    """Go 测试生成器集成测试."""

    def test_generate_from_file(self, tmp_path):
        """测试从文件生成测试."""
        go_file = tmp_path / "calculator.go"
        go_file.write_text('''
package calc

type Calculator struct{}

func (c *Calculator) Add(a, b int) int {
    return a + b
}
''')
        
        generator = GoTestGenerator()
        test_file = generator.generate_from_file(go_file)
        
        assert "package calc" in test_file
        assert "TestAdd" in test_file

    def test_generate_complete_test_file(self, tmp_path):
        """测试生成完整测试文件."""
        go_file = tmp_path / "service.go"
        go_file.write_text('''
package service

type UserRepository interface {
    FindByID(id int64) (*User, error)
}

type User struct {
    ID   int64
    Name string
}

type UserService struct {
    repo UserRepository
}

func NewUserService(repo UserRepository) *UserService {
    return &UserService{repo: repo}
}

func (s *UserService) GetUser(id int64) (*User, error) {
    return s.repo.FindByID(id)
}
''')
        
        generator = GoTestGenerator()
        test_file = generator.generate_from_file(go_file)
        
        # 应该包含测试文件的所有部分
        assert "package service" in test_file
        assert "func Test" in test_file

    def test_save_generated_test(self, tmp_path):
        """测试保存生成的测试文件."""
        generator = GoTestGenerator()
        test_code = '''
package test

import "testing"

func TestSomething(t *testing.T) {}
'''
        output_path = tmp_path / "something_test.go"
        
        generator.save_test(test_code, output_path)
        
        assert output_path.exists()
        assert output_path.read_text() == test_code
