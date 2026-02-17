"""Rust 测试生成器测试."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from ut_agent.tools.rust_test_generator import RustTestGenerator, RustTestTemplate
from ut_agent.tools.rust_analyzer import RustAnalyzer, RustFunction, RustStruct, RustTrait


class TestRustTestTemplate:
    """Rust 测试模板测试."""

    def test_template_creation(self):
        """测试模板创建."""
        template = RustTestTemplate(
            name="standard",
            description="Standard Rust test template",
            content="""
#[test]
fn test_{{ function_name }}() {
    {% if is_async %}#[tokio::test]
    async {% endif %}fn test_{{ function_name }}() {
        // Arrange
        {% if has_receiver %}let instance = {{ struct_name }}::new();{% endif %}
        
        // Act
        {% if has_return %}let result = {% endif %}{% if has_receiver %}instance.{% endif %}{{ function_name }}({{ param_values }});
        
        // Assert
        {% if has_return %}assert!(result.is_ok());{% endif %}
    }
}
"""
        )
        assert template.name == "standard"
        assert "{{ function_name }}" in template.content

    def test_template_rendering(self):
        """测试模板渲染."""
        template = RustTestTemplate(
            name="simple",
            content="#[test]\nfn test_{{ function_name }}() { assert!(true); }"
        )
        
        rendered = template.render({
            "function_name": "add"
        })
        
        assert "test_add" in rendered
        assert "assert!(true)" in rendered


class TestRustTestGenerator:
    """Rust 测试生成器测试."""

    @pytest.fixture
    def generator(self):
        """创建生成器实例."""
        return RustTestGenerator()

    @pytest.fixture
    def sample_function(self):
        """示例函数."""
        return RustFunction(
            name="add",
            params=[{"name": "a", "type": "i32"}, {"name": "b", "type": "i32"}],
            return_type="i32",
            is_async=False,
            is_public=True
        )

    @pytest.fixture
    def sample_async_function(self):
        """示例异步函数."""
        return RustFunction(
            name="fetch_data",
            params=[{"name": "url", "type": "String"}],
            return_type="Result<String, Error>",
            is_async=True,
            is_public=True
        )

    def test_generate_standard_test(self, generator, sample_function):
        """测试生成标准测试."""
        test_code = generator.generate_test(sample_function, template="standard")
        
        assert "#[test]" in test_code
        assert "fn test_add" in test_code
        assert "add(" in test_code

    def test_generate_async_test(self, generator, sample_async_function):
        """测试生成异步测试."""
        test_code = generator.generate_test(sample_async_function, template="standard")
        
        assert "#[tokio::test]" in test_code
        assert "async fn test_fetch_data" in test_code
        assert ".await" in test_code

    def test_generate_mockall_test(self, generator):
        """测试生成 mockall Mock 测试."""
        func = RustFunction(
            name="get_user",
            params=[{"name": "id", "type": "i64"}],
            return_type="Option<User>",
            is_async=False,
            is_public=True
        )
        
        test_code = generator.generate_test(func, template="mockall")
        
        # mockall 模板应该包含基本的测试结构
        assert "#[test]" in test_code
        assert "fn test_get_user" in test_code

    def test_generate_test_file_header(self, generator):
        """测试生成测试文件头."""
        header = generator.generate_file_header(
            module="user_service",
            imports=["tokio", "mockall"]
        )
        
        assert "use" in header
        assert "tokio" in header
        assert "mockall" in header or "super" in header

    def test_generate_test_data(self, generator):
        """测试生成测试数据."""
        test_data = generator.generate_test_data("i32", "boundary")
        
        assert isinstance(test_data, list)
        assert len(test_data) > 0
        # 边界值应该包含 0, 1, -1, i32::MAX, i32::MIN
        assert any(d in [0, 1, -1] for d in test_data)

    def test_generate_test_data_string(self, generator):
        """测试生成字符串测试数据."""
        test_data = generator.generate_test_data("String", "boundary")
        
        assert isinstance(test_data, list)
        # 应该包含字符串测试数据
        assert len(test_data) > 0

    def test_generate_test_data_result(self, generator):
        """测试生成 Result 类型测试数据."""
        test_data = generator.generate_test_data("Result<i32, Error>", "boundary")
        
        assert isinstance(test_data, list)
        # 应该包含 Result 类型数据
        assert len(test_data) > 0

    def test_generate_assertion(self, generator, sample_function):
        """测试生成断言."""
        assertion = generator.generate_assertion(sample_function)
        
        assert "assert" in assertion.lower()

    def test_generate_assertion_for_result(self, generator):
        """测试为 Result 类型生成断言."""
        func = RustFunction(
            name="divide",
            params=[{"name": "a", "type": "f64"}, {"name": "b", "type": "f64"}],
            return_type="Result<f64, String>",
            is_async=False,
            is_public=True
        )
        
        assertion = generator.generate_assertion(func)
        
        assert "assert" in assertion.lower() or "is_ok" in assertion or "is_err" in assertion

    def test_generate_tests_for_struct(self, generator):
        """测试为结构体生成完整测试."""
        struct = RustStruct(
            name="Calculator",
            fields=[{"name": "value", "type": "i32", "is_public": False}],
            is_public=True
        )
        
        test_file = generator.generate_tests_for_struct(struct, methods=["add", "subtract"])
        
        assert "mod tests" in test_file or "#[cfg(test)]" in test_file
        assert "test_add" in test_file or "TestCalculator" in test_file

    def test_generate_benchmark(self, generator, sample_function):
        """测试生成基准测试."""
        benchmark = generator.generate_benchmark(sample_function)
        
        assert "#[bench]" in benchmark or "fn bench_" in benchmark
        assert "bencher" in benchmark.lower() or "criterion" in benchmark.lower()

    def test_generate_doc_test(self, generator, sample_function):
        """测试生成文档测试."""
        doc_test = generator.generate_doc_test(sample_function)
        
        assert "///" in doc_test
        assert "```" in doc_test
        assert "# Examples" in doc_test or sample_function.name in doc_test

    def test_generate_property_test(self, generator, sample_function):
        """测试生成属性测试 (proptest)."""
        prop_test = generator.generate_property_test(sample_function)
        
        assert "proptest!" in prop_test or "#[proptest]" in prop_test

    def test_generate_integration_test(self, generator):
        """测试生成集成测试."""
        func = RustFunction(
            name="create_user",
            params=[{"name": "name", "type": "String"}],
            return_type="Result<User, Error>",
            is_async=True,
            is_public=True
        )
        
        test_code = generator.generate_integration_test(func)
        
        assert "#[tokio::test]" in test_code or "async" in test_code


class TestRustTestGeneratorIntegration:
    """Rust 测试生成器集成测试."""

    def test_generate_from_file(self, tmp_path):
        """测试从文件生成测试."""
        rust_file = tmp_path / "calculator.rs"
        rust_file.write_text('''
pub struct Calculator {
    value: i32,
}

impl Calculator {
    pub fn new() -> Self {
        Self { value: 0 }
    }

    pub fn add(&self, a: i32, b: i32) -> i32 {
        a + b
    }
}
''')
        
        generator = RustTestGenerator()
        test_file = generator.generate_from_file(rust_file)
        
        assert "#[cfg(test)]" in test_file or "mod tests" in test_file
        assert "test_add" in test_file

    def test_generate_with_mocks(self, tmp_path):
        """测试生成带 Mock 的测试."""
        rust_file = tmp_path / "service.rs"
        rust_file.write_text('''
pub trait Repository {
    fn find(&self, id: i64) -> Option<String>;
}

pub struct Service {
    repo: Box<dyn Repository>,
}

impl Service {
    pub fn new(repo: Box<dyn Repository>) -> Self {
        Self { repo }
    }

    pub fn get(&self, id: i64) -> Option<String> {
        self.repo.find(id)
    }
}
''')
        
        generator = RustTestGenerator()
        test_file = generator.generate_from_file(rust_file)
        
        # 应该包含 Mock 设置
        assert "mock!" in test_file or "MockRepository" in test_file or "test_get" in test_file

    def test_save_generated_test(self, tmp_path):
        """测试保存生成的测试文件."""
        generator = RustTestGenerator()
        test_code = '''
#[cfg(test)]
mod tests {
    #[test]
    fn test_something() {}
}
'''
        output_path = tmp_path / "something_test.rs"
        
        generator.save_test(test_code, output_path)
        
        assert output_path.exists()
        assert output_path.read_text() == test_code
