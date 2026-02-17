"""TestGenerator 类测试模块."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage

from ut_agent.graph.state import GeneratedTestFile, CoverageGap
from ut_agent.tools.test_generator_v2 import (
    TestGenerator,
    TestGeneratorConfig,
    TestGenerationResult,
    TestGenerationStatus,
)
from ut_agent.utils.async_llm import AsyncLLMCaller, LLMCallResult, LLMCallStatus
from ut_agent.prompts.loader import PromptTemplate, PromptTemplateLoader


class MockAsyncLLMCaller:
    """Mock AsyncLLMCaller for testing."""

    def __init__(self, response_content: str = "Generated test code"):
        self._response_content = response_content
        self._call_count = 0
        self._last_prompt: Optional[str] = None

    async def call(self, prompt: str, **kwargs) -> LLMCallResult:
        self._call_count += 1
        self._last_prompt = prompt
        return LLMCallResult(
            status=LLMCallStatus.SUCCESS,
            content=self._response_content,
        )

    async def call_with_messages(self, messages, **kwargs) -> LLMCallResult:
        return LLMCallResult(
            status=LLMCallStatus.SUCCESS,
            content=self._response_content,
        )


class MockTemplateLoader:
    """Mock PromptTemplateLoader for testing."""

    def __init__(self):
        self._templates = {
            "java_test_full": PromptTemplate(
                name="java_test_full",
                content="Generate test for {{ class_name }}",
            ),
            "java_test_gap": PromptTemplate(
                name="java_test_gap",
                content="Generate test for gap in {{ class_name }}",
            ),
            "ts_test_full": PromptTemplate(
                name="ts_test_full",
                content="Generate test for {{ file_name }}",
            ),
            "vue_test_full": PromptTemplate(
                name="vue_test_full",
                content="Generate Vue test for {{ file_name }}",
            ),
        }

    def load_template(self, name: str) -> PromptTemplate:
        return self._templates.get(name, PromptTemplate(name=name, content="Default template"))

    def render(self, name: str, **kwargs) -> str:
        template = self.load_template(name)
        return template.render(**kwargs)


class TestTestGeneratorConfig:
    """TestGeneratorConfig 测试."""

    def test_default_config(self):
        """测试默认配置."""
        config = TestGeneratorConfig()
        assert config.use_boundary_values is True
        assert config.max_test_methods is None
        assert config.include_comments is True

    def test_custom_config(self):
        """测试自定义配置."""
        config = TestGeneratorConfig(
            use_boundary_values=False,
            max_test_methods=10,
            include_comments=False,
        )
        assert config.use_boundary_values is False
        assert config.max_test_methods == 10
        assert config.include_comments is False


class TestTestGenerationResult:
    """TestGenerationResult 测试."""

    def test_success_result(self):
        """测试成功结果."""
        result = TestGenerationResult(
            status=TestGenerationStatus.SUCCESS,
            test_file=GeneratedTestFile(
                source_file="/src/Main.java",
                test_file_path="/test/MainTest.java",
                test_code="public class MainTest {}",
                language="java",
            ),
        )
        assert result.status == TestGenerationStatus.SUCCESS
        assert result.success is True
        assert result.test_file is not None

    def test_failed_result(self):
        """测试失败结果."""
        result = TestGenerationResult(
            status=TestGenerationStatus.FAILED,
            errors=["Generation failed"],
        )
        assert result.status == TestGenerationStatus.FAILED
        assert result.success is False
        assert len(result.errors) == 1

    def test_skipped_result(self):
        """测试跳过结果."""
        result = TestGenerationResult(
            status=TestGenerationStatus.SKIPPED,
            warnings=["No methods to test"],
        )
        assert result.status == TestGenerationStatus.SKIPPED
        assert result.success is True


class TestTestGenerator:
    """TestGenerator 测试."""

    @pytest.fixture
    def llm_caller(self):
        """创建 Mock LLM 调用器."""
        return MockAsyncLLMCaller()

    @pytest.fixture
    def template_loader(self):
        """创建 Mock 模板加载器."""
        return MockTemplateLoader()

    @pytest.fixture
    def generator(self, llm_caller, template_loader):
        """创建测试生成器实例."""
        return TestGenerator(
            llm_caller=llm_caller,
            template_loader=template_loader,
        )

    @pytest.fixture
    def java_file_analysis(self):
        """创建 Java 文件分析结果."""
        return {
            "file_path": "/src/main/java/com/example/UserService.java",
            "class_name": "UserService",
            "package": "com.example",
            "methods": [
                {
                    "name": "getUser",
                    "signature": "public User getUser(Long id)",
                    "return_type": "User",
                    "is_public": True,
                },
                {
                    "name": "saveUser",
                    "signature": "public void saveUser(User user)",
                    "return_type": "void",
                    "is_public": True,
                },
            ],
            "fields": [
                {"name": "userRepository", "type": "UserRepository", "access": "private"},
            ],
        }

    @pytest.fixture
    def ts_file_analysis(self):
        """创建 TypeScript 文件分析结果."""
        return {
            "file_path": "/src/utils/helper.ts",
            "functions": [
                {
                    "name": "formatDate",
                    "parameters": [{"name": "date", "type": "Date"}],
                    "return_type": "string",
                    "is_exported": True,
                },
            ],
        }

    def test_generator_initialization(self, llm_caller, template_loader):
        """测试生成器初始化."""
        generator = TestGenerator(llm_caller=llm_caller, template_loader=template_loader)

        assert generator._llm_caller == llm_caller
        assert generator._template_loader == template_loader
        assert generator._config is not None

    @pytest.mark.asyncio
    async def test_generate_java_test(self, generator, java_file_analysis, llm_caller):
        """测试生成 Java 测试."""
        result = await generator.generate_java_test(java_file_analysis)

        assert result.success
        assert result.test_file is not None
        assert result.test_file.language == "java"
        assert "UserService" in result.test_file.test_file_path
        assert llm_caller._call_count == 1

    @pytest.mark.asyncio
    async def test_generate_java_test_with_gap(self, generator, java_file_analysis, llm_caller):
        """测试生成带覆盖率缺口的 Java 测试."""
        gap = CoverageGap(
            file_path="/src/main/java/com/example/UserService.java",
            line_number=42,
            line_content="return userRepository.findById(id);",
            gap_type="branch",
        )

        result = await generator.generate_java_test(java_file_analysis, gap_info=gap)

        assert result.success
        assert llm_caller._call_count == 1

    @pytest.mark.asyncio
    async def test_generate_typescript_test(self, generator, ts_file_analysis, llm_caller):
        """测试生成 TypeScript 测试."""
        result = await generator.generate_typescript_test(ts_file_analysis, "typescript")

        assert result.success
        assert result.test_file is not None
        assert result.test_file.language == "typescript"

    @pytest.mark.asyncio
    async def test_generate_vue_test(self, generator, llm_caller):
        """测试生成 Vue 测试."""
        file_analysis = {
            "file_path": "/src/components/Button.vue",
            "is_vue": True,
            "component_info": {
                "has_props": True,
                "has_emits": True,
            },
            "functions": [],
        }

        result = await generator.generate_frontend_test(file_analysis, "vue")

        assert result.success
        assert result.test_file is not None

    @pytest.mark.asyncio
    async def test_generate_with_custom_config(self, llm_caller, template_loader, java_file_analysis):
        """测试使用自定义配置生成."""
        config = TestGeneratorConfig(
            use_boundary_values=False,
            max_test_methods=5,
        )
        generator = TestGenerator(
            llm_caller=llm_caller,
            template_loader=template_loader,
            config=config,
        )

        result = await generator.generate_java_test(java_file_analysis)

        assert result.success

    @pytest.mark.asyncio
    async def test_generate_empty_methods(self, generator, llm_caller):
        """测试生成空方法列表的处理."""
        file_analysis = {
            "file_path": "/src/Empty.java",
            "class_name": "Empty",
            "package": "com.example",
            "methods": [],
        }

        result = await generator.generate_java_test(file_analysis)

        assert result.status == TestGenerationStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_generate_with_llm_failure(self, template_loader, java_file_analysis):
        """测试 LLM 调用失败的处理."""
        failing_caller = MockAsyncLLMCaller()
        failing_caller.call = AsyncMock(return_value=LLMCallResult(
            status=LLMCallStatus.FAILED,
            errors=["API error"],
        ))

        generator = TestGenerator(
            llm_caller=failing_caller,
            template_loader=template_loader,
        )

        result = await generator.generate_java_test(java_file_analysis)

        assert not result.success
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_batch_generate(self, generator, llm_caller):
        """测试批量生成."""
        file_analyses = [
            {
                "file_path": f"/src/Class{i}.java",
                "class_name": f"Class{i}",
                "package": "com.example",
                "methods": [{"name": "method", "signature": "void method()", "is_public": True}],
            }
            for i in range(3)
        ]

        results = await generator.batch_generate(file_analyses, "java")

        assert len(results) == 3
        assert all(r.success for r in results)
        assert llm_caller._call_count == 3

    @pytest.mark.asyncio
    async def test_generate_with_plan(self, generator, java_file_analysis, llm_caller):
        """测试带改进计划的生成."""
        plan = "Add more edge case tests for null inputs"

        result = await generator.generate_java_test(
            java_file_analysis,
            improvement_plan=plan,
        )

        assert result.success

    def test_get_supported_languages(self, generator):
        """测试获取支持的语言列表."""
        languages = generator.get_supported_languages()

        assert "java" in languages
        assert "typescript" in languages
        assert "vue" in languages
        assert "react" in languages


class TestTestGeneratorIntegration:
    """TestGenerator 集成测试."""

    @pytest.mark.asyncio
    async def test_full_generation_workflow(self):
        """测试完整生成工作流."""
        llm_caller = MockAsyncLLMCaller(response_content="""
package com.example;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class UserServiceTest {
    @Test
    void testGetUser() {
        // Test implementation
    }
}
""")
        template_loader = MockTemplateLoader()
        generator = TestGenerator(llm_caller=llm_caller, template_loader=template_loader)

        file_analysis = {
            "file_path": "/src/UserService.java",
            "class_name": "UserService",
            "package": "com.example",
            "methods": [
                {"name": "getUser", "signature": "User getUser(Long)", "is_public": True},
            ],
        }

        result = await generator.generate_java_test(file_analysis)

        assert result.success
        assert "UserServiceTest" in result.test_file.test_code
        assert "@Test" in result.test_file.test_code

    @pytest.mark.asyncio
    async def test_multi_language_generation(self):
        """测试多语言生成."""
        llm_caller = MockAsyncLLMCaller()
        template_loader = MockTemplateLoader()
        generator = TestGenerator(llm_caller=llm_caller, template_loader=template_loader)

        java_result = await generator.generate_java_test({
            "file_path": "/src/Service.java",
            "class_name": "Service",
            "package": "com.example",
            "methods": [{"name": "method", "signature": "void method()", "is_public": True}],
        })

        ts_result = await generator.generate_typescript_test({
            "file_path": "/src/utils.ts",
            "functions": [{"name": "helper", "is_exported": True}],
        }, "typescript")

        assert java_result.success
        assert ts_result.success
        assert java_result.test_file.language == "java"
        assert ts_result.test_file.language == "typescript"
