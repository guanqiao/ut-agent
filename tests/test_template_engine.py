"""模板引擎模块单元测试."""

import tempfile
from pathlib import Path

import pytest

from ut_agent.templates.template_engine import (
    TemplateEngine,
    TemplateManager,
    UnitTestTemplate,
    lower_first,
)


class TestUnitTestTemplate:
    """UnitTestTemplate 数据类测试."""

    def test_template_creation(self):
        """测试模板创建."""
        template = UnitTestTemplate(
            name="test-template",
            description="Test template description",
            language="java",
            framework="junit5",
            template_content="public class {{ class_name }} {}",
            variables={"class_name": "TestClass"},
            tags=["spring", "test"],
            author="Test Author",
            version="1.0.0",
        )

        assert template.name == "test-template"
        assert template.language == "java"
        assert template.framework == "junit5"
        assert "class_name" in template.variables

    def test_template_defaults(self):
        """测试模板默认值."""
        template = UnitTestTemplate(
            name="simple-template",
            description="Simple template",
            language="typescript",
            framework="vitest",
            template_content="test",
        )

        assert template.variables == {}
        assert template.tags == []
        assert template.author == ""
        assert template.version == "1.0.0"


class TestTemplateEngine:
    """TemplateEngine 测试."""

    @pytest.fixture
    def engine(self):
        """创建模板引擎实例."""
        return TemplateEngine()

    @pytest.fixture
    def sample_template(self):
        """创建示例模板."""
        return UnitTestTemplate(
            name="sample",
            description="Sample template",
            language="java",
            framework="junit5",
            template_content="""package {{ package }};

public class {{ class_name }}Test {
    {% for method in methods %}
    void test_{{ method.name }}() {}
    {% endfor %}
}""",
        )

    def test_register_template(self, engine, sample_template):
        """测试注册模板."""
        engine.register_template(sample_template)

        retrieved = engine.get_template("sample")
        assert retrieved is not None
        assert retrieved.name == "sample"

    def test_get_nonexistent_template(self, engine):
        """测试获取不存在的模板."""
        result = engine.get_template("nonexistent")
        assert result is None

    def test_list_templates(self, engine):
        """测试列出模板."""
        template1 = UnitTestTemplate(
            name="java-template",
            description="Java template",
            language="java",
            framework="junit5",
            template_content="test",
        )
        template2 = UnitTestTemplate(
            name="ts-template",
            description="TypeScript template",
            language="typescript",
            framework="vitest",
            template_content="test",
        )

        engine.register_template(template1)
        engine.register_template(template2)

        all_templates = engine.list_templates()
        assert len(all_templates) == 2

    def test_list_templates_with_filter(self, engine):
        """测试带过滤条件的模板列表."""
        template1 = UnitTestTemplate(
            name="java-template",
            description="Java template",
            language="java",
            framework="junit5",
            template_content="test",
        )
        template2 = UnitTestTemplate(
            name="ts-template",
            description="TypeScript template",
            language="typescript",
            framework="vitest",
            template_content="test",
        )

        engine.register_template(template1)
        engine.register_template(template2)

        java_templates = engine.list_templates(language="java")
        assert len(java_templates) == 1
        assert java_templates[0].language == "java"

        vitest_templates = engine.list_templates(framework="vitest")
        assert len(vitest_templates) == 1
        assert vitest_templates[0].framework == "vitest"

    def test_render_template(self, engine, sample_template):
        """测试渲染模板."""
        engine.register_template(sample_template)

        context = {
            "package": "com.example",
            "class_name": "UserService",
            "methods": [{"name": "getUser"}, {"name": "saveUser"}],
        }

        result = engine.render("sample", context)

        assert "package com.example;" in result
        assert "UserServiceTest" in result
        # Jinja2 循环会生成多行
        assert "test_getUser" in result or "getUser" in result
        assert "test_saveUser" in result or "saveUser" in result

    def test_render_nonexistent_template(self, engine):
        """测试渲染不存在的模板."""
        from ut_agent.exceptions import TemplateNotFoundError
        with pytest.raises(TemplateNotFoundError):
            engine.render("nonexistent", {})

    def test_render_string(self, engine):
        """测试渲染字符串模板."""
        template_string = "Hello, {{ name }}!"
        context = {"name": "World"}

        result = engine.render_string(template_string, context)
        assert result == "Hello, World!"

    def test_render_with_conditionals(self, engine):
        """测试带条件语句的模板渲染."""
        template_string = """
{% if show_header %}
Header: {{ header_text }}
{% endif %}
Content
"""
        context = {"show_header": True, "header_text": "Test Header"}

        result = engine.render_string(template_string, context)
        assert "Header: Test Header" in result
        assert "Content" in result


class TestTemplateManager:
    """TemplateManager 测试."""

    def test_manager_initialization(self):
        """测试管理器初始化."""
        manager = TemplateManager()

        # 检查内置模板是否已加载
        templates = manager.list_templates()
        assert len(templates) > 0

    def test_get_builtin_templates(self):
        """测试获取内置模板."""
        manager = TemplateManager()

        java_templates = manager.list_templates(language="java")
        assert len(java_templates) >= 3  # controller, service, repository

        ts_templates = manager.list_templates(language="typescript")
        assert len(ts_templates) >= 2  # utility, hook

    def test_select_template_for_java_controller(self):
        """测试为 Java Controller 选择模板."""
        manager = TemplateManager()

        file_analysis = {
            "language": "java",
            "content": "@RestController public class UserController {}",
        }

        template = manager.select_template_for_file(file_analysis)
        assert template is not None
        assert template.name == "java-spring-controller"

    def test_select_template_for_java_service(self):
        """测试为 Java Service 选择模板."""
        manager = TemplateManager()

        file_analysis = {
            "language": "java",
            "content": "@Service public class UserService {}",
        }

        template = manager.select_template_for_file(file_analysis)
        assert template is not None
        assert template.name == "java-spring-service"

    def test_select_template_for_java_repository(self):
        """测试为 Java Repository 选择模板."""
        manager = TemplateManager()

        file_analysis = {
            "language": "java",
            "content": "@Repository public interface UserRepository extends JpaRepository {}",
        }

        template = manager.select_template_for_file(file_analysis)
        assert template is not None
        assert template.name == "java-spring-repository"

    def test_select_template_for_vue(self):
        """测试为 Vue 文件选择模板."""
        manager = TemplateManager()

        file_analysis = {"language": "vue", "content": "<template></template>"}

        template = manager.select_template_for_file(file_analysis)
        assert template is not None
        assert template.name == "vue-component"

    def test_select_template_for_react_hook(self):
        """测试为 React Hook 选择模板."""
        manager = TemplateManager()

        file_analysis = {
            "language": "typescript",
            "file_name": "useAuth.ts",
            "content": "export function useAuth() {}",
        }

        template = manager.select_template_for_file(file_analysis)
        assert template is not None
        assert template.name == "react-hook"

    def test_select_template_for_ts_utility(self):
        """测试为 TypeScript 工具函数选择模板."""
        manager = TemplateManager()

        file_analysis = {
            "language": "typescript",
            "file_name": "utils.ts",
            "content": "export function helper() {}",
        }

        template = manager.select_template_for_file(file_analysis)
        assert template is not None
        assert template.name == "ts-utility"

    def test_select_template_for_unknown_language(self):
        """测试为未知语言选择模板."""
        manager = TemplateManager()

        file_analysis = {"language": "ruby", "content": "def test; end"}

        template = manager.select_template_for_file(file_analysis)
        assert template is None

    def test_render_template(self):
        """测试通过管理器渲染模板."""
        manager = TemplateManager()

        context = {
            "package": "com.example",
            "class_name": "UserService",
            "methods": [],
            "mocks": [],
        }

        result = manager.render_template("java-spring-service", context)

        assert "package com.example;" in result
        assert "UserServiceTest" in result
        assert "@ExtendWith(MockitoExtension.class)" in result

    def test_load_custom_templates(self):
        """测试加载自定义模板."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建自定义模板文件
            template_content = """
name: custom-template
description: Custom test template
language: java
framework: junit5
template: |
  public class {{ class_name }} {
      // Custom template
  }
variables: {}
tags: [custom]
version: "1.0.0"
"""
            template_file = Path(tmpdir) / "custom-template.yaml"
            template_file.write_text(template_content)

            manager = TemplateManager(custom_templates_dir=tmpdir)

            template = manager.get_template("custom-template")
            assert template is not None
            assert template.name == "custom-template"

    def test_create_custom_template(self):
        """测试创建自定义模板."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = TemplateManager(custom_templates_dir=tmpdir)

            manager.create_custom_template(
                name="my-template",
                description="My custom template",
                language="java",
                framework="junit5",
                template_content="public class {{ name }} {}",
                variables={"name": "Default"},
                tags=["custom", "test"],
            )

            # 验证文件已创建
            template_file = Path(tmpdir) / "my-template.yaml"
            assert template_file.exists()

            # 验证模板已注册
            template = manager.get_template("my-template")
            assert template is not None
            assert template.name == "my-template"

    def test_create_custom_template_without_dir(self):
        """测试在没有配置目录时创建模板."""
        manager = TemplateManager()

        with pytest.raises(ValueError, match="未配置自定义模板目录"):
            manager.create_custom_template(
                name="my-template",
                description="My template",
                language="java",
                framework="junit5",
                template_content="test",
            )


class TestLowerFirst:
    """lower_first 过滤器测试."""

    def test_lower_first_normal(self):
        """测试正常字符串."""
        assert lower_first("HelloWorld") == "helloWorld"
        assert lower_first("Test") == "test"
        assert lower_first("ABC") == "aBC"

    def test_lower_first_empty(self):
        """测试空字符串."""
        assert lower_first("") == ""

    def test_lower_first_single_char(self):
        """测试单字符."""
        assert lower_first("A") == "a"
        assert lower_first("a") == "a"

    def test_lower_first_already_lower(self):
        """测试已经是小写的字符串."""
        assert lower_first("hello") == "hello"
