"""测试生成器模块 V2 - 使用 AsyncLLMCaller 和 PromptTemplateLoader."""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from ut_agent.graph.state import GeneratedTestFile, CoverageGap
from ut_agent.utils.async_llm import AsyncLLMCaller, LLMCallResult, LLMCallStatus
from ut_agent.prompts.loader import PromptTemplateLoader
from ut_agent.utils import get_logger

logger = get_logger("test_generator_v2")


class TestGenerationStatus(Enum):
    """测试生成状态枚举."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


@dataclass
class TestGeneratorConfig:
    """测试生成器配置."""

    use_boundary_values: bool = True
    max_test_methods: Optional[int] = None
    include_comments: bool = True
    template_name_java: str = "java_test_full"
    template_name_java_gap: str = "java_test_gap"
    template_name_ts: str = "ts_test_full"
    template_name_vue: str = "vue_test_full"


@dataclass
class TestGenerationResult:
    """测试生成结果."""

    status: TestGenerationStatus
    test_file: Optional[GeneratedTestFile] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duration_ms: int = 0

    @property
    def success(self) -> bool:
        """是否成功."""
        return self.status in [TestGenerationStatus.SUCCESS, TestGenerationStatus.SKIPPED]


class TestGenerator:
    """测试生成器 - 使用 AsyncLLMCaller 和 PromptTemplateLoader.

    功能:
    - 异步生成测试代码
    - 支持多种语言 (Java, TypeScript, Vue, React)
    - 支持覆盖率缺口补充测试
    - 批量生成支持
    """

    SUPPORTED_LANGUAGES = ["java", "typescript", "vue", "react"]

    def __init__(
        self,
        llm_caller: AsyncLLMCaller,
        template_loader: Optional[PromptTemplateLoader] = None,
        config: Optional[TestGeneratorConfig] = None,
    ):
        """初始化测试生成器.

        Args:
            llm_caller: 异步 LLM 调用器
            template_loader: Prompt 模板加载器
            config: 生成器配置
        """
        self._llm_caller = llm_caller
        self._template_loader = template_loader
        self._config = config or TestGeneratorConfig()

    async def generate_java_test(
        self,
        file_analysis: Dict[str, Any],
        gap_info: Optional[CoverageGap] = None,
        improvement_plan: Optional[str] = None,
    ) -> TestGenerationResult:
        """生成 Java JUnit 5 测试.

        Args:
            file_analysis: 文件分析结果
            gap_info: 覆盖率缺口信息
            improvement_plan: 改进计划

        Returns:
            TestGenerationResult: 生成结果
        """
        class_name = file_analysis.get("class_name", "Unknown")
        methods = file_analysis.get("methods", [])
        file_path = file_analysis.get("file_path", "")

        if not methods:
            return TestGenerationResult(
                status=TestGenerationStatus.SKIPPED,
                warnings=[f"No methods to test in {class_name}"],
            )

        test_file_path = self._get_java_test_path(file_analysis)

        prompt = await self._build_java_prompt(
            file_analysis=file_analysis,
            gap_info=gap_info,
            improvement_plan=improvement_plan,
        )

        result = await self._llm_caller.call(prompt)

        if result.status != LLMCallStatus.SUCCESS:
            return TestGenerationResult(
                status=TestGenerationStatus.FAILED,
                errors=result.errors,
                duration_ms=result.duration_ms,
            )

        test_code = self._clean_code_blocks(result.content)

        if gap_info:
            test_code = self._wrap_additional_test(test_code, file_analysis)

        return TestGenerationResult(
            status=TestGenerationStatus.SUCCESS,
            test_file=GeneratedTestFile(
                source_file=file_path,
                test_file_path=str(test_file_path),
                test_code=test_code,
                language="java",
            ),
            duration_ms=result.duration_ms,
        )

    async def generate_typescript_test(
        self,
        file_analysis: Dict[str, Any],
        project_type: str = "typescript",
        gap_info: Optional[CoverageGap] = None,
        improvement_plan: Optional[str] = None,
    ) -> TestGenerationResult:
        """生成 TypeScript/Vitest 测试.

        Args:
            file_analysis: 文件分析结果
            project_type: 项目类型
            gap_info: 覆盖率缺口信息
            improvement_plan: 改进计划

        Returns:
            TestGenerationResult: 生成结果
        """
        functions = file_analysis.get("functions", [])
        file_path = file_analysis.get("file_path", "")

        if not functions:
            return TestGenerationResult(
                status=TestGenerationStatus.SKIPPED,
                warnings=["No functions to test"],
            )

        test_file_path = self._get_typescript_test_path(file_analysis)

        prompt = await self._build_typescript_prompt(
            file_analysis=file_analysis,
            project_type=project_type,
            gap_info=gap_info,
            improvement_plan=improvement_plan,
        )

        result = await self._llm_caller.call(prompt)

        if result.status != LLMCallStatus.SUCCESS:
            return TestGenerationResult(
                status=TestGenerationStatus.FAILED,
                errors=result.errors,
                duration_ms=result.duration_ms,
            )

        test_code = self._clean_code_blocks(result.content)

        return TestGenerationResult(
            status=TestGenerationStatus.SUCCESS,
            test_file=GeneratedTestFile(
                source_file=file_path,
                test_file_path=str(test_file_path),
                test_code=test_code,
                language="typescript",
            ),
            duration_ms=result.duration_ms,
        )

    async def generate_frontend_test(
        self,
        file_analysis: Dict[str, Any],
        project_type: str,
        gap_info: Optional[CoverageGap] = None,
        improvement_plan: Optional[str] = None,
    ) -> TestGenerationResult:
        """生成前端测试 (Vue/React).

        Args:
            file_analysis: 文件分析结果
            project_type: 项目类型 (vue/react)
            gap_info: 覆盖率缺口信息
            improvement_plan: 改进计划

        Returns:
            TestGenerationResult: 生成结果
        """
        if project_type == "vue":
            return await self._generate_vue_test(
                file_analysis, gap_info, improvement_plan
            )
        elif project_type == "react":
            return await self._generate_react_test(
                file_analysis, gap_info, improvement_plan
            )
        else:
            return await self.generate_typescript_test(
                file_analysis, project_type, gap_info, improvement_plan
            )

    async def _generate_vue_test(
        self,
        file_analysis: Dict[str, Any],
        gap_info: Optional[CoverageGap] = None,
        improvement_plan: Optional[str] = None,
    ) -> TestGenerationResult:
        """生成 Vue 组件测试."""
        file_path = file_analysis.get("file_path", "")
        test_file_path = self._get_typescript_test_path(file_analysis)

        prompt = await self._build_vue_prompt(file_analysis, gap_info, improvement_plan)

        result = await self._llm_caller.call(prompt)

        if result.status != LLMCallStatus.SUCCESS:
            return TestGenerationResult(
                status=TestGenerationStatus.FAILED,
                errors=result.errors,
            )

        return TestGenerationResult(
            status=TestGenerationStatus.SUCCESS,
            test_file=GeneratedTestFile(
                source_file=file_path,
                test_file_path=str(test_file_path),
                test_code=self._clean_code_blocks(result.content),
                language="typescript",
            ),
        )

    async def _generate_react_test(
        self,
        file_analysis: Dict[str, Any],
        gap_info: Optional[CoverageGap] = None,
        improvement_plan: Optional[str] = None,
    ) -> TestGenerationResult:
        """生成 React 组件测试."""
        file_path = file_analysis.get("file_path", "")
        test_file_path = self._get_typescript_test_path(file_analysis)

        prompt = await self._build_react_prompt(file_analysis, gap_info, improvement_plan)

        result = await self._llm_caller.call(prompt)

        if result.status != LLMCallStatus.SUCCESS:
            return TestGenerationResult(
                status=TestGenerationStatus.FAILED,
                errors=result.errors,
            )

        return TestGenerationResult(
            status=TestGenerationStatus.SUCCESS,
            test_file=GeneratedTestFile(
                source_file=file_path,
                test_file_path=str(test_file_path),
                test_code=self._clean_code_blocks(result.content),
                language="typescript",
            ),
        )

    async def batch_generate(
        self,
        file_analyses: List[Dict[str, Any]],
        language: str,
        max_concurrent: int = 4,
    ) -> List[TestGenerationResult]:
        """批量生成测试.

        Args:
            file_analyses: 文件分析结果列表
            language: 语言类型
            max_concurrent: 最大并发数

        Returns:
            List[TestGenerationResult]: 生成结果列表
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def generate_with_limit(file_analysis: Dict[str, Any]) -> TestGenerationResult:
            async with semaphore:
                if language == "java":
                    return await self.generate_java_test(file_analysis)
                else:
                    return await self.generate_typescript_test(file_analysis, language)

        results = await asyncio.gather(
            *[generate_with_limit(fa) for fa in file_analyses],
            return_exceptions=True,
        )

        return [
            r if isinstance(r, TestGenerationResult) else TestGenerationResult(
                status=TestGenerationStatus.FAILED,
                errors=[str(r)],
            )
            for r in results
        ]

    async def _build_java_prompt(
        self,
        file_analysis: Dict[str, Any],
        gap_info: Optional[CoverageGap] = None,
        improvement_plan: Optional[str] = None,
    ) -> str:
        """构建 Java 测试 Prompt."""
        class_name = file_analysis.get("class_name", "Unknown")
        package = file_analysis.get("package", "")
        methods = file_analysis.get("methods", [])
        fields = file_analysis.get("fields", [])

        if self._template_loader:
            template_name = self._config.template_name_java_gap if gap_info else self._config.template_name_java
            try:
                return self._template_loader.render(
                    template_name,
                    class_name=class_name,
                    package=package,
                    methods=methods,
                    fields=fields,
                    gap_info=gap_info,
                    improvement_plan=improvement_plan,
                )
            except Exception:
                pass

        if gap_info and improvement_plan:
            return f"""作为 Java 单元测试专家，请为以下类生成补充测试用例，针对特定的覆盖率缺口。

目标类: {class_name}
包名: {package}

需要覆盖的代码:
文件: {gap_info.file_path}
行号: {gap_info.line_number}
代码: {gap_info.line_content}
缺口类型: {gap_info.gap_type}

改进计划:
{improvement_plan}

已有方法:
{self._format_java_methods(methods)}

请生成 JUnit 5 测试代码，只包含针对该缺口的测试方法。
要求:
1. 使用 JUnit 5 (org.junit.jupiter.api)
2. 使用 Mockito 进行依赖模拟
3. 包含 Arrange-Act-Assert 结构
4. 添加清晰的注释说明测试目的
"""
        else:
            return f"""作为 Java 单元测试专家，请为以下类生成完整的 JUnit 5 测试类。

目标类: {class_name}
包名: {package}

类字段:
{self._format_java_fields(fields)}

类方法:
{self._format_java_methods(methods)}

请生成完整的 JUnit 5 测试类代码。
要求:
1. 使用 JUnit 5 (org.junit.jupiter.api.Test, org.junit.jupiter.api.BeforeEach 等)
2. 使用 Mockito (org.mockito.Mockito, org.mockito.InjectMocks, org.mockito.Mock)
3. 为每个公共方法生成至少 2 个测试用例 (正常场景 + 异常场景)
4. 使用 given-when-then 命名风格
5. 添加 @DisplayName 注解说明测试目的
6. 测试类命名为 {class_name}Test
"""

    async def _build_typescript_prompt(
        self,
        file_analysis: Dict[str, Any],
        project_type: str,
        gap_info: Optional[CoverageGap] = None,
        improvement_plan: Optional[str] = None,
    ) -> str:
        """构建 TypeScript 测试 Prompt."""
        file_path = file_analysis.get("file_path", "")
        file_name = Path(file_path).stem
        functions = file_analysis.get("functions", [])

        if gap_info and improvement_plan:
            return f"""作为 TypeScript 单元测试专家，请为以下代码生成补充测试用例。

目标文件: {file_name}
项目类型: {project_type}

需要覆盖的代码:
文件: {gap_info.file_path}
行号: {gap_info.line_number}
代码: {gap_info.line_content}
缺口类型: {gap_info.gap_type}

改进计划:
{improvement_plan}

导出函数:
{self._format_ts_functions(functions)}

请生成针对该缺口的测试代码。
"""
        else:
            return f"""作为 TypeScript 单元测试专家，请为以下代码生成完整的测试文件。

文件名: {file_name}
项目类型: {project_type}

导出函数:
{self._format_ts_functions(functions)}

请生成完整的 Vitest 测试代码。
要求:
1. 使用 Vitest (describe, it, expect, vi)
2. 为每个导出函数生成测试
3. 包含正常输入、边界条件、异常输入测试
4. 使用 vi.fn() 模拟依赖
5. 测试文件命名为 {file_name}.spec.ts
"""

    async def _build_vue_prompt(
        self,
        file_analysis: Dict[str, Any],
        gap_info: Optional[CoverageGap] = None,
        improvement_plan: Optional[str] = None,
    ) -> str:
        """构建 Vue 组件测试 Prompt."""
        file_path = file_analysis.get("file_path", "")
        file_name = Path(file_path).stem
        component_info = file_analysis.get("component_info", {})
        functions = file_analysis.get("functions", [])

        return f"""作为 Vue 单元测试专家，请为以下 Vue 组件生成完整的测试文件。

组件名: {file_name}

组件功能:
{self._format_vue_component_info(component_info)}

导出函数:
{self._format_ts_functions(functions)}

请生成完整的 Vitest + Vue Test Utils 测试代码。
要求:
1. 使用 Vitest (describe, it, expect, vi)
2. 使用 @vue/test-utils (mount, shallowMount)
3. 测试组件渲染、props、事件、方法
4. 使用 vi.fn() 模拟依赖
5. 包含正常场景和异常场景
"""

    async def _build_react_prompt(
        self,
        file_analysis: Dict[str, Any],
        gap_info: Optional[CoverageGap] = None,
        improvement_plan: Optional[str] = None,
    ) -> str:
        """构建 React 组件测试 Prompt."""
        file_path = file_analysis.get("file_path", "")
        file_name = Path(file_path).stem
        functions = file_analysis.get("functions", [])

        return f"""作为 React 单元测试专家，请为以下 React 组件生成完整的测试文件。

组件名: {file_name}

导出函数:
{self._format_ts_functions(functions)}

请生成完整的 Vitest + React Testing Library 测试代码。
"""

    def _get_java_test_path(self, file_analysis: Dict[str, Any]) -> Path:
        """获取 Java 测试文件路径."""
        file_path = file_analysis.get("file_path", "")
        class_name = file_analysis.get("class_name", "Unknown")

        path = Path(file_path)
        project_path = path.parent

        while project_path.name not in ["java", "src"] and project_path.parent != project_path:
            project_path = project_path.parent

        if project_path.name == "java":
            test_dir = project_path.parent / "test" / "java"
        else:
            test_dir = path.parent

        relative_path = path.relative_to(project_path) if path.is_relative_to(project_path) else path
        return test_dir / relative_path.parent / f"{class_name}Test.java"

    def _get_typescript_test_path(self, file_analysis: Dict[str, Any]) -> Path:
        """获取 TypeScript 测试文件路径."""
        file_path = file_analysis.get("file_path", "")
        path = Path(file_path)
        return path.parent / f"{path.stem}.spec.ts"

    def _format_java_methods(self, methods: List[Dict[str, Any]]) -> str:
        """格式化 Java 方法信息."""
        if not methods:
            return "无"

        result = []
        for m in methods:
            signature = m.get("signature", "void method()")
            return_type = m.get("return_type", "void")
            result.append(f"- {signature} (返回: {return_type})")
        return "\n".join(result)

    def _format_java_fields(self, fields: List[Dict[str, Any]]) -> str:
        """格式化 Java 字段信息."""
        if not fields:
            return "无"

        result = []
        for f in fields:
            result.append(f"- {f.get('access', 'private')} {f.get('type', 'Object')} {f.get('name', 'field')}")
        return "\n".join(result)

    def _format_ts_functions(self, functions: List[Dict[str, Any]]) -> str:
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
            result.append(f"- {export_mark}{async_mark}{name}({params}): {return_type}")
        return "\n".join(result)

    def _format_vue_component_info(self, component_info: Dict[str, Any]) -> str:
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

    def _clean_code_blocks(self, code: str) -> str:
        """清理代码块标记."""
        code = code.strip()
        if code.startswith("```"):
            lines = code.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            code = "\n".join(lines)
        return code.strip()

    def _wrap_additional_test(
        self,
        test_code: str,
        file_analysis: Dict[str, Any],
    ) -> str:
        """将补充测试包装成完整类."""
        class_name = file_analysis.get("class_name", "Unknown")
        package = file_analysis.get("package", "")
        imports = file_analysis.get("imports", [])

        import_statements = "\n".join([f"import {imp};" for imp in imports[:5]])

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

    def get_supported_languages(self) -> List[str]:
        """获取支持的语言列表."""
        return self.SUPPORTED_LANGUAGES.copy()
