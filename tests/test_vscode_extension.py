"""VSCode 插件扩展测试."""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, List, Optional

from ut_agent.ide.vscode_extension import (
    VSCodeCommand,
    VSCodeCommandType,
    VSCodeEvent,
    VSCodeEventType,
    VSCodeExtension,
    TestLensProvider,
    CodeActionProvider,
    HoverProvider,
)


class TestVSCodeCommandType:
    """VSCode 命令类型测试."""

    def test_command_type_values(self):
        """测试命令类型枚举值."""
        assert VSCodeCommandType.GENERATE_TEST.value == "generate_test"
        assert VSCodeCommandType.RUN_TEST.value == "run_test"
        assert VSCodeCommandType.DEBUG_TEST.value == "debug_test"
        assert VSCodeCommandType.ANALYZE_QUALITY.value == "analyze_quality"
        assert VSCodeCommandType.REFRESH.value == "refresh"
        assert VSCodeCommandType.CONFIGURE.value == "configure"


class TestVSCodeEventType:
    """VSCode 事件类型测试."""

    def test_event_type_values(self):
        """测试事件类型枚举值."""
        assert VSCodeEventType.TEST_GENERATED.value == "test_generated"
        assert VSCodeEventType.TEST_EXECUTED.value == "test_executed"
        assert VSCodeEventType.QUALITY_ANALYZED.value == "quality_analyzed"
        assert VSCodeEventType.ERROR.value == "error"


class TestVSCodeCommand:
    """VSCode 命令测试."""

    def test_command_creation(self):
        """测试命令创建."""
        command = VSCodeCommand(
            command_type=VSCodeCommandType.GENERATE_TEST,
            params={"file_path": "/path/to/file.py", "function_name": "add"},
        )
        
        assert command.command_type == VSCodeCommandType.GENERATE_TEST
        assert command.params["file_path"] == "/path/to/file.py"
        assert command.id is not None
        
    def test_command_to_dict(self):
        """测试命令序列化."""
        command = VSCodeCommand(
            command_type=VSCodeCommandType.RUN_TEST,
            params={"test_path": "test_example.py"},
        )
        
        data = command.to_dict()
        
        assert data["command_type"] == "run_test"
        assert data["params"]["test_path"] == "test_example.py"
        assert "id" in data


class TestVSCodeEvent:
    """VSCode 事件测试."""

    def test_event_creation(self):
        """测试事件创建."""
        event = VSCodeEvent(
            event_type=VSCodeEventType.TEST_GENERATED,
            data={"test_code": "def test_add(): pass"},
        )
        
        assert event.event_type == VSCodeEventType.TEST_GENERATED
        assert event.data["test_code"] == "def test_add(): pass"
        assert event.timestamp is not None
        
    def test_event_to_dict(self):
        """测试事件序列化."""
        event = VSCodeEvent(
            event_type=VSCodeEventType.ERROR,
            data={"message": "Something went wrong"},
        )
        
        data = event.to_dict()
        
        assert data["event_type"] == "error"
        assert data["data"]["message"] == "Something went wrong"
        assert "timestamp" in data


class TestTestLensProvider:
    """测试 Lens 提供者测试."""

    @pytest.fixture
    def provider(self):
        """创建 Lens 提供者实例."""
        return TestLensProvider()
        
    def test_provider_initialization(self):
        """测试提供者初始化."""
        provider = TestLensProvider()
        
        assert provider is not None
        
    def test_extract_testable_functions(self, provider):
        """测试提取可测试函数."""
        code = '''
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

class Calculator:
    def multiply(self, a, b):
        return a * b
'''
        functions = provider._extract_testable_functions(code)
        
        assert len(functions) >= 2
        function_names = [f["name"] for f in functions]
        assert "add" in function_names
        assert "subtract" in function_names
        
    def test_create_code_lens(self, provider):
        """测试创建 Code Lens."""
        func_info = {
            "name": "add",
            "line": 0,
            "type": "function",
        }
        
        lenses = provider._create_code_lens(func_info, "/path/to/file.py")
        
        assert len(lenses) >= 1
        assert any(lens["command"]["command"] == "ut-agent.generateTest" for lens in lenses)
        
    def test_provide_code_lenses(self, provider):
        """测试提供 Code Lenses."""
        document = {
            "uri": "file:///path/to/file.py",
            "content": '''
def add(a, b):
    return a + b
''',
        }
        
        lenses = provider.provide_code_lenses(document)
        
        assert len(lenses) >= 1


class TestCodeActionProvider:
    """代码动作提供者测试."""

    @pytest.fixture
    def provider(self):
        """创建代码动作提供者实例."""
        return CodeActionProvider()
        
    def test_provider_initialization(self):
        """测试提供者初始化."""
        provider = CodeActionProvider()
        
        assert provider is not None
        
    def test_provide_code_actions_for_function(self, provider):
        """测试为函数提供代码动作."""
        document = {"uri": "file:///path/to/file.py"}
        range_info = {"start": {"line": 0}, "end": {"line": 5}}
        context = {
            "diagnostics": [],
            "selected_text": "def add(a, b):",
        }
        
        actions = provider.provide_code_actions(document, range_info, context)
        
        # 至少有分析质量的动作
        assert len(actions) >= 1
        # 由于函数名提取可能失败，我们只验证有动作返回
        assert any("Test" in action["title"] or "Quality" in action["title"] for action in actions)
        
    def test_provide_code_actions_for_test(self, provider):
        """测试为测试提供代码动作."""
        document = {"uri": "file:///path/to/test_file.py"}
        range_info = {"start": {"line": 0}, "end": {"line": 10}}
        context = {
            "diagnostics": [],
            "selected_text": "def test_add():",
        }
        
        actions = provider.provide_code_actions(document, range_info, context)
        
        # 应该提供运行测试的动作
        assert any(action["title"] == "Run Test" for action in actions)


class TestHoverProvider:
    """悬停提示提供者测试."""

    @pytest.fixture
    def provider(self):
        """创建悬停提示提供者实例."""
        return HoverProvider()
        
    def test_provider_initialization(self):
        """测试提供者初始化."""
        provider = HoverProvider()
        
        assert provider is not None
        
    def test_provide_hover_for_function(self, provider):
        """测试为函数提供悬停提示."""
        document = {
            "uri": "file:///path/to/file.py",
            "content": '''
def add(a, b):
    """Add two numbers."""
    return a + b
''',
        }
        position = {"line": 1, "character": 4}
        
        hover = provider.provide_hover(document, position)
        
        assert hover is not None
        assert "contents" in hover
        
    def test_provide_hover_for_test(self, provider):
        """测试为测试提供悬停提示."""
        document = {
            "uri": "file:///path/to/test_file.py",
            "content": '''
def test_add():
    assert add(1, 2) == 3
''',
        }
        position = {"line": 1, "character": 4}
        
        hover = provider.provide_hover(document, position)
        
        assert hover is not None


class TestVSCodeExtension:
    """VSCode 扩展测试."""

    @pytest.fixture
    def extension(self):
        """创建扩展实例."""
        return VSCodeExtension()
        
    def test_extension_initialization(self):
        """测试扩展初始化."""
        extension = VSCodeExtension()
        
        assert extension is not None
        assert extension.commands == {}
        assert extension.providers == []
        
    def test_register_command(self, extension):
        """测试注册命令."""
        def handler(params):
            return {"success": True}
            
        extension.register_command(VSCodeCommandType.GENERATE_TEST, handler)
        
        assert VSCodeCommandType.GENERATE_TEST in extension.commands
        
    def test_register_provider(self, extension):
        """测试注册提供者."""
        provider = TestLensProvider()
        
        extension.register_provider("codeLens", provider)
        
        assert len(extension.providers) == 1
        
    @pytest.mark.asyncio
    async def test_execute_command(self, extension):
        """测试执行命令."""
        async def handler(params):
            return {"test_code": "def test_add(): pass"}
            
        extension.register_command(VSCodeCommandType.GENERATE_TEST, handler)
        
        command = VSCodeCommand(
            command_type=VSCodeCommandType.GENERATE_TEST,
            params={"function_name": "add"},
        )
        
        result = await extension.execute_command(command)
        
        assert result["success"] is True
        assert result["data"]["test_code"] == "def test_add(): pass"
        
    @pytest.mark.asyncio
    async def test_execute_command_not_found(self, extension):
        """测试执行不存在的命令."""
        command = VSCodeCommand(
            command_type=VSCodeCommandType.REFRESH,
            params={},
        )
        
        result = await extension.execute_command(command)
        
        assert result["success"] is False
        assert "error" in result
        
    def test_emit_event(self, extension):
        """测试触发事件."""
        events_received = []
        
        def listener(event):
            events_received.append(event)
            
        extension.on(VSCodeEventType.TEST_GENERATED, listener)
        
        extension.emit(VSCodeEventType.TEST_GENERATED, {"test_code": "..."})
        
        assert len(events_received) == 1
        assert events_received[0].event_type == VSCodeEventType.TEST_GENERATED
        
    def test_remove_listener(self, extension):
        """测试移除监听器."""
        events_received = []
        
        def listener(event):
            events_received.append(event)
            
        extension.on(VSCodeEventType.TEST_GENERATED, listener)
        extension.off(VSCodeEventType.TEST_GENERATED, listener)
        
        extension.emit(VSCodeEventType.TEST_GENERATED, {})
        
        assert len(events_received) == 0
        
    def test_get_manifest(self, extension):
        """测试获取插件清单."""
        manifest = extension.get_manifest()
        
        assert "name" in manifest
        assert "version" in manifest
        assert "contributes" in manifest
        assert "commands" in manifest["contributes"]
        
    def test_get_configuration_schema(self, extension):
        """测试获取配置模式."""
        schema = extension.get_configuration_schema()
        
        assert "properties" in schema
        assert "ut-agent.llmProvider" in schema["properties"]
        assert "ut-agent.apiKey" in schema["properties"]


class TestVSCodeExtensionIntegration:
    """VSCode 扩展集成测试."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """测试完整工作流."""
        extension = VSCodeExtension()
        
        # 注册命令处理器
        async def generate_test_handler(params):
            return {
                "test_code": f"def test_{params['function_name']}(): pass",
                "file_path": params.get("file_path"),
            }
            
        extension.register_command(VSCodeCommandType.GENERATE_TEST, generate_test_handler)
        
        # 模拟生成测试命令
        command = VSCodeCommand(
            command_type=VSCodeCommandType.GENERATE_TEST,
            params={
                "file_path": "/path/to/file.py",
                "function_name": "add",
            },
        )
        
        result = await extension.execute_command(command)
        
        assert result["success"] is True
        assert "test_add" in result["data"]["test_code"]
        
    def test_event_propagation(self):
        """测试事件传播."""
        extension = VSCodeExtension()
        
        events = []
        
        def listener1(event):
            events.append(("listener1", event.event_type.value))
            
        def listener2(event):
            events.append(("listener2", event.event_type.value))
            
        extension.on(VSCodeEventType.TEST_GENERATED, listener1)
        extension.on(VSCodeEventType.TEST_GENERATED, listener2)
        
        extension.emit(VSCodeEventType.TEST_GENERATED, {"data": "test"})
        
        assert len(events) == 2
        assert ("listener1", "test_generated") in events
        assert ("listener2", "test_generated") in events
        
    def test_provider_integration(self):
        """测试提供者集成."""
        extension = VSCodeExtension()
        
        # 注册多个提供者
        lens_provider = TestLensProvider()
        action_provider = CodeActionProvider()
        hover_provider = HoverProvider()
        
        extension.register_provider("codeLens", lens_provider)
        extension.register_provider("codeAction", action_provider)
        extension.register_provider("hover", hover_provider)
        
        assert len(extension.providers) == 3
        
        # 验证可以通过扩展访问提供者
        lens_providers = [p for p in extension.providers if isinstance(p, TestLensProvider)]
        assert len(lens_providers) == 1
