"""基于搜索的软件测试 (SBST) 模块.

实现 EvoSuite 风格的测试生成算法，与 LLM 生成的测试形成混合架构。
"""

import random
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from abc import ABC, abstractmethod


class SearchStrategy(Enum):
    RANDOM = "random"
    GA = "genetic_algorithm"
    MOSA = "many_objective_search"
    DYNAMOSA = "dynamic_mosa"


class TestCaseType(Enum):
    METHOD_CALL = "method_call"
    CONSTRUCTOR = "constructor"
    FIELD_ACCESS = "field_access"
    ASSERTION = "assertion"


@dataclass
class TestCase:
    test_id: str
    test_type: TestCaseType
    code: str
    target_method: str
    target_class: str
    fitness: float = 0.0
    coverage: float = 0.0
    mutation_score: float = 0.0
    assertions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "test_type": self.test_type.value,
            "code": self.code,
            "target_method": self.target_method,
            "target_class": self.target_class,
            "fitness": round(self.fitness, 4),
            "coverage": round(self.coverage, 4),
            "mutation_score": round(self.mutation_score, 4),
            "assertions": self.assertions,
            "dependencies": self.dependencies,
        }


@dataclass
class TestChromosome:
    test_case: TestCase
    age: int = 0
    rank: int = 0
    crowding_distance: float = 0.0
    
    def copy(self) -> "TestChromosome":
        return TestChromosome(
            test_case=TestCase(
                test_id=f"{self.test_case.test_id}_copy",
                test_type=self.test_case.test_type,
                code=self.test_case.code,
                target_method=self.test_case.target_method,
                target_class=self.test_case.target_class,
                fitness=self.test_case.fitness,
                coverage=self.test_case.coverage,
                mutation_score=self.test_case.mutation_score,
                assertions=self.test_case.assertions.copy(),
                dependencies=self.test_case.dependencies.copy(),
            ),
            age=self.age,
            rank=self.rank,
            crowding_distance=self.crowding_distance,
        )


@dataclass
class BranchTarget:
    class_name: str
    method_name: str
    line_number: int
    branch_type: str
    branch_id: str
    covered: bool = False
    covering_tests: List[str] = field(default_factory=list)


@dataclass
class SBSTConfiguration:
    population_size: int = 50
    max_generations: int = 100
    crossover_rate: float = 0.8
    mutation_rate: float = 0.1
    elite_size: int = 5
    max_test_length: int = 50
    timeout_seconds: int = 60
    seed: Optional[int] = None
    strategy: SearchStrategy = SearchStrategy.MOSA


class FitnessCalculator:
    
    def __init__(self, branch_targets: List[BranchTarget]):
        self.branch_targets = branch_targets
        self.coverage_cache: Dict[str, float] = {}
    
    def calculate_branch_coverage(self, test_case: TestCase) -> float:
        covered = 0
        total = len(self.branch_targets)
        
        if total == 0:
            return 0.0
        
        for target in self.branch_targets:
            if self._is_branch_covered(test_case, target):
                covered += 1
        
        return covered / total
    
    def calculate_approach_level(
        self,
        test_case: TestCase,
        target: BranchTarget,
        control_flow_graph: Dict[str, List[str]],
    ) -> int:
        return 0
    
    def calculate_branch_distance(
        self,
        test_case: TestCase,
        target: BranchTarget,
    ) -> float:
        return 0.0
    
    def calculate_fitness(
        self,
        test_case: TestCase,
        objectives: List[str],
    ) -> float:
        fitness = 0.0
        
        branch_coverage = self.calculate_branch_coverage(test_case)
        fitness += branch_coverage * 0.5
        
        assertion_score = len(test_case.assertions) / max(1, test_case.code.count('\n'))
        fitness += min(1.0, assertion_score) * 0.3
        
        complexity_score = self._calculate_complexity_score(test_case)
        fitness += complexity_score * 0.2
        
        return fitness
    
    def _is_branch_covered(
        self,
        test_case: TestCase,
        target: BranchTarget,
    ) -> bool:
        code = test_case.code
        
        if target.method_name in code:
            return True
        
        return False
    
    def _calculate_complexity_score(self, test_case: TestCase) -> float:
        lines = [l.strip() for l in test_case.code.split('\n') if l.strip()]
        
        if len(lines) < 5:
            return 0.5
        elif len(lines) < 20:
            return 1.0
        else:
            return max(0.0, 1.0 - (len(lines) - 20) / 50)


class TestGenerator(ABC):
    
    @abstractmethod
    def generate(self, target_class: str, target_method: str) -> List[TestCase]:
        pass
    
    @abstractmethod
    def mutate(self, test_case: TestCase) -> TestCase:
        pass
    
    @abstractmethod
    def crossover(
        self,
        parent1: TestCase,
        parent2: TestCase,
    ) -> Tuple[TestCase, TestCase]:
        pass


class JavaTestGenerator(TestGenerator):
    
    def __init__(self, class_info: Dict[str, Any]):
        self.class_info = class_info
        self.methods = class_info.get("methods", [])
        self.fields = class_info.get("fields", [])
        self.class_name = class_info.get("class_name", "UnknownClass")
        self.package = class_info.get("package", "")
        self._test_counter = 0
    
    def generate(self, target_class: str, target_method: str) -> List[TestCase]:
        test_cases = []
        
        for method in self.methods:
            if method.get("name") == target_method or target_method == "*":
                tests = self._generate_tests_for_method(method)
                test_cases.extend(tests)
        
        return test_cases
    
    def _generate_tests_for_method(self, method: Dict[str, Any]) -> List[TestCase]:
        test_cases = []
        method_name = method.get("name", "unknown")
        params = method.get("parameters", [])
        return_type = method.get("return_type", "void")
        
        normal_test = self._generate_normal_test(method_name, params, return_type)
        test_cases.append(normal_test)
        
        boundary_tests = self._generate_boundary_tests(method_name, params, return_type)
        test_cases.extend(boundary_tests)
        
        exception_test = self._generate_exception_test(method_name, params)
        test_cases.append(exception_test)
        
        return test_cases
    
    def _generate_normal_test(
        self,
        method_name: str,
        params: List[Dict],
        return_type: str,
    ) -> TestCase:
        self._test_counter += 1
        test_id = f"test_{method_name}_{self._test_counter}"
        
        param_values = self._generate_param_values(params)
        param_str = ", ".join(param_values)
        
        assertions = []
        if return_type != "void":
            assertions.append(f"assertNotNull(result)")
        
        code = f"""@Test
@DisplayName("test{method_name}Normal")
void {test_id}() {{
    // Arrange
    {self.class_name} target = new {self.class_name}();
    
    // Act
    {return_type} result = target.{method_name}({param_str});
    
    // Assert
    {chr(10).join('    ' + a + ';' for a in assertions)}
}}"""
        
        return TestCase(
            test_id=test_id,
            test_type=TestCaseType.METHOD_CALL,
            code=code,
            target_method=method_name,
            target_class=self.class_name,
            assertions=assertions,
        )
    
    def _generate_boundary_tests(
        self,
        method_name: str,
        params: List[Dict],
        return_type: str,
    ) -> List[TestCase]:
        tests = []
        
        for i, param in enumerate(params):
            param_type = param.get("type", "Object")
            param_name = param.get("name", f"param{i}")
            
            boundary_values = self._get_boundary_values(param_type)
            
            for bv in boundary_values[:2]:
                self._test_counter += 1
                test_id = f"test_{method_name}_boundary_{self._test_counter}"
                
                param_values = self._generate_param_values(params)
                param_values[i] = bv
                
                code = f"""@Test
@DisplayName("test{method_name}Boundary_{param_name}")
void {test_id}() {{
    // Arrange
    {self.class_name} target = new {self.class_name}();
    
    // Act & Assert
    assertDoesNotThrow(() -> target.{method_name}({', '.join(param_values)}));
}}"""
                
                tests.append(TestCase(
                    test_id=test_id,
                    test_type=TestCaseType.METHOD_CALL,
                    code=code,
                    target_method=method_name,
                    target_class=self.class_name,
                    assertions=["assertDoesNotThrow"],
                ))
        
        return tests
    
    def _generate_exception_test(
        self,
        method_name: str,
        params: List[Dict],
    ) -> TestCase:
        self._test_counter += 1
        test_id = f"test_{method_name}_exception_{self._test_counter}"
        
        null_params = ["null" if p.get("type", "").startswith(("String", "Object", "List")) 
                       else self._get_default_value(p.get("type", "Object"))
                       for p in params]
        
        code = f"""@Test
@DisplayName("test{method_name}Exception")
void {test_id}() {{
    // Arrange
    {self.class_name} target = new {self.class_name}();
    
    // Act & Assert
    assertThrows(Exception.class, () -> target.{method_name}({', '.join(null_params)}));
}}"""
        
        return TestCase(
            test_id=test_id,
            test_type=TestCaseType.METHOD_CALL,
            code=code,
            target_method=method_name,
            target_class=self.class_name,
            assertions=["assertThrows"],
        )
    
    def _generate_param_values(self, params: List[Dict]) -> List[str]:
        values = []
        for p in params:
            param_type = p.get("type", "Object")
            values.append(self._get_default_value(param_type))
        return values
    
    def _get_default_value(self, type_name: str) -> str:
        defaults = {
            "int": "0",
            "long": "0L",
            "double": "0.0",
            "float": "0.0f",
            "boolean": "false",
            "char": "'\\0'",
            "String": "\"test\"",
            "Integer": "Integer.valueOf(0)",
            "Long": "Long.valueOf(0L)",
            "Double": "Double.valueOf(0.0)",
            "Boolean": "Boolean.FALSE",
            "List": "Collections.emptyList()",
            "Map": "Collections.emptyMap()",
            "Set": "Collections.emptySet()",
        }
        
        if type_name in defaults:
            return defaults[type_name]
        
        if type_name.endswith("[]"):
            return f"new {type_name}{{}}"
        
        if "<" in type_name:
            base_type = type_name.split("<")[0]
            if base_type == "List":
                return "Collections.emptyList()"
            if base_type == "Map":
                return "Collections.emptyMap()"
            if base_type == "Set":
                return "Collections.emptySet()"
        
        return "null"
    
    def _get_boundary_values(self, type_name: str) -> List[str]:
        boundaries = {
            "int": ["Integer.MAX_VALUE", "Integer.MIN_VALUE", "0", "-1", "1"],
            "long": ["Long.MAX_VALUE", "Long.MIN_VALUE", "0L", "-1L", "1L"],
            "double": ["Double.MAX_VALUE", "Double.MIN_VALUE", "0.0", "-1.0", "1.0", "Double.NaN"],
            "float": ["Float.MAX_VALUE", "Float.MIN_VALUE", "0.0f", "-1.0f", "1.0f", "Float.NaN"],
            "String": ["\"\"", "\" \"", "\"null\"", "\"a\"", "\"test_value_123\""],
        }
        
        return boundaries.get(type_name, ["null"])
    
    def mutate(self, test_case: TestCase) -> TestCase:
        self._test_counter += 1
        mutated_code = test_case.code
        
        mutations = [
            self._mutate_parameter_value,
            self._mutate_assertion,
            self._add_boundary_check,
        ]
        
        mutation_func = random.choice(mutations)
        mutated_code = mutation_func(mutated_code)
        
        return TestCase(
            test_id=f"{test_case.test_id}_mut_{self._test_counter}",
            test_type=test_case.test_type,
            code=mutated_code,
            target_method=test_case.target_method,
            target_class=test_case.target_class,
            assertions=test_case.assertions.copy(),
        )
    
    def _mutate_parameter_value(self, code: str) -> str:
        int_pattern = re.compile(r'\b(\d+)\b')
        
        def replace_int(match):
            old_val = int(match.group(1))
            new_val = old_val + random.randint(-10, 10)
            return str(new_val)
        
        return int_pattern.sub(replace_int, code, count=1)
    
    def _mutate_assertion(self, code: str) -> str:
        assertion_replacements = {
            "assertTrue": "assertFalse",
            "assertFalse": "assertTrue",
            "assertEquals": "assertNotEquals",
            "assertNotNull": "assertNull",
        }
        
        for old_assert, new_assert in assertion_replacements.items():
            if old_assert in code and random.random() < 0.3:
                return code.replace(old_assert, new_assert, 1)
        
        return code
    
    def _add_boundary_check(self, code: str) -> str:
        if "MAX_VALUE" not in code and "MIN_VALUE" not in code:
            code = code.replace(
                "// Act",
                "// Act - boundary test\n    // Act"
            )
        
        return code
    
    def crossover(
        self,
        parent1: TestCase,
        parent2: TestCase,
    ) -> Tuple[TestCase, TestCase]:
        self._test_counter += 2
        
        lines1 = parent1.code.split('\n')
        lines2 = parent2.code.split('\n')
        
        crossover_point = random.randint(1, min(len(lines1), len(lines2)) - 1)
        
        child1_code = '\n'.join(lines1[:crossover_point] + lines2[crossover_point:])
        child2_code = '\n'.join(lines2[:crossover_point] + lines1[crossover_point:])
        
        child1 = TestCase(
            test_id=f"cross_{self._test_counter - 1}",
            test_type=parent1.test_type,
            code=child1_code,
            target_method=parent1.target_method,
            target_class=parent1.target_class,
            assertions=parent1.assertions[:len(parent1.assertions)//2] + 
                      parent2.assertions[len(parent2.assertions)//2:],
        )
        
        child2 = TestCase(
            test_id=f"cross_{self._test_counter}",
            test_type=parent2.test_type,
            code=child2_code,
            target_method=parent2.target_method,
            target_class=parent2.target_class,
            assertions=parent2.assertions[:len(parent2.assertions)//2] + 
                      parent1.assertions[len(parent1.assertions)//2:],
        )
        
        return child1, child2


class SBSTEngine:
    
    def __init__(
        self,
        class_info: Dict[str, Any],
        config: Optional[SBSTConfiguration] = None,
    ):
        self.class_info = class_info
        self.config = config or SBSTConfiguration()
        self.generator = JavaTestGenerator(class_info)
        self.fitness_calculator = FitnessCalculator([])
        self.population: List[TestChromosome] = []
        self.archive: List[TestCase] = []
        self.generation = 0
        
        if self.config.seed is not None:
            random.seed(self.config.seed)
    
    def evolve(self) -> List[TestCase]:
        self._initialize_population()
        
        for gen in range(self.config.max_generations):
            self.generation = gen
            
            self._evaluate_population()
            
            self._update_archive()
            
            if self._termination_condition():
                break
            
            self._evolve_population()
        
        return self.archive
    
    def _initialize_population(self) -> None:
        self.population = []
        
        target_methods = [m.get("name") for m in self.class_info.get("methods", [])]
        
        for method_name in target_methods:
            tests = self.generator.generate(
                self.class_info.get("class_name", ""),
                method_name,
            )
            
            for test in tests:
                chromosome = TestChromosome(test_case=test)
                self.population.append(chromosome)
        
        while len(self.population) < self.config.population_size:
            if self.population:
                parent = random.choice(self.population)
                mutated = self.generator.mutate(parent.test_case)
                self.population.append(TestChromosome(test_case=mutated))
    
    def _evaluate_population(self) -> None:
        for chromosome in self.population:
            fitness = self.fitness_calculator.calculate_fitness(
                chromosome.test_case,
                objectives=["coverage", "assertion", "complexity"],
            )
            chromosome.test_case.fitness = fitness
    
    def _update_archive(self) -> None:
        self.population.sort(key=lambda c: c.test_case.fitness, reverse=True)
        
        for chromosome in self.population[:self.config.elite_size]:
            if chromosome.test_case.fitness > 0.5:
                if not any(t.test_id == chromosome.test_case.test_id for t in self.archive):
                    self.archive.append(chromosome.test_case)
    
    def _evolve_population(self) -> None:
        new_population: List[TestChromosome] = []
        
        self.population.sort(key=lambda c: c.test_case.fitness, reverse=True)
        for i in range(self.config.elite_size):
            elite = self.population[i].copy()
            elite.age += 1
            new_population.append(elite)
        
        while len(new_population) < self.config.population_size:
            if random.random() < self.config.crossover_rate and len(self.population) >= 2:
                parent1, parent2 = random.sample(self.population[:20], 2)
                child1, child2 = self.generator.crossover(
                    parent1.test_case,
                    parent2.test_case,
                )
                new_population.append(TestChromosome(test_case=child1))
                if len(new_population) < self.config.population_size:
                    new_population.append(TestChromosome(test_case=child2))
            
            if random.random() < self.config.mutation_rate and self.population:
                parent = random.choice(self.population)
                mutated = self.generator.mutate(parent.test_case)
                new_population.append(TestChromosome(test_case=mutated))
        
        self.population = new_population[:self.config.population_size]
    
    def _termination_condition(self) -> bool:
        if len(self.archive) >= 10:
            avg_fitness = sum(t.fitness for t in self.archive) / len(self.archive)
            if avg_fitness > 0.9:
                return True
        
        return False
    
    def get_best_tests(self, n: int = 5) -> List[TestCase]:
        sorted_archive = sorted(
            self.archive,
            key=lambda t: t.fitness,
            reverse=True,
        )
        return sorted_archive[:n]


class HybridTestGenerator:
    
    def __init__(
        self,
        class_info: Dict[str, Any],
        llm_generated_tests: Optional[List[str]] = None,
    ):
        self.class_info = class_info
        self.llm_tests = llm_generated_tests or []
        self.sbst_engine = SBSTEngine(class_info)
    
    def generate_optimized_tests(self) -> List[TestCase]:
        sbst_tests = self.sbst_engine.evolve()
        
        llm_test_cases = self._convert_llm_tests()
        
        all_tests = sbst_tests + llm_test_cases
        
        optimized = self._remove_redundant_tests(all_tests)
        
        return optimized
    
    def _convert_llm_tests(self) -> List[TestCase]:
        test_cases = []
        
        for i, code in enumerate(self.llm_tests):
            test_case = TestCase(
                test_id=f"llm_test_{i}",
                test_type=TestCaseType.METHOD_CALL,
                code=code,
                target_method=self._extract_target_method(code),
                target_class=self.class_info.get("class_name", ""),
                fitness=0.8,
            )
            test_cases.append(test_case)
        
        return test_cases
    
    def _extract_target_method(self, code: str) -> str:
        method_pattern = re.compile(r'\.(\w+)\s*\(')
        matches = method_pattern.findall(code)
        
        for method in matches:
            if not method.startswith(('assert', 'verify', 'when', 'mock')):
                return method
        
        return "unknown"
    
    def _remove_redundant_tests(self, tests: List[TestCase]) -> List[TestCase]:
        unique_tests = []
        seen_signatures = set()
        
        for test in tests:
            signature = self._get_test_signature(test)
            
            if signature not in seen_signatures:
                unique_tests.append(test)
                seen_signatures.add(signature)
        
        return unique_tests
    
    def _get_test_signature(self, test: TestCase) -> str:
        code = test.code
        
        code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'@DisplayName\([^)]+\)', '', code)
        code = re.sub(r'\s+', ' ', code).strip()
        
        return f"{test.target_method}:{hash(code)}"
    
    def generate_test_class(self, tests: List[TestCase]) -> str:
        class_name = self.class_info.get("class_name", "Unknown")
        package = self.class_info.get("package", "")
        
        test_methods = '\n\n'.join(t.code for t in tests)
        
        return f"""package {package};

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.BeforeEach;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

public class {class_name}Test {{

    private {class_name} target;

    @BeforeEach
    void setUp() {{
        target = new {class_name}();
    }}

{test_methods}
}}"""
