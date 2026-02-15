"""测试生成模块."""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from ut_agent.graph.state import TestFile, CoverageGap


def generate_java_test(
    file_analysis: Dict[str, Any],
    llm: BaseChatModel,
    gap_info: Optional[CoverageGap] = None,
    plan: Optional[str] = None,
) -> TestFile:
    """生成 Java JUnit 5 测试.

    Args:
        file_analysis: 文件分析结果
        llm: LLM 模型
        gap_info: 覆盖率缺口信息 (用于补充测试)
        plan: 改进计划

    Returns:
        TestFile: 生成的测试文件
    """
    class_name = file_analysis["class_name"]
    package = file_analysis["package"]
    methods = file_analysis.get("methods", [])
    fields = file_analysis.get("fields", [])

    # 构建测试类路径
    file_path = file_analysis["file_path"]
    path = Path(file_path)

    # 推断测试目录
    project_path = path.parent
    while project_path.name not in ["java", "src"] and project_path.parent != project_path:
        project_path = project_path.parent

    if project_path.name == "java":
        test_dir = project_path.parent / "test" / "java"
    else:
        test_dir = path.parent

    relative_path = path.relative_to(project_path) if path.is_relative_to(project_path) else path
    test_file_path = test_dir / relative_path.parent / f"{class_name}Test.java"

    # 构建 Prompt
    if gap_info and plan:
        # 补充测试模式
        prompt = f"""作为 Java 单元测试专家，请为以下类生成补充测试用例，针对特定的覆盖率缺口。

目标类: {class_name}
包名: {package}

需要覆盖的代码:
文件: {gap_info.file_path}
行号: {gap_info.line_number}
代码: {gap_info.line_content}
缺口类型: {gap_info.gap_type}

改进计划:
{plan}

已有方法:
{format_java_methods(methods)}

请生成 JUnit 5 测试代码，只包含针对该缺口的测试方法。
要求:
1. 使用 JUnit 5 (org.junit.jupiter.api)
2. 使用 Mockito 进行依赖模拟
3. 包含 Arrange-Act-Assert 结构
4. 添加清晰的注释说明测试目的
5. 只返回测试方法代码，不要包含类声明和导入
"""
    else:
        # 完整测试模式
        prompt = f"""作为 Java 单元测试专家，请为以下类生成完整的 JUnit 5 测试类。

目标类: {class_name}
包名: {package}

类字段:
{format_java_fields(fields)}

类方法:
{format_java_methods(methods)}

请生成完整的 JUnit 5 测试类代码。
要求:
1. 使用 JUnit 5 (org.junit.jupiter.api.Test, org.junit.jupiter.api.BeforeEach 等)
2. 使用 Mockito (org.mockito.Mockito, org.mockito.InjectMocks, org.mockito.Mock)
3. 为每个公共方法生成至少 2 个测试用例 (正常场景 + 异常场景)
4. 包含边界条件测试
5. 使用 given-when-then 命名风格
6. 添加 @DisplayName 注解说明测试目的
7. 包含必要的导入语句
8. 测试类命名为 {class_name}Test
"""

    # 调用 LLM
    response = llm.invoke(prompt)
    test_code = str(response.content)

    # 清理代码块标记
    test_code = clean_code_blocks(test_code)

    # 确保是完整类
    if gap_info and plan:
        # 补充测试需要包装成完整类
        test_code = wrap_additional_test(test_code, class_name, package, file_analysis)

    return TestFile(
        source_file=file_path,
        test_file_path=str(test_file_path),
        test_code=test_code,
        language="java",
    )


def generate_frontend_test(
    file_analysis: Dict[str, Any],
    project_type: str,
    llm: BaseChatModel,
    gap_info: Optional[CoverageGap] = None,
    plan: Optional[str] = None,
) -> TestFile:
    """生成前端测试 (Jest/Vitest).

    Args:
        file_analysis: 文件分析结果
        project_type: 项目类型 (vue/react/typescript)
        llm: LLM 模型
        gap_info: 覆盖率缺口信息
        plan: 改进计划

    Returns:
        TestFile: 生成的测试文件
    """
    file_path = file_analysis["file_path"]
    path = Path(file_path)
    file_name = path.stem
    functions = file_analysis.get("functions", [])
    is_vue = file_analysis.get("is_vue", False)
    component_info = file_analysis.get("component_info", {})

    # 测试文件路径
    test_file_path = path.parent / f"{file_name}.spec.ts"

    # 构建 Prompt
    if gap_info and plan:
        prompt = f"""作为前端单元测试专家，请为以下代码生成补充测试用例。

目标文件: {file_name}
项目类型: {project_type}

需要覆盖的代码:
文件: {gap_info.file_path}
行号: {gap_info.line_number}
代码: {gap_info.line_content}
缺口类型: {gap_info.gap_type}

改进计划:
{plan}

请生成针对该缺口的测试代码，只返回测试代码块。
要求:
1. 使用 Vitest (describe, it, expect, vi)
2. 包含 Arrange-Act-Assert 结构
3. 添加清晰的注释
"""
    else:
        if is_vue:
            prompt = f"""作为 Vue 单元测试专家，请为以下 Vue 组件生成完整的测试文件。

组件名: {file_name}

组件功能:
{format_vue_component_info(component_info)}

导出函数:
{format_ts_functions(functions)}

请生成完整的 Vitest + Vue Test Utils 测试代码。
要求:
1. 使用 Vitest (describe, it, expect, vi)
2. 使用 @vue/test-utils (mount, shallowMount)
3. 测试组件渲染、props、事件、方法
4. 使用 vi.fn() 模拟依赖
5. 包含正常场景和异常场景
6. 添加清晰的 describe 和 it 描述
7. 测试文件命名为 {file_name}.spec.ts
"""
        else:
            prompt = f"""作为 TypeScript 单元测试专家，请为以下代码生成完整的测试文件。

文件名: {file_name}
项目类型: {project_type}

导出函数:
{format_ts_functions(functions)}

请生成完整的 Vitest 测试代码。
要求:
1. 使用 Vitest (describe, it, expect, vi)
2. 为每个导出函数生成测试
3. 包含正常输入、边界条件、异常输入测试
4. 使用 vi.fn() 模拟依赖
5. 添加清晰的 describe 和 it 描述
6. 测试文件命名为 {file_name}.spec.ts
"""

    # 调用 LLM
    response = llm.invoke(prompt)
    test_code = str(response.content)

    # 清理代码块标记
    test_code = clean_code_blocks(test_code)

    return TestFile(
        source_file=file_path,
        test_file_path=str(test_file_path),
        test_code=test_code,
        language="typescript",
    )


def format_java_methods(methods: list) -> str:
    """格式化 Java 方法信息."""
    if not methods:
        return "无"

    result = []
    for m in methods:
        params = ", ".join([f"{p['type']} {p['name']}" for p in m.get("parameters", [])])
        result.append(f"- {m['signature']} (返回: {m['return_type']})")
    return "\n".join(result)


def format_java_fields(fields: list) -> str:
    """格式化 Java 字段信息."""
    if not fields:
        return "无"

    result = []
    for f in fields:
        result.append(f"- {f['access']} {f['type']} {f['name']}")
    return "\n".join(result)


def format_ts_functions(functions: list) -> str:
    """格式化 TypeScript 函数信息."""
    if not functions:
        return "无"

    result = []
    for f in functions:
        params = ", ".join([f"{p['name']}: {p['type']}" for p in f.get("parameters", [])])
        export_mark = "export " if f.get("is_exported") else ""
        async_mark = "async " if f.get("is_async") else ""
        result.append(
            f"- {export_mark}{async_mark}{f['name']}({params}): {f['return_type']}"
        )
    return "\n".join(result)


def format_vue_component_info(component_info: Dict[str, Any]) -> str:
    """格式化 Vue 组件信息."""
    result = []
    if component_info.get("has_props"):
        result.append("- 有 Props 定义")
    if component_info.get("has_emits"):
        result.append("- 有 Emits 定义")
    if component_info.get("has_setup"):
        result.append("- 使用 Composition API (setup)")
    if component_info.get("has_data"):
        result.append("- 使用 Options API (data)")

    return "\n".join(result) if result else "- 基础组件"


def clean_code_blocks(code: str) -> str:
    """清理代码块标记."""
    # 移除 ```java, ```typescript, ``` 等标记
    code = code.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        code = "\n".join(lines)
    return code.strip()


def wrap_additional_test(
    test_code: str, class_name: str, package: str, file_analysis: Dict[str, Any]
) -> str:
    """将补充测试包装成完整类."""
    imports = file_analysis.get("imports", [])

    import_statements = "\n".join([
        f"import {imp};" for imp in imports[:5]
    ])

    return f"""package {package};

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.BeforeEach;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
{import_statements}

public class {class_name}Test {{

    @InjectMocks
    private {class_name} target;

    @BeforeEach
    void setUp() {{
        MockitoAnnotations.openMocks(this);
    }}

{test_code}
}}
"""
