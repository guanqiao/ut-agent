"""断言质量评分.

分析测试代码中的断言质量，提供评分和改进建议。
"""

import ast
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class AssertionType(Enum):
    """断言类型枚举."""
    EQUALITY = "equality"           # 相等性断言 (assertEqual, assertNotEqual)
    MEMBERSHIP = "membership"       # 成员关系 (assertIn, assertNotIn)
    EXCEPTION = "exception"         # 异常断言 (assertRaises)
    TRUTHINESS = "truthiness"       # 真值断言 (assertTrue, assertFalse)
    COMPARISON = "comparison"       # 比较断言 (assertGreater, assertLess, etc.)
    TYPE_CHECK = "type_check"       # 类型检查 (assertIsInstance, assertIsNotNone)
    COLLECTION = "collection"       # 集合断言 (assertListEqual, assertDictEqual)
    CUSTOM = "custom"               # 自定义断言


@dataclass
class AssertionQuality:
    """断言质量评估结果.
    
    Attributes:
        assertion_type: 断言类型
        score: 质量分数 (0-1)
        line_number: 行号
        message: 描述信息
        suggestions: 改进建议列表
    """
    assertion_type: AssertionType
    score: float
    line_number: int
    message: str
    suggestions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "assertion_type": self.assertion_type.value,
            "score": round(self.score, 2),
            "line_number": self.line_number,
            "message": self.message,
            "suggestions": self.suggestions,
        }


@dataclass
class AssertionPattern:
    """断言模式.
    
    Attributes:
        name: 模式名称
        description: 模式描述
        assertion_type: 断言类型
        quality_score: 质量分数
        anti_pattern: 是否为反模式
    """
    name: str
    description: str
    assertion_type: AssertionType
    quality_score: float
    anti_pattern: bool = False


@dataclass
class AssertionRecommendation:
    """断言改进建议.
    
    Attributes:
        category: 建议类别
        message: 建议内容
        priority: 优先级 (high/medium/low)
        example: 示例代码
    """
    category: str
    message: str
    priority: str = "medium"
    example: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "category": self.category,
            "message": self.message,
            "priority": self.priority,
            "example": self.example,
        }


class AssertionQualityScorer:
    """断言质量评分器.
    
    分析测试代码中的断言，评估其质量并提供改进建议。
    """
    
    # 断言方法到类型的映射
    ASSERTION_METHODS: Dict[str, AssertionType] = {
        # 相等性
        "assertEqual": AssertionType.EQUALITY,
        "assertNotEqual": AssertionType.EQUALITY,
        "assertIs": AssertionType.EQUALITY,
        "assertIsNot": AssertionType.EQUALITY,
        # 真值
        "assertTrue": AssertionType.TRUTHINESS,
        "assertFalse": AssertionType.TRUTHINESS,
        # 成员关系
        "assertIn": AssertionType.MEMBERSHIP,
        "assertNotIn": AssertionType.MEMBERSHIP,
        # 异常
        "assertRaises": AssertionType.EXCEPTION,
        "assertRaisesRegex": AssertionType.EXCEPTION,
        # 类型检查
        "assertIsInstance": AssertionType.TYPE_CHECK,
        "assertNotIsInstance": AssertionType.TYPE_CHECK,
        "assertIsNone": AssertionType.TYPE_CHECK,
        "assertIsNotNone": AssertionType.TYPE_CHECK,
        # 比较
        "assertGreater": AssertionType.COMPARISON,
        "assertGreaterEqual": AssertionType.COMPARISON,
        "assertLess": AssertionType.COMPARISON,
        "assertLessEqual": AssertionType.COMPARISON,
        # 集合
        "assertListEqual": AssertionType.COLLECTION,
        "assertTupleEqual": AssertionType.COLLECTION,
        "assertSetEqual": AssertionType.COLLECTION,
        "assertDictEqual": AssertionType.COLLECTION,
        "assertCountEqual": AssertionType.COLLECTION,
        # 其他
        "assertAlmostEqual": AssertionType.EQUALITY,
        "assertNotAlmostEqual": AssertionType.EQUALITY,
        "assertRegex": AssertionType.CUSTOM,
        "assertNotRegex": AssertionType.CUSTOM,
    }
    
    def __init__(self):
        """初始化评分器."""
        self.patterns = self._init_patterns()
        
    def _init_patterns(self) -> List[AssertionPattern]:
        """初始化断言模式."""
        return [
            AssertionPattern(
                name="assert_true_with_comparison",
                description="assertTrue with comparison expression",
                assertion_type=AssertionType.TRUTHINESS,
                quality_score=0.5,
                anti_pattern=True,
            ),
            AssertionPattern(
                name="assert_equal_with_message",
                description="assertEqual with descriptive message",
                assertion_type=AssertionType.EQUALITY,
                quality_score=1.0,
            ),
            AssertionPattern(
                name="bare_assert",
                description="Using bare assert statement",
                assertion_type=AssertionType.CUSTOM,
                quality_score=0.6,
                anti_pattern=True,
            ),
            AssertionPattern(
                name="magic_number",
                description="Using magic numbers in assertions",
                assertion_type=AssertionType.EQUALITY,
                quality_score=0.6,
                anti_pattern=True,
            ),
        ]
        
    def _detect_assertion_type(self, node: ast.AST) -> AssertionType:
        """检测断言类型.
        
        Args:
            node: AST节点
            
        Returns:
            AssertionType: 断言类型
        """
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                method_name = node.func.attr
                return self.ASSERTION_METHODS.get(method_name, AssertionType.CUSTOM)
            elif isinstance(node.func, ast.Name):
                method_name = node.func.id
                return self.ASSERTION_METHODS.get(method_name, AssertionType.CUSTOM)
        elif isinstance(node, ast.Assert):
            return AssertionType.CUSTOM
            
        return AssertionType.CUSTOM
        
    def _score_assertion(
        self,
        node: ast.AST,
        assertion_type: AssertionType,
    ) -> AssertionQuality:
        """评分单个断言.
        
        Args:
            node: AST节点
            assertion_type: 断言类型
            
        Returns:
            AssertionQuality: 质量评估结果
        """
        score = 0.7  # 基础分数
        suggestions = []
        line_number = getattr(node, 'lineno', 0)
        
        if isinstance(node, ast.Call):
            # 检查是否有错误消息参数
            has_message = len(node.args) >= 3 or any(
                isinstance(kw, ast.keyword) and kw.arg == "msg"
                for kw in node.keywords
            )
            
            if has_message:
                score += 0.2
            else:
                suggestions.append("Add a descriptive error message to the assertion")
                
            # 检查方法名
            method_name = ""
            if isinstance(node.func, ast.Attribute):
                method_name = node.func.attr
            elif isinstance(node.func, ast.Name):
                method_name = node.func.id
                
            # 检测反模式
            if method_name == "assertTrue" and len(node.args) >= 1:
                # assertTrue with comparison is a weak pattern
                arg = node.args[0]
                if isinstance(arg, (ast.Compare, ast.BoolOp)):
                    score -= 0.2
                    suggestions.append(
                        "Use a more specific assertion instead of assertTrue with comparison"
                    )
                    
            # 检查魔法数字
            if assertion_type == AssertionType.EQUALITY and len(node.args) >= 2:
                for arg in node.args[:2]:
                    if isinstance(arg, ast.Num) and isinstance(arg.n, int):
                        if arg.n not in (0, 1, -1):  # 0, 1, -1 are acceptable
                            score -= 0.1
                            suggestions.append(
                                "Consider using a named constant instead of magic number"
                            )
                            break
                            
            # 检查类型检查断言
            if assertion_type == AssertionType.TYPE_CHECK:
                score += 0.1  # 类型检查是好的实践
                
        elif isinstance(node, ast.Assert):
            # 裸 assert 语句
            score = 0.6
            suggestions.append("Consider using unittest assertion methods for better error messages")
            
        # 确保分数在合理范围内
        score = max(0.0, min(1.0, score))
        
        return AssertionQuality(
            assertion_type=assertion_type,
            score=score,
            line_number=line_number,
            message=f"{assertion_type.value} assertion",
            suggestions=suggestions,
        )
        
    def analyze_test_function(self, func_node: ast.FunctionDef) -> List[AssertionQuality]:
        """分析测试函数.
        
        Args:
            func_node: 函数定义AST节点
            
        Returns:
            List[AssertionQuality]: 断言质量列表
        """
        qualities = []
        
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                assertion_type = self._detect_assertion_type(node)
                if assertion_type != AssertionType.CUSTOM or self._is_assertion_call(node):
                    quality = self._score_assertion(node, assertion_type)
                    qualities.append(quality)
            elif isinstance(node, ast.Assert):
                quality = self._score_assertion(node, AssertionType.CUSTOM)
                qualities.append(quality)
                
        return qualities
        
    def _is_assertion_call(self, node: ast.Call) -> bool:
        """检查是否为断言调用.
        
        Args:
            node: 调用节点
            
        Returns:
            bool: 是否为断言调用
        """
        if isinstance(node.func, ast.Attribute):
            return node.func.attr in self.ASSERTION_METHODS
        elif isinstance(node.func, ast.Name):
            return node.func.id in self.ASSERTION_METHODS
        return False
        
    def calculate_overall_score(self, qualities: List[AssertionQuality]) -> float:
        """计算总体质量分数.
        
        Args:
            qualities: 断言质量列表
            
        Returns:
            float: 总体分数 (0-1)
        """
        if not qualities:
            return 0.0
            
        # 基础分数：平均分
        base_score = sum(q.score for q in qualities) / len(qualities)
        
        # 多样性加分
        diversity_score = self._calculate_diversity_score(qualities)
        
        # 综合分数
        overall = base_score * 0.7 + diversity_score * 0.3
        
        return round(min(1.0, overall), 2)
        
    def _calculate_diversity_score(self, qualities: List[AssertionQuality]) -> float:
        """计算断言多样性分数.
        
        Args:
            qualities: 断言质量列表
            
        Returns:
            float: 多样性分数
        """
        if not qualities:
            return 0.0
            
        type_counts: Dict[AssertionType, int] = {}
        for q in qualities:
            type_counts[q.assertion_type] = type_counts.get(q.assertion_type, 0) + 1
            
        # 类型越多，多样性越高
        unique_types = len(type_counts)
        total_assertions = len(qualities)
        
        # 使用香农熵计算多样性
        import math
        entropy = 0.0
        for count in type_counts.values():
            if count > 0:
                p = count / total_assertions
                entropy -= p * math.log2(p)
                
        # 归一化到 0-1
        max_entropy = math.log2(max(1, unique_types))
        if max_entropy == 0:
            return 1.0
            
        return entropy / max_entropy
        
    def generate_recommendations(
        self,
        qualities: List[AssertionQuality],
    ) -> List[AssertionRecommendation]:
        """生成改进建议.
        
        Args:
            qualities: 断言质量列表
            
        Returns:
            List[AssertionRecommendation]: 建议列表
        """
        recommendations = []
        
        # 统计各类问题
        low_quality_count = sum(1 for q in qualities if q.score < 0.6)
        no_message_count = sum(
            1 for q in qualities 
            if any("message" in s.lower() for s in q.suggestions)
        )
        
        # 总体建议
        if low_quality_count > len(qualities) * 0.3:
            recommendations.append(AssertionRecommendation(
                category="general",
                message=f"{low_quality_count} assertions have low quality scores. Consider reviewing them.",
                priority="high",
            ))
            
        if no_message_count > 0:
            recommendations.append(AssertionRecommendation(
                category="message",
                message=f"{no_message_count} assertions are missing error messages. Add descriptive messages for better debugging.",
                priority="medium",
                example='self.assertEqual(a, b, "Values should match")',
            ))
            
        # 针对具体断言的建议
        for quality in qualities:
            for suggestion in quality.suggestions:
                if "assertTrue" in suggestion.lower():
                    recommendations.append(AssertionRecommendation(
                        category="type",
                        message=f"Line {quality.line_number}: {suggestion}",
                        priority="medium",
                        example="# Instead of: self.assertTrue(a == b)\n# Use: self.assertEqual(a, b)",
                    ))
                elif "magic number" in suggestion.lower():
                    recommendations.append(AssertionRecommendation(
                        category="maintainability",
                        message=f"Line {quality.line_number}: {suggestion}",
                        priority="low",
                        example="EXPECTED_VALUE = 42\nself.assertEqual(result, EXPECTED_VALUE)",
                    ))
                    
        return recommendations
        
    def get_quality_report(self, test_code: str) -> Dict[str, Any]:
        """获取质量报告.
        
        Args:
            test_code: 测试代码
            
        Returns:
            Dict[str, Any]: 质量报告
        """
        try:
            tree = ast.parse(test_code)
        except SyntaxError as e:
            return {"error": f"Syntax error: {e}"}
            
        all_qualities = []
        function_reports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 检查是否为测试函数
                if node.name.startswith("test"):
                    qualities = self.analyze_test_function(node)
                    all_qualities.extend(qualities)
                    
                    if qualities:
                        function_reports.append({
                            "function_name": node.name,
                            "line_number": node.lineno,
                            "assertion_count": len(qualities),
                            "average_score": round(
                                sum(q.score for q in qualities) / len(qualities), 2
                            ),
                            "assertions": [q.to_dict() for q in qualities],
                        })
                        
        overall_score = self.calculate_overall_score(all_qualities)
        recommendations = self.generate_recommendations(all_qualities)
        
        # 统计断言类型
        type_counts: Dict[str, int] = {}
        for q in all_qualities:
            type_name = q.assertion_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
            
        return {
            "overall_score": overall_score,
            "assertion_count": len(all_qualities),
            "function_count": len(function_reports),
            "assertion_types": type_counts,
            "functions": function_reports,
            "recommendations": [r.to_dict() for r in recommendations],
        }
        
    def score_file(self, file_path: str) -> Dict[str, Any]:
        """评分测试文件.
        
        Args:
            file_path: 文件路径
            
        Returns:
            Dict[str, Any]: 评分结果
        """
        path = Path(file_path)
        
        if not path.exists():
            return {"error": f"File not found: {file_path}"}
            
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            return {"error": f"Failed to read file: {e}"}
            
        report = self.get_quality_report(content)
        report["file_path"] = str(file_path)
        
        return report
