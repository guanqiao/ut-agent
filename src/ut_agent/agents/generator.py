"""Generator Agent - 测试生成专家."""

import time
from typing import Any, Dict, List, Optional
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel

from ut_agent.agents.base import (
    BaseAgent,
    AgentContext,
    AgentResult,
    AgentCapability,
    AgentStatus,
)
from ut_agent.graph.state import GeneratedTestFile, CoverageGap
from ut_agent.models import get_llm
from ut_agent.tools.test_data_generator import BoundaryValueGenerator


class TemplateSelector:
    """测试模板选择器."""
    
    JAVA_TEMPLATES = {
        "controller": {
            "pattern": ["controller", "restcontroller", "api"],
            "template": "spring_controller_test",
            "imports": [
                "org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest",
                "org.springframework.test.web.servlet.MockMvc",
            ],
        },
        "service": {
            "pattern": ["service", "component"],
            "template": "spring_service_test",
            "imports": [
                "org.springframework.boot.test.context.SpringBootTest",
            ],
        },
        "repository": {
            "pattern": ["repository", "dao"],
            "template": "spring_repository_test",
            "imports": [
                "org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest",
            ],
        },
        "util": {
            "pattern": ["util", "helper", "utils"],
            "template": "util_test",
            "imports": [],
        },
    }
    
    FRONTEND_TEMPLATES = {
        "vue_component": {
            "pattern": [".vue"],
            "template": "vue_component_test",
        },
        "react_component": {
            "pattern": [".tsx", ".jsx"],
            "template": "react_component_test",
        },
        "util": {
            "pattern": ["util", "helper", "utils"],
            "template": "util_test",
        },
    }
    
    @classmethod
    def select_template(cls, file_analysis: Dict[str, Any]) -> Dict[str, Any]:
        language = file_analysis.get("language", "java")
        class_name = file_analysis.get("class_name", file_analysis.get("file_name", ""))
        annotations = file_analysis.get("annotations", [])
        file_path = file_analysis.get("file_path", "")
        
        class_name_lower = class_name.lower()
        annotations_lower = [a.lower() for a in annotations]
        
        if language == "java":
            for template_type, config in cls.JAVA_TEMPLATES.items():
                for pattern in config["pattern"]:
                    if pattern in class_name_lower or pattern in annotations_lower:
                        return {
                            "type": template_type,
                            "template": config["template"],
                            "imports": config["imports"],
                        }
            
            return {
                "type": "default",
                "template": "default_java_test",
                "imports": [],
            }
        else:
            for template_type, config in cls.FRONTEND_TEMPLATES.items():
                for pattern in config["pattern"]:
                    if pattern in file_path.lower() or pattern in class_name_lower:
                        return {
                            "type": template_type,
                            "template": config["template"],
                        }
            
            return {
                "type": "default",
                "template": "default_frontend_test",
            }


class MockGenerator:
    """Mock 对象生成器."""
    
    @staticmethod
    def generate_java_mocks(mock_suggestions: List[Dict[str, Any]]) -> str:
        if not mock_suggestions:
            return ""
        
        mock_fields = []
        mock_setup = []
        
        for suggestion in mock_suggestions:
            field_name = suggestion.get("field_name", "mock")
            field_type = suggestion.get("field_type", "Object")
            
            mock_fields.append(f"    @Mock\n    private {field_type} {field_name};")
            mock_setup.append(f"        // Mock {field_name} behavior\n        // when({field_name}.method()).thenReturn(value);")
        
        return "\n".join(mock_fields) + "\n\n" + "\n".join(mock_setup)
    
    @staticmethod
    def generate_frontend_mocks(dependencies: List[str]) -> str:
        if not dependencies:
            return ""
        
        mocks = []
        for dep in dependencies:
            mock_name = dep.split("/")[-1]
            mocks.append(f"    const {mock_name}Mock = vi.fn();")
        
        return "\n".join(mocks)


class AssertionGenerator:
    """断言生成器."""
    
    @staticmethod
    def generate_java_assertions(method_info: Dict[str, Any]) -> List[str]:
        assertions = []
        return_type = method_info.get("return_type", "void")
        method_name = method_info.get("name", "method")
        
        if return_type == "void":
            assertions.append(f"        // Verify {method_name} was called")
            assertions.append(f"        verify(target).{method_name}(any());")
        elif return_type in ["int", "Integer", "long", "Long"]:
            assertions.append(f"        // Assert result")
            assertions.append(f"        assertNotNull(result);")
            assertions.append(f"        assertTrue(result > 0);")
        elif return_type in ["boolean", "Boolean"]:
            assertions.append(f"        // Assert boolean result")
            assertions.append(f"        assertTrue(result);")
        elif return_type == "String":
            assertions.append(f"        // Assert string result")
            assertions.append(f"        assertNotNull(result);")
            assertions.append(f"        assertFalse(result.isEmpty());")
        elif return_type in ["List", "Collection", "Set"]:
            assertions.append(f"        // Assert collection result")
            assertions.append(f"        assertNotNull(result);")
            assertions.append(f"        assertFalse(result.isEmpty());")
        else:
            assertions.append(f"        // Assert object result")
            assertions.append(f"        assertNotNull(result);")
        
        return assertions
    
    @staticmethod
    def generate_frontend_assertions(function_info: Dict[str, Any]) -> List[str]:
        assertions = []
        return_type = function_info.get("return_type", "void")
        func_name = function_info.get("name", "func")
        
        if return_type == "void":
            assertions.append(f"    // Verify {func_name} was called")
            assertions.append(f"    expect({func_name}Mock).toHaveBeenCalled();")
        else:
            assertions.append(f"    // Assert result")
            assertions.append(f"    expect(result).toBeDefined();")
            if return_type in ["number", "Number"]:
                assertions.append(f"    expect(result).toBeGreaterThan(0);")
            elif return_type in ["string", "String"]:
                assertions.append(f"    expect(result.length).toBeGreaterThan(0);")
            elif return_type in ["boolean", "Boolean"]:
                assertions.append(f"    expect(typeof result).toBe('boolean');")
        
        return assertions


class GeneratorAgent(BaseAgent):
    """测试生成 Agent."""
    
    name = "generator"
    description = "测试生成专家 - 基于分析结果生成高质量测试代码"
    capabilities = [
        AgentCapability.TEMPLATE_SELECTION,
        AgentCapability.MOCK_GENERATION,
        AgentCapability.TEST_DATA_GENERATION,
        AgentCapability.ASSERTION_GENERATION,
        AgentCapability.SCENARIO_COVERAGE,
    ]
    
    def __init__(
        self,
        memory: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
        llm: Optional[BaseChatModel] = None,
    ):
        super().__init__(memory, config)
        self._llm = llm
        self._template_selector = TemplateSelector()
        self._mock_generator = MockGenerator()
        self._assertion_generator = AssertionGenerator()
        self._test_data_generator = BoundaryValueGenerator()
    
    def set_llm(self, llm: BaseChatModel) -> None:
        self._llm = llm
    
    async def execute(self, context: AgentContext) -> AgentResult:
        start_time = time.time()
        self._status = AgentStatus.RUNNING
        
        errors = []
        warnings = []
        
        try:
            file_analysis = context.file_analysis
            if not file_analysis:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    task_id=context.task_id,
                    errors=["No file analysis provided"],
                )
            
            if not self._llm:
                llm_provider = context.config.get("llm_provider", "openai")
                self._llm = get_llm(llm_provider)
            
            template = self._select_template(file_analysis)
            
            mock_code = self._generate_mocks(context)
            
            test_data = self._generate_test_data(file_analysis)
            
            test_code = await self._generate_test_code(
                file_analysis=file_analysis,
                template=template,
                mock_code=mock_code,
                test_data=test_data,
                context=context,
            )
            
            test_file = self._create_test_file(file_analysis, test_code)
            
            self.remember(f"test:{file_analysis.get('file_path', '')}", {
                "test_code": test_code,
                "template": template,
                "generated_at": time.time(),
            })
            
            duration_ms = int((time.time() - start_time) * 1000)
            self._status = AgentStatus.SUCCESS
            
            result = AgentResult(
                success=True,
                agent_name=self.name,
                task_id=context.task_id,
                data={
                    "test_file": test_file,
                    "template": template,
                    "test_data_count": len(test_data),
                },
                warnings=warnings,
                metrics={
                    "duration_ms": duration_ms,
                    "test_code_lines": len(test_code.split("\n")),
                },
                duration_ms=duration_ms,
            )
            
            self.record_execution(result)
            return result
            
        except Exception as e:
            self._status = AgentStatus.FAILED
            errors.append(str(e))
            return AgentResult(
                success=False,
                agent_name=self.name,
                task_id=context.task_id,
                errors=errors,
            )
    
    def _select_template(self, file_analysis: Dict[str, Any]) -> Dict[str, Any]:
        return self._template_selector.select_template(file_analysis)
    
    def _generate_mocks(self, context: AgentContext) -> str:
        file_analysis = context.file_analysis or {}
        language = file_analysis.get("language", "java")
        
        mock_suggestions = context.memory_context.get("mock_suggestions", [])
        dependencies = context.memory_context.get("dependencies", {})
        
        if language == "java":
            return self._mock_generator.generate_java_mocks(mock_suggestions)
        else:
            external_deps = dependencies.get("external", [])
            return self._mock_generator.generate_frontend_mocks(external_deps)
    
    def _generate_test_data(self, file_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        methods = file_analysis.get("methods", file_analysis.get("functions", []))
        test_data = []
        
        for method in methods:
            params = method.get("parameters", [])
            if params:
                data = self._test_data_generator.generate_for_parameters(params)
                test_data.append({
                    "method": method.get("name"),
                    "data": data,
                })
        
        return test_data
    
    async def _generate_test_code(
        self,
        file_analysis: Dict[str, Any],
        template: Dict[str, Any],
        mock_code: str,
        test_data: List[Dict[str, Any]],
        context: AgentContext,
    ) -> str:
        language = file_analysis.get("language", "java")
        
        if language == "java":
            return await self._generate_java_test(
                file_analysis, template, mock_code, test_data, context
            )
        else:
            return await self._generate_frontend_test(
                file_analysis, template, mock_code, test_data, context
            )
    
    async def _generate_java_test(
        self,
        file_analysis: Dict[str, Any],
        template: Dict[str, Any],
        mock_code: str,
        test_data: List[Dict[str, Any]],
        context: AgentContext,
    ) -> str:
        class_name = file_analysis.get("class_name", "Unknown")
        package = file_analysis.get("package", "")
        methods = file_analysis.get("methods", [])
        fields = file_analysis.get("fields", [])
        
        prompt = self._build_java_prompt(
            class_name, package, methods, fields, template, mock_code, test_data
        )
        
        response = await self._llm.ainvoke(prompt)
        test_code = str(response.content)
        
        test_code = self._clean_code_blocks(test_code)
        
        return test_code
    
    async def _generate_frontend_test(
        self,
        file_analysis: Dict[str, Any],
        template: Dict[str, Any],
        mock_code: str,
        test_data: List[Dict[str, Any]],
        context: AgentContext,
    ) -> str:
        file_name = file_analysis.get("file_name", "unknown")
        functions = file_analysis.get("functions", [])
        is_vue = file_analysis.get("is_vue", False)
        component_info = file_analysis.get("component_info", {})
        
        prompt = self._build_frontend_prompt(
            file_name, functions, template, mock_code, test_data, is_vue, component_info
        )
        
        response = await self._llm.ainvoke(prompt)
        test_code = str(response.content)
        
        test_code = self._clean_code_blocks(test_code)
        
        return test_code
    
    def _build_java_prompt(
        self,
        class_name: str,
        package: str,
        methods: List[Dict[str, Any]],
        fields: List[Dict[str, Any]],
        template: Dict[str, Any],
        mock_code: str,
        test_data: List[Dict[str, Any]],
    ) -> str:
        method_strs = []
        for m in methods:
            params = ", ".join([f"{p.get('type', 'Object')} {p.get('name', 'param')}" for p in m.get("parameters", [])])
            method_strs.append(f"- {m.get('signature', m.get('name'))} (返回: {m.get('return_type', 'void')})")
        
        field_strs = [f"- {f.get('access', 'private')} {f.get('type', 'Object')} {f.get('name', 'field')}" for f in fields]
        
        return f"""作为 Java 单元测试专家，请为以下类生成完整的 JUnit 5 测试类。

目标类: {class_name}
包名: {package}
模板类型: {template.get('type', 'default')}

类字段:
{chr(10).join(field_strs) if field_strs else '无'}

类方法:
{chr(10).join(method_strs) if method_strs else '无'}

建议的 Mock 配置:
{mock_code if mock_code else '无'}

请生成完整的 JUnit 5 测试类代码。
要求:
1. 使用 JUnit 5 (org.junit.jupiter.api.Test, @BeforeEach, @DisplayName)
2. 使用 Mockito (@Mock, @InjectMocks, when(), verify())
3. 为每个公共方法生成至少 2 个测试用例 (正常场景 + 异常场景)
4. 包含边界条件测试
5. 使用 given_when_then 命名风格
6. 添加 @DisplayName 注解说明测试目的
7. 包含必要的导入语句
8. 测试类命名为 {class_name}Test
9. 包名: {package}
"""
    
    def _build_frontend_prompt(
        self,
        file_name: str,
        functions: List[Dict[str, Any]],
        template: Dict[str, Any],
        mock_code: str,
        test_data: List[Dict[str, Any]],
        is_vue: bool,
        component_info: Dict[str, Any],
    ) -> str:
        func_strs = []
        for f in functions:
            params = ", ".join([f"{p.get('name', 'param')}: {p.get('type', 'any')}" for p in f.get("parameters", [])])
            export_mark = "export " if f.get("is_exported") else ""
            async_mark = "async " if f.get("is_async") else ""
            func_strs.append(f"- {export_mark}{async_mark}{f.get('name')}({params}): {f.get('return_type', 'void')}")
        
        component_strs = []
        if component_info.get("has_props"):
            component_strs.append("- 有 Props 定义")
        if component_info.get("has_emits"):
            component_strs.append("- 有 Emits 定义")
        if component_info.get("has_setup"):
            component_strs.append("- 使用 Composition API (setup)")
        
        if is_vue:
            return f"""作为 Vue 单元测试专家，请为以下 Vue 组件生成完整的测试文件。

组件名: {file_name}
模板类型: {template.get('type', 'default')}

组件功能:
{chr(10).join(component_strs) if component_strs else '- 基础组件'}

导出函数:
{chr(10).join(func_strs) if func_strs else '无'}

建议的 Mock 配置:
{mock_code if mock_code else '无'}

请生成完整的 Vitest + Vue Test Utils 测试代码。
要求:
1. 使用 Vitest (describe, it, expect, vi, beforeEach)
2. 使用 @vue/test-utils (mount, shallowMount)
3. 测试组件渲染、props、事件、方法
4. 使用 vi.fn() 模拟依赖
5. 包含正常场景和异常场景
6. 添加清晰的 describe 和 it 描述
7. 测试文件命名为 {file_name}.spec.ts
"""
        else:
            return f"""作为 TypeScript 单元测试专家，请为以下代码生成完整的测试文件。

文件名: {file_name}
模板类型: {template.get('type', 'default')}

导出函数:
{chr(10).join(func_strs) if func_strs else '无'}

建议的 Mock 配置:
{mock_code if mock_code else '无'}

请生成完整的 Vitest 测试代码。
要求:
1. 使用 Vitest (describe, it, expect, vi, beforeEach)
2. 为每个导出函数生成测试
3. 包含正常输入、边界条件、异常输入测试
4. 使用 vi.fn() 模拟依赖
5. 添加清晰的 describe 和 it 描述
6. 测试文件命名为 {file_name}.spec.ts
"""
    
    def _clean_code_blocks(self, code: str) -> str:
        code = code.strip()
        if code.startswith("```"):
            lines = code.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            code = "\n".join(lines)
        return code.strip()
    
    def _create_test_file(self, file_analysis: Dict[str, Any], test_code: str) -> GeneratedTestFile:
        source_file = file_analysis.get("file_path", "")
        path = Path(source_file)
        language = file_analysis.get("language", "java")
        
        if language == "java":
            class_name = file_analysis.get("class_name", path.stem)
            test_file_name = f"{class_name}Test.java"
            
            package = file_analysis.get("package", "")
            if package:
                package_path = package.replace(".", "/")
                test_file_path = str(path.parent / "test" / package_path / test_file_name)
            else:
                test_file_path = str(path.parent / f"{class_name}Test.java")
        else:
            test_file_path = str(path.parent / f"{path.stem}.spec.ts")
        
        return GeneratedTestFile(
            source_file=source_file,
            test_file_path=test_file_path,
            test_code=test_code,
            language=language,
        )
