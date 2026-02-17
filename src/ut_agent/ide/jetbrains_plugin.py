"""JetBrains 插件扩展.

提供 JetBrains IDE (IntelliJ IDEA/PyCharm) 插件支持，包括工具窗口、代码检查、意图动作等功能。
"""

import ast
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class JetBrainsActionType(Enum):
    """JetBrains 动作类型枚举."""
    GENERATE_TEST = "generate_test"       # 生成测试
    RUN_TEST = "run_test"                 # 运行测试
    DEBUG_TEST = "debug_test"             # 调试测试
    ANALYZE_QUALITY = "analyze_quality"   # 分析质量
    REFRESH = "refresh"                   # 刷新


class JetBrainsEventType(Enum):
    """JetBrains 事件类型枚举."""
    TEST_GENERATED = "test_generated"     # 测试已生成
    TEST_EXECUTED = "test_executed"       # 测试已执行
    QUALITY_ANALYZED = "quality_analyzed" # 质量已分析
    ERROR = "error"                       # 错误


@dataclass
class JetBrainsAction:
    """JetBrains 动作.
    
    Attributes:
        action_type: 动作类型
        params: 动作参数
        id: 动作唯一标识
    """
    action_type: JetBrainsActionType
    params: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "id": self.id,
            "action_type": self.action_type.value,
            "params": self.params,
        }


@dataclass
class JetBrainsEvent:
    """JetBrains 事件.
    
    Attributes:
        event_type: 事件类型
        data: 事件数据
        timestamp: 时间戳
    """
    event_type: JetBrainsEventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "event_type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


class ToolWindowFactory:
    """工具窗口工厂.
    
    创建 UT Agent 工具窗口。
    """
    
    def __init__(self):
        """初始化工厂."""
        self.window_title = "UT Agent"
        self.logger = logging.getLogger(__name__)
        
    def create_tool_window_content(self, project: Dict[str, Any]) -> Dict[str, Any]:
        """创建工具窗口内容.
        
        Args:
            project: 项目信息
            
        Returns:
            Dict[str, Any]: 窗口内容
        """
        components = [
            {
                "type": "button",
                "text": "Generate Tests",
                "action": "generate_test",
            },
            {
                "type": "button",
                "text": "Run All Tests",
                "action": "run_test",
            },
            {
                "type": "button",
                "text": "Analyze Quality",
                "action": "analyze_quality",
            },
            {
                "type": "panel",
                "name": "test_results",
                "title": "Test Results",
            },
            {
                "type": "panel",
                "name": "quality_report",
                "title": "Quality Report",
            },
        ]
        
        return {
            "panel": {
                "title": self.window_title,
                "project": project.get("name", "Unknown"),
            },
            "components": components,
        }
        
    def get_tool_window_id(self) -> str:
        """获取工具窗口 ID.
        
        Returns:
            str: 窗口 ID
        """
        return "UTAgentToolWindow"


class InspectionProvider:
    """代码检查提供者.
    
    检查代码中的测试覆盖情况。
    """
    
    def __init__(self):
        """初始化提供者."""
        self.inspection_short_name = "UTAgentInspection"
        self.logger = logging.getLogger(__name__)
        
    def check_file(self, code: str, file_name: str) -> List[Dict[str, Any]]:
        """检查文件.
        
        Args:
            code: 源代码
            file_name: 文件名
            
        Returns:
            List[Dict[str, Any]]: 问题列表
        """
        problems = []
        
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return problems
            
        # 提取所有函数
        functions = []
        test_functions = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith("test_"):
                    test_functions.append(node.name)
                elif not node.name.startswith("_"):
                    functions.append(node.name)
                    
        # 检查每个函数是否有对应的测试
        for func_name in functions:
            test_name = f"test_{func_name}"
            if test_name not in test_functions:
                problems.append({
                    "description": f"Function '{func_name}' has no corresponding test",
                    "severity": "WARNING",
                    "line": self._get_function_line(tree, func_name),
                })
                
        return problems
        
    def _get_function_line(self, tree: ast.AST, func_name: str) -> int:
        """获取函数所在行.
        
        Args:
            tree: AST 树
            func_name: 函数名
            
        Returns:
            int: 行号
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                return node.lineno
        return 1
        
    def get_display_name(self) -> str:
        """获取显示名称.
        
        Returns:
            str: 显示名称
        """
        return "UT Agent Test Coverage"
        
    def get_group_display_name(self) -> str:
        """获取组显示名称.
        
        Returns:
            str: 组显示名称
        """
        return "Testing"


class IntentionActionProvider:
    """意图动作提供者.
    
    提供快速修复和重构意图。
    """
    
    def __init__(self):
        """初始化提供者."""
        self.logger = logging.getLogger(__name__)
        
    def get_text(self, code: str) -> str:
        """获取动作文本.
        
        Args:
            code: 代码片段
            
        Returns:
            str: 动作文本
        """
        code = code.strip()
        
        if code.startswith("def test_"):
            return "Run Test / Debug Test"
        elif code.startswith("def "):
            return "Generate Test for this function"
        else:
            return "UT Agent Action"
            
    def is_available(self, code: str) -> bool:
        """检查是否可用.
        
        Args:
            code: 代码片段
            
        Returns:
            bool: 是否可用
        """
        code = code.strip()
        return code.startswith("def ")
        
    def invoke(
        self,
        editor: Dict[str, Any],
        action_type: JetBrainsActionType,
    ) -> Dict[str, Any]:
        """调用动作.
        
        Args:
            editor: 编辑器信息
            action_type: 动作类型
            
        Returns:
            Dict[str, Any]: 调用结果
        """
        return {
            "success": True,
            "action": action_type.value,
            "file_path": editor.get("file_path"),
            "line": editor.get("caret_line"),
        }


class RunConfigurationProvider:
    """运行配置提供者.
    
    创建测试运行配置。
    """
    
    def __init__(self):
        """初始化提供者."""
        self.logger = logging.getLogger(__name__)
        
    def create_configuration(
        self,
        test_file: str,
        test_function: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建运行配置.
        
        Args:
            test_file: 测试文件
            test_function: 测试函数名（可选）
            
        Returns:
            Dict[str, Any]: 运行配置
        """
        if test_function:
            name = f"Test: {test_function}"
            target = f"{test_file}::{test_function}"
        else:
            name = f"Test: {test_file}"
            target = test_file
            
        return {
            "name": name,
            "type": "pytest",
            "target": target,
            "working_directory": "$PROJECT_DIR$",
            "env_vars": {},
        }
        
    def get_configuration_type(self) -> str:
        """获取配置类型.
        
        Returns:
            str: 配置类型
        """
        return "pytest"


class JetBrainsPlugin:
    """JetBrains 插件.
    
    管理 JetBrains 插件的动作、事件和提供者。
    """
    
    def __init__(self):
        """初始化插件."""
        self.actions: Dict[JetBrainsActionType, Callable] = {}
        self.providers: List[Any] = []
        self._event_listeners: Dict[JetBrainsEventType, List[Callable]] = {}
        self.logger = logging.getLogger(__name__)
        
    def register_action(
        self,
        action_type: JetBrainsActionType,
        handler: Callable[[Dict[str, Any]], Any],
    ) -> None:
        """注册动作.
        
        Args:
            action_type: 动作类型
            handler: 动作处理器
        """
        self.actions[action_type] = handler
        self.logger.debug(f"Registered action: {action_type.value}")
        
    def register_provider(self, provider_type: str, provider: Any) -> None:
        """注册提供者.
        
        Args:
            provider_type: 提供者类型
            provider: 提供者实例
        """
        self.providers.append(provider)
        self.logger.debug(f"Registered provider: {provider_type}")
        
    async def execute_action(self, action: JetBrainsAction) -> Dict[str, Any]:
        """执行动作.
        
        Args:
            action: 动作对象
            
        Returns:
            Dict[str, Any]: 执行结果
        """
        handler = self.actions.get(action.action_type)
        
        if not handler:
            return {
                "success": False,
                "error": f"Action not found: {action.action_type.value}",
            }
            
        try:
            import asyncio
            if asyncio.iscoroutinefunction(handler):
                result = await handler(action.params)
            else:
                result = handler(action.params)
                
            return {
                "success": True,
                "data": result,
            }
        except Exception as e:
            self.logger.exception(f"Action execution failed: {action.action_type.value}")
            return {
                "success": False,
                "error": str(e),
            }
            
    def on(
        self,
        event_type: JetBrainsEventType,
        listener: Callable[[JetBrainsEvent], None],
    ) -> None:
        """注册事件监听器.
        
        Args:
            event_type: 事件类型
            listener: 监听器函数
        """
        if event_type not in self._event_listeners:
            self._event_listeners[event_type] = []
        self._event_listeners[event_type].append(listener)
        
    def off(
        self,
        event_type: JetBrainsEventType,
        listener: Callable[[JetBrainsEvent], None],
    ) -> None:
        """移除事件监听器.
        
        Args:
            event_type: 事件类型
            listener: 监听器函数
        """
        if event_type in self._event_listeners:
            self._event_listeners[event_type] = [
                l for l in self._event_listeners[event_type] if l != listener
            ]
            
    def emit(self, event_type: JetBrainsEventType, data: Dict[str, Any]) -> None:
        """触发事件.
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        event = JetBrainsEvent(event_type=event_type, data=data)
        listeners = self._event_listeners.get(event_type, [])
        
        for listener in listeners:
            try:
                listener(event)
            except Exception as e:
                self.logger.exception(f"Event listener failed: {e}")
                
    def get_plugin_xml(self) -> str:
        """获取 plugin.xml 配置.
        
        Returns:
            str: plugin.xml 内容
        """
        return '''<?xml version="1.0" encoding="UTF-8"?>
<idea-plugin>
    <id>com.utagent.plugin</id>
    <name>UT Agent</name>
    <version>1.0.0</version>
    <vendor>UT Agent Team</vendor>
    
    <description><![CDATA[
        AI-powered unit test generation and quality analysis for Python.
    ]]></description>
    
    <change-notes><![CDATA[
        Initial release with test generation and quality analysis features.
    ]]></change-notes>
    
    <idea-version since-build="231"/>
    
    <depends>com.intellij.modules.platform</depends>
    <depends>com.intellij.modules.python</depends>
    
    <extensions defaultExtensionNs="com.intellij">
        <!-- Tool Window -->
        <toolWindow id="UTAgentToolWindow"
                    anchor="right"
                    factoryClass="com.utagent.plugin.ToolWindowFactory"
                    icon="/icons/utagent.svg"/>
        
        <!-- Inspection -->
        <localInspection language="Python"
                         shortName="UTAgentInspection"
                         displayName="UT Agent Test Coverage"
                         groupName="Testing"
                         enabledByDefault="true"
                         level="WARNING"
                         implementationClass="com.utagent.plugin.InspectionProvider"/>
        
        <!-- Intention Action -->
        <intentionAction>
            <className>com.utagent.plugin.IntentionActionProvider</className>
            <category>Testing</category>
        </intentionAction>
        
        <!-- Run Configuration -->
        <configurationType implementation="com.utagent.plugin.RunConfigurationProvider"/>
    </extensions>
    
    <actions>
        <action id="UTAgent.GenerateTest"
                class="com.utagent.plugin.actions.GenerateTestAction"
                text="Generate Test"
                description="Generate test for selected function">
            <add-to-group group-id="EditorPopupMenu" anchor="after" relative-to-action="Generate"/>
        </action>
        
        <action id="UTAgent.RunTest"
                class="com.utagent.plugin.actions.RunTestAction"
                text="Run Test"
                description="Run selected test">
            <add-to-group group-id="RunContextGroup" anchor="after" relative-to-action="RunClass"/>
        </action>
    </actions>
</idea-plugin>'''
        
    def get_configuration(self) -> Dict[str, Any]:
        """获取配置.
        
        Returns:
            Dict[str, Any]: 配置
        """
        return {
            "llm_provider": {
                "type": "string",
                "default": "openai",
                "options": ["openai", "azure", "anthropic", "gemini"],
            },
            "api_key": {
                "type": "string",
                "default": "",
                "secure": True,
            },
            "model": {
                "type": "string",
                "default": "gpt-4",
            },
            "temperature": {
                "type": "float",
                "default": 0.7,
                "min": 0.0,
                "max": 2.0,
            },
            "max_tokens": {
                "type": "integer",
                "default": 2000,
            },
        }
