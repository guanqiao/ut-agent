"""SBST 生成器模块测试."""

import pytest
from ut_agent.tools.sbst_generator import (
    SBSTEngine,
    HybridTestGenerator,
    SBSTConfiguration,
    SearchStrategy,
    TestCase,
    TestCaseType,
    TestChromosome,
    FitnessCalculator,
    BranchTarget,
    JavaTestGenerator,
)


class TestSBSTConfiguration:
    
    def test_default_configuration(self):
        config = SBSTConfiguration()
        assert config.population_size == 50
        assert config.max_generations == 100
        assert config.crossover_rate == 0.8
        assert config.mutation_rate == 0.1
        assert config.strategy == SearchStrategy.MOSA
    
    def test_custom_configuration(self):
        config = SBSTConfiguration(
            population_size=100,
            max_generations=50,
            strategy=SearchStrategy.GA,
        )
        assert config.population_size == 100
        assert config.max_generations == 50
        assert config.strategy == SearchStrategy.GA


class TestTestCase:
    
    def test_test_case_creation(self):
        test_case = TestCase(
            test_id="test_001",
            test_type=TestCaseType.METHOD_CALL,
            code="@Test void testMethod() {}",
            target_method="methodA",
            target_class="ClassA",
        )
        assert test_case.test_id == "test_001"
        assert test_case.test_type == TestCaseType.METHOD_CALL
        assert test_case.fitness == 0.0
    
    def test_test_case_to_dict(self):
        test_case = TestCase(
            test_id="test_002",
            test_type=TestCaseType.ASSERTION,
            code="assert true",
            target_method="methodB",
            target_class="ClassB",
            fitness=0.8,
        )
        result = test_case.to_dict()
        assert result["test_id"] == "test_002"
        assert result["fitness"] == 0.8


class TestTestChromosome:
    
    def test_chromosome_copy(self):
        test_case = TestCase(
            test_id="test_003",
            test_type=TestCaseType.METHOD_CALL,
            code="code",
            target_method="m",
            target_class="C",
        )
        chromosome = TestChromosome(test_case=test_case, age=5)
        copied = chromosome.copy()
        
        assert copied.test_case.test_id == "test_003_copy"
        assert copied.age == 5
        assert copied is not chromosome


class TestFitnessCalculator:
    
    def test_calculate_fitness(self):
        targets = [
            BranchTarget(
                class_name="ClassA",
                method_name="methodA",
                line_number=10,
                branch_type="if",
                branch_id="b1",
            )
        ]
        calculator = FitnessCalculator(targets)
        
        test_case = TestCase(
            test_id="test_001",
            test_type=TestCaseType.METHOD_CALL,
            code="target.methodA();",
            target_method="methodA",
            target_class="ClassA",
            assertions=["assertNotNull"],
        )
        
        fitness = calculator.calculate_fitness(
            test_case,
            ["coverage", "assertion", "complexity"],
        )
        
        assert fitness >= 0.0


class TestJavaTestGenerator:
    
    def test_generate_normal_test(self):
        class_info = {
            "class_name": "Calculator",
            "package": "com.example",
            "methods": [
                {
                    "name": "add",
                    "parameters": [{"type": "int", "name": "a"}, {"type": "int", "name": "b"}],
                    "return_type": "int",
                }
            ],
        }
        
        generator = JavaTestGenerator(class_info)
        tests = generator.generate("Calculator", "add")
        
        assert len(tests) > 0
        assert any("add" in t.code for t in tests)
    
    def test_generate_boundary_tests(self):
        class_info = {
            "class_name": "MathUtils",
            "package": "com.example",
            "methods": [
                {
                    "name": "divide",
                    "parameters": [{"type": "int", "name": "a"}, {"type": "int", "name": "b"}],
                    "return_type": "int",
                }
            ],
        }
        
        generator = JavaTestGenerator(class_info)
        tests = generator.generate("MathUtils", "divide")
        
        boundary_tests = [t for t in tests if "boundary" in t.test_id.lower()]
        assert len(boundary_tests) > 0
    
    def test_mutate_test_case(self):
        class_info = {
            "class_name": "Service",
            "package": "com.example",
            "methods": [{"name": "process", "parameters": [], "return_type": "void"}],
        }
        
        generator = JavaTestGenerator(class_info)
        original = TestCase(
            test_id="test_original",
            test_type=TestCaseType.METHOD_CALL,
            code="@Test void test() { int x = 5; }",
            target_method="process",
            target_class="Service",
        )
        
        mutated = generator.mutate(original)
        
        assert mutated.test_id != original.test_id


class TestSBSTEngine:
    
    def test_engine_initialization(self):
        class_info = {
            "class_name": "TestService",
            "package": "com.test",
            "methods": [{"name": "doSomething", "parameters": [], "return_type": "void"}],
        }
        
        config = SBSTConfiguration(
            population_size=10,
            max_generations=5,
        )
        
        engine = SBSTEngine(class_info, config)
        
        assert engine.config.population_size == 10
        assert engine.generator is not None
    
    def test_evolve_returns_tests(self):
        class_info = {
            "class_name": "SimpleService",
            "package": "com.test",
            "methods": [{"name": "execute", "parameters": [], "return_type": "void"}],
        }
        
        config = SBSTConfiguration(
            population_size=5,
            max_generations=2,
        )
        
        engine = SBSTEngine(class_info, config)
        tests = engine.evolve()
        
        assert isinstance(tests, list)


class TestHybridTestGenerator:
    
    def test_hybrid_generator_creation(self):
        class_info = {
            "class_name": "HybridService",
            "package": "com.test",
            "methods": [{"name": "run", "parameters": [], "return_type": "void"}],
        }
        
        generator = HybridTestGenerator(class_info)
        
        assert generator.sbst_engine is not None
    
    def test_generate_optimized_tests(self):
        class_info = {
            "class_name": "OptService",
            "package": "com.test",
            "methods": [{"name": "process", "parameters": [], "return_type": "void"}],
        }
        
        generator = HybridTestGenerator(
            class_info,
            llm_generated_tests=["@Test void llmTest() {}"],
        )
        
        tests = generator.generate_optimized_tests()
        
        assert isinstance(tests, list)
    
    def test_generate_test_class(self):
        class_info = {
            "class_name": "TestClass",
            "package": "com.test",
            "methods": [],
        }
        
        generator = HybridTestGenerator(class_info)
        
        test_case = TestCase(
            test_id="test_001",
            test_type=TestCaseType.METHOD_CALL,
            code="@Test void test() {}",
            target_method="method",
            target_class="TestClass",
        )
        
        test_class_code = generator.generate_test_class([test_case])
        
        assert "class TestClassTest" in test_class_code
        assert "@Test" in test_class_code
