"""C# 测试生成器测试."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from ut_agent.tools.cs_test_generator import CsTestGenerator, CsTestTemplate
from ut_agent.tools.cs_analyzer import CsAnalyzer, CsMethod, CsClass


class TestCsTestTemplate:
    """C# 测试模板测试."""

    def test_template_creation(self):
        """测试模板创建."""
        template = CsTestTemplate(
            name="xunit",
            description="xUnit test template",
            content="""
[Fact]
public void Test{{ method_name }}()
{
    // Arrange
    {{ arrange_code }}
    
    // Act
    {{ act_code }}
    
    // Assert
    {{ assert_code }}
}
"""
        )
        assert template.name == "xunit"
        assert "{{ method_name }}" in template.content

    def test_template_rendering(self):
        """测试模板渲染."""
        template = CsTestTemplate(
            name="simple",
            content="[Fact]\npublic void Test{{ method_name }}() { Assert.True(true); }"
        )
        
        rendered = template.render({
            "method_name": "Add"
        })
        
        assert "TestAdd" in rendered
        assert "Assert.True" in rendered


class TestCsTestGenerator:
    """C# 测试生成器测试."""

    @pytest.fixture
    def generator(self):
        """创建生成器实例."""
        return CsTestGenerator()

    @pytest.fixture
    def sample_method(self):
        """示例方法."""
        return CsMethod(
            name="Add",
            return_type="int",
            parameters=[{"name": "a", "type": "int"}, {"name": "b", "type": "int"}],
            is_async=False,
            is_static=False,
            is_public=True
        )

    @pytest.fixture
    def sample_async_method(self):
        """示例异步方法."""
        return CsMethod(
            name="GetUserAsync",
            return_type="Task<User>",
            parameters=[{"name": "id", "type": "long"}],
            is_async=True,
            is_public=True
        )

    def test_generate_xunit_test(self, generator, sample_method):
        """测试生成 xUnit 测试."""
        test_code = generator.generate_test(sample_method, template="xunit")
        
        assert "[Fact]" in test_code
        assert "public void TestAdd" in test_code
        assert "Add(" in test_code

    def test_generate_nunit_test(self, generator, sample_method):
        """测试生成 NUnit 测试."""
        test_code = generator.generate_test(sample_method, template="nunit")
        
        assert "[Test]" in test_code
        assert "public void TestAdd" in test_code

    def test_generate_mstest_test(self, generator, sample_method):
        """测试生成 MSTest 测试."""
        test_code = generator.generate_test(sample_method, template="mstest")
        
        assert "[TestMethod]" in test_code
        assert "public void TestAdd" in test_code

    def test_generate_async_test(self, generator, sample_async_method):
        """测试生成异步测试."""
        test_code = generator.generate_test(sample_async_method, template="xunit")
        
        assert "[Fact]" in test_code
        assert "public async Task TestGetUserAsync" in test_code
        assert "await" in test_code

    def test_generate_moq_test(self, generator):
        """测试生成 Moq Mock 测试."""
        method = CsMethod(
            name="GetUser",
            return_type="User",
            parameters=[{"name": "id", "type": "long"}],
            is_async=False,
            is_public=True
        )
        
        test_code = generator.generate_test(method, template="moq")
        
        assert "Mock<" in test_code or "mock" in test_code.lower()
        assert "Setup" in test_code or "Returns" in test_code

    def test_generate_test_file_header(self, generator):
        """测试生成测试文件头."""
        header = generator.generate_file_header(
            namespace="MyApp.Tests",
            usings=["Xunit", "Moq"]
        )
        
        assert "namespace MyApp.Tests" in header
        assert "using Xunit" in header
        assert "using Moq" in header

    def test_generate_test_data(self, generator):
        """测试生成测试数据."""
        test_data = generator.generate_test_data("int", "boundary")
        
        assert isinstance(test_data, list)
        assert len(test_data) > 0
        # 边界值应该包含 0, 1, -1
        assert any(d in [0, 1, -1] for d in test_data)

    def test_generate_test_data_string(self, generator):
        """测试生成字符串测试数据."""
        test_data = generator.generate_test_data("string", "boundary")
        
        assert isinstance(test_data, list)
        # 应该包含字符串测试数据
        assert len(test_data) > 0

    def test_generate_assertion(self, generator, sample_method):
        """测试生成断言."""
        assertion = generator.generate_assertion(sample_method)
        
        assert "Assert" in assertion

    def test_generate_assertion_for_task(self, generator):
        """测试为 Task 类型生成断言."""
        method = CsMethod(
            name="SaveAsync",
            return_type="Task<bool>",
            parameters=[],
            is_async=True,
            is_public=True
        )
        
        assertion = generator.generate_assertion(method)
        
        assert "Assert" in assertion or "True" in assertion

    def test_generate_tests_for_class(self, generator):
        """测试为类生成完整测试."""
        cls = CsClass(
            name="Calculator",
            namespace="MyApp",
            methods=["Add", "Subtract"],
            is_public=True
        )
        
        test_file = generator.generate_tests_for_class(cls)
        
        assert "namespace" in test_file
        assert "public class CalculatorTests" in test_file or "TestAdd" in test_file

    def test_generate_theory_test(self, generator, sample_method):
        """测试生成 Theory 测试 (参数化测试)."""
        test_code = generator.generate_theory_test(sample_method)
        
        assert "[Theory]" in test_code
        assert "[InlineData" in test_code

    def test_generate_benchmark(self, generator, sample_method):
        """测试生成基准测试."""
        benchmark = generator.generate_benchmark(sample_method)
        
        assert "[Benchmark]" in benchmark or "BenchmarkDotNet" in benchmark


class TestCsTestGeneratorIntegration:
    """C# 测试生成器集成测试."""

    def test_generate_from_file(self, tmp_path):
        """测试从文件生成测试."""
        cs_file = tmp_path / "Calculator.cs"
        cs_file.write_text('''
using System;

namespace MyApp
{
    public class Calculator
    {
        public int Add(int a, int b)
        {
            return a + b;
        }
    }
}
''')
        
        generator = CsTestGenerator()
        test_file = generator.generate_from_file(cs_file)
        
        assert "namespace" in test_file
        assert "TestAdd" in test_file

    def test_generate_with_mocks(self, tmp_path):
        """测试生成带 Mock 的测试."""
        cs_file = tmp_path / "Service.cs"
        cs_file.write_text('''
using System;

namespace MyApp
{
    public interface IRepository
    {
        string Find(long id);
    }

    public class Service
    {
        private readonly IRepository _repository;

        public Service(IRepository repository)
        {
            _repository = repository;
        }

        public string Get(long id)
        {
            return _repository.Find(id);
        }
    }
}
''')
        
        generator = CsTestGenerator()
        test_file = generator.generate_from_file(cs_file)
        
        # 应该包含 Mock 设置
        assert "Mock" in test_file or "mock" in test_file.lower() or "TestGet" in test_file

    def test_save_generated_test(self, tmp_path):
        """测试保存生成的测试文件."""
        generator = CsTestGenerator()
        test_code = '''
using Xunit;

namespace MyApp.Tests
{
    public class CalculatorTests
    {
        [Fact]
        public void TestAdd()
        {
            Assert.True(true);
        }
    }
}
'''
        output_path = tmp_path / "CalculatorTests.cs"
        
        generator.save_test(test_code, output_path)
        
        assert output_path.exists()
        assert output_path.read_text() == test_code
