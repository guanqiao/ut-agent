"""Prompt 模板加载器测试模块."""

import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from ut_agent.prompts.loader import (
    PromptTemplate,
    PromptTemplateLoader,
    PromptTemplateRegistry,
    TemplateNotFoundError,
    TemplateRenderError,
)


class TestPromptTemplate:
    """PromptTemplate 测试."""

    def test_template_creation(self):
        """测试模板创建."""
        template = PromptTemplate(
            name="test_template",
            content="Hello, {{ name }}!",
            description="Test template",
        )
        assert template.name == "test_template"
        assert template.content == "Hello, {{ name }}!"
        assert template.description == "Test template"

    def test_template_render(self):
        """测试模板渲染."""
        template = PromptTemplate(
            name="test_template",
            content="Hello, {{ name }}! You are {{ age }} years old.",
        )

        result = template.render(name="Alice", age=30)

        assert result == "Hello, Alice! You are 30 years old."

    def test_template_render_with_default(self):
        """测试带默认值的模板渲染."""
        template = PromptTemplate(
            name="test_template",
            content="Hello, {{ name | default('Guest') }}!",
        )

        result = template.render()

        assert result == "Hello, Guest!"

    def test_template_render_with_missing_variable(self):
        """测试缺少变量时的渲染."""
        template = PromptTemplate(
            name="test_template",
            content="Hello, {{ name }}!",
        )

        result = template.render()

        assert "Hello," in result

    def test_template_render_with_filter(self):
        """测试带过滤器的模板渲染."""
        template = PromptTemplate(
            name="test_template",
            content="Items: {{ items | join(', ') }}",
        )

        result = template.render(items=["a", "b", "c"])

        assert result == "Items: a, b, c"

    def test_template_get_variables(self):
        """测试获取模板变量."""
        template = PromptTemplate(
            name="test_template",
            content="{{ name }} is {{ age }} years old.",
        )

        variables = template.get_variables()

        assert "name" in variables
        assert "age" in variables

    def test_template_to_dict(self):
        """测试模板转换为字典."""
        template = PromptTemplate(
            name="test_template",
            content="Hello, {{ name }}!",
            description="Test template",
            metadata={"version": "1.0"},
        )

        result = template.to_dict()

        assert result["name"] == "test_template"
        assert result["content"] == "Hello, {{ name }}!"
        assert result["description"] == "Test template"
        assert result["metadata"]["version"] == "1.0"


class TestPromptTemplateLoader:
    """PromptTemplateLoader 测试."""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def loader(self, temp_dir):
        """创建加载器实例."""
        return PromptTemplateLoader(template_dir=temp_dir)

    @pytest.fixture
    def sample_template_file(self, temp_dir):
        """创建示例模板文件."""
        template_content = """---
name: java_test
description: Java test template
language: java
version: "1.0"
---
作为 Java 单元测试专家，请为以下类生成测试：

目标类: {{ class_name }}
包名: {{ package }}

类方法:
{% for method in methods %}
- {{ method.name }}({{ method.params | join(', ') }})
{% endfor %}

请生成 JUnit 5 测试代码。
"""
        template_file = temp_dir / "java_test.yaml"
        template_file.write_text(template_content, encoding="utf-8")
        return template_file

    def test_loader_initialization(self, temp_dir):
        """测试加载器初始化."""
        loader = PromptTemplateLoader(template_dir=temp_dir)
        assert loader._template_dir == temp_dir
        assert loader._templates == {}

    def test_load_template_from_file(self, loader, sample_template_file):
        """测试从文件加载模板."""
        template = loader.load_template("java_test")

        assert template is not None
        assert template.name == "java_test"
        assert template.language == "java"

    def test_load_nonexistent_template(self, loader):
        """测试加载不存在的模板."""
        with pytest.raises(TemplateNotFoundError):
            loader.load_template("nonexistent")

    def test_load_all_templates(self, loader, temp_dir):
        """测试加载所有模板."""
        template1 = temp_dir / "template1.yaml"
        template1.write_text("""---
name: template1
---
Content 1
""", encoding="utf-8")

        template2 = temp_dir / "template2.yaml"
        template2.write_text("""---
name: template2
---
Content 2
""", encoding="utf-8")

        templates = loader.load_all_templates()

        assert len(templates) == 2
        assert "template1" in templates
        assert "template2" in templates

    def test_render_template(self, loader, sample_template_file):
        """测试渲染模板."""
        loader.load_template("java_test")

        result = loader.render(
            "java_test",
            class_name="UserService",
            package="com.example",
            methods=[
                {"name": "getUser", "params": ["id"]},
                {"name": "saveUser", "params": ["user"]},
            ],
        )

        assert "UserService" in result
        assert "com.example" in result
        assert "getUser(id)" in result
        assert "saveUser(user)" in result

    def test_reload_templates(self, loader, sample_template_file):
        """测试重新加载模板."""
        loader.load_template("java_test")

        new_content = """---
name: java_test
description: Updated template
---
Updated content for {{ class_name }}
"""
        sample_template_file.write_text(new_content, encoding="utf-8")

        loader.reload_template("java_test")

        template = loader.get_template("java_test")
        assert "Updated content" in template.content

    def test_get_template_names(self, loader, temp_dir):
        """测试获取模板名称列表."""
        for i in range(3):
            template_file = temp_dir / f"template{i}.yaml"
            template_file.write_text(f"""---
name: template{i}
---
Content {i}
""", encoding="utf-8")

        loader.load_all_templates()
        names = loader.get_template_names()

        assert len(names) == 3
        assert "template0" in names
        assert "template1" in names
        assert "template2" in names


class TestPromptTemplateRegistry:
    """PromptTemplateRegistry 测试."""

    @pytest.fixture
    def registry(self):
        """创建注册表实例."""
        return PromptTemplateRegistry()

    @pytest.fixture
    def sample_template(self):
        """创建示例模板."""
        return PromptTemplate(
            name="test_template",
            content="Hello, {{ name }}!",
            description="Test template",
            language="java",
        )

    def test_registry_initialization(self, registry):
        """测试注册表初始化."""
        assert registry._templates == {}

    def test_register_template(self, registry, sample_template):
        """测试注册模板."""
        registry.register(sample_template)

        assert "test_template" in registry._templates
        assert registry._templates["test_template"] == sample_template

    def test_get_template(self, registry, sample_template):
        """测试获取模板."""
        registry.register(sample_template)

        retrieved = registry.get_template("test_template")

        assert retrieved == sample_template

    def test_get_nonexistent_template(self, registry):
        """测试获取不存在的模板."""
        with pytest.raises(TemplateNotFoundError):
            registry.get_template("nonexistent")

    def test_get_templates_by_language(self, registry):
        """测试按语言获取模板."""
        java_template = PromptTemplate(
            name="java_template",
            content="Java content",
            language="java",
        )
        ts_template = PromptTemplate(
            name="ts_template",
            content="TypeScript content",
            language="typescript",
        )

        registry.register(java_template)
        registry.register(ts_template)

        java_templates = registry.get_templates_by_language("java")

        assert len(java_templates) == 1
        assert java_templates[0].name == "java_template"

    def test_unregister_template(self, registry, sample_template):
        """测试注销模板."""
        registry.register(sample_template)
        registry.unregister("test_template")

        assert "test_template" not in registry._templates

    def test_list_templates(self, registry, sample_template):
        """测试列出模板."""
        registry.register(sample_template)

        templates = registry.list_templates()

        assert len(templates) == 1
        assert templates[0]["name"] == "test_template"


class TestPromptTemplateIntegration:
    """Prompt 模板集成测试."""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_full_template_workflow(self, temp_dir):
        """测试完整模板工作流."""
        java_template = temp_dir / "java_test.yaml"
        java_template.write_text("""---
name: java_test
description: Java test template
language: java
version: "1.0"
---
作为 Java 单元测试专家，请为以下类生成测试：

目标类: {{ class_name }}
包名: {{ package }}

{% if methods %}
类方法:
{% for method in methods %}
- {{ method.signature }}
{% endfor %}
{% endif %}

{% if boundary_values %}
边界值测试数据:
{{ boundary_values }}
{% endif %}

请生成 JUnit 5 测试代码。
""", encoding="utf-8")

        ts_template = temp_dir / "ts_test.yaml"
        ts_template.write_text("""---
name: ts_test
description: TypeScript test template
language: typescript
version: "1.0"
---
作为 TypeScript 单元测试专家，请为以下代码生成测试：

文件名: {{ file_name }}

{% if functions %}
导出函数:
{% for func in functions %}
- {{ func.name }}({{ func.params | join(', ') }}): {{ func.return_type }}
{% endfor %}
{% endif %}

请生成 Vitest 测试代码。
""", encoding="utf-8")

        loader = PromptTemplateLoader(template_dir=temp_dir)
        templates = loader.load_all_templates()

        assert len(templates) == 2

        java_result = loader.render(
            "java_test",
            class_name="UserService",
            package="com.example.service",
            methods=[
                {"signature": "public User getUser(Long id)"},
                {"signature": "public void saveUser(User user)"},
            ],
            boundary_values="userId: [null, 0, 1, Long.MAX_VALUE]",
        )

        assert "UserService" in java_result
        assert "com.example.service" in java_result
        assert "getUser(Long id)" in java_result
        assert "Long.MAX_VALUE" in java_result

        ts_result = loader.render(
            "ts_test",
            file_name="utils.ts",
            functions=[
                {"name": "formatDate", "params": ["date: Date"], "return_type": "string"},
                {"name": "parseDate", "params": ["str: string"], "return_type": "Date"},
            ],
        )

        assert "utils.ts" in ts_result
        assert "formatDate" in ts_result
        assert "parseDate" in ts_result
