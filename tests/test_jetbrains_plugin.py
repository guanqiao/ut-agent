"""JetBrains 插件扩展测试."""

import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any, List, Optional

from ut_agent.ide.jetbrains_plugin import (
    JetBrainsAction,
    JetBrainsActionType,
    JetBrainsEvent,
    JetBrainsEventType,
    JetBrainsPlugin,
    ToolWindowFactory,
    InspectionProvider,
    IntentionActionProvider,
    RunConfigurationProvider,
)


class TestJetBrainsActionType:
    """JetBrains 动作类型测试."""

    def test_action_type_values(self):
        """测试动作类型枚举值."""
        assert JetBrainsActionType.GENERATE_TEST.value == "generate_test"
        assert JetBrainsActionType.RUN_TEST.value == "run_test"
        assert JetBrainsActionType.DEBUG_TEST.value == "debug_test"
        assert JetBrainsActionType.ANALYZE_QUALITY.value == "analyze_quality"
        assert JetBrainsActionType.REFRESH.value == "refresh"


class TestJetBrainsEventType:
    """JetBrains 事件类型测试."""

    def test_event_type_values(self):
        """测试事件类型枚举值."""
        assert JetBrainsEventType.TEST_GENERATED.value == "test_generated"
        assert JetBrainsEventType.TEST_EXECUTED.value == "test_executed"
        assert JetBrainsEventType.QUALITY_ANALYZED.value == "quality_analyzed"
        assert JetBrainsEventType.ERROR.value == "error"


class TestJetBrainsAction:
    """JetBrains 动作测试."""

    def test_action_creation(self):
        """测试动作创建."""
        action = JetBrainsAction(
            action_type=JetBrainsActionType.GENERATE_TEST,
            params={"file_path": "/path/to/file.py", "function_name": "add"},
        )
        
        assert action.action_type == JetBrainsActionType.GENERATE_TEST
        assert action.params["file_path"] == "/path/to/file.py"
        assert action.id is not None
        
    def test_action_to_dict(self):
        """测试动作序列化."""
        action = JetBrainsAction(
            action_type=JetBrainsActionType.RUN_TEST,
            params={"test_path": "test_example.py"},
        )
        
        data = action.to_dict()
        
        assert data["action_type"] == "run_test"
        assert data["params"]["test_path"] == "test_example.py"
        assert "id" in data


class TestJetBrainsEvent:
    """JetBrains 事件测试."""

    def test_event_creation(self):
        """测试事件创建."""
        event = JetBrainsEvent(
            event_type=JetBrainsEventType.TEST_GENERATED,
            data={"test_code": "def test_add(): pass"},
        )
        
        assert event.event_type == JetBrainsEventType.TEST_GENERATED
        assert event.data["test_code"] == "def test_add(): pass"
        assert event.timestamp is not None
        
    def test_event_to_dict(self):
        """测试事件序列化."""
        event = JetBrainsEvent(
            event_type=JetBrainsEventType.ERROR,
            data={"message": "Something went wrong"},
        )
        
        data = event.to_dict()
        
        assert data["event_type"] == "error"
        assert data["data"]["message"] == "Something went wrong"
        assert "timestamp" in data


class TestToolWindowFactory:
    """工具窗口工厂测试."""

    @pytest.fixture
    def factory(self):
        """创建工具窗口工厂实例."""
        return ToolWindowFactory()
        
    def test_factory_initialization(self):
        """测试工厂初始化."""
        factory = ToolWindowFactory()
        
        assert factory is not None
        assert factory.window_title == "UT Agent"
        
    def test_create_tool_window_content(self, factory):
        """测试创建工具窗口内容."""
        project = {"name": "test_project", "base_path": "/path/to/project"}
        
        content = factory.create_tool_window_content(project)
        
        assert "panel" in content
        assert "components" in content
        assert len(content["components"]) > 0
        
    def test_get_tool_window_id(self, factory):
        """测试获取工具窗口 ID."""
        window_id = factory.get_tool_window_id()
        
        assert window_id == "UTAgentToolWindow"


class TestInspectionProvider:
    """代码检查提供者测试."""

    @pytest.fixture
    def provider(self):
        """创建检查提供者实例."""
        return InspectionProvider()
        
    def test_provider_initialization(self):
        """测试提供者初始化."""
        provider = InspectionProvider()
        
        assert provider is not None
        assert provider.inspection_short_name == "UTAgentInspection"
        
    def test_check_function_without_test(self, provider):
        """测试检查无测试的函数."""
        code = '''
def add(a, b):
    return a + b
'''
        problems = provider.check_file(code, "example.py")
        
        assert len(problems) > 0
        assert any("test" in p["description"].lower() for p in problems)
        
    def test_check_function_with_test(self, provider):
        """测试检查有测试的函数."""
        code = '''
def add(a, b):
    return a + b

def test_add():
    assert add(1, 2) == 3
'''
        problems = provider.check_file(code, "example.py")
        
        # 有测试的函数不应该有问题
        assert len(problems) == 0
        
    def test_get_display_name(self, provider):
        """测试获取显示名称."""
        name = provider.get_display_name()
        
        assert "UT Agent" in name or "Test" in name
        
    def test_get_group_display_name(self, provider):
        """测试获取组显示名称."""
        name = provider.get_group_display_name()
        
        assert len(name) > 0


class TestIntentionActionProvider:
    """意图动作提供者测试."""

    @pytest.fixture
    def provider(self):
        """创建意图动作提供者实例."""
        return IntentionActionProvider()
        
    def test_provider_initialization(self):
        """测试提供者初始化."""
        provider = IntentionActionProvider()
        
        assert provider is not None
        
    def test_get_text_for_function(self, provider):
        """测试获取函数的动作文本."""
        code = "def add(a, b):"
        
        text = provider.get_text(code)
        
        assert "Generate Test" in text or "test" in text.lower()
        
    def test_get_text_for_test(self, provider):
        """测试获取测试函数的动作文本."""
        code = "def test_add():"
        
        text = provider.get_text(code)
        
        assert "Run Test" in text or "Debug Test" in text
        
    def test_is_available_for_function(self, provider):
        """测试函数是否可用."""
        code = "def add(a, b):"
        
        available = provider.is_available(code)
        
        assert available is True
        
    def test_is_available_for_test(self, provider):
        """测试测试函数是否可用."""
        code = "def test_add():"
        
        available = provider.is_available(code)
        
        assert available is True
        
    def test_invoke_generate_test(self, provider):
        """测试调用生成测试."""
        editor = {"file_path": "/path/to/file.py", "caret_line": 1}
        
        result = provider.invoke(editor, JetBrainsActionType.GENERATE_TEST)
        
        assert result is not None
        assert "success" in result


class TestRunConfigurationProvider:
    """运行配置提供者测试."""

    @pytest.fixture
    def provider(self):
        """创建运行配置提供者实例."""
        return RunConfigurationProvider()
        
    def test_provider_initialization(self):
        """测试提供者初始化."""
        provider = RunConfigurationProvider()
        
        assert provider is not None
        
    def test_create_configuration_for_test(self, provider):
        """测试为测试创建配置."""
        test_file = "test_example.py"
        test_function = "test_add"
        
        config = provider.create_configuration(test_file, test_function)
        
        assert config["name"] == f"Test: {test_function}"
        assert config["type"] == "pytest"
        assert test_file in config["target"]
        assert test_function in config["target"]
        
    def test_create_configuration_for_module(self, provider):
        """测试为模块创建配置."""
        test_file = "test_example.py"
        
        config = provider.create_configuration(test_file)
        
        assert config["name"] == f"Test: {test_file}"
        assert config["type"] == "pytest"
        
    def test_get_configuration_type(self, provider):
        """测试获取配置类型."""
        config_type = provider.get_configuration_type()
        
        assert config_type == "pytest"


class TestJetBrainsPlugin:
    """JetBrains 插件测试."""

    @pytest.fixture
    def plugin(self):
        """创建插件实例."""
        return JetBrainsPlugin()
        
    def test_plugin_initialization(self):
        """测试插件初始化."""
        plugin = JetBrainsPlugin()
        
        assert plugin is not None
        assert plugin.actions == {}
        assert plugin.providers == []
        
    def test_register_action(self, plugin):
        """测试注册动作."""
        def handler(params):
            return {"success": True}
            
        plugin.register_action(JetBrainsActionType.GENERATE_TEST, handler)
        
        assert JetBrainsActionType.GENERATE_TEST in plugin.actions
        
    def test_register_provider(self, plugin):
        """测试注册提供者."""
        provider = InspectionProvider()
        
        plugin.register_provider("inspection", provider)
        
        assert len(plugin.providers) == 1
        
    @pytest.mark.asyncio
    async def test_execute_action(self, plugin):
        """测试执行动作."""
        async def handler(params):
            return {"test_code": "def test_add(): pass"}
            
        plugin.register_action(JetBrainsActionType.GENERATE_TEST, handler)
        
        action = JetBrainsAction(
            action_type=JetBrainsActionType.GENERATE_TEST,
            params={"function_name": "add"},
        )
        
        result = await plugin.execute_action(action)
        
        assert result["success"] is True
        assert result["data"]["test_code"] == "def test_add(): pass"
        
    @pytest.mark.asyncio
    async def test_execute_action_not_found(self, plugin):
        """测试执行不存在的动作."""
        action = JetBrainsAction(
            action_type=JetBrainsActionType.REFRESH,
            params={},
        )
        
        result = await plugin.execute_action(action)
        
        assert result["success"] is False
        assert "error" in result
        
    def test_emit_event(self, plugin):
        """测试触发事件."""
        events_received = []
        
        def listener(event):
            events_received.append(event)
            
        plugin.on(JetBrainsEventType.TEST_GENERATED, listener)
        
        plugin.emit(JetBrainsEventType.TEST_GENERATED, {"test_code": "..."})
        
        assert len(events_received) == 1
        assert events_received[0].event_type == JetBrainsEventType.TEST_GENERATED
        
    def test_remove_listener(self, plugin):
        """测试移除监听器."""
        events_received = []
        
        def listener(event):
            events_received.append(event)
            
        plugin.on(JetBrainsEventType.TEST_GENERATED, listener)
        plugin.off(JetBrainsEventType.TEST_GENERATED, listener)
        
        plugin.emit(JetBrainsEventType.TEST_GENERATED, {})
        
        assert len(events_received) == 0
        
    def test_get_plugin_xml(self, plugin):
        """测试获取 plugin.xml 配置."""
        xml = plugin.get_plugin_xml()
        
        assert "<idea-plugin>" in xml
        assert "UT Agent" in xml
        assert "<extensions" in xml
        
    def test_get_configuration(self, plugin):
        """测试获取配置."""
        config = plugin.get_configuration()
        
        assert "llm_provider" in config
        assert "api_key" in config
        assert "model" in config


class TestJetBrainsPluginIntegration:
    """JetBrains 插件集成测试."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """测试完整工作流."""
        plugin = JetBrainsPlugin()
        
        # 注册动作处理器
        async def generate_test_handler(params):
            return {
                "test_code": f"def test_{params['function_name']}(): pass",
                "file_path": params.get("file_path"),
            }
            
        plugin.register_action(JetBrainsActionType.GENERATE_TEST, generate_test_handler)
        
        # 模拟生成测试动作
        action = JetBrainsAction(
            action_type=JetBrainsActionType.GENERATE_TEST,
            params={
                "file_path": "/path/to/file.py",
                "function_name": "add",
            },
        )
        
        result = await plugin.execute_action(action)
        
        assert result["success"] is True
        assert "test_add" in result["data"]["test_code"]
        
    def test_event_propagation(self):
        """测试事件传播."""
        plugin = JetBrainsPlugin()
        
        events = []
        
        def listener1(event):
            events.append(("listener1", event.event_type.value))
            
        def listener2(event):
            events.append(("listener2", event.event_type.value))
            
        plugin.on(JetBrainsEventType.TEST_GENERATED, listener1)
        plugin.on(JetBrainsEventType.TEST_GENERATED, listener2)
        
        plugin.emit(JetBrainsEventType.TEST_GENERATED, {"data": "test"})
        
        assert len(events) == 2
        assert ("listener1", "test_generated") in events
        assert ("listener2", "test_generated") in events
        
    def test_provider_integration(self):
        """测试提供者集成."""
        plugin = JetBrainsPlugin()
        
        # 注册多个提供者
        inspection_provider = InspectionProvider()
        intention_provider = IntentionActionProvider()
        run_config_provider = RunConfigurationProvider()
        
        plugin.register_provider("inspection", inspection_provider)
        plugin.register_provider("intention", intention_provider)
        plugin.register_provider("runConfiguration", run_config_provider)
        
        assert len(plugin.providers) == 3
        
        # 验证可以通过插件访问提供者
        inspection_providers = [p for p in plugin.providers if isinstance(p, InspectionProvider)]
        assert len(inspection_providers) == 1
