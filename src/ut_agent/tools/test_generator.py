"""测试生成模块."""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from langchain_core.language_models.chat_models import BaseChatModel
from ut_agent.graph.state import GeneratedTestFile, CoverageGap
from ut_agent.tools.test_data_generator import (
    BoundaryValueGenerator,
    format_test_data_for_prompt,
)
from ut_agent.tools.test_analyzer import (
    TestAnalyzer,
    TestCoverageInfo,
    TestGap,
    IncrementalTestPlan,
    format_existing_tests_for_prompt,
    format_test_gaps_for_prompt,
    format_incremental_plan_for_prompt,
)


def generate_java_test(
    file_analysis: Dict[str, Any],
    llm: BaseChatModel,
    gap_info: Optional[CoverageGap] = None,
    plan: Optional[str] = None,
    use_boundary_values: bool = True,
) -> GeneratedTestFile:
    """生成 Java JUnit 5 测试.

    Args:
        file_analysis: 文件分析结果
        llm: LLM 模型
        gap_info: 覆盖率缺口信息 (用于补充测试)
        plan: 改进计划
        use_boundary_values: 是否使用边界值生成器

    Returns:
        GeneratedTestFile: 生成的测试文件
    """
    class_name = file_analysis["class_name"]
    package = file_analysis["package"]
    methods = file_analysis.get("methods", [])
    fields = file_analysis.get("fields", [])

    file_path = file_analysis["file_path"]
    path = Path(file_path)

    project_path = path.parent
    while project_path.name not in ["java", "src"] and project_path.parent != project_path:
        project_path = project_path.parent

    if project_path.name == "java":
        test_dir = project_path.parent / "test" / "java"
    else:
        test_dir = path.parent

    relative_path = path.relative_to(project_path) if path.is_relative_to(project_path) else path
    test_file_path = test_dir / relative_path.parent / f"{class_name}Test.java"

    boundary_data_section = ""
    if use_boundary_values:
        data_generator = BoundaryValueGenerator(language="java")
        boundary_data_sections = []
        for method in methods:
            if method.get("is_public", True):
                test_data = data_generator.generate_test_data_for_method(method)
                if test_data:
                    formatted = format_test_data_for_prompt(test_data, language="java")
                    boundary_data_sections.append(f"\n方法 {method['name']}:\n{formatted}")

        if boundary_data_sections:
            boundary_data_section = "\n\n边界值测试数据建议:\n" + "\n".join(boundary_data_sections[:5])

    if gap_info and plan:
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
{boundary_data_section}

请生成 JUnit 5 测试代码，只包含针对该缺口的测试方法。
要求:
1. 使用 JUnit 5 (org.junit.jupiter.api)
2. 使用 Mockito 进行依赖模拟
3. 包含 Arrange-Act-Assert 结构
4. 添加清晰的注释说明测试目的
5. 只返回测试方法代码，不要包含类声明和导入
6. 优先使用上述边界值建议中的测试数据
"""
    else:
        prompt = f"""作为 Java 单元测试专家，请为以下类生成完整的 JUnit 5 测试类。

目标类: {class_name}
包名: {package}

类字段:
{format_java_fields(fields)}

类方法:
{format_java_methods(methods)}
{boundary_data_section}

请生成完整的 JUnit 5 测试类代码。
要求:
1. 使用 JUnit 5 (org.junit.jupiter.api.Test, org.junit.jupiter.api.BeforeEach 等)
2. 使用 Mockito (org.mockito.Mockito, org.mockito.InjectMocks, org.mockito.Mock)
3. 为每个公共方法生成至少 2 个测试用例 (正常场景 + 异常场景)
4. 包含边界条件测试，优先使用上述边界值建议
5. 使用 given-when-then 命名风格
6. 添加 @DisplayName 注解说明测试目的
7. 包含必要的导入语句
8. 测试类命名为 {class_name}Test
"""

    response = llm.invoke(prompt)
    test_code = str(response.content)

    test_code = clean_code_blocks(test_code)

    if gap_info and plan:
        test_code = wrap_additional_test(test_code, class_name, package, file_analysis)

    return GeneratedTestFile(
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
    use_boundary_values: bool = True,
) -> GeneratedTestFile:
    """生成前端测试 (Jest/Vitest).

    Args:
        file_analysis: 文件分析结果
        project_type: 项目类型 (vue/react/typescript)
        llm: LLM 模型
        gap_info: 覆盖率缺口信息
        plan: 改进计划
        use_boundary_values: 是否使用边界值生成器

    Returns:
        TestFile: 生成的测试文件
    """
    file_path = file_analysis["file_path"]
    path = Path(file_path)
    file_name = path.stem
    functions = file_analysis.get("functions", [])
    is_vue = file_analysis.get("is_vue", False)
    component_info = file_analysis.get("component_info", {})

    test_file_path = path.parent / f"{file_name}.spec.ts"

    boundary_data_section = ""
    if use_boundary_values:
        data_generator = BoundaryValueGenerator(language="typescript")
        boundary_data_sections = []
        for func in functions:
            if func.get("is_exported", False) or func.get("type") == "function":
                test_data = data_generator.generate_test_data_for_method(func)
                if test_data:
                    formatted = format_test_data_for_prompt(test_data, language="typescript")
                    boundary_data_sections.append(f"\n函数 {func['name']}:\n{formatted}")

        if boundary_data_sections:
            boundary_data_section = "\n\n边界值测试数据建议:\n" + "\n".join(boundary_data_sections[:5])

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
{boundary_data_section}

请生成针对该缺口的测试代码，只返回测试代码块。
要求:
1. 使用 Vitest (describe, it, expect, vi)
2. 包含 Arrange-Act-Assert 结构
3. 添加清晰的注释
4. 优先使用上述边界值建议中的测试数据
"""
    else:
        if is_vue:
            prompt = f"""作为 Vue 单元测试专家，请为以下 Vue 组件生成完整的测试文件。

组件名: {file_name}

组件功能:
{format_vue_component_info(component_info)}

导出函数:
{format_ts_functions(functions)}
{boundary_data_section}

请生成完整的 Vitest + Vue Test Utils 测试代码。
要求:
1. 使用 Vitest (describe, it, expect, vi)
2. 使用 @vue/test-utils (mount, shallowMount)
3. 测试组件渲染、props、事件、方法
4. 使用 vi.fn() 模拟依赖
5. 包含正常场景和异常场景
6. 添加清晰的 describe 和 it 描述
7. 测试文件命名为 {file_name}.spec.ts
8. 优先使用上述边界值建议中的测试数据
"""
        else:
            prompt = f"""作为 TypeScript 单元测试专家，请为以下代码生成完整的测试文件。

文件名: {file_name}
项目类型: {project_type}

导出函数:
{format_ts_functions(functions)}
{boundary_data_section}

请生成完整的 Vitest 测试代码。
要求:
1. 使用 Vitest (describe, it, expect, vi)
2. 为每个导出函数生成测试
3. 包含正常输入、边界条件、异常输入测试
4. 使用 vi.fn() 模拟依赖
5. 添加清晰的 describe 和 it 描述
6. 测试文件命名为 {file_name}.spec.ts
7. 优先使用上述边界值建议中的测试数据
"""

    response = llm.invoke(prompt)
    test_code = str(response.content)

    test_code = clean_code_blocks(test_code)

    return GeneratedTestFile(
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
        signature = m.get("signature", "void method()")
        return_type = m.get("return_type", "void")
        result.append(f"- {signature} (返回: {return_type})")
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
        params = ", ".join([f"{p.get('name', 'param')}: {p.get('type', 'any')}" for p in f.get("parameters", [])])
        export_mark = "export " if f.get("is_exported") else ""
        async_mark = "async " if f.get("is_async") else ""
        name = f.get("name", "anonymous")
        return_type = f.get("return_type", "void")
        result.append(
            f"- {export_mark}{async_mark}{name}({params}): {return_type}"
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


def generate_incremental_java_test(
    file_analysis: Dict[str, Any],
    llm: BaseChatModel,
    existing_test_path: Optional[str] = None,
    added_methods: Optional[List[str]] = None,
    modified_methods: Optional[List[str]] = None,
    use_boundary_values: bool = True,
) -> GeneratedTestFile:
    """增量生成 Java 测试 - 只为新增/修改的方法生成测试.

    Args:
        file_analysis: 文件分析结果
        llm: LLM 模型
        existing_test_path: 已有测试文件路径
        added_methods: 新增方法列表
        modified_methods: 修改的方法列表
        use_boundary_values: 是否使用边界值生成器

    Returns:
        GeneratedTestFile: 生成的测试文件
    """
    class_name = file_analysis["class_name"]
    package = file_analysis["package"]
    all_methods = file_analysis.get("methods", [])
    fields = file_analysis.get("fields", [])

    file_path = file_analysis["file_path"]
    path = Path(file_path)

    project_path = path.parent
    while project_path.name not in ["java", "src"] and project_path.parent != project_path:
        project_path = project_path.parent

    if project_path.name == "java":
        test_dir = project_path.parent / "test" / "java"
    else:
        test_dir = path.parent

    relative_path = path.relative_to(project_path) if path.is_relative_to(project_path) else path
    test_file_path = test_dir / relative_path.parent / f"{class_name}Test.java"

    added_methods = added_methods or []
    modified_methods = modified_methods or []
    methods_to_test = list(set(added_methods + modified_methods))

    if not methods_to_test:
        all_method_names = [m.get("name") for m in all_methods if m.get("is_public", True)]
        methods_to_test = all_method_names

    target_methods = [
        m for m in all_methods 
        if m.get("name") in methods_to_test and m.get("is_public", True)
    ]

    existing_test_info = ""
    test_patterns = {}
    incremental_plan = None
    reuse_hints = ""
    
    if existing_test_path:
        try:
            analyzer = TestAnalyzer("java")
            source_method_names = [m.get("name") for m in all_methods]
            coverage_info = analyzer.analyze_existing_tests(existing_test_path, source_method_names)
            existing_test_info = format_existing_tests_for_prompt(coverage_info)
            
            incremental_plan = analyzer.create_incremental_plan(
                coverage_info, methods_to_test
            )
            
            with open(existing_test_path, "r", encoding="utf-8") as f:
                existing_content = f.read()
            test_patterns = analyzer.extract_test_patterns(existing_content)
            
            if incremental_plan.reuse_candidates:
                reuse_hints = "\n\n可复用的测试资源:\n"
                for key, values in incremental_plan.reuse_candidates.items():
                    reuse_hints += f"- {key}: {', '.join(values[:2])}\n"
            
            for method in target_methods:
                similar_tests = analyzer.suggest_test_reuse(
                    method,
                    analyzer._extract_test_methods(existing_content) if existing_content else []
                )
                if similar_tests:
                    method["similar_tests"] = [t[0].name for t in similar_tests]
                    
        except Exception:
            existing_test_info = "无法读取已有测试文件"

    boundary_data_section = ""
    if use_boundary_values:
        data_generator = BoundaryValueGenerator(language="java")
        boundary_data_sections = []
        for method in target_methods:
            test_data = data_generator.generate_test_data_for_method(method)
            if test_data:
                formatted = format_test_data_for_prompt(test_data, language="java")
                boundary_data_sections.append(f"\n方法 {method['name']}:\n{formatted}")

        if boundary_data_sections:
            boundary_data_section = "\n\n边界值测试数据建议:\n" + "\n".join(boundary_data_sections[:5])

    naming_hint = ""
    if test_patterns.get("naming_convention") == "given_when_then":
        naming_hint = "使用 given_when_then 命名风格 (如 givenX_whenY_thenZ)"
    elif test_patterns.get("naming_convention") == "should_style":
        naming_hint = "使用 should 命名风格 (如 shouldDoSomething)"
    else:
        naming_hint = "使用 test 前缀命名风格 (如 testMethodName)"

    similar_tests_hint = ""
    for method in target_methods:
        if method.get("similar_tests"):
            similar_tests_hint += f"\n- {method['name']} 可参考已有测试: {', '.join(method['similar_tests'][:2])}"

    prompt = f"""作为 Java 单元测试专家，请为以下类增量生成测试方法。

目标类: {class_name}
包名: {package}

需要生成测试的方法:
{format_java_methods(target_methods)}

已有测试情况:
{existing_test_info}
{reuse_hints}

类字段:
{format_java_fields(fields)}
{boundary_data_section}

命名风格提示: {naming_hint}
{similar_tests_hint}

请只生成针对上述方法的测试方法代码，不要包含类声明和导入语句。
要求:
1. 使用 JUnit 5 (@Test, @DisplayName, @BeforeEach)
2. 使用 Mockito (@Mock, @InjectMocks, when(), verify())
3. 为每个方法生成至少 2 个测试用例 (正常场景 + 异常场景)
4. 包含边界条件测试
5. 添加 @DisplayName 注解说明测试目的
6. 只返回测试方法代码，不要包含类声明和导入
7. 保持与已有测试风格一致
8. 优先使用上述边界值建议中的测试数据
9. 参考可复用的 Mock 配置和断言模式
"""

    response = llm.invoke(prompt)
    test_code = str(response.content)
    test_code = clean_code_blocks(test_code)

    return GeneratedTestFile(
        source_file=file_path,
        test_file_path=str(test_file_path),
        test_code=test_code,
        language="java",
    )


def generate_incremental_frontend_test(
    file_analysis: Dict[str, Any],
    project_type: str,
    llm: BaseChatModel,
    existing_test_path: Optional[str] = None,
    added_functions: Optional[List[str]] = None,
    modified_functions: Optional[List[str]] = None,
    use_boundary_values: bool = True,
) -> GeneratedTestFile:
    """增量生成前端测试 - 只为新增/修改的函数生成测试.

    Args:
        file_analysis: 文件分析结果
        project_type: 项目类型 (vue/react/typescript)
        llm: LLM 模型
        existing_test_path: 已有测试文件路径
        added_functions: 新增函数列表
        modified_functions: 修改的函数列表
        use_boundary_values: 是否使用边界值生成器

    Returns:
        GeneratedTestFile: 生成的测试文件
    """
    file_path = file_analysis["file_path"]
    path = Path(file_path)
    file_name = path.stem
    all_functions = file_analysis.get("functions", [])
    is_vue = file_analysis.get("is_vue", False)
    component_info = file_analysis.get("component_info", {})

    test_file_path = path.parent / f"{file_name}.spec.ts"

    added_functions = added_functions or []
    modified_functions = modified_functions or []
    functions_to_test = list(set(added_functions + modified_functions))

    if not functions_to_test:
        all_func_names = [
            f.get("name") for f in all_functions 
            if f.get("is_exported", False) or f.get("type") == "function"
        ]
        functions_to_test = all_func_names

    target_functions = [
        f for f in all_functions 
        if f.get("name") in functions_to_test
    ]

    existing_test_info = ""
    test_patterns = {}
    incremental_plan = None
    reuse_hints = ""
    
    if existing_test_path:
        try:
            analyzer = TestAnalyzer(project_type)
            source_func_names = [f.get("name") for f in all_functions]
            coverage_info = analyzer.analyze_existing_tests(existing_test_path, source_func_names)
            existing_test_info = format_existing_tests_for_prompt(coverage_info)
            
            incremental_plan = analyzer.create_incremental_plan(
                coverage_info, functions_to_test
            )
            
            with open(existing_test_path, "r", encoding="utf-8") as f:
                existing_content = f.read()
            test_patterns = analyzer.extract_test_patterns(existing_content)
            
            if incremental_plan.reuse_candidates:
                reuse_hints = "\n\n可复用的测试资源:\n"
                for key, values in incremental_plan.reuse_candidates.items():
                    reuse_hints += f"- {key}: {', '.join(values[:2])}\n"
            
            for func in target_functions:
                similar_tests = analyzer.suggest_test_reuse(
                    func,
                    analyzer._extract_test_methods(existing_content) if existing_content else []
                )
                if similar_tests:
                    func["similar_tests"] = [t[0].name for t in similar_tests]
                    
        except Exception:
            existing_test_info = "无法读取已有测试文件"

    boundary_data_section = ""
    if use_boundary_values:
        data_generator = BoundaryValueGenerator(language="typescript")
        boundary_data_sections = []
        for func in target_functions:
            test_data = data_generator.generate_test_data_for_method(func)
            if test_data:
                formatted = format_test_data_for_prompt(test_data, language="typescript")
                boundary_data_sections.append(f"\n函数 {func['name']}:\n{formatted}")

        if boundary_data_sections:
            boundary_data_section = "\n\n边界值测试数据建议:\n" + "\n".join(boundary_data_sections[:5])

    naming_hint = ""
    if test_patterns.get("naming_convention") == "should_style":
        naming_hint = "使用 should 风格 (如 'should return correct value')"
    else:
        naming_hint = "使用 describe/it 风格"

    similar_tests_hint = ""
    for func in target_functions:
        if func.get("similar_tests"):
            similar_tests_hint += f"\n- {func['name']} 可参考已有测试: {', '.join(func['similar_tests'][:2])}"

    if is_vue:
        prompt = f"""作为 Vue 单元测试专家，请为以下组件增量生成测试。

组件名: {file_name}

需要生成测试的函数:
{format_ts_functions(target_functions)}

已有测试情况:
{existing_test_info}
{reuse_hints}

组件功能:
{format_vue_component_info(component_info)}
{boundary_data_section}

命名风格提示: {naming_hint}
{similar_tests_hint}

请只生成针对上述函数的测试代码，不要包含外层 describe 块。
要求:
1. 使用 Vitest (it, expect, vi)
2. 使用 @vue/test-utils (mount, shallowMount)
3. 包含正常场景和异常场景
4. 使用 vi.fn() 模拟依赖
5. 添加清晰的 it 描述
6. 只返回测试代码块
7. 保持与已有测试风格一致
8. 参考可复用的 Mock 配置和断言模式
"""
    else:
        prompt = f"""作为 TypeScript 单元测试专家，请为以下代码增量生成测试。

文件名: {file_name}
项目类型: {project_type}

需要生成测试的函数:
{format_ts_functions(target_functions)}

已有测试情况:
{existing_test_info}
{reuse_hints}
{boundary_data_section}

命名风格提示: {naming_hint}
{similar_tests_hint}

请只生成针对上述函数的测试代码，不要包含外层 describe 块。
要求:
1. 使用 Vitest (it, expect, vi)
2. 包含正常输入、边界条件、异常输入测试
3. 使用 vi.fn() 模拟依赖
4. 添加清晰的 it 描述
5. 只返回测试代码块
6. 保持与已有测试风格一致
7. 优先使用上述边界值建议中的测试数据
8. 参考可复用的 Mock 配置和断言模式
"""

    response = llm.invoke(prompt)
    test_code = str(response.content)
    test_code = clean_code_blocks(test_code)

    return GeneratedTestFile(
        source_file=file_path,
        test_file_path=str(test_file_path),
        test_code=test_code,
        language="typescript",
    )
