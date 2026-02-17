"""VSCode 插件扩展.

提供 VSCode 插件支持，包括 Code Lens、代码动作、悬停提示等功能。
"""

import ast
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union

logger = logging.getLogger(__name__)


class VSCodeCommandType(Enum):
    """VSCode 命令类型枚举."""
    GENERATE_TEST = "generate_test"       # 生成测试
    RUN_TEST = "run_test"                 # 运行测试
    DEBUG_TEST = "debug_test"             # 调试测试
    ANALYZE_QUALITY = "analyze_quality"   # 分析质量
    REFRESH = "refresh"                   # 刷新
    CONFIGURE = "configure"               # 配置


class VSCodeEventType(Enum):
    """VSCode 事件类型枚举."""
    TEST_GENERATED = "test_generated"     # 测试已生成
    TEST_EXECUTED = "test_executed"       # 测试已执行
    QUALITY_ANALYZED = "quality_analyzed" # 质量已分析
    ERROR = "error"                       # 错误


@dataclass
class VSCodeCommand:
    """VSCode 命令.
    
    Attributes:
        command_type: 命令类型
        params: 命令参数
        id: 命令唯一标识
    """
    command_type: VSCodeCommandType
    params: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "id": self.id,
            "command_type": self.command_type.value,
            "params": self.params,
        }


@dataclass
class VSCodeEvent:
    """VSCode 事件.
    
    Attributes:
        event_type: 事件类型
        data: 事件数据
        timestamp: 时间戳
    """
    event_type: VSCodeEventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "event_type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


class TestLensProvider:
    """测试 Lens 提供者.
    
    为代码中的可测试函数提供 Code Lens（代码镜头）。
    """
    
    def __init__(self):
        """初始化提供者."""
        self.logger = logging.getLogger(__name__)
        
    def _extract_testable_functions(self, code: str) -> List[Dict[str, Any]]:
        """提取可测试函数.
        
        Args:
            code: 源代码
            
        Returns:
            List[Dict[str, Any]]: 函数信息列表
        """
        functions = []
        
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return functions
            
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 跳过私有函数和测试函数
                if node.name.startswith("_") or node.name.startswith("test_"):
                    continue
                    
                functions.append({
                    "name": node.name,
                    "line": node.lineno - 1,  # 转换为0-based
                    "type": "function",
                    "args": [arg.arg for arg in node.args.args],
                })
            elif isinstance(node, ast.ClassDef):
                # 提取类方法
                for child in node.body:
                    if isinstance(child, ast.FunctionDef):
                        if child.name.startswith("_"):
                            continue
                            
                        functions.append({
                            "name": f"{node.name}.{child.name}",
                            "line": child.lineno - 1,
                            "type": "method",
                            "class_name": node.name,
                            "args": [arg.arg for arg in child.args.args],
                        })
                        
        return functions
        
    def _create_code_lens(
        self,
        func_info: Dict[str, Any],
        file_path: str,
    ) -> List[Dict[str, Any]]:
        """创建 Code Lens.
        
        Args:
            func_info: 函数信息
            file_path: 文件路径
            
        Returns:
            List[Dict[str, Any]]: Code Lens 列表
        """
        lenses = []
        
        # 生成测试 lens
        lenses.append({
            "range": {
                "start": {"line": func_info["line"], "character": 0},
                "end": {"line": func_info["line"], "character": len(func_info["name"])},
            },
            "command": {
                "title": "$(beaker) Generate Test",
                "command": "ut-agent.generateTest",
                "arguments": [file_path, func_info["name"]],
            },
            "data": func_info,
        })
        
        return lenses
        
    def provide_code_lenses(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提供 Code Lenses.
        
        Args:
            document: 文档信息，包含 uri 和 content
            
        Returns:
            List[Dict[str, Any]]: Code Lens 列表
        """
        code = document.get("content", "")
        file_path = document.get("uri", "")
        
        functions = self._extract_testable_functions(code)
        lenses = []
        
        for func in functions:
            lenses.extend(self._create_code_lens(func, file_path))
            
        return lenses


class CodeActionProvider:
    """代码动作提供者.
    
    为代码提供快速修复和重构动作。
    """
    
    def __init__(self):
        """初始化提供者."""
        self.logger = logging.getLogger(__name__)
        
    def provide_code_actions(
        self,
        document: Dict[str, Any],
        range_info: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """提供代码动作.
        
        Args:
            document: 文档信息
            range_info: 选中的范围
            context: 上下文信息
            
        Returns:
            List[Dict[str, Any]]: 代码动作列表
        """
        actions = []
        selected_text = context.get("selected_text", "")
        file_path = document.get("uri", "")
        
        # 检测是否为函数定义
        if selected_text.strip().startswith("def "):
            func_name = self._extract_function_name(selected_text)
            if func_name and not func_name.startswith("test_"):
                actions.append({
                    "title": "Generate Test",
                    "kind": "quickfix",
                    "command": {
                        "command": "ut-agent.generateTest",
                        "arguments": [file_path, func_name],
                    },
                })
                
        # 检测是否为测试函数
        if selected_text.strip().startswith("def test_"):
            actions.append({
                "title": "Run Test",
                "kind": "quickfix",
                "command": {
                    "command": "ut-agent.runTest",
                    "arguments": [file_path, selected_text.strip()],
                },
            })
            actions.append({
                "title": "Debug Test",
                "kind": "quickfix",
                "command": {
                    "command": "ut-agent.debugTest",
                    "arguments": [file_path, selected_text.strip()],
                },
            })
            
        # 添加分析质量动作
        actions.append({
            "title": "Analyze Test Quality",
            "kind": "refactor",
            "command": {
                "command": "ut-agent.analyzeQuality",
                "arguments": [file_path],
            },
        })
        
        return actions
        
    def _extract_function_name(self, code: str) -> Optional[str]:
        """提取函数名.
        
        Args:
            code: 代码片段
            
        Returns:
            Optional[str]: 函数名
        """
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    return node.name
        except SyntaxError:
            pass
        return None


class HoverProvider:
    """悬停提示提供者.
    
    为代码提供悬停提示信息。
    """
    
    def __init__(self):
        """初始化提供者."""
        self.logger = logging.getLogger(__name__)
        
    def provide_hover(
        self,
        document: Dict[str, Any],
        position: Dict[str, int],
    ) -> Optional[Dict[str, Any]]:
        """提供悬停提示.
        
        Args:
            document: 文档信息
            position: 光标位置
            
        Returns:
            Optional[Dict[str, Any]]: 悬停信息
        """
        code = document.get("content", "")
        line = position.get("line", 0)
        
        lines = code.split("\n")
        if line >= len(lines):
            return None
            
        line_content = lines[line]
        
        # 检测是否为函数定义行
        if line_content.strip().startswith("def "):
            func_name = self._extract_function_name(line_content)
            if func_name:
                return {
                    "contents": {
                        "kind": "markdown",
                        "value": f"**{func_name}**\n\nClick 'Generate Test' to create a test for this function.",
                    },
                    "range": {
                        "start": {"line": line, "character": 0},
                        "end": {"line": line, "character": len(line_content)},
                    },
                }
                
        # 检测是否为测试函数
        if line_content.strip().startswith("def test_"):
            return {
                "contents": {
                    "kind": "markdown",
                    "value": "**Test Function**\n\n- Run Test: Execute this test\n- Debug Test: Debug this test\n- Analyze Quality: Check test quality",
                },
                "range": {
                    "start": {"line": line, "character": 0},
                    "end": {"line": line, "character": len(line_content)},
                },
            }
            
        return None
        
    def _extract_function_name(self, line: str) -> Optional[str]:
        """从行中提取函数名.
        
        Args:
            line: 代码行
            
        Returns:
            Optional[str]: 函数名
        """
        import re
        match = re.search(r"def\s+(\w+)", line)
        if match:
            return match.group(1)
        return None


class VSCodeExtension:
    """VSCode 扩展.
    
    管理 VSCode 插件的命令、事件和提供者。
    """
    
    def __init__(self):
        """初始化扩展."""
        self.commands: Dict[VSCodeCommandType, Callable] = {}
        self.providers: List[Any] = []
        self._event_listeners: Dict[VSCodeEventType, List[Callable]] = {}
        self.logger = logging.getLogger(__name__)
        
    def register_command(
        self,
        command_type: VSCodeCommandType,
        handler: Callable[[Dict[str, Any]], Any],
    ) -> None:
        """注册命令.
        
        Args:
            command_type: 命令类型
            handler: 命令处理器
        """
        self.commands[command_type] = handler
        self.logger.debug(f"Registered command: {command_type.value}")
        
    def register_provider(self, provider_type: str, provider: Any) -> None:
        """注册提供者.
        
        Args:
            provider_type: 提供者类型
            provider: 提供者实例
        """
        self.providers.append(provider)
        self.logger.debug(f"Registered provider: {provider_type}")
        
    async def execute_command(self, command: VSCodeCommand) -> Dict[str, Any]:
        """执行命令.
        
        Args:
            command: 命令对象
            
        Returns:
            Dict[str, Any]: 执行结果
        """
        handler = self.commands.get(command.command_type)
        
        if not handler:
            return {
                "success": False,
                "error": f"Command not found: {command.command_type.value}",
            }
            
        try:
            import asyncio
            if asyncio.iscoroutinefunction(handler):
                result = await handler(command.params)
            else:
                result = handler(command.params)
                
            return {
                "success": True,
                "data": result,
            }
        except Exception as e:
            self.logger.exception(f"Command execution failed: {command.command_type.value}")
            return {
                "success": False,
                "error": str(e),
            }
            
    def on(self, event_type: VSCodeEventType, listener: Callable[[VSCodeEvent], None]) -> None:
        """注册事件监听器.
        
        Args:
            event_type: 事件类型
            listener: 监听器函数
        """
        if event_type not in self._event_listeners:
            self._event_listeners[event_type] = []
        self._event_listeners[event_type].append(listener)
        
    def off(self, event_type: VSCodeEventType, listener: Callable[[VSCodeEvent], None]) -> None:
        """移除事件监听器.
        
        Args:
            event_type: 事件类型
            listener: 监听器函数
        """
        if event_type in self._event_listeners:
            self._event_listeners[event_type] = [
                l for l in self._event_listeners[event_type] if l != listener
            ]
            
    def emit(self, event_type: VSCodeEventType, data: Dict[str, Any]) -> None:
        """触发事件.
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        event = VSCodeEvent(event_type=event_type, data=data)
        listeners = self._event_listeners.get(event_type, [])
        
        for listener in listeners:
            try:
                listener(event)
            except Exception as e:
                self.logger.exception(f"Event listener failed: {e}")
                
    def get_manifest(self) -> Dict[str, Any]:
        """获取插件清单.
        
        Returns:
            Dict[str, Any]: 插件清单
        """
        return {
            "name": "ut-agent",
            "displayName": "UT Agent - AI Test Generator",
            "description": "AI-powered unit test generation and quality analysis",
            "version": "1.0.0",
            "publisher": "ut-agent",
            "engines": {
                "vscode": "^1.74.0",
            },
            "categories": ["Testing", "Machine Learning", "Snippets"],
            "activationEvents": [
                "onLanguage:python",
                "onCommand:ut-agent.generateTest",
            ],
            "main": "./out/extension.js",
            "contributes": {
                "commands": [
                    {
                        "command": "ut-agent.generateTest",
                        "title": "Generate Test",
                        "category": "UT Agent",
                        "icon": "$(beaker)",
                    },
                    {
                        "command": "ut-agent.runTest",
                        "title": "Run Test",
                        "category": "UT Agent",
                        "icon": "$(play)",
                    },
                    {
                        "command": "ut-agent.debugTest",
                        "title": "Debug Test",
                        "category": "UT Agent",
                        "icon": "$(debug-alt)",
                    },
                    {
                        "command": "ut-agent.analyzeQuality",
                        "title": "Analyze Test Quality",
                        "category": "UT Agent",
                        "icon": "$(star)",
                    },
                    {
                        "command": "ut-agent.refresh",
                        "title": "Refresh",
                        "category": "UT Agent",
                        "icon": "$(refresh)",
                    },
                    {
                        "command": "ut-agent.configure",
                        "title": "Configure",
                        "category": "UT Agent",
                        "icon": "$(gear)",
                    },
                ],
                "menus": {
                    "editor/context": [
                        {
                            "command": "ut-agent.generateTest",
                            "when": "editorHasSelection && resourceExtname == .py",
                            "group": "ut-agent@1",
                        },
                    ],
                },
                "configuration": {
                    "title": "UT Agent",
                    "properties": {
                        "ut-agent.llmProvider": {
                            "type": "string",
                            "default": "openai",
                            "enum": ["openai", "azure", "anthropic", "gemini"],
                            "description": "LLM provider to use",
                        },
                        "ut-agent.apiKey": {
                            "type": "string",
                            "default": "",
                            "description": "API key for the LLM provider",
                        },
                        "ut-agent.model": {
                            "type": "string",
                            "default": "gpt-4",
                            "description": "Model to use for test generation",
                        },
                    },
                },
            },
        }
        
    def get_configuration_schema(self) -> Dict[str, Any]:
        """获取配置模式.
        
        Returns:
            Dict[str, Any]: 配置模式
        """
        return {
            "properties": {
                "ut-agent.llmProvider": {
                    "type": "string",
                    "default": "openai",
                    "description": "LLM provider to use",
                },
                "ut-agent.apiKey": {
                    "type": "string",
                    "default": "",
                    "description": "API key for the LLM provider",
                },
                "ut-agent.model": {
                    "type": "string",
                    "default": "gpt-4",
                    "description": "Model to use for test generation",
                },
                "ut-agent.temperature": {
                    "type": "number",
                    "default": 0.7,
                    "minimum": 0,
                    "maximum": 2,
                    "description": "Temperature for LLM generation",
                },
                "ut-agent.maxTokens": {
                    "type": "integer",
                    "default": 2000,
                    "description": "Maximum tokens for generation",
                },
            },
        }
