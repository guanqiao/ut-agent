"""测试选择器测试"""

import pytest
from typing import List

from ut_agent.selection.test_selector import (
    TestSelector,
    SelectionResult,
    TestTask,
    TaskType,
    SelectionStrategy,
)
from ut_agent.selection.change_detector import ChangeType, FileChange, MethodChange
from ut_agent.selection.impact_analyzer import ImpactReport, DirectImpact, IndirectImpact, TestImpact


class TestTaskType:
    """测试任务类型枚举"""
    
    def test_task_type_values(self):
        """测试任务类型值"""
        assert TaskType.GENERATE_NEW.value == "generate_new"
        assert TaskType.UPDATE_EXISTING.value == "update_existing"
        assert TaskType.DEPRECATE.value == "deprecate"
        assert TaskType.VERIFY.value == "verify"


class TestSelectionStrategy:
    """测试选择策略枚举"""
    
    def test_selection_strategy_values(self):
        """测试选择策略值"""
        assert SelectionStrategy.CONSERVATIVE.value == "conservative"
        assert SelectionStrategy.AGGRESSIVE.value == "aggressive"
        assert SelectionStrategy.SMART.value == "smart"


class TestTestTask:
    """测试测试任务数据类"""
    
    def test_test_task_creation(self):
        """测试测试任务创建"""
        task = TestTask(
            source_file="test.py",
            task_type=TaskType.GENERATE_NEW,
            test_file="test_test.py",
            methods=["test_method"],
            priority=10,
            reason="测试原因",
            metadata={"key": "value"}
        )
        
        assert task.source_file == "test.py"
        assert task.task_type == TaskType.GENERATE_NEW
        assert task.test_file == "test_test.py"
        assert task.methods == ["test_method"]
        assert task.priority == 10
        assert task.reason == "测试原因"
        assert task.metadata == {"key": "value"}
    
    def test_test_task_defaults(self):
        """测试测试任务默认值"""
        task = TestTask(
            source_file="test.py",
            task_type=TaskType.GENERATE_NEW
        )
        
        assert task.test_file is None
        assert task.methods == []
        assert task.priority == 0
        assert task.reason == ""
        assert task.metadata == {}


class TestSelectionResult:
    """测试选择结果数据类"""
    
    def test_selection_result_creation(self):
        """测试选择结果创建"""
        result = SelectionResult()
        assert result.to_generate == []
        assert result.to_update == []
        assert result.to_deprecate == []
        assert result.to_verify == []
    
    def test_add_task_generate_new(self):
        """测试添加生成新测试任务"""
        result = SelectionResult()
        task = TestTask(
            source_file="test.py",
            task_type=TaskType.GENERATE_NEW
        )
        result.add_task(task)
        assert len(result.to_generate) == 1
        assert len(result.to_update) == 0
        assert len(result.to_deprecate) == 0
        assert len(result.to_verify) == 0
    
    def test_add_task_update_existing(self):
        """测试添加更新现有测试任务"""
        result = SelectionResult()
        task = TestTask(
            source_file="test.py",
            task_type=TaskType.UPDATE_EXISTING
        )
        result.add_task(task)
        assert len(result.to_generate) == 0
        assert len(result.to_update) == 1
        assert len(result.to_deprecate) == 0
        assert len(result.to_verify) == 0
    
    def test_add_task_deprecate(self):
        """测试添加废弃测试任务"""
        result = SelectionResult()
        task = TestTask(
            source_file="test.py",
            task_type=TaskType.DEPRECATE
        )
        result.add_task(task)
        assert len(result.to_generate) == 0
        assert len(result.to_update) == 0
        assert len(result.to_deprecate) == 1
        assert len(result.to_verify) == 0
    
    def test_add_task_verify(self):
        """测试添加验证测试任务"""
        result = SelectionResult()
        task = TestTask(
            source_file="test.py",
            task_type=TaskType.VERIFY
        )
        result.add_task(task)
        assert len(result.to_generate) == 0
        assert len(result.to_update) == 0
        assert len(result.to_deprecate) == 0
        assert len(result.to_verify) == 1
    
    def test_all_tasks_property(self):
        """测试所有任务属性"""
        result = SelectionResult()
        
        task1 = TestTask(source_file="test1.py", task_type=TaskType.GENERATE_NEW)
        task2 = TestTask(source_file="test2.py", task_type=TaskType.UPDATE_EXISTING)
        task3 = TestTask(source_file="test3.py", task_type=TaskType.DEPRECATE)
        task4 = TestTask(source_file="test4.py", task_type=TaskType.VERIFY)
        
        result.add_task(task1)
        result.add_task(task2)
        result.add_task(task3)
        result.add_task(task4)
        
        all_tasks = result.all_tasks
        assert len(all_tasks) == 4
        assert task1 in all_tasks
        assert task2 in all_tasks
        assert task3 in all_tasks
        assert task4 in all_tasks
    
    def test_total_count_property(self):
        """测试总任务数属性"""
        result = SelectionResult()
        assert result.total_count == 0
        
        task1 = TestTask(source_file="test1.py", task_type=TaskType.GENERATE_NEW)
        task2 = TestTask(source_file="test2.py", task_type=TaskType.UPDATE_EXISTING)
        
        result.add_task(task1)
        result.add_task(task2)
        
        assert result.total_count == 2


class TestTestSelector:
    """测试测试选择器"""
    
    def create_mock_impact_report(self):
        """创建模拟影响报告"""
        # 创建直接影响
        direct_impact_added = DirectImpact(
            file_path="new_file.py",
            change_type=ChangeType.ADDED,
            method_changes=[
                MethodChange(name="new_method", change_type=ChangeType.ADDED, signature="")
            ],
            test_file=None
        )
        
        direct_impact_modified_with_test = DirectImpact(
            file_path="modified_file_with_test.py",
            change_type=ChangeType.MODIFIED,
            method_changes=[
                MethodChange(name="modified_method", change_type=ChangeType.MODIFIED, signature=""),
                MethodChange(name="deleted_method", change_type=ChangeType.DELETED, signature="")
            ],
            test_file="test_modified_file_with_test.py"
        )
        
        direct_impact_modified_no_test = DirectImpact(
            file_path="modified_file_no_test.py",
            change_type=ChangeType.MODIFIED,
            method_changes=[
                MethodChange(name="modified_method", change_type=ChangeType.MODIFIED, signature="")
            ],
            test_file=None
        )
        
        direct_impact_deleted_with_test = DirectImpact(
            file_path="deleted_file.py",
            change_type=ChangeType.DELETED,
            method_changes=[],
            test_file="test_deleted_file.py"
        )
        
        # 创建间接影响
        indirect_impact = IndirectImpact(
            file_path="indirect_file.py",
            reason="间接影响",
            call_sites=[],
            test_file="test_indirect_file.py"
        )
        
        # 创建测试影响
        test_impact = TestImpact(
            test_file="test_impacted.py",
            test_method="test_affected",
            reason="测试受影响",
            priority=5
        )
        
        return ImpactReport(
            direct_impacts=[
                direct_impact_added,
                direct_impact_modified_with_test,
                direct_impact_modified_no_test,
                direct_impact_deleted_with_test
            ],
            indirect_impacts=[indirect_impact],
            test_impacts=[test_impact]
        )
    
    def test_select_tests_smart_strategy(self):
        """测试智能策略选择测试"""
        selector = TestSelector(strategy=SelectionStrategy.SMART)
        impact_report = self.create_mock_impact_report()
        
        result = selector.select_tests(impact_report)
        
        # 验证结果
        assert len(result.to_generate) == 2  # 新增文件 + 修改无测试文件
        assert len(result.to_update) == 2  # 修改有测试文件 + 测试影响
        assert len(result.to_deprecate) == 1  # 删除文件
        assert len(result.to_verify) == 1  # 间接影响（智能策略下有测试文件）
        assert result.total_count == 6
    
    def test_select_tests_conservative_strategy(self):
        """测试保守策略选择测试"""
        selector = TestSelector(strategy=SelectionStrategy.CONSERVATIVE)
        impact_report = self.create_mock_impact_report()
        
        result = selector.select_tests(impact_report)
        
        # 验证结果
        assert len(result.to_generate) == 2
        assert len(result.to_update) == 2
        assert len(result.to_deprecate) == 1
        assert len(result.to_verify) == 1  # 间接影响（保守策略）
        assert result.total_count == 6
    
    def test_select_tests_empty_impact_report(self):
        """测试空影响报告选择测试"""
        selector = TestSelector()
        empty_impact_report = ImpactReport(
            direct_impacts=[],
            indirect_impacts=[],
            test_impacts=[]
        )
        
        result = selector.select_tests(empty_impact_report)
        
        # 验证结果
        assert len(result.to_generate) == 0
        assert len(result.to_update) == 0
        assert len(result.to_deprecate) == 0
        assert len(result.to_verify) == 0
        assert result.total_count == 0
    
    def test_prioritize_tasks(self):
        """测试任务优先级排序"""
        selector = TestSelector()
        
        # 创建测试任务
        task1 = TestTask(
            source_file="test1.py",
            task_type=TaskType.GENERATE_NEW,
            priority=0
        )
        
        task2 = TestTask(
            source_file="test2.py",
            task_type=TaskType.UPDATE_EXISTING,
            priority=0
        )
        
        task3 = TestTask(
            source_file="test3.py",
            task_type=TaskType.VERIFY,
            priority=0
        )
        
        task4 = TestTask(
            source_file="test4.py",
            task_type=TaskType.DEPRECATE,
            priority=0
        )
        
        # 创建选择结果
        result = SelectionResult()
        result.add_task(task1)
        result.add_task(task2)
        result.add_task(task3)
        result.add_task(task4)
        
        # 优先级排序
        prioritized_tasks = selector.prioritize(result)
        
        # 验证排序结果（GENERATE_NEW > UPDATE_EXISTING > VERIFY > DEPRECATE）
        assert prioritized_tasks[0].task_type == TaskType.GENERATE_NEW
        assert prioritized_tasks[1].task_type == TaskType.UPDATE_EXISTING
        assert prioritized_tasks[2].task_type == TaskType.VERIFY
        assert prioritized_tasks[3].task_type == TaskType.DEPRECATE
    
    def test_calculate_priority_with_context(self):
        """测试带上下文的优先级计算"""
        selector = TestSelector()
        
        # 创建测试任务
        task = TestTask(
            source_file="service/core.py",
            task_type=TaskType.GENERATE_NEW,
            priority=0
        )
        
        # 创建上下文
        context = {
            "core_patterns": ["service", "controller"],
            "low_coverage_files": {"service/core.py": 0.3},
            "recently_modified": ["service/core.py"],
            "failure_history": ["service/core.py"]
        }
        
        # 计算优先级
        priority = selector._calculate_priority(task, context)
        
        # 验证优先级计算结果
        # 基础优先级: 0
        # 任务类型: GENERATE_NEW (+30)
        # 核心模块: 是 (+25)
        # 低覆盖率: 是 (+20)
        # 最近修改: 是 (+15)
        # 失败历史: 是 (+10)
        # 总计: 0 + 30 + 25 + 20 + 15 + 10 = 100
        assert priority == 100
    
    def test_is_core_module(self):
        """测试核心模块判断"""
        selector = TestSelector()
        
        context = {
            "core_patterns": ["service", "controller", "repository"]
        }
        
        # 测试核心模块
        assert selector._is_core_module("service/user_service.py", context) is True
        assert selector._is_core_module("controller/api_controller.py", context) is True
        assert selector._is_core_module("repository/user_repository.py", context) is True
        
        # 测试非核心模块
        assert selector._is_core_module("utils/helpers.py", context) is False
        assert selector._is_core_module("models/user.py", context) is False
    
    def test_get_summary(self):
        """测试获取摘要"""
        selector = TestSelector(strategy=SelectionStrategy.SMART)
        
        # 创建测试任务
        task1 = TestTask(source_file="test1.py", task_type=TaskType.GENERATE_NEW)
        task2 = TestTask(source_file="test2.py", task_type=TaskType.UPDATE_EXISTING)
        task3 = TestTask(source_file="test3.py", task_type=TaskType.DEPRECATE)
        task4 = TestTask(source_file="test4.py", task_type=TaskType.VERIFY)
        
        # 创建选择结果
        result = SelectionResult()
        result.add_task(task1)
        result.add_task(task2)
        result.add_task(task3)
        result.add_task(task4)
        
        # 获取摘要
        summary = selector.get_summary(result)
        
        # 验证摘要
        assert summary["total_tasks"] == 4
        assert summary["generate_new"] == 1
        assert summary["update_existing"] == 1
        assert summary["deprecate"] == 1
        assert summary["verify"] == 1
        assert summary["strategy"] == "smart"


if __name__ == "__main__":
    pytest.main([__file__])
