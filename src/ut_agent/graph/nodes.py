"""LangGraph 节点实现."""

import asyncio
import os
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional
from langchain_core.runnables import RunnableConfig
from ut_agent.graph.state import (
    AgentState, GeneratedTestFile, CoverageGap, CodeChange, ChangeSummary,
)
from ut_agent.tools.project_detector import detect_project_type, find_source_files
from ut_agent.tools.code_analyzer import analyze_java_file, analyze_ts_file
from ut_agent.tools.test_generator import generate_java_test, generate_frontend_test
from ut_agent.tools.test_executor import execute_java_tests, execute_frontend_tests
from ut_agent.tools.coverage_analyzer import (
    parse_jacoco_report,
    parse_istanbul_report,
    identify_coverage_gaps,
)
from ut_agent.tools.git_analyzer import GitAnalyzer, filter_source_files
from ut_agent.tools.change_detector import create_change_detector
from ut_agent.tools.test_mapper import TestFileMapper
from ut_agent.reporting.html_generator import generate_coverage_report
from ut_agent.models import get_llm
from ut_agent.utils import get_logger


def get_optimal_thread_count() -> int:
    """获取最优线程数.

    根据 CPU 核心数和 I/O 密集型任务特点计算最优线程数。
    对于 I/O 密集型任务，线程数通常设置为 CPU 核心数的 2-4 倍。
    """
    from ut_agent.config import settings
    if settings.max_concurrent_threads > 0:
        return settings.max_concurrent_threads
    cpu_count = multiprocessing.cpu_count()
    optimal = min(cpu_count * 2, 8)
    return max(optimal, 2)


MAX_CONCURRENT_GENERATIONS = get_optimal_thread_count()
logger = get_logger("nodes")


async def detect_project_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """检测项目类型和结构."""
    project_path = state["project_path"]
    incremental = state.get("incremental", False)

    project_type, build_tool = detect_project_type(project_path)

    if incremental:
        try:
            git_analyzer = GitAnalyzer(project_path)
            base_ref = state.get("base_ref")
            head_ref = state.get("head_ref")
            code_changes = git_analyzer.get_changed_files(base_ref, head_ref)
            source_changes = filter_source_files(code_changes, project_type)
            source_files = [c.file_path for c in source_changes]

            return {
                "project_type": project_type,
                "build_tool": build_tool,
                "target_files": source_files,
                "code_changes": source_changes,
                "status": "project_detected",
                "message": f"增量模式：检测到 {len(source_files)} 个变更的源文件",
            }
        except Exception as e:
            logger.warning(f"Git分析失败，回退到全量分析: {e}")
            source_files = find_source_files(project_path, project_type)
            return {
                "project_type": project_type,
                "build_tool": build_tool,
                "target_files": source_files,
                "code_changes": [],
                "status": "project_detected",
                "message": f"Git分析失败({e})，回退到全量分析，找到 {len(source_files)} 个源文件",
            }
    else:
        source_files = find_source_files(project_path, project_type)
        return {
            "project_type": project_type,
            "build_tool": build_tool,
            "target_files": source_files,
            "code_changes": [],
            "status": "project_detected",
            "message": f"检测到 {project_type} 项目，使用 {build_tool} 构建工具，找到 {len(source_files)} 个源文件",
        }


async def detect_changes_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """检测代码变更详情."""
    project_path = state["project_path"]
    project_type = state["project_type"]
    code_changes = state.get("code_changes", [])

    if not code_changes:
        return {
            "change_summaries": [],
            "status": "changes_detected",
            "message": "没有检测到代码变更",
        }

    try:
        detector = create_change_detector(project_path, project_type)
        change_summaries = detector.analyze_changes(code_changes)

        total_added = sum(len(s.added_methods) for s in change_summaries)
        total_modified = sum(len(s.modified_methods) for s in change_summaries)
        total_deleted = sum(len(s.deleted_methods) for s in change_summaries)

        return {
            "change_summaries": change_summaries,
            "status": "changes_detected",
            "message": f"变更分析完成：新增 {total_added} 个方法，修改 {total_modified} 个方法，删除 {total_deleted} 个方法",
        }
    except Exception as e:
        logger.error(f"变更分析失败: {e}")
        return {
            "change_summaries": [],
            "status": "changes_error",
            "message": f"变更分析失败: {e}",
        }


async def analyze_code_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """分析源代码（支持并行分析）."""
    project_type = state["project_type"]
    target_files = state["target_files"]
    analyzed_files = []

    max_workers = config.get("configurable", {}).get("max_workers", MAX_CONCURRENT_GENERATIONS)

    def analyze_single_file(file_path: str) -> Optional[Dict[str, Any]]:
        try:
            if project_type == "java":
                return analyze_java_file(file_path)
            elif project_type in ["vue", "react", "typescript"]:
                return analyze_ts_file(file_path)
            return None
        except Exception as e:
            logger.error(f"分析文件失败 {file_path}: {e}")
            return None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        loop = asyncio.get_event_loop()
        futures = [
            loop.run_in_executor(executor, analyze_single_file, file_path)
            for file_path in target_files
        ]
        results = await asyncio.gather(*futures)

    analyzed_files = [r for r in results if r is not None]

    return {
        "analyzed_files": analyzed_files,
        "status": "code_analyzed",
        "message": f"成功分析 {len(analyzed_files)} 个文件",
    }


async def generate_tests_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """生成单元测试（支持并行生成）."""
    project_type = state["project_type"]
    analyzed_files = state["analyzed_files"]
    llm_provider = config.get("configurable", {}).get("llm_provider", "openai")
    max_workers = config.get("configurable", {}).get("max_workers", MAX_CONCURRENT_GENERATIONS)

    llm = get_llm(llm_provider)
    generated_tests = []

    def generate_single_test(file_analysis: Dict[str, Any]) -> Optional[GeneratedTestFile]:
        try:
            if project_type == "java":
                return generate_java_test(file_analysis, llm)
            elif project_type in ["vue", "react", "typescript"]:
                return generate_frontend_test(file_analysis, project_type, llm)
            return None
        except Exception as e:
            logger.error(f"生成测试失败: {e}")
            return None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        loop = asyncio.get_event_loop()
        futures = [
            loop.run_in_executor(executor, generate_single_test, file_analysis)
            for file_analysis in analyzed_files
        ]
        results = await asyncio.gather(*futures)

    generated_tests = [r for r in results if r is not None]

    return {
        "generated_tests": generated_tests,
        "status": "tests_generated",
        "message": f"成功生成 {len(generated_tests)} 个测试文件",
    }


async def save_tests_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """保存生成的测试文件."""
    generated_tests = state["generated_tests"]
    project_path = state["project_path"]
    project_type = state["project_type"]
    incremental = state.get("incremental", False)
    change_summaries = state.get("change_summaries", [])

    saved_count = 0
    warnings = []

    test_mapper = TestFileMapper(project_path, project_type)

    change_dict = {s.file_path: s for s in change_summaries}

    for test_file in generated_tests:
        try:
            test_dir = os.path.dirname(test_file.test_file_path)
            os.makedirs(test_dir, exist_ok=True)

            final_test_code = test_file.test_code

            if incremental:
                source_file = test_file.source_file
                if source_file in change_dict:
                    change_summary = change_dict[source_file]

                    source_content = ""
                    try:
                        with open(source_file, "r", encoding="utf-8") as f:
                            source_content = f.read()
                    except Exception as e:
                        logger.warning(f"读取源文件失败 {source_file}: {e}")

                    final_test_code, merge_warnings = test_mapper.update_mapping(
                        source_file=source_file,
                        new_source_content=source_content,
                        new_test_content=test_file.test_code,
                        added_methods=change_summary.added_methods,
                        modified_methods=change_summary.modified_methods,
                        deleted_methods=change_summary.deleted_methods,
                    )
                    warnings.extend(merge_warnings)

            with open(test_file.test_file_path, "w", encoding="utf-8") as f:
                f.write(final_test_code)

            saved_count += 1
        except Exception as e:
            logger.error(f"保存测试文件失败 {test_file.test_file_path}: {e}")
            warnings.append(f"保存测试文件失败 {test_file.test_file_path}: {e}")

    message = f"成功保存 {saved_count} 个测试文件"
    if warnings:
        message += f"，警告: {len(warnings)} 个"

    return {
        "status": "tests_saved",
        "message": message,
    }


async def execute_tests_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """执行测试."""
    project_path = state["project_path"]
    project_type = state["project_type"]
    build_tool = state["build_tool"]

    try:
        if project_type == "java":
            success, output = execute_java_tests(project_path, build_tool)
        elif project_type in ["vue", "react", "typescript"]:
            success, output = execute_frontend_tests(project_path)
        else:
            success, output = False, "不支持的项目类型"

        return {
            "status": "tests_executed" if success else "tests_failed",
            "message": output,
        }
    except Exception as e:
        logger.error(f"执行测试出错: {e}")
        return {
            "status": "execution_error",
            "message": f"执行测试出错: {e}",
        }


async def analyze_coverage_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """分析覆盖率报告."""
    project_path = state["project_path"]
    project_type = state["project_type"]

    try:
        if project_type == "java":
            coverage_report = parse_jacoco_report(project_path)
        elif project_type in ["vue", "react", "typescript"]:
            coverage_report = parse_istanbul_report(project_path)
        else:
            return {
                "status": "coverage_error",
                "message": "不支持的项目类型",
            }

        if coverage_report:
            gaps = identify_coverage_gaps(coverage_report, project_path)
            coverage_report.gaps = gaps

            return {
                "coverage_report": coverage_report,
                "current_coverage": coverage_report.overall_coverage,
                "coverage_gaps": gaps,
                "status": "coverage_analyzed",
                "message": f"当前覆盖率: {coverage_report.overall_coverage:.2f}%",
            }
        else:
            return {
                "status": "coverage_not_found",
                "message": "未找到覆盖率报告",
            }
    except Exception as e:
        logger.error(f"分析覆盖率出错: {e}")
        return {
            "status": "coverage_error",
            "message": f"分析覆盖率出错: {e}",
        }


async def check_coverage_target_node(
    state: AgentState, config: RunnableConfig
) -> Dict[str, Any]:
    """检查是否达到覆盖率目标."""
    current_coverage = state.get("current_coverage", 0)
    coverage_target = state["coverage_target"]
    iteration_count = state["iteration_count"]
    max_iterations = state["max_iterations"]

    if current_coverage >= coverage_target:
        return {
            "status": "target_reached",
            "message": f"覆盖率目标已达成! 当前: {current_coverage:.2f}% >= 目标: {coverage_target:.2f}%",
        }
    elif iteration_count >= max_iterations:
        return {
            "status": "max_iterations_reached",
            "message": f"达到最大迭代次数 ({max_iterations})，当前覆盖率: {current_coverage:.2f}%",
        }
    else:
        return {
            "status": "needs_improvement",
            "message": f"覆盖率未达标，当前: {current_coverage:.2f}% < 目标: {coverage_target:.2f}%",
        }


async def plan_improvement_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """制定改进计划."""
    coverage_gaps = state.get("coverage_gaps", [])
    analyzed_files = state["analyzed_files"]
    llm_provider = config.get("configurable", {}).get("llm_provider", "openai")

    llm = get_llm(llm_provider)

    gap_summary = "\n".join([
        f"- {gap.file_path}:{gap.line_number} ({gap.gap_type}): {gap.line_content[:50]}..."
        for gap in coverage_gaps[:20]
    ])

    prompt = f"""作为单元测试专家，请分析以下覆盖率缺口并制定改进计划:

覆盖率缺口:
{gap_summary}

需要补充的测试场景:
1. 边界条件测试
2. 异常路径测试
3. 分支覆盖测试

请提供具体的改进建议。"""

    try:
        response = await llm.ainvoke(prompt)
        improvement_plan = str(response.content)

        return {
            "improvement_plan": improvement_plan,
            "iteration_count": state["iteration_count"] + 1,
            "status": "improvement_planned",
            "message": "已制定改进计划",
        }
    except Exception as e:
        logger.error(f"制定改进计划出错: {e}")
        return {
            "improvement_plan": "",
            "iteration_count": state["iteration_count"] + 1,
            "status": "plan_error",
            "message": f"制定改进计划出错: {e}",
        }


async def generate_additional_tests_node(
    state: AgentState, config: RunnableConfig
) -> Dict[str, Any]:
    """生成补充测试."""
    coverage_gaps = state.get("coverage_gaps", [])
    analyzed_files = state["analyzed_files"]
    improvement_plan = state.get("improvement_plan", "")
    project_type = state["project_type"]
    llm_provider = config.get("configurable", {}).get("llm_provider", "openai")

    llm = get_llm(llm_provider)
    additional_tests = []

    for gap in coverage_gaps[:10]:
        try:
            file_analysis = next(
                (f for f in analyzed_files if f["file_path"] == gap.file_path), None
            )
            if file_analysis:
                if project_type == "java":
                    test_file = generate_java_test(
                        file_analysis, llm, gap_info=gap, plan=improvement_plan
                    )
                else:
                    test_file = generate_frontend_test(
                        file_analysis, project_type, llm, gap_info=gap, plan=improvement_plan
                    )

                additional_tests.append(test_file)
        except Exception as e:
            logger.error(f"生成补充测试失败: {e}")

    return {
        "generated_tests": additional_tests,
        "status": "additional_tests_generated",
        "message": f"生成了 {len(additional_tests)} 个补充测试",
    }


async def generate_html_report_node(
    state: AgentState, config: RunnableConfig
) -> Dict[str, Any]:
    """生成HTML报告."""
    from pathlib import Path
    
    project_path = state["project_path"]
    coverage_report = state.get("coverage_report")

    if not coverage_report:
        return {
            "html_report_path": None,
            "status": state["status"],
            "message": "无覆盖率数据，跳过HTML报告生成",
        }

    try:
        report_path = generate_coverage_report(
            project_path=project_path,
            coverage_report=coverage_report,
            project_name=Path(project_path).name,
        )
        return {
            "html_report_path": report_path,
            "status": state["status"],
            "message": f"HTML报告已生成: {report_path}",
        }
    except Exception as e:
        logger.error(f"HTML报告生成失败: {e}")
        return {
            "html_report_path": None,
            "status": state["status"],
            "message": f"HTML报告生成失败: {e}",
        }


async def finalize_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """完成工作流."""
    coverage_report = state.get("coverage_report")
    generated_tests = state.get("generated_tests", [])
    status = state["status"]
    html_report_path = state.get("html_report_path")
    incremental = state.get("incremental", False)

    summary = f"""
测试生成完成!

状态: {status}
生成测试文件数: {len(generated_tests)}
模式: {"增量" if incremental else "全量"}
"""

    if coverage_report:
        summary += f"""
覆盖率统计:
- 总体覆盖率: {coverage_report.overall_coverage:.2f}%
- 行覆盖率: {coverage_report.line_coverage:.2f}%
- 分支覆盖率: {coverage_report.branch_coverage:.2f}%
- 方法覆盖率: {coverage_report.method_coverage:.2f}%
"""

    if html_report_path:
        summary += f"""
HTML报告: {html_report_path}
"""

    return {
        "summary": summary,
        "status": "completed",
        "message": "测试生成工作流已完成",
    }
