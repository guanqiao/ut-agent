"""Go 语言代码分析器."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class GoMethod:
    """Go 方法定义."""
    
    name: str
    receiver: Optional[str] = None
    params: List[Dict[str, Any]] = field(default_factory=list)
    returns: List[Dict[str, Any]] = field(default_factory=list)
    is_exported: bool = False
    docstring: Optional[str] = None
    
    def get_signature(self) -> str:
        """生成方法签名."""
        params_str = ", ".join([f"{p.get('name', '')} {p.get('type', '')}".strip() for p in self.params])
        returns_str = ""
        if self.returns:
            if len(self.returns) == 1:
                returns_str = self.returns[0].get("type", "")
            else:
                returns_str = "(" + ", ".join([r.get("type", "") for r in self.returns]) + ")"
        
        sig = f"func {self.name}({params_str})"
        if returns_str:
            sig += f" {returns_str}"
        return sig


@dataclass
class GoStruct:
    """Go 结构体定义."""
    
    name: str
    fields: List[Dict[str, Any]] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    
    def get_interface_dependencies(self) -> Set[str]:
        """获取接口类型的依赖."""
        deps = set()
        for field in self.fields:
            if field.get("is_interface", False):
                deps.add(field.get("type", "").lstrip("*"))
        return deps


@dataclass
class GoInterface:
    """Go 接口定义."""
    
    name: str
    methods: List[Dict[str, Any]] = field(default_factory=list)
    docstring: Optional[str] = None


@dataclass
class GoAnalysisResult:
    """Go 代码分析结果."""
    
    structs: Dict[str, GoStruct] = field(default_factory=dict)
    interfaces: Dict[str, GoInterface] = field(default_factory=dict)
    methods: Dict[str, GoMethod] = field(default_factory=dict)
    imports: Set[str] = field(default_factory=set)
    package: Optional[str] = None
    
    def get_testable_methods(self) -> List[GoMethod]:
        """获取可测试的导出方法."""
        return [m for m in self.methods.values() if m.is_exported]
    
    def get_mock_targets(self, struct_name: str) -> Set[str]:
        """获取指定结构体的 Mock 目标."""
        if struct_name in self.structs:
            return self.structs[struct_name].get_interface_dependencies()
        return set()


class GoAnalyzer:
    """Go 代码分析器."""
    
    def __init__(self):
        """初始化分析器."""
        self._struct_pattern = re.compile(
            r'(?://\s*(.+?)\s*\n)?type\s+(\w+)\s+struct\s*\{([^}]*)\}',
            re.MULTILINE | re.DOTALL
        )
        self._interface_pattern = re.compile(
            r'(?://\s*(.+?)\s*\n)?type\s+(\w+)\s+interface\s*\{([^}]*)\}',
            re.MULTILINE | re.DOTALL
        )
        self._method_pattern = re.compile(
            r'(?://\s*(.+?)\s*\n)?func\s+\((\w+)\s*\*?(\w+)\)\s+(\w+)\s*\(([^)]*)\)\s*(.*?)\s*\{',
            re.MULTILINE | re.DOTALL
        )
        self._import_pattern = re.compile(
            r'import\s*\(([^)]+)\)',
            re.MULTILINE | re.DOTALL
        )
        self._single_import_pattern = re.compile(
            r'import\s+"([^"]+)"'
        )
        self._package_pattern = re.compile(
            r'package\s+(\w+)'
        )
    
    def analyze(self, code: str) -> GoAnalysisResult:
        """分析 Go 代码.
        
        Args:
            code: Go 源代码字符串
            
        Returns:
            GoAnalysisResult: 分析结果
        """
        result = GoAnalysisResult()
        
        if not code or not code.strip():
            return result
        
        try:
            # 分析包名
            result.package = self._extract_package(code)
            
            # 分析导入
            result.imports = self._extract_imports(code)
            
            # 分析结构体
            result.structs = self._extract_structs(code)
            
            # 分析接口
            result.interfaces = self._extract_interfaces(code)
            
            # 分析方法
            result.methods = self._extract_methods(code, result.structs)
            
        except Exception:
            # 优雅处理错误，返回空结果
            pass
        
        return result
    
    def analyze_file(self, file_path: Path) -> GoAnalysisResult:
        """分析单个 Go 文件.
        
        Args:
            file_path: Go 文件路径
            
        Returns:
            GoAnalysisResult: 分析结果
        """
        code = file_path.read_text(encoding="utf-8")
        return self.analyze(code)
    
    def analyze_directory(self, dir_path: Path) -> Dict[Path, GoAnalysisResult]:
        """分析目录中的所有 Go 文件.
        
        Args:
            dir_path: 目录路径
            
        Returns:
            Dict[Path, GoAnalysisResult]: 文件路径到分析结果的映射
        """
        results = {}
        for go_file in dir_path.rglob("*.go"):
            if "_test.go" not in go_file.name:  # 跳过测试文件
                results[go_file] = self.analyze_file(go_file)
        return results
    
    def _extract_package(self, code: str) -> Optional[str]:
        """提取包名."""
        match = self._package_pattern.search(code)
        return match.group(1) if match else None
    
    def _extract_imports(self, code: str) -> Set[str]:
        """提取导入的包."""
        imports = set()
        
        # 多行导入
        for match in self._import_pattern.finditer(code):
            import_block = match.group(1)
            for line in import_block.split('\n'):
                line = line.strip()
                if line and not line.startswith('//'):
                    # 处理别名和路径
                    parts = line.split()
                    if len(parts) >= 1:
                        pkg = parts[-1].strip('"')
                        imports.add(pkg.split('/')[-1])
        
        # 单行导入
        for match in self._single_import_pattern.finditer(code):
            pkg = match.group(1)
            imports.add(pkg.split('/')[-1])
        
        return imports
    
    def _extract_structs(self, code: str) -> Dict[str, GoStruct]:
        """提取结构体定义."""
        structs = {}
        
        # 使用正则匹配结构体
        pattern = re.compile(
            r'(?://\s*(.+?)\s*\n)?type\s+(\w+)\s+struct\s*\{([^}]*)\}',
            re.MULTILINE | re.DOTALL
        )
        
        for match in pattern.finditer(code):
            docstring = match.group(1)
            name = match.group(2)
            fields_block = match.group(3)
            
            fields = self._parse_fields(fields_block, code)
            
            structs[name] = GoStruct(
                name=name,
                fields=fields,
                docstring=docstring
            )
        
        return structs
    
    def _parse_fields(self, fields_block: str, full_code: str) -> List[Dict[str, Any]]:
        """解析结构体字段."""
        fields = []
        
        # 检测已知的接口类型
        known_interfaces = self._detect_interfaces(full_code)
        
        for line in fields_block.split('\n'):
            line = line.strip()
            if not line or line.startswith('//'):
                continue
            
            # 匹配字段定义: name type 或 name type `tag`
            parts = line.split()
            if len(parts) >= 2:
                field_name = parts[0]
                field_type = parts[1]
                
                # 检查是否是接口类型
                base_type = field_type.lstrip("*")
                is_interface = base_type in known_interfaces
                
                fields.append({
                    "name": field_name,
                    "type": field_type,
                    "is_interface": is_interface
                })
        
        return fields
    
    def _detect_interfaces(self, code: str) -> Set[str]:
        """检测代码中定义的接口类型."""
        interfaces = set()
        pattern = re.compile(r'type\s+(\w+)\s+interface\s*\{', re.MULTILINE)
        for match in pattern.finditer(code):
            interfaces.add(match.group(1))
        return interfaces
    
    def _extract_interfaces(self, code: str) -> Dict[str, GoInterface]:
        """提取接口定义."""
        interfaces = {}
        
        pattern = re.compile(
            r'(?://\s*(.+?)\s*\n)?type\s+(\w+)\s+interface\s*\{([^}]*)\}',
            re.MULTILINE | re.DOTALL
        )
        
        for match in pattern.finditer(code):
            docstring = match.group(1)
            name = match.group(2)
            methods_block = match.group(3)
            
            methods = self._parse_interface_methods(methods_block)
            
            interfaces[name] = GoInterface(
                name=name,
                methods=methods,
                docstring=docstring
            )
        
        return interfaces
    
    def _parse_interface_methods(self, methods_block: str) -> List[Dict[str, Any]]:
        """解析接口方法."""
        methods = []
        
        for line in methods_block.split('\n'):
            line = line.strip()
            if not line or line.startswith('//'):
                continue
            
            # 匹配方法签名: MethodName(params) returns
            match = re.match(r'(\w+)\s*\(([^)]*)\)\s*(.*)', line)
            if match:
                method_name = match.group(1)
                params_str = match.group(2)
                returns_str = match.group(3)
                
                params = self._parse_params(params_str)
                returns = self._parse_returns(returns_str)
                
                methods.append({
                    "name": method_name,
                    "params": params,
                    "returns": returns
                })
        
        return methods
    
    def _extract_methods(self, code: str, structs: Dict[str, GoStruct]) -> Dict[str, GoMethod]:
        """提取方法定义."""
        methods = {}
        
        # 匹配方法定义
        pattern = re.compile(
            r'(?://\s*(.+?)\s*\n)?func\s+\((\w+)\s*\*?(\w+)\)\s+(\w+)\s*\(([^)]*)\)\s*(.*?)\s*\{',
            re.MULTILINE | re.DOTALL
        )
        
        for match in pattern.finditer(code):
            docstring = match.group(1)
            receiver_var = match.group(2)
            receiver_type = match.group(3)
            method_name = match.group(4)
            params_str = match.group(5)
            returns_str = match.group(6).strip()
            
            # 判断是否是导出方法（首字母大写）
            is_exported = method_name[0].isupper() if method_name else False
            
            params = self._parse_params(params_str)
            returns = self._parse_returns(returns_str)
            
            method = GoMethod(
                name=method_name,
                receiver=receiver_type,
                params=params,
                returns=returns,
                is_exported=is_exported,
                docstring=docstring
            )
            
            methods[method_name] = method
            
            # 更新结构体的方法列表
            if receiver_type in structs:
                structs[receiver_type].methods.append(method_name)
        
        return methods
    
    def _parse_params(self, params_str: str) -> List[Dict[str, Any]]:
        """解析参数列表."""
        params = []
        if not params_str.strip():
            return params
        
        # 简化处理，按逗号分割
        for param in params_str.split(','):
            param = param.strip()
            if not param:
                continue
            
            parts = param.split()
            if len(parts) >= 2:
                params.append({
                    "name": parts[0],
                    "type": parts[1]
                })
            elif len(parts) == 1:
                params.append({
                    "name": "",
                    "type": parts[0]
                })
        
        return params
    
    def _parse_returns(self, returns_str: str) -> List[Dict[str, Any]]:
        """解析返回值."""
        returns = []
        if not returns_str:
            return returns
        
        # 处理括号包裹的多返回值
        returns_str = returns_str.strip()
        if returns_str.startswith('(') and returns_str.endswith(')'):
            returns_str = returns_str[1:-1]
        
        # 按逗号分割
        for ret in returns_str.split(','):
            ret = ret.strip()
            if ret:
                returns.append({"type": ret})
        
        return returns
