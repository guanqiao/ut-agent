"""Rust 语言代码分析器."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class RustFunction:
    """Rust 函数定义."""
    
    name: str
    params: List[Dict[str, Any]] = field(default_factory=list)
    return_type: Optional[str] = None
    is_async: bool = False
    is_public: bool = False
    docstring: Optional[str] = None
    
    def get_signature(self) -> str:
        """生成函数签名."""
        visibility = "pub " if self.is_public else ""
        async_kw = "async " if self.is_async else ""
        params_str = ", ".join([f"{p.get('name', '_')}: {p.get('type', '_')}" for p in self.params])
        return_type_str = f" -> {self.return_type}" if self.return_type else ""
        return f"{visibility}{async_kw}fn {self.name}({params_str}){return_type_str}"


@dataclass
class RustStruct:
    """Rust 结构体定义."""
    
    name: str
    fields: List[Dict[str, Any]] = field(default_factory=list)
    is_public: bool = False
    docstring: Optional[str] = None
    derives: List[str] = field(default_factory=list)
    
    def get_trait_dependencies(self) -> Set[str]:
        """获取 trait 类型的依赖."""
        deps = set()
        for field in self.fields:
            if field.get("is_trait", False):
                field_type = field.get("type", "")
                # 提取 dyn Trait 或 Box<dyn Trait> 中的 Trait 名称
                if "dyn " in field_type:
                    match = re.search(r'dyn\s+(\w+)', field_type)
                    if match:
                        deps.add(match.group(1))
        return deps


@dataclass
class RustTrait:
    """Rust Trait 定义."""
    
    name: str
    methods: List[Dict[str, Any]] = field(default_factory=list)
    is_public: bool = False
    docstring: Optional[str] = None
    super_traits: List[str] = field(default_factory=list)


@dataclass
class RustImpl:
    """Rust Impl 块定义."""
    
    struct_name: str
    trait_name: Optional[str] = None
    methods: List[str] = field(default_factory=list)
    is_for_trait: bool = False


@dataclass
class RustAnalysisResult:
    """Rust 代码分析结果."""
    
    structs: Dict[str, RustStruct] = field(default_factory=dict)
    traits: Dict[str, RustTrait] = field(default_factory=dict)
    functions: Dict[str, RustFunction] = field(default_factory=dict)
    impls: List[RustImpl] = field(default_factory=list)
    imports: Set[str] = field(default_factory=set)
    
    def get_testable_functions(self) -> List[RustFunction]:
        """获取可测试的公开函数."""
        return [f for f in self.functions.values() if f.is_public]
    
    def get_mock_targets(self, struct_name: str) -> Set[str]:
        """获取指定结构体的 Mock 目标."""
        if struct_name in self.structs:
            return self.structs[struct_name].get_trait_dependencies()
        return set()


class RustAnalyzer:
    """Rust 代码分析器."""
    
    def __init__(self):
        """初始化分析器."""
        self._struct_pattern = re.compile(
            r'(?:(?:#\[derive\([^)]+\)\]\s*)?(?:///\s*(.+?)\s*)?(?:#\[\w+\]\s*)*)?'
            r'(pub\s+)?struct\s+(\w+)\s*\{([^}]*)\}',
            re.MULTILINE | re.DOTALL
        )
        self._trait_pattern = re.compile(
            r'(?:(?:///\s*(.+?)\s*)?(?:#\[\w+\]\s*)*)?'
            r'(pub\s+)?trait\s+(\w+)(?::\s*([^{]+))?\s*\{([^}]*)\}',
            re.MULTILINE | re.DOTALL
        )
        self._impl_pattern = re.compile(
            r'impl(?:<[^>]+>)?\s+(?:(\w+)\s+for\s+)?(\w+)\s*\{([^}]*)\}',
            re.MULTILINE | re.DOTALL
        )
        self._function_pattern = re.compile(
            r'(?:(?:///\s*(.+?)\s*)?(?:#\[\w+\]\s*)*)?'
            r'(pub\s+)?(async\s+)?fn\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*([^\{;]+))?',
            re.MULTILINE
        )
        self._use_pattern = re.compile(
            r'use\s+([^;]+);',
            re.MULTILINE
        )
    
    def analyze(self, code: str) -> RustAnalysisResult:
        """分析 Rust 代码.
        
        Args:
            code: Rust 源代码字符串
            
        Returns:
            RustAnalysisResult: 分析结果
        """
        result = RustAnalysisResult()
        
        if not code or not code.strip():
            return result
        
        try:
            # 分析导入
            result.imports = self._extract_imports(code)
            
            # 分析结构体
            result.structs = self._extract_structs(code)
            
            # 分析 trait
            result.traits = self._extract_traits(code)
            
            # 分析 impl 块
            result.impls = self._extract_impls(code)
            
            # 分析函数（在 impl 块中）
            result.functions = self._extract_functions(code)
            
        except Exception:
            # 优雅处理错误，返回空结果
            pass
        
        return result
    
    def analyze_file(self, file_path: Path) -> RustAnalysisResult:
        """分析单个 Rust 文件.
        
        Args:
            file_path: Rust 文件路径
            
        Returns:
            RustAnalysisResult: 分析结果
        """
        code = file_path.read_text(encoding="utf-8")
        return self.analyze(code)
    
    def analyze_directory(self, dir_path: Path) -> Dict[Path, RustAnalysisResult]:
        """分析目录中的所有 Rust 文件.
        
        Args:
            dir_path: 目录路径
            
        Returns:
            Dict[Path, RustAnalysisResult]: 文件路径到分析结果的映射
        """
        results = {}
        for rs_file in dir_path.rglob("*.rs"):
            # 跳过测试文件和生成的文件
            if "_test.rs" not in rs_file.name and "/target/" not in str(rs_file):
                results[rs_file] = self.analyze_file(rs_file)
        return results
    
    def _extract_imports(self, code: str) -> Set[str]:
        """提取导入."""
        imports = set()
        for match in self._use_pattern.finditer(code):
            import_path = match.group(1).strip()
            imports.add(import_path)
            # 也添加最后一部分作为快捷名
            if "::" in import_path:
                imports.add(import_path.split("::")[-1])
        return imports
    
    def _extract_structs(self, code: str) -> Dict[str, RustStruct]:
        """提取结构体定义."""
        structs = {}
        
        # 匹配结构体定义（包括 derive 属性）
        pattern = re.compile(
            r'(?:(?:#\[derive\(([^)]+)\)\]\s*)?(?:///\s*(.+?)\s*\n)?(?:#\[\w+\]\s*)*)?'
            r'(pub\s+)?struct\s+(\w+)\s*\{([^}]*)\}',
            re.MULTILINE | re.DOTALL
        )
        
        for match in pattern.finditer(code):
            derives_str = match.group(1) or ""
            docstring = match.group(2)
            is_public = match.group(3) is not None
            name = match.group(4)
            fields_block = match.group(5)
            
            derives = [d.strip() for d in derives_str.split(",") if d.strip()]
            fields = self._parse_struct_fields(fields_block, code)
            
            structs[name] = RustStruct(
                name=name,
                fields=fields,
                is_public=is_public,
                docstring=docstring,
                derives=derives
            )
        
        return structs
    
    def _parse_struct_fields(self, fields_block: str, full_code: str) -> List[Dict[str, Any]]:
        """解析结构体字段."""
        fields = []
        
        for line in fields_block.split('\n'):
            line = line.strip()
            if not line or line.startswith('//') or line.startswith('#'):
                continue
            
            # 匹配字段定义: name: Type 或 pub name: Type
            match = re.match(r'(pub\s+)?(\w+)\s*:\s*(.+)', line)
            if match:
                is_public = match.group(1) is not None
                field_name = match.group(2)
                field_type = match.group(3).rstrip(',')
                
                # 检查是否是 trait 对象类型
                is_trait = "dyn " in field_type or "impl " in field_type
                
                fields.append({
                    "name": field_name,
                    "type": field_type,
                    "is_public": is_public,
                    "is_trait": is_trait
                })
        
        return fields
    
    def _extract_traits(self, code: str) -> Dict[str, RustTrait]:
        """提取 trait 定义."""
        traits = {}
        
        pattern = re.compile(
            r'(?:(?:///\s*(.+?)\s*\n)?(?:#\[\w+\]\s*)*)?'
            r'(pub\s+)?trait\s+(\w+)(?::\s*([^{]+))?\s*\{([^}]*)\}',
            re.MULTILINE | re.DOTALL
        )
        
        for match in pattern.finditer(code):
            docstring = match.group(1)
            is_public = match.group(2) is not None
            name = match.group(3)
            super_traits_str = match.group(4) or ""
            methods_block = match.group(5)
            
            super_traits = [t.strip() for t in super_traits_str.split('+') if t.strip()]
            methods = self._parse_trait_methods(methods_block)
            
            traits[name] = RustTrait(
                name=name,
                methods=methods,
                is_public=is_public,
                docstring=docstring,
                super_traits=super_traits
            )
        
        return traits
    
    def _parse_trait_methods(self, methods_block: str) -> List[Dict[str, Any]]:
        """解析 trait 方法."""
        methods = []
        
        # 匹配 trait 中的方法签名
        pattern = re.compile(
            r'(?:(?:///\s*(.+?)\s*\n)?(?:#\[\w+\]\s*)*)?'
            r'(async\s+)?fn\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*([^;]+))?;?',
            re.MULTILINE
        )
        
        for match in pattern.finditer(methods_block):
            docstring = match.group(1)
            is_async = match.group(2) is not None
            name = match.group(3)
            params_str = match.group(4)
            return_type = match.group(5)
            
            if return_type:
                return_type = return_type.strip().rstrip(';')
            
            params = self._parse_params(params_str)
            
            methods.append({
                "name": name,
                "params": params,
                "return_type": return_type,
                "is_async": is_async,
                "docstring": docstring
            })
        
        return methods
    
    def _extract_impls(self, code: str) -> List[RustImpl]:
        """提取 impl 块."""
        impls = []
        
        pattern = re.compile(
            r'impl(?:<[^>]+>)?\s+(?:(\w+)\s+for\s+)?(\w+)\s*\{([^}]*)\}',
            re.MULTILINE | re.DOTALL
        )
        
        for match in pattern.finditer(code):
            trait_name = match.group(1)
            struct_name = match.group(2)
            methods_block = match.group(3)
            
            # 提取方法名
            methods = self._extract_method_names(methods_block)
            
            impls.append(RustImpl(
                struct_name=struct_name,
                trait_name=trait_name,
                methods=methods,
                is_for_trait=trait_name is not None
            ))
        
        return impls
    
    def _extract_method_names(self, block: str) -> List[str]:
        """提取 impl 块中的方法名."""
        names = []
        pattern = re.compile(r'fn\s+(\w+)\s*\(')
        for match in pattern.finditer(block):
            names.append(match.group(1))
        return names
    
    def _extract_functions(self, code: str) -> Dict[str, RustFunction]:
        """提取函数定义."""
        functions = {}
        
        # 匹配函数定义（包括 impl 块中的方法）
        pattern = re.compile(
            r'(?:(?:///\s*(.+?)\s*\n)?(?:#\[\w+\]\s*)*)?'
            r'(pub\s+)?(async\s+)?fn\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*([^\{;]+))?\s*[\{;]',
            re.MULTILINE
        )
        
        for match in pattern.finditer(code):
            docstring = match.group(1)
            is_public = match.group(2) is not None
            is_async = match.group(3) is not None
            name = match.group(4)
            params_str = match.group(5)
            return_type = match.group(6)
            
            if return_type:
                return_type = return_type.strip()
            
            params = self._parse_params(params_str)
            
            functions[name] = RustFunction(
                name=name,
                params=params,
                return_type=return_type,
                is_async=is_async,
                is_public=is_public,
                docstring=docstring
            )
        
        return functions
    
    def _parse_params(self, params_str: str) -> List[Dict[str, Any]]:
        """解析参数列表."""
        params = []
        if not params_str.strip():
            return params
        
        # 处理 &self, &mut self, self
        self_pattern = re.compile(r'&(?:mut\s+)?self')
        params_str = self_pattern.sub('', params_str)
        
        # 按逗号分割参数
        for param in params_str.split(','):
            param = param.strip()
            if not param:
                continue
            
            # 匹配 name: Type 或模式匹配
            match = re.match(r'(?:(\w+)\s*:\s*)?(.+)', param)
            if match:
                name = match.group(1) or ""
                param_type = match.group(2).strip()
                params.append({
                    "name": name,
                    "type": param_type
                })
        
        return params
