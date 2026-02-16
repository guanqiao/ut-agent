"""代码分析模块."""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional
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


def analyze_java_file(file_path: str, use_cache: bool = True) -> Dict[str, Any]:
    """分析 Java 文件.

    Args:
        file_path: Java 文件路径
        use_cache: 是否使用 AST 缓存

    Returns:
        Dict: 分析结果
    """
    path = Path(file_path)
    try:
        content = path.read_text(encoding="utf-8")
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
    lines = content.split("\n")

    ast_data = None
    if use_cache:
        try:
            ast_data = parse_java_ast(file_path, use_cache=True)
        except ASTParseError:
            pass
        except Exception:
            pass

    package = ""
    imports = []
    class_name = path.stem
    class_annotations = []
    methods = []
    fields = []

    if ast_data:
        package, imports, class_name, class_annotations, methods, fields = _extract_java_info_from_ast(
            ast_data, content
        )
    else:
        package_match = re.search(r"package\s+([\w.]+);", content)
        package = package_match.group(1) if package_match else ""

        imports = re.findall(r"import\s+([\w.*]+);", content)

        class_pattern = r"(public\s+)?(abstract\s+)?(final\s+)?class\s+(\w+)"
        class_match = re.search(class_pattern, content)
        class_name = class_match.group(4) if class_match else path.stem

        class_annotations = re.findall(r"@(\w+)(?:\([^)]*\))?\s*(?=class|public\s+class)", content)

        methods = _extract_java_methods_regex(content)

        field_pattern = r"(private|public|protected)\s+(\w+(?:<[^>]+>)?)\s+(\w+)\s*;"
        for match in re.finditer(field_pattern, content):
            fields.append({
                "access": match.group(1),
                "type": match.group(2),
                "name": match.group(3),
            })

    return {
        "file_path": file_path,
        "file_name": path.name,
        "language": "java",
        "package": package,
        "imports": imports,
        "class_name": class_name,
        "annotations": class_annotations,
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


def _extract_java_info_from_ast(
    ast_data: Dict[str, Any], content: str
) -> tuple:
    """从 AST 提取 Java 信息."""
    package = ""
    imports = []
    class_name = ""
    class_annotations = []
    methods = []
    fields = []

    def find_nodes(node: Dict[str, Any], node_type: str) -> List[Dict[str, Any]]:
        """递归查找指定类型的节点."""
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
            package = scoped_id[0].get("text", "")

    import_nodes = find_nodes(ast_data, "import_declaration")
    for imp_node in import_nodes:
        scoped_id = find_nodes(imp_node, "scoped_identifier")
        if scoped_id:
            imports.append(scoped_id[0].get("text", ""))

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
                    class_annotations.append(ann_name)

    method_nodes = find_nodes(ast_data, "method_declaration")
    for method_node in method_nodes:
        method_info = _parse_java_method_node(method_node, content)
        if method_info:
            methods.append(method_info)

    field_nodes = find_nodes(ast_data, "field_declaration")
    for field_node in field_nodes:
        field_info = _parse_java_field_node(field_node)
        if field_info:
            fields.append(field_info)

    return package, imports, class_name, class_annotations, methods, fields


def _parse_java_method_node(method_node: Dict[str, Any], content: str) -> Optional[MethodInfo]:
    """解析 Java 方法节点."""
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
            params = _parse_java_params_node(child)

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


def _parse_java_params_node(params_node: Dict[str, Any]) -> List[Dict[str, str]]:
    """解析 Java 参数节点."""
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


def _parse_java_field_node(field_node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """解析 Java 字段节点."""
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


def _extract_java_methods_regex(content: str) -> List[MethodInfo]:
    """使用正则表达式提取 Java 方法（后备方案）."""
    methods = []
    method_pattern = r"(public|private|protected)\s+(static\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*\(([^)]*)\)"

    for match in re.finditer(method_pattern, content):
        access = match.group(1)
        is_static = bool(match.group(2))
        return_type = match.group(3)
        method_name = match.group(4)
        params_str = match.group(5)

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

        start_pos = match.start()
        line_num = content[:start_pos].count("\n") + 1

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


def analyze_ts_file(file_path: str, use_cache: bool = True) -> Dict[str, Any]:
    """分析 TypeScript/Vue 文件.

    Args:
        file_path: 文件路径
        use_cache: 是否使用 AST 缓存

    Returns:
        Dict: 分析结果
    """
    path = Path(file_path)
    content = path.read_text(encoding="utf-8")
    lines = content.split("\n")

    is_vue = path.suffix == ".vue"

    if is_vue:
        script_match = re.search(r"<script[^>]*>(.*?)</script>", content, re.DOTALL)
        if script_match:
            ts_content = script_match.group(1)
        else:
            ts_content = content
    else:
        ts_content = content

    ast_data = None
    if use_cache and not is_vue:
        try:
            ast_data = parse_typescript_ast(file_path, use_cache=True)
        except Exception:
            pass

    imports = []
    functions = []
    component_info = {}

    if ast_data:
        imports, functions = _extract_ts_info_from_ast(ast_data, ts_content)
    else:
        imports = _extract_ts_imports_regex(ts_content)
        functions = _extract_ts_functions_regex(ts_content)

    if is_vue:
        component_info = _extract_vue_component_info(ts_content)

    return {
        "file_path": file_path,
        "file_name": path.name,
        "language": "typescript" if not is_vue else "vue",
        "is_vue": is_vue,
        "imports": imports,
        "functions": functions,
        "component_info": component_info,
        "content": content,
        "script_content": ts_content if is_vue else content,
        "line_count": len(lines),
    }


def _extract_ts_info_from_ast(
    ast_data: Dict[str, Any], content: str
) -> tuple:
    """从 AST 提取 TypeScript 信息."""
    imports = []
    functions = []

    def find_nodes(node: Dict[str, Any], node_type: str) -> List[Dict[str, Any]]:
        """递归查找指定类型的节点."""
        result = []
        if node.get("type") == node_type:
            result.append(node)
        for child in node.get("children", []):
            result.extend(find_nodes(child, node_type))
        return result

    import_nodes = find_nodes(ast_data, "import_statement")
    for imp_node in import_nodes:
        import_info = _parse_ts_import_node(imp_node)
        if import_info:
            imports.extend(import_info)

    func_nodes = find_nodes(ast_data, "function_declaration")
    for func_node in func_nodes:
        func_info = _parse_ts_function_node(func_node)
        if func_info:
            functions.append(func_info)

    arrow_nodes = find_nodes(ast_data, "variable_declarator")
    for arrow_node in arrow_nodes:
        func_info = _parse_ts_arrow_function_node(arrow_node)
        if func_info:
            functions.append(func_info)

    return imports, functions


def _parse_ts_import_node(import_node: Dict[str, Any]) -> List[Dict[str, str]]:
    """解析 TypeScript 导入节点."""
    imports = []
    source = ""
    named_imports = []
    default_import = ""

    for child in import_node.get("children", []):
        node_type = child.get("type", "")

        if node_type == "string":
            source = child.get("text", "").strip("\"'")

        elif node_type == "import_clause":
            for ic in child.get("children", []):
                if ic.get("type") == "identifier":
                    default_import = ic.get("text", "")
                elif ic.get("type") == "named_imports":
                    for ni in ic.get("children", []):
                        if ni.get("type") == "import_specifier":
                            for nsc in ni.get("children", []):
                                if nsc.get("type") == "identifier":
                                    named_imports.append(nsc.get("text", ""))

    if default_import:
        imports.append({
            "name": default_import,
            "source": source,
            "type": "default"
        })

    for name in named_imports:
        imports.append({
            "name": name,
            "source": source,
            "type": "named"
        })

    return imports


def _parse_ts_function_node(func_node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """解析 TypeScript 函数节点."""
    func_name = ""
    params = []
    return_type = "void"
    is_async = False
    is_exported = False

    for child in func_node.get("children", []):
        node_type = child.get("type", "")

        if node_type == "identifier":
            func_name = child.get("text", "")

        elif node_type == "formal_parameters":
            params = _parse_ts_params_node(child)

        elif node_type == "type_annotation":
            for tc in child.get("children", []):
                if tc.get("type") in ("type_identifier", "predefined_type"):
                    return_type = tc.get("text", "")

        elif node_type == "async":
            is_async = True

        elif node_type == "export_statement":
            is_exported = True

    if not func_name:
        return None

    return {
        "name": func_name,
        "type": "function",
        "parameters": params,
        "return_type": return_type,
        "is_async": is_async,
        "is_exported": is_exported,
        "line": func_node.get("start_point", {}).get("row", 0) + 1,
    }


def _parse_ts_arrow_function_node(var_node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """解析 TypeScript 箭头函数节点."""
    func_name = ""
    params = []
    return_type = "inferred"
    is_async = False
    is_exported = False

    for child in var_node.get("children", []):
        node_type = child.get("type", "")

        if node_type == "identifier":
            func_name = child.get("text", "")

        elif node_type == "arrow_function":
            for afc in child.get("children", []):
                afc_type = afc.get("type", "")

                if afc_type == "formal_parameters":
                    params = _parse_ts_params_node(afc)
                elif afc_type == "async":
                    is_async = True

    if not func_name:
        return None

    return {
        "name": func_name,
        "type": "arrow_function",
        "parameters": params,
        "return_type": return_type,
        "is_async": is_async,
        "is_exported": is_exported,
        "line": var_node.get("start_point", {}).get("row", 0) + 1,
    }


def _parse_ts_params_node(params_node: Dict[str, Any]) -> List[Dict[str, str]]:
    """解析 TypeScript 参数节点."""
    params = []

    for child in params_node.get("children", []):
        if child.get("type") == "required_parameter":
            param_name = ""
            param_type = "any"

            for pc in child.get("children", []):
                pc_type = pc.get("type", "")

                if pc_type == "identifier":
                    param_name = pc.get("text", "")
                elif pc_type == "type_annotation":
                    for tc in pc.get("children", []):
                        if tc.get("type") in ("type_identifier", "predefined_type"):
                            param_type = tc.get("text", "")

            if param_name:
                params.append({"name": param_name, "type": param_type})

    return params


def _extract_ts_imports_regex(ts_content: str) -> List[Dict[str, str]]:
    """使用正则表达式提取 TypeScript 导入."""
    imports = re.findall(r"import\s+{([^}]+)}\s+from\s+['\"]([^'\"]+)['\"]", ts_content)
    default_imports = re.findall(r"import\s+(\w+)\s+from\s+['\"]([^'\"]+)['\"]", ts_content)

    all_imports = []
    for names, source in imports:
        for name in names.split(","):
            all_imports.append({
                "name": name.strip(),
                "source": source,
                "type": "named"
            })
    for name, source in default_imports:
        all_imports.append({
            "name": name,
            "source": source,
            "type": "default"
        })

    return all_imports


def _extract_ts_functions_regex(ts_content: str) -> List[Dict[str, Any]]:
    """使用正则表达式提取 TypeScript 函数."""
    functions = []

    func_pattern = r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)(?:\s*:\s*(\w+))?"
    for match in re.finditer(func_pattern, ts_content):
        func_name = match.group(1)
        params = match.group(2)
        return_type = match.group(3) or "void"

        start_pos = match.start()
        line_num = ts_content[:start_pos].count("\n") + 1

        functions.append({
            "name": func_name,
            "type": "function",
            "parameters": parse_ts_params(params),
            "return_type": return_type,
            "is_async": "async" in match.group(0),
            "is_exported": "export" in match.group(0),
            "line": line_num,
        })

    arrow_pattern = r"(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)(?:\s*:\s*[^=]+)?\s*=>"
    for match in re.finditer(arrow_pattern, ts_content):
        func_name = match.group(1)
        params = match.group(2)

        start_pos = match.start()
        line_num = ts_content[:start_pos].count("\n") + 1

        functions.append({
            "name": func_name,
            "type": "arrow_function",
            "parameters": parse_ts_params(params),
            "return_type": "inferred",
            "is_async": "async" in match.group(0),
            "is_exported": "export" in match.group(0),
            "line": line_num,
        })

    method_pattern = r"(?:async\s+)?(\w+)\s*\(([^)]*)\)(?:\s*:\s*(\w+))?\s*{"
    for match in re.finditer(method_pattern, ts_content):
        method_name = match.group(1)
        if method_name in ["if", "while", "for", "switch", "catch"]:
            continue

        params = match.group(2)
        return_type = match.group(3) or "void"

        start_pos = match.start()
        line_num = ts_content[:start_pos].count("\n") + 1

        functions.append({
            "name": method_name,
            "type": "method",
            "parameters": parse_ts_params(params),
            "return_type": return_type,
            "is_async": "async" in match.group(0),
            "is_exported": False,
            "line": line_num,
        })

    return functions


def _extract_vue_component_info(ts_content: str) -> Dict[str, Any]:
    """提取 Vue 组件信息."""
    component_info = {}

    props_match = re.search(r"props\s*:\s*{([^}]+)}", ts_content, re.DOTALL)
    if props_match:
        component_info["has_props"] = True

    emits_match = re.search(r"emits\s*:\s*\[([^\]]+)\]", ts_content)
    if emits_match:
        component_info["has_emits"] = True

    component_info["has_setup"] = "setup" in ts_content
    component_info["has_data"] = "data()" in ts_content or "data:" in ts_content

    return component_info


def parse_ts_params(params_str: str) -> List[Dict[str, str]]:
    """解析 TypeScript 参数.

    Args:
        params_str: 参数字符串

    Returns:
        List[Dict]: 参数列表
    """
    params = []
    if not params_str.strip():
        return params

    # 简单解析，处理解构和默认值
    for param in params_str.split(","):
        param = param.strip()
        if not param:
            continue

        # 移除默认值
        if "=" in param:
            param = param.split("=")[0].strip()

        # 处理类型注解
        if ":" in param:
            parts = param.split(":")
            name = parts[0].strip()
            type_str = parts[1].strip()

            # 处理解构
            if name.startswith("{"):
                name = "options"

            params.append({
                "name": name,
                "type": type_str,
            })
        else:
            params.append({
                "name": param,
                "type": "any",
            })

    return params


def extract_dependencies(file_analysis: Dict[str, Any]) -> List[str]:
    """提取文件依赖.

    Args:
        file_analysis: 文件分析结果

    Returns:
        List[str]: 依赖列表
    """
    deps = []

    if file_analysis["language"] == "java":
        deps = file_analysis.get("imports", [])
    elif file_analysis["language"] in ["typescript", "vue"]:
        imports = file_analysis.get("imports", [])
        deps = [imp["source"] for imp in imports]

    return deps


def find_testable_methods(file_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """查找可测试的方法.

    Args:
        file_analysis: 文件分析结果

    Returns:
        List[Dict]: 可测试方法列表
    """
    if file_analysis["language"] == "java":
        methods = file_analysis.get("methods", [])
        return [m for m in methods if m.get("is_public", True)]

    elif file_analysis["language"] in ["typescript", "vue"]:
        functions = file_analysis.get("functions", [])
        return [f for f in functions if f.get("is_exported", False) or f["type"] == "function"]

    return []
