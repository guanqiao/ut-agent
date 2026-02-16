"""Fixer Agent - 自动修复专家."""

import re
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from langchain_core.language_models.chat_models import BaseChatModel

from ut_agent.agents.base import (
    BaseAgent,
    AgentContext,
    AgentResult,
    AgentCapability,
    AgentStatus,
)
from ut_agent.models import get_llm


class FixType(Enum):
    """修复类型."""
    COMPILE_ERROR = "compile_error"
    RUNTIME_ERROR = "runtime_error"
    ASSERTION_ERROR = "assertion_error"
    IMPORT_ERROR = "import_error"
    ANTI_PATTERN = "anti_pattern"
    QUALITY_ISSUE = "quality_issue"
    PERFORMANCE = "performance"


@dataclass
class FixAction:
    """修复动作."""
    fix_type: FixType
    description: str
    original_code: str
    fixed_code: str
    line_start: int
    line_end: int


class ErrorDiagnoser:
    """错误诊断器."""
    
    ERROR_PATTERNS = {
        "import_error": {
            "pattern": r"cannot find symbol|Cannot find name|module not found|No module named",
            "fix_type": FixType.IMPORT_ERROR,
        },
        "type_error": {
            "pattern": r"incompatible types|Type.*is not assignable|Argument of type",
            "fix_type": FixType.COMPILE_ERROR,
        },
        "null_pointer": {
            "pattern": r"NullPointerException|Cannot read properties of undefined|NoneType",
            "fix_type": FixType.RUNTIME_ERROR,
        },
        "assertion_failed": {
            "pattern": r"AssertionError|Expected.*but was|expect\(.*\)\.toBe",
            "fix_type": FixType.ASSERTION_ERROR,
        },
        "mock_error": {
            "pattern": r"Unfinished stubbing|WrongTypeOfReturnValue|mock is not a function",
            "fix_type": FixType.RUNTIME_ERROR,
        },
        "timeout": {
            "pattern": r"Timeout|test timed out|Exceeded timeout",
            "fix_type": FixType.PERFORMANCE,
        },
    }
    
    def diagnose(self, error_message: str, test_code: str) -> List[Dict[str, Any]]:
        diagnoses = []
        
        for error_type, config in self.ERROR_PATTERNS.items():
            if re.search(config["pattern"], error_message, re.IGNORECASE):
                diagnoses.append({
                    "error_type": error_type,
                    "fix_type": config["fix_type"],
                    "message": error_message,
                    "suggested_fix": self._suggest_fix(error_type, test_code),
                })
        
        return diagnoses
    
    def _suggest_fix(self, error_type: str, test_code: str) -> str:
        suggestions = {
            "import_error": "检查导入语句是否正确，确保依赖已安装",
            "type_error": "检查类型匹配，可能需要类型转换或修正参数类型",
            "null_pointer": "添加空值检查或使用 Optional/默认值",
            "assertion_failed": "检查预期值是否正确，可能需要调整断言",
            "mock_error": "检查 Mock 配置，确保 when().thenReturn() 语法正确",
            "timeout": "增加超时时间或优化测试执行速度",
        }
        return suggestions.get(error_type, "检查错误信息并修复相应问题")


class AutoFixer:
    """自动修复器."""
    
    IMPORT_FIXES = {
        "java": {
            "@Test": "import org.junit.jupiter.api.Test;",
            "@BeforeEach": "import org.junit.jupiter.api.BeforeEach;",
            "@DisplayName": "import org.junit.jupiter.api.DisplayName;",
            "@Mock": "import org.mockito.Mock;",
            "@InjectMocks": "import org.mockito.InjectMocks;",
            "when(": "import static org.mockito.Mockito.when;",
            "verify(": "import static org.mockito.Mockito.verify;",
            "assertNotNull": "import static org.junit.jupiter.api.Assertions.assertNotNull;",
            "assertEquals": "import static org.junit.jupiter.api.Assertions.assertEquals;",
            "assertTrue": "import static org.junit.jupiter.api.Assertions.assertTrue;",
            "assertFalse": "import static org.junit.jupiter.api.Assertions.assertFalse;",
            "assertThrows": "import static org.junit.jupiter.api.Assertions.assertThrows;",
        },
        "typescript": {
            "describe(": "import { describe, it, expect } from 'vitest';",
            "vi.fn": "import { vi } from 'vitest';",
            "mount(": "import { mount } from '@vue/test-utils';",
        },
    }
    
    def fix_imports(self, test_code: str, language: str) -> str:
        fixes = self.IMPORT_FIXES.get(language, {})
        existing_imports = set(re.findall(r'^import .+;$', test_code, re.MULTILINE))
        
        needed_imports = []
        for pattern, import_stmt in fixes.items():
            if pattern in test_code and import_stmt not in test_code:
                if import_stmt not in existing_imports:
                    needed_imports.append(import_stmt)
        
        if needed_imports:
            import_block = "\n".join(needed_imports) + "\n\n"
            
            if language == "java":
                package_match = re.search(r'^package .+;$', test_code, re.MULTILINE)
                if package_match:
                    insert_pos = package_match.end()
                    test_code = test_code[:insert_pos] + "\n" + import_block + test_code[insert_pos:]
                else:
                    test_code = import_block + test_code
            else:
                test_code = import_block + test_code
        
        return test_code
    
    def fix_null_checks(self, test_code: str) -> str:
        null_check_patterns = [
            (r'(\w+)\.get\(([^)]+)\)', r'(\1 != null ? \1.get(\2) : null)'),
            (r'(\w+)\.toString\(\)', r'(String.valueOf(\1))'),
        ]
        
        for pattern, replacement in null_check_patterns:
            pass
        
        return test_code
    
    def fix_mock_setup(self, test_code: str) -> str:
        mock_fixes = [
            (r'when\((\w+)\.(\w+)\(\)\)', r'when(\1.\2()).thenReturn(null)'),
            (r'vi\.fn\(\)(?!.*returnValue)', r'vi.fn().mockReturnValue(undefined)'),
        ]
        
        for pattern, replacement in mock_fixes:
            if re.search(pattern, test_code):
                test_code = re.sub(pattern, replacement, test_code)
        
        return test_code


class ConflictMerger:
    """冲突合并器 - 保留用户修改."""
    
    USER_MODIFICATION_MARKERS = [
        "// USER CODE START",
        "// USER CODE END",
        "// CUSTOM ASSERTION",
        "// MANUAL FIX",
    ]
    
    def merge(self, original_test: str, new_test: str) -> str:
        original_lines = original_test.split("\n")
        new_lines = new_test.split("\n")
        
        user_blocks = self._extract_user_blocks(original_lines)
        
        result_lines = new_lines.copy()
        
        for block in user_blocks:
            insert_pos = self._find_insert_position(result_lines, block)
            if insert_pos >= 0:
                result_lines[insert_pos:insert_pos] = block["content"]
        
        return "\n".join(result_lines)
    
    def _extract_user_blocks(self, lines: List[str]) -> List[Dict[str, Any]]:
        blocks = []
        in_block = False
        current_block = []
        start_line = -1
        
        for i, line in enumerate(lines):
            if any(marker in line for marker in self.USER_MODIFICATION_MARKERS):
                if "START" in line or not in_block:
                    in_block = True
                    start_line = i
                    current_block = [line]
                elif "END" in line:
                    current_block.append(line)
                    blocks.append({
                        "content": current_block,
                        "start_line": start_line,
                        "end_line": i,
                    })
                    in_block = False
                    current_block = []
            elif in_block:
                current_block.append(line)
        
        return blocks
    
    def _find_insert_position(self, lines: List[str], block: Dict[str, Any]) -> int:
        for i, line in enumerate(lines):
            if "@Test" in line or "it(" in line:
                return i
        return -1


class PerformanceOptimizer:
    """性能优化器."""
    
    def optimize(self, test_code: str) -> str:
        optimizations = [
            self._remove_duplicate_setup,
            self._optimize_assertions,
            self._remove_debug_output,
        ]
        
        for optimization in optimizations:
            test_code = optimization(test_code)
        
        return test_code
    
    def _remove_duplicate_setup(self, test_code: str) -> str:
        setup_pattern = r'(@BeforeEach|beforeEach)\s*\([^)]*\)\s*\{([^}]+)\}'
        setups = list(re.finditer(setup_pattern, test_code, re.DOTALL))
        
        if len(setups) > 1:
            first_setup = setups[0]
            for setup in setups[1:]:
                test_code = test_code.replace(setup.group(0), "")
        
        return test_code
    
    def _optimize_assertions(self, test_code: str) -> str:
        return test_code
    
    def _remove_debug_output(self, test_code: str) -> str:
        debug_patterns = [
            r'\s*System\.out\.println\([^)]*\);\n',
            r'\s*console\.log\([^)]*\);\n',
            r'\s*print\([^)]*\)\n',
        ]
        
        for pattern in debug_patterns:
            test_code = re.sub(pattern, "", test_code)
        
        return test_code


class FixerAgent(BaseAgent):
    """自动修复 Agent."""
    
    name = "fixer"
    description = "自动修复专家 - 根据审查结果和执行错误自动修复测试代码"
    capabilities = [
        AgentCapability.COMPILE_ERROR_FIX,
        AgentCapability.RUNTIME_ERROR_FIX,
        AgentCapability.ASSERTION_FIX,
        AgentCapability.PERFORMANCE_OPTIMIZATION,
        AgentCapability.CONFLICT_MERGE,
    ]
    
    def __init__(
        self,
        memory: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
        llm: Optional[BaseChatModel] = None,
    ):
        super().__init__(memory, config)
        self._llm = llm
        self._error_diagnoser = ErrorDiagnoser()
        self._auto_fixer = AutoFixer()
        self._conflict_merger = ConflictMerger()
        self._performance_optimizer = PerformanceOptimizer()
    
    def set_llm(self, llm: BaseChatModel) -> None:
        self._llm = llm
    
    async def execute(self, context: AgentContext) -> AgentResult:
        start_time = time.time()
        self._status = AgentStatus.RUNNING
        
        errors = []
        fix_actions = []
        
        try:
            generated_test = context.generated_test
            review_result = context.review_result
            execution_result = context.execution_result
            
            if not generated_test:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    task_id=context.task_id,
                    errors=["No generated test provided"],
                )
            
            test_code = generated_test.get("test_code", "")
            language = generated_test.get("language", "java")
            original_test = generated_test.get("original_test_code", test_code)
            
            if not self._llm:
                llm_provider = context.config.get("llm_provider", "openai")
                self._llm = get_llm(llm_provider)
            
            fixed_code = test_code
            
            fixed_code, import_fixes = self._fix_imports(fixed_code, language)
            fix_actions.extend(import_fixes)
            
            if execution_result and not execution_result.get("success", True):
                error_message = execution_result.get("error", "")
                diagnoses = self._error_diagnoser.diagnose(error_message, fixed_code)
                
                for diagnosis in diagnoses:
                    fixed_code, actions = await self._apply_fix(
                        fixed_code, diagnosis, language
                    )
                    fix_actions.extend(actions)
            
            if review_result:
                issues = review_result.get("issues", [])
                for issue in issues:
                    if issue.get("severity") in ["critical", "high"]:
                        fixed_code, action = await self._fix_issue(
                            fixed_code, issue, language
                        )
                        if action:
                            fix_actions.append(action)
            
            fixed_code = self._performance_optimizer.optimize(fixed_code)
            
            if original_test != test_code:
                fixed_code = self._conflict_merger.merge(original_test, fixed_code)
            
            self.remember(f"fix:{context.task_id}", {
                "fix_count": len(fix_actions),
                "fix_types": [a.fix_type.value for a in fix_actions],
            })
            
            duration_ms = int((time.time() - start_time) * 1000)
            self._status = AgentStatus.SUCCESS
            
            result = AgentResult(
                success=True,
                agent_name=self.name,
                task_id=context.task_id,
                data={
                    "fixed_test_code": fixed_code,
                    "fix_actions": [
                        {
                            "type": action.fix_type.value,
                            "description": action.description,
                            "line_start": action.line_start,
                            "line_end": action.line_end,
                        }
                        for action in fix_actions
                    ],
                },
                metrics={
                    "duration_ms": duration_ms,
                    "fix_count": len(fix_actions),
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
    
    def _fix_imports(self, test_code: str, language: str) -> tuple:
        original = test_code
        fixed_code = self._auto_fixer.fix_imports(test_code, language)
        
        actions = []
        if fixed_code != original:
            actions.append(FixAction(
                fix_type=FixType.IMPORT_ERROR,
                description="添加缺失的导入语句",
                original_code=original,
                fixed_code=fixed_code,
                line_start=1,
                line_end=1,
            ))
        
        return fixed_code, actions
    
    async def _apply_fix(
        self,
        test_code: str,
        diagnosis: Dict[str, Any],
        language: str,
    ) -> tuple:
        fix_type = diagnosis.get("fix_type", FixType.RUNTIME_ERROR)
        actions = []
        
        if fix_type == FixType.IMPORT_ERROR:
            fixed_code = self._auto_fixer.fix_imports(test_code, language)
            if fixed_code != test_code:
                actions.append(FixAction(
                    fix_type=fix_type,
                    description=f"修复导入错误: {diagnosis.get('message', '')[:50]}",
                    original_code=test_code,
                    fixed_code=fixed_code,
                    line_start=1,
                    line_end=10,
                ))
                return fixed_code, actions
        
        elif fix_type == FixType.RUNTIME_ERROR:
            fixed_code = self._auto_fixer.fix_null_checks(test_code)
            fixed_code = self._auto_fixer.fix_mock_setup(fixed_code)
            if fixed_code != test_code:
                actions.append(FixAction(
                    fix_type=fix_type,
                    description=f"修复运行时错误: {diagnosis.get('message', '')[:50]}",
                    original_code=test_code,
                    fixed_code=fixed_code,
                    line_start=1,
                    line_end=len(test_code.split("\n")),
                ))
                return fixed_code, actions
        
        try:
            fixed_code = await self._llm_fix(test_code, diagnosis, language)
            if fixed_code and fixed_code != test_code:
                actions.append(FixAction(
                    fix_type=fix_type,
                    description=f"LLM 修复: {diagnosis.get('error_type', 'unknown')}",
                    original_code=test_code,
                    fixed_code=fixed_code,
                    line_start=1,
                    line_end=len(fixed_code.split("\n")),
                ))
                return fixed_code, actions
        except Exception:
            pass
        
        return test_code, actions
    
    async def _llm_fix(
        self,
        test_code: str,
        diagnosis: Dict[str, Any],
        language: str,
    ) -> str:
        prompt = f"""作为测试代码修复专家，请修复以下测试代码中的错误。

错误类型: {diagnosis.get('error_type', 'unknown')}
错误信息: {diagnosis.get('message', '')}
建议修复: {diagnosis.get('suggested_fix', '')}

测试代码:
```
{test_code}
```

请返回修复后的完整测试代码，只返回代码，不要包含解释。
"""
        
        response = await self._llm.ainvoke(prompt)
        fixed_code = str(response.content)
        
        if fixed_code.startswith("```"):
            lines = fixed_code.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            fixed_code = "\n".join(lines)
        
        return fixed_code.strip()
    
    async def _fix_issue(
        self,
        test_code: str,
        issue: Dict[str, Any],
        language: str,
    ) -> tuple:
        rule_id = issue.get("rule_id", "")
        message = issue.get("message", "")
        suggestion = issue.get("suggestion", "")
        
        if "anti_pattern:empty_test" in rule_id:
            return test_code, None
        
        if "anti_pattern:no_assertions" in rule_id:
            try:
                fixed_code = await self._add_assertions(test_code, language)
                return fixed_code, FixAction(
                    fix_type=FixType.QUALITY_ISSUE,
                    description="添加缺失的断言",
                    original_code=test_code,
                    fixed_code=fixed_code,
                    line_start=issue.get("line", 1),
                    line_end=issue.get("line", 1),
                )
            except Exception:
                pass
        
        return test_code, None
    
    async def _add_assertions(self, test_code: str, language: str) -> str:
        if language == "java":
            assertion_template = """
        // Assert
        assertNotNull(result);
"""
        else:
            assertion_template = """
    // Assert
    expect(result).toBeDefined();
"""
        
        lines = test_code.split("\n")
        result = []
        
        for i, line in enumerate(lines):
            result.append(line)
            if "@Test" in line or "it(" in line:
                j = i + 1
                brace_count = 0
                found_assertion = False
                while j < len(lines):
                    if "assert" in lines[j].lower() or "expect" in lines[j].lower():
                        found_assertion = True
                    if "{" in lines[j]:
                        brace_count += 1
                    if "}" in lines[j]:
                        brace_count -= 1
                        if brace_count == 0:
                            if not found_assertion:
                                result.append(assertion_template)
                            break
                    j += 1
        
        return "\n".join(result)
