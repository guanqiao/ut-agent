"""代码分析模块 - 重构版.

优化点：
1. 将过长函数拆分为小函数
2. 提取文件读取逻辑
3. 提取 AST 解析逻辑
4. 提取信息提取逻辑
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

from ut_agent.tools.ast_cache import ASTCacheManager, parse_java_ast, parse_typescript_ast
from ut_agent.exceptions import FileReadError, ASTParseError, CodeAnalysisError


@dataclass
class MethodInfo:
    """方法信息."""
    name: str
    signature: str
    return_type: str
    parameters: List[Dict[str, str]]
    annotations: List[str]
    start_line: int
    end_line: int
    is_public: bool = True
    is_static: bool = False


@dataclass
class ClassInfo:
    """类信息."""
    name: str
    package: str
    imports: List[str]
    annotations: List[str]
    methods: List[MethodInfo]
    fields: List[Dict[str, Any]]
    superclass: Optional[str] = None
    interfaces: List[str] = field(default_factory=list)


class FileReader:
    """文件读取器."""
    
    @staticmethod
    def read_file(file_path: str) -> str:
        """读取文件内容.
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 文件内容
            
        Raises:
            FileReadError: 读取失败时抛出
        """
        path = Path(file_path)
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            raise FileReadError(
                f"Failed to read file with encoding error: {e}",
                file_path=file_path,
                reason="encoding"
            )
        except FileNotFoundError:
            raise FileReadError(
                f"File not found: {file_path}",
                file_path=file_path,
                reason="not_found"
            )
        except PermissionError:
            raise FileReadError(
                f"Permission denied: {file_path}",
                file_path=file_path,
                reason="permission"
            )


class JavaASTParser:
    """Java AST 解析器."""
    
    @staticmethod
    def parse(file_path: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """解析 Java AST.
        
        Args:
            file_path: 文件路径
            use_cache: 是否使用缓存
            
        Returns:
            Optional[Dict]: AST 数据或 None
        """
        if not use_cache:
            return None
        try:
            return parse_java_ast(file_path, use_cache=True)
        except (ASTParseError, Exception):
            return None


class JavaInfoExtractor:
    """Java 信息提取器."""
    
    @classmethod
    def extract(
        cls,
        ast_data: Optional[Dict[str, Any]],
        content: str,
        file_path: str
    ) -> Tuple[str, List[str], str, List[str], List[MethodInfo], List[Dict]]:
        """提取 Java 文件信息.
        
        Args:
            ast_data: AST 数据
            content: 文件内容
            file_path: 文件路径
            
        Returns:
            Tuple: (package, imports, class_name, annotations, methods, fields)
        """
        if ast_data:
            return cls._extract_from_ast(ast_data, content)
        return cls._extract_from_regex(content, file_path)
    
    @classmethod
    def _extract_from_ast(
        cls,
        ast_data: Dict[str, Any],
        content: str
    ) -> Tuple[str, List[str], str, List[str], List[MethodInfo], List[Dict]]:
        """从 AST 提取信息."""
        package = cls._extract_package(ast_data)
        imports = cls._extract_imports(ast_data)
        class_name, annotations = cls._extract_class_info(ast_data)
        methods = cls._extract_methods(ast_data, content)
        fields = cls._extract_fields(ast_data)
        return package, imports, class_name, annotations, methods, fields
    
    @classmethod
    def _extract_from_regex(
        cls,
        content: str,
        file_path: str
    ) -> Tuple[str, List[str], str, List[str], List[MethodInfo], List[Dict]]:
        """从正则表达式提取信息."""
        path = Path(file_path)
        
        package = cls._extract_package_regex(content)
        imports = cls._extract_imports_regex(content)
        class_name, annotations = cls._extract_class_info_regex(content, path)
        methods = cls._extract_methods_regex(content)
        fields = cls._extract_fields_regex(content)
        
        return package, imports, class_name, annotations, methods, fields
    
    @staticmethod
    def _extract_package(ast_data: Dict[str, Any]) -> str:
        """提取包名."""
        def find_nodes(node: Dict[str, Any], node_type: str) -> List[Dict[str, Any]]:
            result = []
            if node.get("type") == node_type:
                result.append(node)
            for child in node.get("children", []):
                result.extend(find_nodes(child, node_type))
            return result
        
        package_nodes = find_nodes(ast_data, "package_declaration")
        for pkg_node in package_nodes:
            scoped_id = find_nodes(pkg_node, "scoped_identifier")
            if scoped_id:
                return scoped_id[0].get("text", "")
        return ""
    
    @staticmethod
    def _extract_imports(ast_data: Dict[str, Any]) -> List[str]:
        """提取导入."""
        def find_nodes(node: Dict[str, Any], node_type: str) -> List[Dict[str, Any]]:
            result = []
            if node.get("type") == node_type:
                result.append(node)
            for child in node.get("children", []):
                result.extend(find_nodes(child, node_type))
            return result
        
        imports = []
        import_nodes = find_nodes(ast_data, "import_declaration")
        for imp_node in import_nodes:
            scoped_id = find_nodes(imp_node, "scoped_identifier")
            if scoped_id:
                imports.append(scoped_id[0].get("text", ""))
        return imports
    
    @staticmethod
    def _extract_class_info(ast_data: Dict[str, Any]) -> Tuple[str, List[str]]:
        """提取类信息."""
        def find_nodes(node: Dict[str, Any], node_type: str) -> List[Dict[str, Any]]:
            result = []
            if node.get("type") == node_type:
                result.append(node)
            for child in node.get("children", []):
                result.extend(find_nodes(child, node_type))
            return result
        
        class_name = ""
        annotations = []
        
        class_nodes = find_nodes(ast_data, "class_declaration")
        if class_nodes:
            class_node = class_nodes[0]
            for child in class_node.get("children", []):
                if child.get("type") == "identifier":
                    class_name = child.get("text", "")
                    break
            
            for sibling in ast_data.get("children", []):
                if sibling.get("type") == "annotation":
                    ann_name = ""
                    for child in sibling.get("children", []):
                        if child.get("type") == "identifier":
                            ann_name = child.get("text", "")
                            break
                    if ann_name:
                        annotations.append(ann_name)
        
        return class_name, annotations
    
    @staticmethod
    def _extract_methods(ast_data: Dict[str, Any], content: str) -> List[MethodInfo]:
        """提取方法."""
        def find_nodes(node: Dict[str, Any], node_type: str) -> List[Dict[str, Any]]:
            result = []
            if node.get("type") == node_type:
                result.append(node)
            for child in node.get("children", []):
                result.extend(find_nodes(child, node_type))
            return result
        
        methods = []
        method_nodes = find_nodes(ast_data, "method_declaration")
        for method_node in method_nodes:
            method_info = JavaMethodParser.parse(method_node, content)
            if method_info:
                methods.append(method_info)
        return methods
    
    @staticmethod
    def _extract_fields(ast_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取字段."""
        def find_nodes(node: Dict[str, Any], node_type: str) -> List[Dict[str, Any]]:
            result = []
            if node.get("type") == node_type:
                result.append(node)
            for child in node.get("children", []):
                result.extend(find_nodes(child, node_type))
            return result
        
        fields = []
        field_nodes = find_nodes(ast_data, "field_declaration")
        for field_node in field_nodes:
            field_info = JavaFieldParser.parse(field_node)
            if field_info:
                fields.append(field_info)
        return fields
    
    @staticmethod
    def _extract_package_regex(content: str) -> str:
        """使用正则提取包名."""
        match = re.search(r"package\s+([\w.]+);", content)
        return match.group(1) if match else ""
    
    @staticmethod
    def _extract_imports_regex(content: str) -> List[str]:
        """使用正则提取导入."""
        return re.findall(r"import\s+([\w.*]+);", content)
    
    @staticmethod
    def _extract_class_info_regex(content: str, path: Path) -> Tuple[str, List[str]]:
        """使用正则提取类信息."""
        pattern = r"(public\s+)?(abstract\s+)?(final\s+)?class\s+(\w+)"
        match = re.search(pattern, content)
        class_name = match.group(4) if match else path.stem
        annotations = re.findall(r"@(\w+)(?:\([^)]*\))?\s*(?=class|public\s+class)", content)
        return class_name, annotations
    
    @staticmethod
    def _extract_methods_regex(content: str) -> List[MethodInfo]:
        """使用正则提取方法."""
        methods = []
        pattern = r"(public|private|protected)\s+(static\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*\(([^)]*)\)"
        
        for match in re.finditer(pattern, content):
            access = match.group(1)
            is_static = bool(match.group(2))
            return_type = match.group(3)
            method_name = match.group(4)
            params_str = match.group(5)
            
            params = JavaParamParser.parse_regex(params_str)
            line_num = content[:match.start()].count("\n") + 1
            
            methods.append(MethodInfo(
                name=method_name,
                signature=f"{access} {return_type} {method_name}({params_str})",
                return_type=return_type,
                parameters=params,
                annotations=[],
                start_line=line_num,
                end_line=line_num + 5,
                is_public=access == "public",
                is_static=is_static,
            ))
        
        return methods
    
    @staticmethod
    def _extract_fields_regex(content: str) -> List[Dict[str, Any]]:
        """使用正则提取字段."""
        fields = []
        pattern = r"(private|public|protected)\s+(\w+(?:<[^>]+>)?)\s+(\w+)\s*;"
        
        for match in re.finditer(pattern, content):
            fields.append({
                "access": match.group(1),
                "type": match.group(2),
                "name": match.group(3),
            })
        
        return fields


class JavaMethodParser:
    """Java 方法解析器."""
    
    @staticmethod
    def parse(method_node: Dict[str, Any], content: str) -> Optional[MethodInfo]:
        """解析方法节点."""
        method_name = ""
        return_type = "void"
        params = []
        is_public = False
        is_static = False
        annotations = []
        
        for child in method_node.get("children", []):
            node_type = child.get("type", "")
            
            if node_type == "identifier":
                method_name = child.get("text", "")
            elif node_type == "type_identifier":
                return_type = child.get("text", "")
            elif node_type == "formal_parameters":
                params = JavaParamParser.parse_ast(child)
            elif node_type == "modifiers":
                for modifier in child.get("children", []):
                    mod_type = modifier.get("type", "")
                    if mod_type == "public":
                        is_public = True
                    elif mod_type == "static":
                        is_static = True
            elif node_type == "annotation":
                for ann_child in child.get("children", []):
                    if ann_child.get("type") == "identifier":
                        annotations.append(ann_child.get("text", ""))
        
        if not method_name:
            return None
        
        params_str = ", ".join([f"{p['type']} {p['name']}" for p in params])
        access = "public" if is_public else "private"
        
        return MethodInfo(
            name=method_name,
            signature=f"{access} {return_type} {method_name}({params_str})",
            return_type=return_type,
            parameters=params,
            annotations=annotations,
            start_line=method_node.get("start_point", {}).get("row", 0) + 1,
            end_line=method_node.get("end_point", {}).get("row", 0) + 1,
            is_public=is_public,
            is_static=is_static,
        )


class JavaFieldParser:
    """Java 字段解析器."""
    
    @staticmethod
    def parse(field_node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """解析字段节点."""
        field_type = ""
        field_name = ""
        access = "private"
        
        for child in field_node.get("children", []):
            node_type = child.get("type", "")
            
            if node_type == "type_identifier":
                field_type = child.get("text", "")
            elif node_type == "variable_declarator":
                for vc in child.get("children", []):
                    if vc.get("type") == "identifier":
                        field_name = vc.get("text", "")
            elif node_type == "modifiers":
                for modifier in child.get("children", []):
                    if modifier.get("type") in ("public", "private", "protected"):
                        access = modifier.get("type")
        
        if field_type and field_name:
            return {"access": access, "type": field_type, "name": field_name}
        return None


class JavaParamParser:
    """Java 参数解析器."""
    
    @staticmethod
    def parse_ast(params_node: Dict[str, Any]) -> List[Dict[str, str]]:
        """从 AST 解析参数."""
        params = []
        
        for child in params_node.get("children", []):
            if child.get("type") == "formal_parameter":
                param_type = ""
                param_name = ""
                
                for param_child in child.get("children", []):
                    pc_type = param_child.get("type", "")
                    if pc_type in ("type_identifier", "integral_type", "floating_point_type", "boolean_type"):
                        param_type = param_child.get("text", "")
                    elif pc_type == "identifier":
                        param_name = param_child.get("text", "")
                
                if param_type and param_name:
                    params.append({"type": param_type, "name": param_name})
        
        return params
    
    @staticmethod
    def parse_regex(params_str: str) -> List[Dict[str, str]]:
        """从正则表达式解析参数."""
        params = []
        
        if params_str.strip():
            for param in params_str.split(","):
                param = param.strip()
                if param:
                    parts = param.split()
                    if len(parts) >= 2:
                        params.append({
                            "type": parts[-2],
                            "name": parts[-1]
                        })
        
        return params


def analyze_java_file_refactored(file_path: str, use_cache: bool = True) -> Dict[str, Any]:
    """分析 Java 文件 - 重构版.
    
    Args:
        file_path: Java 文件路径
        use_cache: 是否使用 AST 缓存
        
    Returns:
        Dict: 分析结果
    """
    # 1. 读取文件
    content = FileReader.read_file(file_path)
    lines = content.split("\n")
    
    # 2. 解析 AST
    ast_data = JavaASTParser.parse(file_path, use_cache)
    
    # 3. 提取信息
    package, imports, class_name, annotations, methods, fields = JavaInfoExtractor.extract(
        ast_data, content, file_path
    )
    
    # 4. 构建结果
    return {
        "file_path": file_path,
        "file_name": Path(file_path).name,
        "language": "java",
        "package": package,
        "imports": imports,
        "class_name": class_name,
        "annotations": annotations,
        "methods": [
            {
                "name": m.name,
                "signature": m.signature,
                "return_type": m.return_type,
                "parameters": m.parameters,
                "annotations": m.annotations,
                "is_public": m.is_public,
                "is_static": m.is_static,
                "start_line": m.start_line,
            }
            for m in methods
        ],
        "fields": fields,
        "content": content,
        "line_count": len(lines),
    }


# 保持向后兼容 - 保留原有函数
# 从原模块导入其他函数
from ut_agent.tools.code_analyzer import (
    analyze_ts_file,
    extract_dependencies,
    find_testable_methods,
    parse_ts_params,
)
