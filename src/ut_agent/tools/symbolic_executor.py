"""符号执行验证模块.

对生成的测试进行符号执行验证，确保测试能够覆盖目标路径。
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from abc import ABC, abstractmethod


class PathConstraintType(Enum):
    EQUALS = "=="
    NOT_EQUALS = "!="
    LESS_THAN = "<"
    LESS_EQUAL = "<="
    GREATER_THAN = ">"
    GREATER_EQUAL = ">="
    IS_NULL = "isNull"
    IS_NOT_NULL = "isNotNull"
    INSTANCE_OF = "instanceof"


@dataclass
class SymbolicValue:
    name: str
    type_name: str
    constraints: List[str] = field(default_factory=list)
    
    def add_constraint(self, constraint: str) -> None:
        if constraint not in self.constraints:
            self.constraints.append(constraint)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type_name,
            "constraints": self.constraints,
        }


@dataclass
class PathCondition:
    variable: str
    constraint_type: PathConstraintType
    value: Any
    negated: bool = False
    
    def to_expression(self) -> str:
        if self.constraint_type == PathConstraintType.IS_NULL:
            expr = f"{self.variable} == null"
        elif self.constraint_type == PathConstraintType.IS_NOT_NULL:
            expr = f"{self.variable} != null"
        elif self.constraint_type == PathConstraintType.INSTANCE_OF:
            expr = f"{self.variable} instanceof {self.value}"
        else:
            op = self.constraint_type.value
            expr = f"{self.variable} {op} {self.value}"
        
        return f"!({expr})" if self.negated else expr
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "variable": self.variable,
            "constraint_type": self.constraint_type.value,
            "value": str(self.value),
            "negated": self.negated,
        }


@dataclass
class ExecutionPath:
    path_id: str
    conditions: List[PathCondition] = field(default_factory=list)
    covered_statements: List[int] = field(default_factory=list)
    is_feasible: bool = True
    input_values: Dict[str, Any] = field(default_factory=dict)
    
    def add_condition(self, condition: PathCondition) -> None:
        self.conditions.append(condition)
    
    def get_path_constraint(self) -> str:
        return " && ".join(c.to_expression() for c in self.conditions)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path_id": self.path_id,
            "conditions": [c.to_dict() for c in self.conditions],
            "covered_statements": self.covered_statements,
            "is_feasible": self.is_feasible,
            "input_values": self.input_values,
        }


@dataclass
class SymbolicExecutionResult:
    source_file: str
    method_name: str
    total_paths: int
    feasible_paths: int
    infeasible_paths: int
    coverage_estimate: float
    paths: List[ExecutionPath]
    uncovered_branches: List[Tuple[int, str]]
    suggested_inputs: Dict[str, List[Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_file": self.source_file,
            "method_name": self.method_name,
            "total_paths": self.total_paths,
            "feasible_paths": self.feasible_paths,
            "infeasible_paths": self.infeasible_paths,
            "coverage_estimate": round(self.coverage_estimate, 4),
            "uncovered_branches": [
                {"line": b[0], "type": b[1]} for b in self.uncovered_branches
            ],
            "suggested_inputs": self.suggested_inputs,
        }


class ConstraintSolver:
    
    NUMERIC_TYPES = {"int", "long", "double", "float", "short", "byte", "Integer", "Long", "Double", "Float"}
    
    def __init__(self):
        self.solutions: Dict[str, List[Any]] = {}
    
    def solve(self, path: ExecutionPath) -> Tuple[bool, Dict[str, Any]]:
        if not path.conditions:
            return True, {}
        
        solutions: Dict[str, Any] = {}
        
        for condition in path.conditions:
            var_name = condition.variable
            
            if var_name not in solutions:
                solutions[var_name] = self._get_default_value_for_type("Object")
            
            solution = self._solve_single_constraint(condition, solutions.get(var_name))
            if solution is None:
                return False, {}
            
            solutions[var_name] = solution
        
        return True, solutions
    
    def _solve_single_constraint(
        self,
        condition: PathCondition,
        current_value: Any,
    ) -> Optional[Any]:
        if condition.constraint_type == PathConstraintType.IS_NULL:
            return None if not condition.negated else "non_null_value"
        
        if condition.constraint_type == PathConstraintType.IS_NOT_NULL:
            return "non_null_value" if not condition.negated else None
        
        if condition.constraint_type == PathConstraintType.EQUALS:
            return condition.value if not condition.negated else self._get_different_value(condition.value)
        
        if condition.constraint_type == PathConstraintType.NOT_EQUALS:
            return self._get_different_value(condition.value) if not condition.negated else condition.value
        
        if condition.constraint_type in (PathConstraintType.LESS_THAN, PathConstraintType.LESS_EQUAL):
            return self._solve_less_than(condition)
        
        if condition.constraint_type in (PathConstraintType.GREATER_THAN, PathConstraintType.GREATER_EQUAL):
            return self._solve_greater_than(condition)
        
        return current_value
    
    def _solve_less_than(self, condition: PathCondition) -> Any:
        try:
            val = int(condition.value) if isinstance(condition.value, (int, str)) else 0
            return val - 1 if not condition.negated else val + 1
        except (ValueError, TypeError):
            return 0
    
    def _solve_greater_than(self, condition: PathCondition) -> Any:
        try:
            val = int(condition.value) if isinstance(condition.value, (int, str)) else 0
            return val + 1 if not condition.negated else val - 1
        except (ValueError, TypeError):
            return 1
    
    def _get_different_value(self, value: Any) -> Any:
        if isinstance(value, int):
            return value + 1
        if isinstance(value, str):
            return value + "_different"
        if value is None:
            return "non_null"
        return value
    
    def _get_default_value_for_type(self, type_name: str) -> Any:
        defaults = {
            "int": 0,
            "long": 0,
            "double": 0.0,
            "float": 0.0,
            "boolean": False,
            "String": "",
            "Integer": 0,
            "Long": 0,
        }
        return defaults.get(type_name, None)


class SymbolicExecutor:
    
    IF_PATTERN = re.compile(
        r'if\s*\(\s*([^)]+)\s*\)',
        re.MULTILINE
    )
    
    CONDITION_OPERATORS = [
        ("==", PathConstraintType.EQUALS),
        ("!=", PathConstraintType.NOT_EQUALS),
        ("<=", PathConstraintType.LESS_EQUAL),
        (">=", PathConstraintType.GREATER_EQUAL),
        ("<", PathConstraintType.LESS_THAN),
        (">", PathConstraintType.GREATER_THAN),
    ]
    
    def __init__(self):
        self.constraint_solver = ConstraintSolver()
        self.path_counter = 0
    
    def analyze_method(
        self,
        source_code: str,
        method_name: str,
        method_body: str,
    ) -> SymbolicExecutionResult:
        paths = self._extract_execution_paths(method_body)
        
        feasible_paths = []
        infeasible_count = 0
        suggested_inputs: Dict[str, List[Any]] = {}
        
        for path in paths:
            is_feasible, inputs = self.constraint_solver.solve(path)
            path.is_feasible = is_feasible
            path.input_values = inputs
            
            if is_feasible:
                feasible_paths.append(path)
                for var, val in inputs.items():
                    if var not in suggested_inputs:
                        suggested_inputs[var] = []
                    if val not in suggested_inputs[var]:
                        suggested_inputs[var].append(val)
            else:
                infeasible_count += 1
        
        uncovered_branches = self._find_uncovered_branches(method_body, feasible_paths)
        
        total_branches = len(self.IF_PATTERN.findall(method_body)) * 2
        covered_branches = total_branches - len(uncovered_branches)
        coverage = covered_branches / max(1, total_branches)
        
        return SymbolicExecutionResult(
            source_file="",
            method_name=method_name,
            total_paths=len(paths),
            feasible_paths=len(feasible_paths),
            infeasible_paths=infeasible_count,
            coverage_estimate=coverage,
            paths=feasible_paths,
            uncovered_branches=uncovered_branches,
            suggested_inputs=suggested_inputs,
        )
    
    def _extract_execution_paths(self, method_body: str) -> List[ExecutionPath]:
        paths = []
        
        if_conditions = self._parse_if_conditions(method_body)
        
        if not if_conditions:
            self.path_counter += 1
            paths.append(ExecutionPath(path_id=f"path_{self.path_counter}"))
            return paths
        
        num_branches = len(if_conditions)
        num_paths = 2 ** num_branches
        
        for i in range(num_paths):
            self.path_counter += 1
            path = ExecutionPath(path_id=f"path_{self.path_counter}")
            
            for j, condition in enumerate(if_conditions):
                take_true = (i >> j) & 1 == 0
                
                path_condition = PathCondition(
                    variable=condition["variable"],
                    constraint_type=condition["constraint_type"],
                    value=condition["value"],
                    negated=not take_true,
                )
                path.add_condition(path_condition)
            
            paths.append(path)
        
        return paths[:16]
    
    def _parse_if_conditions(self, code: str) -> List[Dict[str, Any]]:
        conditions = []
        
        for match in self.IF_PATTERN.finditer(code):
            condition_str = match.group(1).strip()
            parsed = self._parse_condition_string(condition_str)
            if parsed:
                conditions.append(parsed)
        
        return conditions
    
    def _parse_condition_string(self, condition: str) -> Optional[Dict[str, Any]]:
        condition = condition.strip()
        
        if "==" in condition:
            parts = condition.split("==")
            if len(parts) == 2:
                return {
                    "variable": parts[0].strip(),
                    "constraint_type": PathConstraintType.EQUALS,
                    "value": parts[1].strip().strip('"\''),
                }
        
        if "!=" in condition:
            parts = condition.split("!=")
            if len(parts) == 2:
                return {
                    "variable": parts[0].strip(),
                    "constraint_type": PathConstraintType.NOT_EQUALS,
                    "value": parts[1].strip().strip('"\''),
                }
        
        for op, constraint_type in self.CONDITION_OPERATORS:
            if op in condition and op not in ("==", "!="):
                parts = condition.split(op)
                if len(parts) == 2:
                    return {
                        "variable": parts[0].strip(),
                        "constraint_type": constraint_type,
                        "value": parts[1].strip(),
                    }
        
        if "null" in condition.lower():
            is_not_null = "!" in condition or "!=" in condition
            var_match = re.match(r'!?(\w+)\s*(?:==|!=)?\s*null', condition, re.IGNORECASE)
            if var_match:
                return {
                    "variable": var_match.group(1),
                    "constraint_type": PathConstraintType.IS_NOT_NULL if is_not_null else PathConstraintType.IS_NULL,
                    "value": None,
                }
        
        return None
    
    def _find_uncovered_branches(
        self,
        method_body: str,
        feasible_paths: List[ExecutionPath],
    ) -> List[Tuple[int, str]]:
        uncovered = []
        
        lines = method_body.split('\n')
        for i, line in enumerate(lines, 1):
            if 'if' in line and '(' in line:
                true_covered = False
                false_covered = False
                
                for path in feasible_paths:
                    for cond in path.conditions:
                        if not cond.negated:
                            true_covered = True
                        else:
                            false_covered = True
                
                if not true_covered:
                    uncovered.append((i, "true_branch"))
                if not false_covered:
                    uncovered.append((i, "false_branch"))
        
        return uncovered


class TestValidator:
    
    def __init__(self):
        self.executor = SymbolicExecutor()
    
    def validate_test_coverage(
        self,
        test_code: str,
        source_code: str,
        method_name: str,
        method_body: str,
    ) -> Dict[str, Any]:
        symbolic_result = self.executor.analyze_method(
            source_code,
            method_name,
            method_body,
        )
        
        test_paths = self._extract_test_paths(test_code)
        
        coverage_gaps = self._identify_coverage_gaps(
            symbolic_result,
            test_paths,
        )
        
        suggestions = self._generate_test_suggestions(
            symbolic_result,
            coverage_gaps,
        )
        
        return {
            "symbolic_analysis": symbolic_result.to_dict(),
            "test_path_count": len(test_paths),
            "coverage_gaps": coverage_gaps,
            "suggestions": suggestions,
            "validation_score": self._calculate_validation_score(
                symbolic_result,
                len(test_paths),
            ),
        }
    
    def _extract_test_paths(self, test_code: str) -> List[Dict[str, Any]]:
        paths = []
        
        test_pattern = re.compile(
            r'@Test\s*(?:\([^)]*\))?\s*'
            r'(?:public\s+)?(?:void\s+)?'
            r'(\w+)\s*\([^)]*\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}',
            re.MULTILINE | re.DOTALL
        )
        
        for match in test_pattern.finditer(test_code):
            test_name = match.group(1)
            test_body = match.group(2)
            
            path_info = {
                "test_name": test_name,
                "assertions": self._count_assertions(test_body),
                "method_calls": self._extract_method_calls(test_body),
                "input_values": self._extract_input_values(test_body),
            }
            paths.append(path_info)
        
        return paths
    
    def _count_assertions(self, code: str) -> int:
        assertion_pattern = re.compile(r'assert\w+\s*\(', re.IGNORECASE)
        return len(assertion_pattern.findall(code))
    
    def _extract_method_calls(self, code: str) -> List[str]:
        call_pattern = re.compile(r'\.(\w+)\s*\(')
        return list(set(call_pattern.findall(code)))
    
    def _extract_input_values(self, code: str) -> Dict[str, List[Any]]:
        values: Dict[str, List[Any]] = {}
        
        int_pattern = re.compile(r'(\w+)\s*=\s*(-?\d+)')
        for match in int_pattern.finditer(code):
            var_name = match.group(1)
            value = int(match.group(2))
            if var_name not in values:
                values[var_name] = []
            values[var_name].append(value)
        
        string_pattern = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
        for match in string_pattern.finditer(code):
            var_name = match.group(1)
            value = match.group(2)
            if var_name not in values:
                values[var_name] = []
            values[var_name].append(value)
        
        return values
    
    def _identify_coverage_gaps(
        self,
        symbolic_result: SymbolicExecutionResult,
        test_paths: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        gaps = []
        
        for branch in symbolic_result.uncovered_branches:
            gaps.append({
                "type": "uncovered_branch",
                "line": branch[0],
                "branch_type": branch[1],
                "description": f"Branch at line {branch[0]} ({branch[1]}) is not covered",
            })
        
        for path in symbolic_result.paths:
            if path.is_feasible:
                path_covered = False
                for test_path in test_paths:
                    if self._path_is_covered(path, test_path):
                        path_covered = True
                        break
                
                if not path_covered:
                    gaps.append({
                        "type": "uncovered_path",
                        "path_id": path.path_id,
                        "conditions": [c.to_dict() for c in path.conditions],
                        "description": f"Execution path {path.path_id} is not covered",
                    })
        
        return gaps
    
    def _path_is_covered(
        self,
        symbolic_path: ExecutionPath,
        test_path: Dict[str, Any],
    ) -> bool:
        test_inputs = test_path.get("input_values", {})
        
        for condition in symbolic_path.conditions:
            var = condition.variable
            if var in test_inputs:
                test_val = test_inputs[var]
                if not self._condition_satisfied(condition, test_val):
                    return False
        
        return True
    
    def _condition_satisfied(self, condition: PathCondition, value: Any) -> bool:
        if condition.constraint_type == PathConstraintType.IS_NULL:
            result = value is None
        elif condition.constraint_type == PathConstraintType.IS_NOT_NULL:
            result = value is not None
        elif condition.constraint_type == PathConstraintType.EQUALS:
            result = value == condition.value
        elif condition.constraint_type == PathConstraintType.NOT_EQUALS:
            result = value != condition.value
        else:
            result = True
        
        return not result if condition.negated else result
    
    def _generate_test_suggestions(
        self,
        symbolic_result: SymbolicExecutionResult,
        coverage_gaps: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        suggestions = []
        
        for gap in coverage_gaps:
            if gap["type"] == "uncovered_branch":
                line = gap["line"]
                branch_type = gap["branch_type"]
                
                suggestion = {
                    "type": "add_branch_test",
                    "target_line": line,
                    "branch_type": branch_type,
                    "suggested_code": self._generate_branch_test_code(
                        line,
                        branch_type,
                        symbolic_result.suggested_inputs,
                    ),
                }
                suggestions.append(suggestion)
            
            elif gap["type"] == "uncovered_path":
                path_conditions = gap.get("conditions", [])
                
                suggestion = {
                    "type": "add_path_test",
                    "path_id": gap["path_id"],
                    "conditions": path_conditions,
                    "suggested_inputs": symbolic_result.suggested_inputs,
                }
                suggestions.append(suggestion)
        
        return suggestions
    
    def _generate_branch_test_code(
        self,
        line: int,
        branch_type: str,
        suggested_inputs: Dict[str, List[Any]],
    ) -> str:
        input_setup = []
        for var, values in suggested_inputs.items():
            if values:
                input_setup.append(f"Object {var} = {repr(values[0])};")
        
        setup_code = "\n        ".join(input_setup) if input_setup else "// Setup test data"
        
        return f"""@Test
    @DisplayName("testBranch_line{line}_{branch_type}")
    void testBranch_line{line}_{branch_type}() {{
        // Arrange
        {setup_code}
        
        // Act
        // Add method call that covers branch at line {line}
        
        // Assert
        // Add appropriate assertions
    }}"""
    
    def _calculate_validation_score(
        self,
        symbolic_result: SymbolicExecutionResult,
        test_path_count: int,
    ) -> float:
        if symbolic_result.total_paths == 0:
            return 1.0
        
        path_ratio = test_path_count / max(1, symbolic_result.feasible_paths)
        path_score = min(1.0, path_ratio)
        
        coverage_score = symbolic_result.coverage_estimate
        
        return (path_score * 0.4 + coverage_score * 0.6) * 100


class HybridValidator:
    
    def __init__(self):
        self.test_validator = TestValidator()
    
    def validate_and_enhance(
        self,
        test_code: str,
        source_code: str,
        class_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        results = {
            "validations": [],
            "overall_score": 0.0,
            "enhancement_suggestions": [],
        }
        
        methods = class_info.get("methods", [])
        total_score = 0.0
        
        for method in methods:
            method_name = method.get("name", "")
            method_body = self._extract_method_body(source_code, method_name)
            
            if method_body:
                validation = self.test_validator.validate_test_coverage(
                    test_code,
                    source_code,
                    method_name,
                    method_body,
                )
                results["validations"].append({
                    "method": method_name,
                    **validation,
                })
                total_score += validation["validation_score"]
        
        if results["validations"]:
            results["overall_score"] = total_score / len(results["validations"])
        
        results["enhancement_suggestions"] = self._prioritize_suggestions(
            results["validations"]
        )
        
        return results
    
    def _extract_method_body(self, source_code: str, method_name: str) -> str:
        pattern = re.compile(
            rf'(?:public|private|protected)?\s*'
            rf'(?:static\s+)?'
            rf'\w+\s+{re.escape(method_name)}\s*\([^)]*\)\s*\{{',
            re.MULTILINE
        )
        
        match = pattern.search(source_code)
        if not match:
            return ""
        
        start = match.end() - 1
        brace_count = 1
        end = start + 1
        
        for i, char in enumerate(source_code[start + 1:], start + 1):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break
        
        return source_code[start:end]
    
    def _prioritize_suggestions(
        self,
        validations: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        all_suggestions = []
        
        for validation in validations:
            suggestions = validation.get("suggestions", [])
            for suggestion in suggestions:
                suggestion["method"] = validation.get("method", "")
                suggestion["priority"] = self._calculate_suggestion_priority(
                    suggestion,
                    validation.get("validation_score", 0),
                )
                all_suggestions.append(suggestion)
        
        return sorted(
            all_suggestions,
            key=lambda s: s.get("priority", 0),
            reverse=True,
        )
    
    def _calculate_suggestion_priority(
        self,
        suggestion: Dict[str, Any],
        validation_score: float,
    ) -> int:
        base_priority = 50
        
        if suggestion.get("type") == "add_branch_test":
            base_priority += 20
        elif suggestion.get("type") == "add_path_test":
            base_priority += 10
        
        if validation_score < 50:
            base_priority += 30
        elif validation_score < 70:
            base_priority += 15
        
        return base_priority
