"""LangGraph 工作流构建测试."""

from unittest.mock import Mock, patch

import pytest

from ut_agent.graph.graph import (
    create_test_generation_graph,
    create_test_generation_graph_with_interrupt,
)


class TestGraphCreation:
    """工作流图创建测试."""

    def test_create_test_generation_graph(self):
        """测试创建测试生成工作流图."""
        # 补丁所有节点函数
        with patch('ut_agent.graph.graph.detect_project_node') as mock_detect_project, \
             patch('ut_agent.graph.graph.detect_changes_node') as mock_detect_changes, \
             patch('ut_agent.graph.graph.analyze_code_node') as mock_analyze_code, \
             patch('ut_agent.graph.graph.generate_tests_node') as mock_generate_tests, \
             patch('ut_agent.graph.graph.save_tests_node') as mock_save_tests, \
             patch('ut_agent.graph.graph.execute_tests_node') as mock_execute_tests, \
             patch('ut_agent.graph.graph.analyze_coverage_node') as mock_analyze_coverage, \
             patch('ut_agent.graph.graph.check_coverage_target_node') as mock_check_coverage, \
             patch('ut_agent.graph.graph.plan_improvement_node') as mock_plan_improvement, \
             patch('ut_agent.graph.graph.generate_additional_tests_node') as mock_generate_additional, \
             patch('ut_agent.graph.graph.generate_html_report_node') as mock_generate_html, \
             patch('ut_agent.graph.graph.finalize_node') as mock_finalize:

            # 创建工作流图
            graph = create_test_generation_graph()

            # 验证返回的是编译后的图
            assert graph is not None
            assert hasattr(graph, 'invoke')  # 编译后的图应该有 invoke 方法

    def test_create_test_generation_graph_with_interrupt(self):
        """测试创建支持中断的测试生成工作流图."""
        # 补丁所有节点函数
        with patch('ut_agent.graph.graph.detect_project_node') as mock_detect_project, \
             patch('ut_agent.graph.graph.analyze_code_node') as mock_analyze_code, \
             patch('ut_agent.graph.graph.generate_tests_node') as mock_generate_tests, \
             patch('ut_agent.graph.graph.save_tests_node') as mock_save_tests, \
             patch('ut_agent.graph.graph.execute_tests_node') as mock_execute_tests, \
             patch('ut_agent.graph.graph.analyze_coverage_node') as mock_analyze_coverage, \
             patch('ut_agent.graph.graph.check_coverage_target_node') as mock_check_coverage, \
             patch('ut_agent.graph.graph.plan_improvement_node') as mock_plan_improvement, \
             patch('ut_agent.graph.graph.generate_additional_tests_node') as mock_generate_additional, \
             patch('ut_agent.graph.graph.finalize_node') as mock_finalize:

            # 创建带中断的工作流图
            graph = create_test_generation_graph_with_interrupt()

            # 验证返回的是编译后的图
            assert graph is not None
            assert hasattr(graph, 'invoke')  # 编译后的图应该有 invoke 方法

    def test_graph_structure_main_workflow(self):
        """测试主工作流的结构."""
        # 这里我们主要测试函数能够正常执行，不测试具体的图结构
        # 因为图结构的验证需要更复杂的测试方法
        try:
            graph = create_test_generation_graph()
            assert graph is not None
        except Exception as e:
            pytest.fail(f"创建工作流图失败: {e}")

    def test_graph_structure_interrupt_workflow(self):
        """测试带中断的工作流结构."""
        try:
            graph = create_test_generation_graph_with_interrupt()
            assert graph is not None
        except Exception as e:
            pytest.fail(f"创建带中断的工作流图失败: {e}")

    def test_graph_compilation(self):
        """测试工作流编译."""
        # 验证两个函数都能成功编译工作流
        graph1 = create_test_generation_graph()
        assert graph1 is not None

        graph2 = create_test_generation_graph_with_interrupt()
        assert graph2 is not None

        # 验证两个图是不同的实例
        assert graph1 is not graph2

    def test_edge_cases(self):
        """测试边缘情况."""
        # 测试函数调用时的异常处理
        # 这里主要依赖于 LangGraph 的异常处理
        # 我们只需要确保函数能够被调用即可
        try:
            create_test_generation_graph()
            create_test_generation_graph_with_interrupt()
        except Exception as e:
            pytest.fail(f"工作流创建失败: {e}")
