"""测试质量评分系统单元测试.

测试测试有效性评分、代码质量分析和覆盖深度评估。
"""

from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import pytest

from ut_agent.tools.quality_scorer import (
    TestQualityScorer,
    TestEffectivenessScore,
    TestCodeQualityScore,
    CoverageDepthScore,
    QualityReport,
    ScoringDimension,
)


class TestTestEffectivenessScore:
    """测试有效性评分测试."""

    def test_effectiveness_score_creation(self):
        """测试创建有效性评分对象."""
        score = TestEffectivenessScore(
            mutation_kill_rate=85.5,
            assertion_density=0.7,
            boundary_coverage=0.8,
            exception_coverage=0.6,
            overall_score=78.0,
        )

        assert score.mutation_kill_rate == 85.5
        assert score.assertion_density == 0.7
        assert score.overall_score == 78.0

    def test_effectiveness_score_to_dict(self):
        """测试转换为字典."""
        score = TestEffectivenessScore(
            mutation_kill_rate=90.0,
            assertion_density=0.8,
            boundary_coverage=0.9,
            exception_coverage=0.7,
            overall_score=85.0,
        )

        result = score.to_dict()

        assert result["mutation_kill_rate"] == 90.0
        assert result["overall_score"] == 85.0


class TestTestCodeQualityScore:
    """测试代码质量评分测试."""

    def test_code_quality_score_creation(self):
        """测试创建代码质量评分对象."""
        score = TestCodeQualityScore(
            readability=85,
            maintainability=80,
            naming_conventions=90,
            documentation=70,
            code_duplication=0.1,
            overall_score=81.25,
        )

        assert score.readability == 85
        assert score.maintainability == 80
        assert score.overall_score == 81.25

    def test_code_quality_score_to_dict(self):
        """测试转换为字典."""
        score = TestCodeQualityScore(
            readability=90,
            maintainability=85,
            naming_conventions=95,
            documentation=80,
            code_duplication=0.05,
            overall_score=87.5,
        )

        result = score.to_dict()

        assert result["readability"] == 90
        assert result["naming_conventions"] == 95


class TestCoverageDepthScore:
    """覆盖深度评分测试."""

    def test_coverage_depth_score_creation(self):
        """测试创建覆盖深度评分对象."""
        score = CoverageDepthScore(
            normal_path_coverage=0.9,
            boundary_path_coverage=0.7,
            exception_path_coverage=0.6,
            edge_case_coverage=0.5,
            overall_score=67.5,
        )

        assert score.normal_path_coverage == 0.9
        assert score.boundary_path_coverage == 0.7
        assert score.overall_score == 67.5

    def test_coverage_depth_score_to_dict(self):
        """测试转换为字典."""
        score = CoverageDepthScore(
            normal_path_coverage=0.95,
            boundary_path_coverage=0.8,
            exception_path_coverage=0.7,
            edge_case_coverage=0.6,
            overall_score=76.25,
        )

        result = score.to_dict()

        assert result["normal_path_coverage"] == 0.95
        assert result["edge_case_coverage"] == 0.6


class TestQualityReport:
    """质量报告测试."""

    def test_quality_report_creation(self):
        """测试创建质量报告对象."""
        effectiveness = TestEffectivenessScore(
            mutation_kill_rate=80.0,
            assertion_density=0.7,
            boundary_coverage=0.8,
            exception_coverage=0.6,
            overall_score=75.0,
        )
        code_quality = TestCodeQualityScore(
            readability=85,
            maintainability=80,
            naming_conventions=90,
            documentation=70,
            code_duplication=0.1,
            overall_score=81.25,
        )
        coverage_depth = CoverageDepthScore(
            normal_path_coverage=0.9,
            boundary_path_coverage=0.7,
            exception_path_coverage=0.6,
            edge_case_coverage=0.5,
            overall_score=67.5,
        )

        report = QualityReport(
            test_file="UserServiceTest.java",
            effectiveness=effectiveness,
            code_quality=code_quality,
            coverage_depth=coverage_depth,
            overall_score=74.58,
            grade="B",
        )

        assert report.test_file == "UserServiceTest.java"
        assert report.grade == "B"
        assert report.overall_score == 74.58

    def test_quality_report_to_dict(self):
        """测试转换为字典."""
        effectiveness = TestEffectivenessScore(
            mutation_kill_rate=90.0,
            assertion_density=0.8,
            boundary_coverage=0.9,
            exception_coverage=0.7,
            overall_score=85.0,
        )
        code_quality = TestCodeQualityScore(
            readability=90,
            maintainability=85,
            naming_conventions=95,
            documentation=80,
            code_duplication=0.05,
            overall_score=87.5,
        )
        coverage_depth = CoverageDepthScore(
            normal_path_coverage=0.95,
            boundary_path_coverage=0.8,
            exception_path_coverage=0.7,
            edge_case_coverage=0.6,
            overall_score=76.25,
        )

        report = QualityReport(
            test_file="CalculatorTest.java",
            effectiveness=effectiveness,
            code_quality=code_quality,
            coverage_depth=coverage_depth,
            overall_score=82.92,
            grade="A",
        )

        result = report.to_dict()

        assert result["test_file"] == "CalculatorTest.java"
        assert result["grade"] == "A"
        assert "effectiveness" in result
        assert "code_quality" in result
        assert "coverage_depth" in result


class TestTestQualityScorer:
    """测试质量评分器测试."""

    def test_score_effectiveness(self):
        """测试评分测试有效性."""
        test_code = '''
@Test
void testAdd() {
    Calculator calc = new Calculator();
    int result = calc.add(2, 3);
    assertEquals(5, result);
}

@Test
void testAddWithNegative() {
    Calculator calc = new Calculator();
    int result = calc.add(-2, 3);
    assertEquals(1, result);
}

@Test
void testAddWithZero() {
    Calculator calc = new Calculator();
    int result = calc.add(0, 0);
    assertEquals(0, result);
}
'''
        scorer = TestQualityScorer()
        score = scorer.score_effectiveness(test_code)

        assert isinstance(score, TestEffectivenessScore)
        assert score.assertion_density > 0
        assert score.overall_score >= 0

    def test_score_effectiveness_with_mutation_data(self):
        """测试使用变异数据评分有效性."""
        test_code = '''
@Test
void testMethod() {
    service.method();
    verify(service).method();
}
'''
        mutation_report = {
            "total_mutations": 100,
            "killed": 85,
            "survived": 15,
        }

        scorer = TestQualityScorer()
        score = scorer.score_effectiveness(test_code, mutation_report)

        assert score.mutation_kill_rate == 85.0

    def test_score_code_quality(self):
        """测试评分代码质量."""
        test_code = '''
/**
 * Calculator test class.
 */
class CalculatorTest {
    
    private Calculator calculator;
    
    @BeforeEach
    void setUp() {
        calculator = new Calculator();
    }
    
    @Test
    @DisplayName("Should add two positive numbers correctly")
    void testAddPositiveNumbers() {
        int result = calculator.add(2, 3);
        assertEquals(5, result, "Addition should work correctly");
    }
    
    @Test
    @DisplayName("Should handle negative numbers")
    void testAddNegativeNumbers() {
        int result = calculator.add(-2, -3);
        assertEquals(-5, result);
    }
}
'''
        scorer = TestQualityScorer()
        score = scorer.score_code_quality(test_code)

        assert isinstance(score, TestCodeQualityScore)
        assert score.readability > 0
        assert score.naming_conventions > 0
        assert score.documentation > 0

    def test_score_code_quality_poor_naming(self):
        """测试评分代码质量 - 差的命名."""
        test_code = '''
@Test
void m1() {
    Object a = new Object();
    Object b = new Object();
    assertNotNull(a);
}

@Test
void m2() {
    Object x = new Object();
    assertNotNull(x);
}
'''
        scorer = TestQualityScorer()
        score = scorer.score_code_quality(test_code)

        assert score.naming_conventions < 70

    def test_score_coverage_depth(self):
        """测试评分覆盖深度."""
        test_code = '''
@Test
void testNormalCase() {
    int result = calculator.add(2, 3);
    assertEquals(5, result);
}

@Test
void testBoundaryCase() {
    int result = calculator.add(Integer.MAX_VALUE, 0);
    assertEquals(Integer.MAX_VALUE, result);
}

@Test
void testExceptionCase() {
    assertThrows(IllegalArgumentException.class, () -> {
        calculator.add(null, null);
    });
}
'''
        source_code = '''
public int add(Integer a, Integer b) {
    if (a == null || b == null) {
        throw new IllegalArgumentException("Arguments cannot be null");
    }
    return a + b;
}
'''
        scorer = TestQualityScorer()
        score = scorer.score_coverage_depth(test_code, source_code)

        assert isinstance(score, CoverageDepthScore)
        assert score.normal_path_coverage > 0
        assert score.boundary_path_coverage > 0
        assert score.exception_path_coverage > 0

    def test_generate_quality_report(self):
        """测试生成质量报告."""
        test_code = '''
@Test
void testAdd() {
    Calculator calc = new Calculator();
    assertEquals(5, calc.add(2, 3));
    assertEquals(0, calc.add(0, 0));
    assertEquals(-1, calc.add(-2, 1));
}
'''
        source_code = '''
public int add(int a, int b) {
    return a + b;
}
'''
        scorer = TestQualityScorer()
        report = scorer.generate_report(test_code, source_code, "CalculatorTest.java")

        assert isinstance(report, QualityReport)
        assert report.test_file == "CalculatorTest.java"
        assert report.overall_score >= 0
        assert report.grade in ["A", "B", "C", "D", "F"]

    def test_calculate_grade(self):
        """测试计算等级."""
        scorer = TestQualityScorer()

        assert scorer.calculate_grade(95) == "A"
        assert scorer.calculate_grade(85) == "A"
        assert scorer.calculate_grade(75) == "B"
        assert scorer.calculate_grade(65) == "C"
        assert scorer.calculate_grade(55) == "D"
        assert scorer.calculate_grade(45) == "F"

    def test_score_empty_test_code(self):
        """测试评分空测试代码."""
        scorer = TestQualityScorer()
        score = scorer.score_effectiveness("")

        assert score.overall_score == 0

    def test_score_test_with_no_assertions(self):
        """测试评分无断言的测试."""
        test_code = '''
@Test
void testNoAssertion() {
    Calculator calc = new Calculator();
    calc.add(2, 3);
}
'''
        scorer = TestQualityScorer()
        score = scorer.score_effectiveness(test_code)

        assert score.assertion_density == 0

    def test_score_test_with_multiple_assertions(self):
        """测试评分多断言的测试."""
        test_code = '''
@Test
void testMultipleAssertions() {
    Calculator calc = new Calculator();
    assertNotNull(calc);
    assertEquals(5, calc.add(2, 3));
    assertTrue(calc.add(1, 1) > 0);
    assertFalse(calc.add(-1, -1) > 0);
}
'''
        scorer = TestQualityScorer()
        score = scorer.score_effectiveness(test_code)

        assert score.assertion_density > 0.5

    def test_analyze_test_methods(self):
        """测试分析方法数量."""
        test_code = '''
@Test
void testMethod1() {}

@Test
void testMethod2() {}

@Test
void testMethod3() {}
'''
        scorer = TestQualityScorer()
        methods = scorer.analyze_test_methods(test_code)

        assert len(methods) == 3

    def test_detect_boundary_tests(self):
        """测试检测边界测试."""
        test_code = '''
@Test
void testNormalCase() {
    assertEquals(5, calc.add(2, 3));
}

@Test
void testBoundaryMax() {
    assertEquals(Integer.MAX_VALUE, calc.add(Integer.MAX_VALUE, 0));
}

@Test
void testBoundaryMin() {
    assertEquals(Integer.MIN_VALUE, calc.add(Integer.MIN_VALUE, 0));
}

@Test
void testBoundaryZero() {
    assertEquals(0, calc.add(0, 0));
}
'''
        scorer = TestQualityScorer()
        boundary_tests = scorer.detect_boundary_tests(test_code)

        assert len(boundary_tests) >= 2

    def test_detect_exception_tests(self):
        """测试检测异常测试."""
        test_code = '''
@Test
void testNormalCase() {
    assertEquals(5, calc.add(2, 3));
}

@Test
void testExceptionNull() {
    assertThrows(IllegalArgumentException.class, () -> {
        calc.add(null, null);
    });
}

@Test
void testExceptionOverflow() {
    assertThrows(ArithmeticException.class, () -> {
        calc.add(Integer.MAX_VALUE, 1);
    });
}
'''
        scorer = TestQualityScorer()
        exception_tests = scorer.detect_exception_tests(test_code)

        assert len(exception_tests) >= 2


class TestScoringDimension:
    """评分维度枚举测试."""

    def test_scoring_dimensions(self):
        """测试评分维度枚举值."""
        assert ScoringDimension.EFFECTIVENESS.value == "effectiveness"
        assert ScoringDimension.CODE_QUALITY.value == "code_quality"
        assert ScoringDimension.COVERAGE_DEPTH.value == "coverage_depth"


class TestIntegration:
    """集成测试."""

    def test_full_scoring_workflow(self):
        """测试完整评分工作流."""
        test_code = '''
package com.example;

import org.junit.jupiter.api.*;
import static org.junit.jupiter.api.Assertions.*;

/**
 * Calculator test class with comprehensive test coverage.
 */
class CalculatorTest {
    
    private Calculator calculator;
    
    @BeforeEach
    void setUp() {
        calculator = new Calculator();
    }
    
    @Test
    @DisplayName("Should add two positive numbers")
    void testAddPositiveNumbers() {
        assertEquals(5, calculator.add(2, 3));
        assertEquals(10, calculator.add(7, 3));
    }
    
    @Test
    @DisplayName("Should add negative numbers")
    void testAddNegativeNumbers() {
        assertEquals(-5, calculator.add(-2, -3));
        assertEquals(1, calculator.add(-2, 3));
    }
    
    @Test
    @DisplayName("Should handle boundary cases")
    void testAddBoundaryCases() {
        assertEquals(Integer.MAX_VALUE, calculator.add(Integer.MAX_VALUE, 0));
        assertEquals(Integer.MIN_VALUE, calculator.add(Integer.MIN_VALUE, 0));
        assertEquals(0, calculator.add(0, 0));
    }
    
    @Test
    @DisplayName("Should throw exception for null arguments")
    void testAddNullArguments() {
        assertThrows(IllegalArgumentException.class, () -> {
            calculator.add(null, 1);
        });
    }
}
'''
        source_code = '''
package com.example;

public class Calculator {
    public int add(Integer a, Integer b) {
        if (a == null || b == null) {
            throw new IllegalArgumentException("Arguments cannot be null");
        }
        return a + b;
    }
}
'''
        mutation_report = {
            "total_mutations": 50,
            "killed": 45,
            "survived": 5,
        }

        scorer = TestQualityScorer()
        report = scorer.generate_report(
            test_code,
            source_code,
            "CalculatorTest.java",
            mutation_report,
        )

        assert report.overall_score > 30
        assert report.effectiveness.mutation_kill_rate == 90.0
        assert report.code_quality.documentation > 0
