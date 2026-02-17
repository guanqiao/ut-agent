"""C# 语言代码分析器."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class CsMethod:
    """C# 方法定义."""
    
    name: str
    return_type: str = "void"
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    is_async: bool = False
    is_static: bool = False
    is_public: bool = False
    is_virtual: bool = False
    is_abstract: bool = False
    attributes: List[str] = field(default_factory=list)
    xml_doc: Optional[str] = None
    
    def get_signature(self) -> str:
        """生成方法签名."""
        modifiers = []
        if self.is_public:
            modifiers.append("public")
        if self.is_static:
            modifiers.append("static")
        if self.is_async:
            modifiers.append("async")
        if self.is_virtual:
            modifiers.append("virtual")
        if self.is_abstract:
            modifiers.append("abstract")
        
        params_str = ", ".join([f"{p.get('type', 'object')} {p.get('name', 'param')}" for p in self.parameters])
        return f"{' '.join(modifiers)} {self.return_type} {self.name}({params_str})"


@dataclass
class CsClass:
    """C# 类定义."""
    
    name: str
    namespace: Optional[str] = None
    base_class: Optional[str] = None
    interfaces: List[str] = field(default_factory=list)
    properties: List[Dict[str, Any]] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)
    is_public: bool = False
    is_abstract: bool = False
    is_sealed: bool = False
    is_generic: bool = False
    attributes: List[str] = field(default_factory=list)
    xml_doc: Optional[str] = None
    
    def get_interface_dependencies(self) -> Set[str]:
        """获取接口类型的依赖."""
        deps = set()
        # 从属性中收集接口依赖
        for prop in self.properties:
            if prop.get("is_interface", False):
                deps.add(prop.get("type", ""))
        # 从实现的接口中收集
        deps.update(self.interfaces)
        return deps


@dataclass
class CsInterface:
    """C# 接口定义."""
    
    name: str
    namespace: Optional[str] = None
    methods: List[Dict[str, Any]] = field(default_factory=list)
    is_public: bool = False
    xml_doc: Optional[str] = None


@dataclass
class CsAnalysisResult:
    """C# 代码分析结果."""
    
    classes: Dict[str, CsClass] = field(default_factory=dict)
    interfaces: Dict[str, CsInterface] = field(default_factory=dict)
    methods: Dict[str, CsMethod] = field(default_factory=dict)
    usings: Set[str] = field(default_factory=set)
    namespace: Optional[str] = None
    
    def get_testable_methods(self) -> List[CsMethod]:
        """获取可测试的公开方法."""
        return [m for m in self.methods.values() if m.is_public]
    
    def get_mock_targets(self, class_name: str) -> Set[str]:
        """获取指定类的 Mock 目标."""
        if class_name in self.classes:
            return self.classes[class_name].get_interface_dependencies()
        return set()


class CsAnalyzer:
    """C# 代码分析器."""
    
    def __init__(self):
        """初始化分析器."""
        self._class_pattern = re.compile(
            r'(?:///\s*<summary>\s*(.+?)\s*</summary>\s*)?'
            r'((?:\[\w+[^\]]*\]\s*)*)'
            r'(public\s+)?(abstract\s+)?(sealed\s+)?(partial\s+)?class\s+(\w+)(?:<[^>]+>)?'
            r'(?:\s*:\s*([^{]+))?\s*\{',
            re.MULTILINE | re.DOTALL
        )
        self._interface_pattern = re.compile(
            r'(?:///\s*<summary>\s*(.+?)\s*</summary>\s*)?'
            r'(public\s+)?interface\s+(\w+)(?:<[^>]+>)?(?:\s*:\s*([^{]+))?\s*\{',
            re.MULTILINE | re.DOTALL
        )
        self._method_pattern = re.compile(
            r'(?:///\s*<summary>\s*(.+?)\s*</summary>\s*)?'
            r'((?:\[\w+[^\]]*\]\s*)*)'
            r'(public\s+)?(private\s+)?(protected\s+)?(internal\s+)?'
            r'(static\s+)?(async\s+)?(virtual\s+)?(abstract\s+)?(override\s+)?'
            r'(\w+(?:<[^>]+>)?(?:\[\])?)\s+(\w+)\s*\(([^)]*)\)',
            re.MULTILINE | re.DOTALL
        )
        self._using_pattern = re.compile(
            r'using\s+([\w.]+);',
            re.MULTILINE
        )
        self._namespace_pattern = re.compile(
            r'namespace\s+([\w.]+)\s*\{',
            re.MULTILINE
        )
        self._property_pattern = re.compile(
            r'(public\s+)?(private\s+)?(protected\s+)?(internal\s+)?'
            r'(readonly\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*\{[^}]*\}',
            re.MULTILINE
        )
    
    def analyze(self, code: str) -> CsAnalysisResult:
        """分析 C# 代码.
        
        Args:
            code: C# 源代码字符串
            
        Returns:
            CsAnalysisResult: 分析结果
        """
        result = CsAnalysisResult()
        
        if not code or not code.strip():
            return result
        
        try:
            # 分析 using 语句
            result.usings = self._extract_usings(code)
            
            # 分析命名空间
            result.namespace = self._extract_namespace(code)
            
            # 分析接口（在类之前，因为类可能实现接口）
            result.interfaces = self._extract_interfaces(code, result.namespace)
            
            # 分析类
            result.classes = self._extract_classes(code, result.namespace)
            
            # 分析方法
            result.methods = self._extract_methods(code)
            
            # 关联方法和类
            self._associate_methods_with_classes(result)
            
        except Exception:
            # 优雅处理错误，返回空结果
            pass
        
        return result
    
    def analyze_file(self, file_path: Path) -> CsAnalysisResult:
        """分析单个 C# 文件.
        
        Args:
            file_path: C# 文件路径
            
        Returns:
            CsAnalysisResult: 分析结果
        """
        code = file_path.read_text(encoding="utf-8")
        return self.analyze(code)
    
    def analyze_directory(self, dir_path: Path) -> Dict[Path, CsAnalysisResult]:
        """分析目录中的所有 C# 文件.
        
        Args:
            dir_path: 目录路径
            
        Returns:
            Dict[Path, CsAnalysisResult]: 文件路径到分析结果的映射
        """
        results = {}
        for cs_file in dir_path.rglob("*.cs"):
            # 跳过生成的文件和测试文件
            if ".g.cs" not in cs_file.name and ".Designer.cs" not in cs_file.name:
                results[cs_file] = self.analyze_file(cs_file)
        return results
    
    def _extract_usings(self, code: str) -> Set[str]:
        """提取 using 语句."""
        usings = set()
        for match in self._using_pattern.finditer(code):
            usings.add(match.group(1))
        return usings
    
    def _extract_namespace(self, code: str) -> Optional[str]:
        """提取命名空间."""
        match = self._namespace_pattern.search(code)
        return match.group(1) if match else None
    
    def _extract_classes(self, code: str, namespace: Optional[str]) -> Dict[str, CsClass]:
        """提取类定义."""
        classes = {}
        
        pattern = re.compile(
            r'(?:///\s*<summary>\s*(.+?)\s*</summary>\s*)?'
            r'((?:\[\w+[^\]]*\]\s*)*)'
            r'(public\s+)?(abstract\s+)?(sealed\s+)?(partial\s+)?class\s+(\w+)(?:<[^>]+>)?'
            r'(?:\s*:\s*([^{]+))?\s*\{',
            re.MULTILINE | re.DOTALL
        )
        
        for match in pattern.finditer(code):
            xml_doc = match.group(1)
            attributes_str = match.group(2) or ""
            is_public = match.group(3) is not None
            is_abstract = match.group(4) is not None
            is_sealed = match.group(5) is not None
            name = match.group(7)
            inheritance_str = match.group(8) or ""
            
            # 解析继承和接口
            base_class = None
            interfaces = []
            if inheritance_str:
                parts = [p.strip() for p in inheritance_str.split(',')]
                for part in parts:
                    if part.startswith('I') or 'I' in part:
                        interfaces.append(part)
                    elif not base_class:
                        base_class = part
            
            # 解析属性
            properties = self._extract_properties(code, match.end())
            
            # 解析属性列表
            attributes = self._parse_attributes(attributes_str)
            
            classes[name] = CsClass(
                name=name,
                namespace=namespace,
                base_class=base_class,
                interfaces=interfaces,
                properties=properties,
                is_public=is_public,
                is_abstract=is_abstract,
                is_sealed=is_sealed,
                is_generic='<' in name,
                attributes=attributes,
                xml_doc=xml_doc
            )
        
        return classes
    
    def _extract_interfaces(self, code: str, namespace: Optional[str]) -> Dict[str, CsInterface]:
        """提取接口定义."""
        interfaces = {}
        
        pattern = re.compile(
            r'(?:///\s*<summary>\s*(.+?)\s*</summary>\s*)?'
            r'(public\s+)?interface\s+(\w+)(?:<[^>]+>)?(?:\s*:\s*([^{]+))?\s*\{([^}]*)\}',
            re.MULTILINE | re.DOTALL
        )
        
        for match in pattern.finditer(code):
            xml_doc = match.group(1)
            is_public = match.group(2) is not None
            name = match.group(3)
            methods_block = match.group(5)
            
            methods = self._parse_interface_methods(methods_block)
            
            interfaces[name] = CsInterface(
                name=name,
                namespace=namespace,
                methods=methods,
                is_public=is_public,
                xml_doc=xml_doc
            )
        
        return interfaces
    
    def _parse_interface_methods(self, block: str) -> List[Dict[str, Any]]:
        """解析接口方法."""
        methods = []
        
        pattern = re.compile(
            r'(\w+(?:<[^>]+>)?)\s+(\w+)\s*\(([^)]*)\);',
            re.MULTILINE
        )
        
        for match in pattern.finditer(block):
            return_type = match.group(1)
            name = match.group(2)
            params_str = match.group(3)
            
            parameters = self._parse_parameters(params_str)
            
            methods.append({
                "name": name,
                "return_type": return_type,
                "parameters": parameters
            })
        
        return methods
    
    def _extract_methods(self, code: str) -> Dict[str, CsMethod]:
        """提取方法定义."""
        methods = {}
        
        pattern = re.compile(
            r'(?:///\s*<summary>\s*(.+?)\s*</summary>\s*)?'
            r'((?:\[\w+[^\]]*\]\s*)*)'
            r'(public\s+)?(?:private\s+)?(?:protected\s+)?(?:internal\s+)?'
            r'(static\s+)?(async\s+)?(?:virtual\s+)?(?:abstract\s+)?(?:override\s+)?'
            r'(\w+(?:<[^>]+>)?(?:\[\])?)\s+(\w+)\s*\(([^)]*)\)',
            re.MULTILINE | re.DOTALL
        )
        
        for match in pattern.finditer(code):
            xml_doc = match.group(1)
            attributes_str = match.group(2) or ""
            is_public = match.group(3) is not None
            is_static = match.group(4) is not None
            is_async = match.group(5) is not None
            return_type = match.group(6)
            name = match.group(7)
            params_str = match.group(8)
            
            parameters = self._parse_parameters(params_str)
            attributes = self._parse_attributes(attributes_str)
            
            methods[name] = CsMethod(
                name=name,
                return_type=return_type,
                parameters=parameters,
                is_async=is_async,
                is_static=is_static,
                is_public=is_public,
                attributes=attributes,
                xml_doc=xml_doc
            )
        
        return methods
    
    def _parse_parameters(self, params_str: str) -> List[Dict[str, Any]]:
        """解析参数列表."""
        parameters = []
        if not params_str.strip():
            return parameters
        
        for param in params_str.split(','):
            param = param.strip()
            if not param:
                continue
            
            # 匹配类型和名称
            parts = param.split()
            if len(parts) >= 2:
                param_type = parts[-2] if parts[-2] not in ['ref', 'out', 'in', 'params'] else parts[-3]
                param_name = parts[-1]
                parameters.append({
                    "name": param_name,
                    "type": param_type
                })
        
        return parameters
    
    def _parse_attributes(self, attributes_str: str) -> List[str]:
        """解析属性."""
        attributes = []
        pattern = re.compile(r'\[(\w+)')
        for match in pattern.finditer(attributes_str):
            attributes.append(match.group(1))
        return attributes
    
    def _extract_properties(self, code: str, start_pos: int) -> List[Dict[str, Any]]:
        """提取属性定义."""
        properties = []
        
        # 获取类体内容（简化处理，找到匹配的 }）
        class_body = code[start_pos:]
        brace_count = 1
        end_pos = 0
        for i, char in enumerate(class_body):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_pos = i
                    break
        
        class_content = class_body[:end_pos]
        
        # 匹配属性
        pattern = re.compile(
            r'(public\s+)?(?:private\s+)?(?:protected\s+)?(?:internal\s+)?'
            r'(readonly\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*\{[^}]*\}',
            re.MULTILINE
        )
        
        for match in pattern.finditer(class_content):
            is_public = match.group(1) is not None
            prop_type = match.group(3)
            prop_name = match.group(4)
            
            # 检查是否是接口类型（以 I 开头）
            is_interface = prop_type.startswith('I') and prop_type[1:].isalpha()
            
            properties.append({
                "name": prop_name,
                "type": prop_type,
                "is_public": is_public,
                "is_interface": is_interface
            })
        
        return properties
    
    def _associate_methods_with_classes(self, result: CsAnalysisResult) -> None:
        """将方法与类关联."""
        # 简化处理：将方法名添加到包含该方法的类
        # 实际实现需要更复杂的代码结构分析
        for class_name, cls in result.classes.items():
            for method_name in result.methods:
                # 这里简化处理，实际应该分析方法在代码中的位置
                if method_name not in cls.methods:
                    cls.methods.append(method_name)
