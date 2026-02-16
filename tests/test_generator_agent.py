"""Generator Agent 单元测试."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ut_agent.agents.generator import (
    GeneratorAgent,
    TemplateSelector,
)
from ut_agent.agents.base import (
    AgentContext,
    AgentResult,
    AgentStatus,
)


class TestTemplateSelector:
    """TemplateSelector 测试."""

    def test_select_java_controller_template(self):
        file_analysis = {
            "language": "java",
            "class_name": "UserController",
            "annotations": ["RestController"],
            "file_path": "/src/UserController.java",
        }
        result = TemplateSelector.select_template(file_analysis)
        assert result["type"] == "controller"
        assert "WebMvcTest" in result["imports"][0]

    def test_select_java_service_template(self):
        file_analysis = {
            "language": "java",
            "class_name": "UserService",
            "annotations": ["Service"],
            "file_path": "/src/UserService.java",
        }
        result = TemplateSelector.select_template(file_analysis)
        assert result["type"] == "service"

    def test_select_java_repository_template(self):
        file_analysis = {
            "language": "java",
            "class_name": "UserRepository",
            "annotations": ["Repository"],
            "file_path": "/src/UserRepository.java",
        }
        result = TemplateSelector.select_template(file_analysis)
        assert result["type"] == "repository"

    def test_select_java_util_template(self):
        file_analysis = {
            "language": "java",
            "class_name": "StringUtils",
            "annotations": [],
            "file_path": "/src/StringUtils.java",
        }
        result = TemplateSelector.select_template(file_analysis)
        assert result["type"] == "util"

    def test_select_java_default_template(self):
        file_analysis = {
            "language": "java",
            "class_name": "SomeClass",
            "annotations": [],
            "file_path": "/src/SomeClass.java",
        }
        result = TemplateSelector.select_template(file_analysis)
        assert result["type"] == "default"

    def test_select_vue_component_template(self):
        file_analysis = {
            "language": "typescript",
            "class_name": "Button",
            "file_path": "/src/components/Button.vue",
        }
        result = TemplateSelector.select_template(file_analysis)
        assert result["type"] == "vue_component"

    def test_select_react_component_template(self):
        file_analysis = {
            "language": "typescript",
            "class_name": "Button",
            "file_path": "/src/components/Button.tsx",
        }
        result = TemplateSelector.select_template(file_analysis)
        assert result["type"] == "react_component"


class TestGeneratorAgent:
    """GeneratorAgent 测试."""

    @pytest.fixture
    def agent(self):
        with patch("ut_agent.agents.generator.get_llm"):
            return GeneratorAgent()

    def test_agent_initialization(self, agent):
        assert agent.name == "generator"
        assert agent.status == AgentStatus.IDLE

    def test_agent_capabilities(self, agent):
        capabilities = agent.get_capabilities()
        assert len(capabilities) > 0

    @pytest.mark.asyncio
    async def test_execute_without_file_analysis(self, agent):
        context = AgentContext(
            task_id="test-task",
            source_file="/test/file.java",
        )
        result = await agent.execute(context)
        assert result.success is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_execute_with_file_analysis(self, agent):
        context = AgentContext(
            task_id="test-task",
            source_file="/test/UserService.java",
            file_analysis={
                "language": "java",
                "class_name": "UserService",
                "methods": [{"name": "getUser", "return_type": "User"}],
            },
        )

        agent._generate_test_code = AsyncMock(return_value="test code")

        result = await agent.execute(context)

        assert result.agent_name == "generator"

    def test_to_dict(self, agent):
        data = agent.to_dict()
        assert data["name"] == "generator"
        assert "capabilities" in data
        assert data["status"] == "idle"
