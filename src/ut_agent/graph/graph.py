"""LangGraph 工作流构建."""

from langgraph.graph import StateGraph, END
from ut_agent.graph.state import AgentState
from ut_agent.graph.nodes import (
    detect_project_node,
    analyze_code_node,
    generate_tests_node,
    save_tests_node,
    execute_tests_node,
    analyze_coverage_node,
    check_coverage_target_node,
    plan_improvement_node,
    generate_additional_tests_node,
    finalize_node,
)


def create_test_generation_graph() -> StateGraph:
    """创建测试生成工作流图.

    Returns:
        StateGraph: 编译后的状态图
    """
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("detect_project", detect_project_node)
    workflow.add_node("analyze_code", analyze_code_node)
    workflow.add_node("generate_tests", generate_tests_node)
    workflow.add_node("save_tests", save_tests_node)
    workflow.add_node("execute_tests", execute_tests_node)
    workflow.add_node("analyze_coverage", analyze_coverage_node)
    workflow.add_node("check_coverage_target", check_coverage_target_node)
    workflow.add_node("plan_improvement", plan_improvement_node)
    workflow.add_node("generate_additional_tests", generate_additional_tests_node)
    workflow.add_node("finalize", finalize_node)

    # 设置入口点
    workflow.set_entry_point("detect_project")

    # 添加边 - 主流程
    workflow.add_edge("detect_project", "analyze_code")
    workflow.add_edge("analyze_code", "generate_tests")
    workflow.add_edge("generate_tests", "save_tests")
    workflow.add_edge("save_tests", "execute_tests")
    workflow.add_edge("execute_tests", "analyze_coverage")
    workflow.add_edge("analyze_coverage", "check_coverage_target")

    # 条件边 - 根据覆盖率检查结果决定下一步
    workflow.add_conditional_edges(
        "check_coverage_target",
        lambda state: state["status"],
        {
            "target_reached": "finalize",
            "max_iterations_reached": "finalize",
            "needs_improvement": "plan_improvement",
        },
    )

    # 迭代改进循环
    workflow.add_edge("plan_improvement", "generate_additional_tests")
    workflow.add_edge("generate_additional_tests", "save_tests")

    # 结束节点
    workflow.add_edge("finalize", END)

    return workflow.compile()


def create_test_generation_graph_with_interrupt() -> StateGraph:
    """创建支持中断的测试生成工作流图 (用于人机协作).

    Returns:
        StateGraph: 编译后的状态图
    """
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("detect_project", detect_project_node)
    workflow.add_node("analyze_code", analyze_code_node)
    workflow.add_node("generate_tests", generate_tests_node)
    workflow.add_node("save_tests", save_tests_node)
    workflow.add_node("execute_tests", execute_tests_node)
    workflow.add_node("analyze_coverage", analyze_coverage_node)
    workflow.add_node("check_coverage_target", check_coverage_target_node)
    workflow.add_node("plan_improvement", plan_improvement_node)
    workflow.add_node("generate_additional_tests", generate_additional_tests_node)
    workflow.add_node("finalize", finalize_node)

    # 设置入口点
    workflow.set_entry_point("detect_project")

    # 添加边
    workflow.add_edge("detect_project", "analyze_code")
    workflow.add_edge("analyze_code", "generate_tests")
    workflow.add_edge("generate_tests", "save_tests")
    workflow.add_edge("save_tests", "execute_tests")
    workflow.add_edge("execute_tests", "analyze_coverage")
    workflow.add_edge("analyze_coverage", "check_coverage_target")

    # 条件边
    workflow.add_conditional_edges(
        "check_coverage_target",
        lambda state: state["status"],
        {
            "target_reached": "finalize",
            "max_iterations_reached": "finalize",
            "needs_improvement": "plan_improvement",
        },
    )

    # 迭代改进循环
    workflow.add_edge("plan_improvement", "generate_additional_tests")
    workflow.add_edge("generate_additional_tests", "save_tests")

    # 结束节点
    workflow.add_edge("finalize", END)

    # 在关键节点设置中断点，允许人工审查
    return workflow.compile(
        interrupt_before=["save_tests", "plan_improvement"],
        interrupt_after=["generate_tests", "analyze_coverage"],
    )
