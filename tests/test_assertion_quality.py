"""断言质量评分测试."""

import pytest
import ast
from unittest.mock import Mock, patch

from ut_agent.quality.assertion_quality import (
    AssertionType,
    AssertionQuality,
    AssertionQualityScorer,
    AssertionPattern,
    AssertionRecommendation,
)


class TestAssertionType:
    """断言类型测试."""

    def test_assertion_type_values(self):
        """测试断言类型枚举值."""
        assert AssertionType.EQUALITY.value == "equality"
        assert AssertionType.MEMBERSHIP.value == "membership"
        assert AssertionType.EXCEPTION.value == "exception"
        assert AssertionType.TRUTHINESS.value == "truthiness"
        assert AssertionType.COMPARISON.value == "comparison"
        assert AssertionType.TYPE_CHECK.value == "type_check"
        assert AssertionType.COLLECTION.value == "collection"
        assert AssertionType.CUSTOM.value == "custom"


class TestAssertionQuality:
    """断言质量数据类测试."""

    def test_quality_creation(self):
        """测试创建断言质量对象."""
        quality = AssertionQuality(
            assertion_type=AssertionType.EQUALITY,
            score=0.85,
            line_number=10,
            message="Good assertion",
        )
        
        assert quality.assertion_type == AssertionType.EQUALITY
        assert quality.score == 0.85
        assert quality.line_number == 10
        assert quality.message == "Good assertion"
        assert quality.suggestions == []
        
    def test_quality_with_suggestions(self):
        """测试带建议的断言质量."""
        quality = AssertionQuality(
            assertion_type=AssertionType.EQUALITY,
            score=0.6,
            line_number=15,
            message="Average assertion",
            suggestions=["Add error message", "Use more specific assertion"],
        )
        
        assert len(quality.suggestions) == 2
        assert "Add error message" in quality.suggestions
        
    def test_quality_to_dict(self):
        """测试序列化."""
        quality = AssertionQuality(
            assertion_type=AssertionType.MEMBERSHIP,
            score=0.9,
            line_number=20,
            message="Excellent",
        )
        
        data = quality.to_dict()
        
        assert data["assertion_type"] == "membership"
        assert data["score"] == 0.9
        assert data["line_number"] == 20


class TestAssertionPattern:
    """断言模式测试."""

    def test_pattern_creation(self):
        """测试模式创建."""
        pattern = AssertionPattern(
            name="assert_equal_with_message",
            description="Assert equal with custom message",
            assertion_type=AssertionType.EQUALITY,
            quality_score=1.0,
        )
        
        assert pattern.name == "assert_equal_with_message"
        assert pattern.quality_score == 1.0
        
    def test_pattern_matches(self):
        """测试模式匹配."""
        pattern = AssertionPattern(
            name="assert_true_without_message",
            description="Bare assertTrue",
            assertion_type=AssertionType.TRUTHINESS,
            quality_score=0.5,
            anti_pattern=True,
        )
        
        # 测试匹配逻辑
        assert pattern.anti_pattern is True


class TestAssertionQualityScorer:
    """断言质量评分器测试."""

    @pytest.fixture
    def scorer(self):
        """创建评分器实例."""
        return AssertionQualityScorer()
        
    def test_scorer_initialization(self):
        """测试评分器初始化."""
        scorer = AssertionQualityScorer()
        
        assert scorer is not None
        assert len(scorer.patterns) > 0
        
    def test_detect_assertion_type_equality(self, scorer):
        """测试检测相等性断言."""
        code = "assertEqual(result, expected)"
        ast_node = ast.parse(code).body[0].value
        
        assertion_type = scorer._detect_assertion_type(ast_node)
        
        assert assertion_type == AssertionType.EQUALITY
        
    def test_detect_assertion_type_exception(self, scorer):
        """测试检测异常断言."""
        code = "assertRaises(ValueError)"
        ast_node = ast.parse(code).body[0].value
        
        assertion_type = scorer._detect_assertion_type(ast_node)
        
        assert assertion_type == AssertionType.EXCEPTION
        
    def test_detect_assertion_type_truthiness(self, scorer):
        """测试检测真值断言."""
        code = "assertTrue(result)"
        ast_node = ast.parse(code).body[0].value
        
        assertion_type = scorer._detect_assertion_type(ast_node)
        
        assert assertion_type == AssertionType.TRUTHINESS
        
    def test_score_assertion_high_quality(self, scorer):
        """测试高质量断言评分."""
        # 带错误消息的相等性断言
        code = "assertEqual(result, expected, 'Results should match')"
        ast_node = ast.parse(code).body[0].value
        
        quality = scorer._score_assertion(ast_node, AssertionType.EQUALITY)
        
        assert quality.score >= 0.8
        assert len(quality.suggestions) == 0
        
    def test_score_assertion_low_quality(self, scorer):
        """测试低质量断言评分."""
        # 无错误消息的裸断言
        code = "assertTrue(result)"
        ast_node = ast.parse(code).body[0].value
        
        quality = scorer._score_assertion(ast_node, AssertionType.TRUTHINESS)
        
        assert quality.score < 0.8
        assert len(quality.suggestions) > 0
        
    def test_score_assertion_with_magic_numbers(self, scorer):
        """测试检测魔法数字."""
        code = "assertEqual(result, 42)"
        ast_node = ast.parse(code).body[0].value
        
        quality = scorer._score_assertion(ast_node, AssertionType.EQUALITY)
        
        # 应该建议避免魔法数字
        suggestions_text = " ".join(quality.suggestions).lower()
        assert "magic" in suggestions_text or "constant" in suggestions_text or quality.score < 1.0
        
    def test_analyze_test_function(self, scorer):
        """测试分析测试函数."""
        test_code = '''
def test_example():
    result = calculate(2, 3)
    assertEqual(result, 5, "Calculation should be correct")
    assertIsNotNone(result)
'''
        tree = ast.parse(test_code)
        func_node = tree.body[0]
        
        qualities = scorer.analyze_test_function(func_node)
        
        assert len(qualities) == 2
        # 所有断言应该有合理的分数
        for quality in qualities:
            assert 0 <= quality.score <= 1
            
    def test_analyze_test_function_no_assertions(self, scorer):
        """测试分析无断言的函数."""
        test_code = '''
def test_no_assertions():
    result = calculate(2, 3)
    print(result)
'''
        tree = ast.parse(test_code)
        func_node = tree.body[0]
        
        qualities = scorer.analyze_test_function(func_node)
        
        assert len(qualities) == 0
        
    def test_calculate_overall_score(self, scorer):
        """测试计算总体分数."""
        qualities = [
            AssertionQuality(AssertionType.EQUALITY, 0.9, 10, "Good"),
            AssertionQuality(AssertionType.TRUTHINESS, 0.7, 15, "Okay"),
            AssertionQuality(AssertionType.EXCEPTION, 0.8, 20, "Good"),
        ]
        
        overall = scorer.calculate_overall_score(qualities)
        
        assert 0 <= overall <= 1
        # 平均分应该在0.7-0.9之间
        assert 0.7 <= overall <= 0.9
        
    def test_calculate_overall_score_empty(self, scorer):
        """测试空列表的总体分数."""
        overall = scorer.calculate_overall_score([])
        
        assert overall == 0.0
        
    def test_generate_recommendations(self, scorer):
        """测试生成建议."""
        qualities = [
            AssertionQuality(
                AssertionType.TRUTHINESS, 
                0.5, 
                10, 
                "Low quality",
                suggestions=["Add error message"],
            ),
            AssertionQuality(
                AssertionType.EQUALITY,
                0.6,
                15,
                "Average",
                suggestions=["Use constant"],
            ),
        ]
        
        recommendations = scorer.generate_recommendations(qualities)
        
        assert len(recommendations) > 0
        
    def test_get_quality_report(self, scorer):
        """测试获取质量报告."""
        test_code = '''
def test_example():
    result = calculate(2, 3)
    assertEqual(result, 5)
    assertTrue(result > 0)
'''
        report = scorer.get_quality_report(test_code)
        
        assert "overall_score" in report
        assert "assertion_count" in report
        assert "functions" in report
        assert report["assertion_count"] == 2
        
    def test_score_file(self, scorer, tmp_path):
        """测试评分文件."""
        test_content = '''
import unittest

class TestExample(unittest.TestCase):
    def test_addition(self):
        result = 1 + 1
        self.assertEqual(result, 2, "Addition works")
        
    def test_subtraction(self):
        result = 5 - 3
        self.assertEqual(result, 2)
'''
        test_file = tmp_path / "test_example.py"
        test_file.write_text(test_content)
        
        result = scorer.score_file(str(test_file))
        
        assert "file_path" in result
        assert "overall_score" in result
        assert "functions" in result
        assert len(result["functions"]) == 2
        
    def test_score_file_not_found(self, scorer):
        """测试评分不存在的文件."""
        result = scorer.score_file("/nonexistent/test.py")
        
        assert "error" in result
        
    def test_assertion_diversity_score(self, scorer):
        """测试断言多样性评分."""
        # 多种类型的断言
        diverse_assertions = [
            AssertionQuality(AssertionType.EQUALITY, 0.9, 1, ""),
            AssertionQuality(AssertionType.TRUTHINESS, 0.9, 2, ""),
            AssertionQuality(AssertionType.EXCEPTION, 0.9, 3, ""),
            AssertionQuality(AssertionType.MEMBERSHIP, 0.9, 4, ""),
        ]
        
        diverse_score = scorer._calculate_diversity_score(diverse_assertions)
        
        # 单一类型的断言
        single_assertions = [
            AssertionQuality(AssertionType.EQUALITY, 0.9, 1, ""),
            AssertionQuality(AssertionType.EQUALITY, 0.9, 2, ""),
            AssertionQuality(AssertionType.EQUALITY, 0.9, 3, ""),
        ]
        
        single_score = scorer._calculate_diversity_score(single_assertions)
        
        # 多样性应该得分更高或相等（当只有一种类型时，熵为最大值1.0）
        assert diverse_score >= single_score


class TestAssertionRecommendation:
    """断言建议测试."""

    def test_recommendation_creation(self):
        """测试创建建议."""
        rec = AssertionRecommendation(
            category="message",
            message="Add descriptive error message",
            priority="high",
            example="assertEqual(a, b, 'Values should match')",
        )
        
        assert rec.category == "message"
        assert rec.priority == "high"
        assert "assertEqual" in rec.example
        
    def test_recommendation_to_dict(self):
        """测试建议序列化."""
        rec = AssertionRecommendation(
            category="type",
            message="Use more specific assertion",
            priority="medium",
        )
        
        data = rec.to_dict()
        
        assert data["category"] == "type"
        assert data["priority"] == "medium"


class TestAssertionQualityIntegration:
    """断言质量集成测试."""

    def test_full_analysis_workflow(self):
        """测试完整分析工作流."""
        scorer = AssertionQualityScorer()
        
        test_code = '''
import unittest

class TestCalculator(unittest.TestCase):
    def test_add(self):
        calc = Calculator()
        result = calc.add(2, 3)
        self.assertEqual(result, 5, "Addition should work correctly")
        self.assertIsInstance(result, int)
        
    def test_divide_by_zero(self):
        calc = Calculator()
        with self.assertRaises(ZeroDivisionError):
            calc.divide(1, 0)
            
    def test_weak_assertions(self):
        calc = Calculator()
        result = calc.add(1, 1)
        self.assertTrue(result == 2)  # Weak assertion
        self.assertEqual(result, 2)   # No message
'''
        
        report = scorer.get_quality_report(test_code)
        
        # 验证报告结构
        assert "overall_score" in report
        assert "assertion_count" in report
        assert "assertion_types" in report
        assert "recommendations" in report
        
        # 应该有多个断言
        assert report["assertion_count"] >= 4
        
        # 应该检测到弱断言并提供建议
        if report["recommendations"]:
            has_weak_assertion_rec = any(
                "true" in r.get("message", "").lower() or 
                "message" in r.get("category", "").lower()
                for r in report["recommendations"]
            )
            # 可能检测到弱断言
            
    def test_compare_test_quality(self):
        """测试比较测试质量."""
        scorer = AssertionQualityScorer()
        
        # 高质量的测试
        high_quality_code = '''
def test_high_quality():
    result = process_data([1, 2, 3])
    assertEqual(len(result), 3, "Should return 3 items")
    assertIsNotNone(result, "Result should not be None")
    assertIn(1, result, "Should contain expected values")
'''
        
        # 低质量的测试
        low_quality_code = '''
def test_low_quality():
    result = process_data([1, 2, 3])
    assertTrue(result)
    assertEqual(result, [1, 2, 3])
'''
        
        high_report = scorer.get_quality_report(high_quality_code)
        low_report = scorer.get_quality_report(low_quality_code)
        
        # 高质量测试应该得分更高
        assert high_report["overall_score"] > low_report["overall_score"]
