"""优先级计算器单元测试."""

from unittest.mock import Mock, patch, MagicMock

import pytest

from ut_agent.selection.priority import Priority, PriorityCalculator


class TestPriority:
    """Priority 数据类测试."""

    def test_priority_creation(self):
        """测试 Priority 创建."""
        priority = Priority(
            score=85,
            factors={"complexity": 70, "coverage": 90},
        )

        assert priority.score == 85
        assert priority.factors == {"complexity": 70, "coverage": 90}

    def test_priority_comparison_lt(self):
        """测试小于比较."""
        p1 = Priority(score=50)
        p2 = Priority(score=75)

        assert p1 < p2
        assert not (p2 < p1)
        assert not (p1 < p1)

    def test_priority_comparison_le(self):
        """测试小于等于比较."""
        p1 = Priority(score=50)
        p2 = Priority(score=50)
        p3 = Priority(score=75)

        assert p1 <= p2
        assert p1 <= p3
        assert not (p3 <= p1)

    def test_priority_comparison_gt(self):
        """测试大于比较."""
        p1 = Priority(score=75)
        p2 = Priority(score=50)

        assert p1 > p2
        assert not (p2 > p1)
        assert not (p1 > p1)

    def test_priority_comparison_ge(self):
        """测试大于等于比较."""
        p1 = Priority(score=50)
        p2 = Priority(score=50)
        p3 = Priority(score=75)

        assert p3 >= p1
        assert p1 >= p2
        assert not (p1 >= p3)

    def test_priority_comparison_eq(self):
        """测试等于比较."""
        p1 = Priority(score=50)
        p2 = Priority(score=50)
        p3 = Priority(score=75)

        assert p1 == p2
        assert not (p1 == p3)
        assert not (p1 == 50)  # 与非 Priority 比较


class TestPriorityCalculator:
    """PriorityCalculator 测试."""

    def test_calculator_initialization_default(self):
        """测试默认初始化."""
        calculator = PriorityCalculator()

        assert calculator._weights == PriorityCalculator.DEFAULT_WEIGHTS
        assert calculator._custom_factors == {}

    def test_calculator_initialization_custom(self):
        """测试自定义初始化."""
        custom_weights = {
            "complexity": 0.3,
            "coverage": 0.3,
            "change_frequency": 0.2,
            "business_value": 0.1,
            "failure_history": 0.1,
        }
        custom_factors = {
            "risk": lambda task, context: 0.8,
        }

        calculator = PriorityCalculator(
            weights=custom_weights,
            custom_factors=custom_factors,
        )

        assert calculator._weights == custom_weights
        assert "risk" in calculator._custom_factors

    def test_complexity_score(self):
        """测试复杂度评分."""
        calculator = PriorityCalculator()

        # 高复杂度
        task_info = {"complexity": 25}
        score = calculator._complexity_score(task_info, {})
        assert score == 1.0

        # 中等复杂度
        task_info = {"complexity": 12}
        score = calculator._complexity_score(task_info, {})
        assert score == 0.6

        # 低复杂度
        task_info = {"complexity": 3}
        score = calculator._complexity_score(task_info, {})
        assert score == 0.2

        # 无复杂度信息
        task_info = {}
        score = calculator._complexity_score(task_info, {})
        assert score == 0.2

    def test_coverage_score(self):
        """测试覆盖率评分."""
        calculator = PriorityCalculator()

        # 低覆盖率
        task_info = {"current_coverage": 0.2}
        score = calculator._coverage_score(task_info, {})
        assert score == 1.0

        # 中等覆盖率
        task_info = {"current_coverage": 0.6}
        score = calculator._coverage_score(task_info, {})
        assert score == 0.5

        # 高覆盖率
        task_info = {"current_coverage": 0.95}
        score = calculator._coverage_score(task_info, {})
        assert score == 0.1

        # 无覆盖率信息
        task_info = {}
        score = calculator._coverage_score(task_info, {})
        assert score == 0.1

    def test_change_frequency_score(self):
        """测试变更频率评分."""
        calculator = PriorityCalculator()

        # 高频变更
        task_info = {"change_count": 15}
        score = calculator._change_frequency_score(task_info, {})
        assert score == 1.0

        # 中频变更
        task_info = {"change_count": 3}
        score = calculator._change_frequency_score(task_info, {})
        assert score == 0.5

        # 低频变更
        task_info = {"change_count": 0}
        score = calculator._change_frequency_score(task_info, {})
        assert score == 0.1

        # 无变更信息
        task_info = {}
        score = calculator._change_frequency_score(task_info, {})
        assert score == 0.1

    def test_business_value_score(self):
        """测试业务价值评分."""
        calculator = PriorityCalculator()

        # 高价值
        task_info = {"source_file": "Service.java"}
        score = calculator._business_value_score(task_info, {})
        assert score == 1.0

        task_info = {"source_file": "Controller.java"}
        score = calculator._business_value_score(task_info, {})
        assert score == 1.0

        # 中等价值
        task_info = {"source_file": "Repository.java"}
        score = calculator._business_value_score(task_info, {})
        assert score == 0.6

        task_info = {"source_file": "Util.java"}
        score = calculator._business_value_score(task_info, {})
        assert score == 0.6

        # 低价值
        task_info = {"source_file": "Test.java"}
        score = calculator._business_value_score(task_info, {})
        assert score == 0.3

        # 无文件信息
        task_info = {}
        score = calculator._business_value_score(task_info, {})
        assert score == 0.3

    def test_failure_history_score(self):
        """测试失败历史评分."""
        calculator = PriorityCalculator()

        # 高频失败
        task_info = {"failure_count": 8}
        score = calculator._failure_history_score(task_info, {})
        assert score == 1.0

        # 中频失败
        task_info = {"failure_count": 2}
        score = calculator._failure_history_score(task_info, {})
        assert score == 0.5

        # 低频失败
        task_info = {"failure_count": 0}
        score = calculator._failure_history_score(task_info, {})
        assert score == 0.0

        # 无失败信息
        task_info = {}
        score = calculator._failure_history_score(task_info, {})
        assert score == 0.0

    def test_calculate(self):
        """测试计算优先级."""
        calculator = PriorityCalculator()

        task_info = {
            "complexity": 15,
            "current_coverage": 0.4,
            "change_count": 8,
            "source_file": "Service.java",
            "failure_count": 3,
        }

        priority = calculator.calculate(task_info, {})

        assert isinstance(priority, Priority)
        assert priority.score >= 0
        assert priority.score <= 100
        assert "complexity" in priority.factors
        assert "coverage" in priority.factors
        assert "change_frequency" in priority.factors
        assert "business_value" in priority.factors
        assert "failure_history" in priority.factors

    def test_calculate_with_custom_factor(self):
        """测试带自定义因子的计算."""
        def custom_factor(task, context):
            return 0.7

        calculator = PriorityCalculator()
        calculator.add_custom_factor("risk", custom_factor, weight=0.1)

        task_info = {
            "complexity": 10,
            "current_coverage": 0.6,
        }

        priority = calculator.calculate(task_info, {})

        assert "risk" in priority.factors
        assert priority.factors["risk"] == 70  # 0.7 * 100

    def test_set_weight(self):
        """测试设置权重."""
        calculator = PriorityCalculator()

        # 设置新权重
        calculator.set_weight("complexity", 0.5)
        weights = calculator.get_weights()

        assert weights["complexity"] == 0.5

    def test_add_custom_factor(self):
        """测试添加自定义因子."""
        calculator = PriorityCalculator()

        def custom_factor(task, context):
            return 0.8

        calculator.add_custom_factor("custom", custom_factor, weight=0.2)

        weights = calculator.get_weights()
        assert "custom" in weights
        assert weights["custom"] == 0.2
        assert "custom" in calculator._custom_factors

    def test_get_weights(self):
        """测试获取权重."""
        calculator = PriorityCalculator()
        weights = calculator.get_weights()

        assert isinstance(weights, dict)
        assert "complexity" in weights
        assert "coverage" in weights
        assert "change_frequency" in weights
        assert "business_value" in weights
        assert "failure_history" in weights

    def test_rank_tasks(self):
        """测试任务排序."""
        calculator = PriorityCalculator()

        tasks = [
            {
                "complexity": 5,
                "current_coverage": 0.9,
                "change_count": 0,
                "source_file": "Test.java",
                "failure_count": 0,
            },
            {
                "complexity": 20,
                "current_coverage": 0.2,
                "change_count": 10,
                "source_file": "Service.java",
                "failure_count": 5,
            },
            {
                "complexity": 10,
                "current_coverage": 0.6,
                "change_count": 3,
                "source_file": "Repository.java",
                "failure_count": 1,
            },
        ]

        ranked = calculator.rank_tasks(tasks, {})

        assert len(ranked) == 3
        assert "priority_score" in ranked[0]
        assert "priority_factors" in ranked[0]

        # 验证排序 - 分数应该降序
        scores = [task["priority_score"] for task in ranked]
        assert scores[0] >= scores[1] >= scores[2]

    def test_rank_tasks_empty(self):
        """测试空任务列表排序."""
        calculator = PriorityCalculator()

        ranked = calculator.rank_tasks([], {})

        assert ranked == []
