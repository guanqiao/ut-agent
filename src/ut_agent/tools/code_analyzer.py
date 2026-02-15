"""代码分析模块."""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


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


def analyze_java_file(file_path: str) -> Dict[str, Any]:
    """分析 Java 文件.

    Args:
        file_path: Java 文件路径

    Returns:
        Dict: 分析结果
    """
    path = Path(file_path)
    content = path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # 提取包名
    package_match = re.search(r"package\s+([\w.]+);", content)
    package = package_match.group(1) if package_match else ""

    # 提取导入
    imports = re.findall(r"import\s+([\w.*]+);", content)

    # 提取类定义
    class_pattern = r"(public\s+)?(abstract\s+)?(final\s+)?class\s+(\w+)"
    class_match = re.search(class_pattern, content)
    class_name = class_match.group(4) if class_match else path.stem

    # 提取类注解
    class_annotations = re.findall(r"@(\w+)(?:\([^)]*\))?\s*(?=class|public\s+class)", content)

    # 提取方法
    methods = []
    method_pattern = r"(public|private|protected)\s+(static\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*\(([^)]*)\)"

    for match in re.finditer(method_pattern, content):
        access = match.group(1)
        is_static = bool(match.group(2))
        return_type = match.group(3)
        method_name = match.group(4)
        params_str = match.group(5)

        # 解析参数
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

        # 计算行号
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

    # 提取字段
    fields = []
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


def analyze_ts_file(file_path: str) -> Dict[str, Any]:
    """分析 TypeScript/Vue 文件.

    Args:
        file_path: 文件路径

    Returns:
        Dict: 分析结果
    """
    path = Path(file_path)
    content = path.read_text(encoding="utf-8")
    lines = content.split("\n")

    is_vue = path.suffix == ".vue"

    if is_vue:
        # 提取 script 部分
        script_match = re.search(r"<script[^>]*>(.*?)</script>", content, re.DOTALL)
        if script_match:
            ts_content = script_match.group(1)
        else:
            ts_content = content
    else:
        ts_content = content

    # 提取导入
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

    # 提取函数/方法
    functions = []

    # 函数声明: function name(params)
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

    # 箭头函数: const name = (params) =>
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

    # 类方法
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

    # 提取 Vue 组件信息
    component_info = {}
    if is_vue:
        # 提取 props
        props_match = re.search(r"props\s*:\s*{([^}]+)}", ts_content, re.DOTALL)
        if props_match:
            component_info["has_props"] = True

        # 提取 emits
        emits_match = re.search(r"emits\s*:\s*\[([^\]]+)\]", ts_content)
        if emits_match:
            component_info["has_emits"] = True

        # 提取 setup 或 data
        component_info["has_setup"] = "setup" in ts_content
        component_info["has_data"] = "data()" in ts_content or "data:" in ts_content

    return {
        "file_path": file_path,
        "file_name": path.name,
        "language": "typescript" if not is_vue else "vue",
        "is_vue": is_vue,
        "imports": all_imports,
        "functions": functions,
        "component_info": component_info,
        "content": content,
        "script_content": ts_content if is_vue else content,
        "line_count": len(lines),
    }


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
