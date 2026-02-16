"""LangGraph 节点实现单元测试."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ut_agent.graph.nodes import (
    analyze_code_node,
    analyze_coverage_node,
    check_coverage_target_node,
    detect_changes_node,
    detect_project_node,
    execute_tests_node,
    generate_tests_node,
    save_tests_node,
)
from ut_agent.graph.state import AgentState, CoverageReport, GeneratedTestFile


class TestDetectProjectNode:
    """detect_project_node 测试."""

    @pytest.mark.asyncio
    @patch("ut_agent.graph.nodes.detect_project_type")
    @patch("ut_agent.graph.nodes.find_source_files")
    async def test_detect_project_full_mode(self, mock_find_files, mock_detect):
        """测试全量模式项目检测."""
        mock_detect.return_value = ("java", "maven")
        mock_find_files.return_value = ["/src/Main.java", "/src/Service.java"]

        state: AgentState = {
            "project_path": "/project",
            "project_type": "",
            "build_tool": "",
            "target_files": [],
            "coverage_target": 80.0,
            "max_iterations": 10,
            "iteration_count": 0,
            "status": "initialized",
            "message": "",
            "analyzed_files": [],
            "generated_tests": [],
            "coverage_report": None,
            "current_coverage": 0.0,
            "coverage_gaps": [],
            "improvement_plan": None,
            "output_path": None,
            "summary": None,
        }

        config = {"configurable": {}}

        result = await detect_project_node(state, config)

        assert result["project_type"] == "java"
        assert result["build_tool"] == "maven"
        assert len(result["target_files"]) == 2
        assert result["status"] == "project_detected"

    @pytest.mark.asyncio
    @patch("ut_agent.graph.nodes.detect_project_type")
    @patch("ut_agent.graph.nodes.GitAnalyzer")
    async def test_detect_project_incremental_mode(self, mock_git, mock_detect):
        """测试增量模式项目检测."""
        mock_detect.return_value = ("java", "maven")

        mock_git_analyzer = Mock()
        mock_changes = [
            Mock(file_path="/src/Main.java"),
            Mock(file_path="/src/Service.java"),
        ]
        mock_git_analyzer.get_changed_files.return_value = mock_changes
        mock_git.return_value = mock_git_analyzer

        with patch("ut_agent.graph.nodes.filter_source_files") as mock_filter:
            mock_filter.return_value = mock_changes

            state: AgentState = {
                "project_path": "/project",
                "project_type": "",
                "build_tool": "",
                "target_files": [],
                "coverage_target": 80.0,
                "max_iterations": 10,
                "iteration_count": 0,
                "status": "initialized",
                "message": "",
                "analyzed_files": [],
                "generated_tests": [],
                "coverage_report": None,
                "current_coverage": 0.0,
                "coverage_gaps": [],
                "improvement_plan": None,
                "output_path": None,
                "summary": None,
                "incremental": True,
                "base_ref": "main",
                "head_ref": "feature",
            }

            config = {"configurable": {}}

            result = await detect_project_node(state, config)

            assert result["project_type"] == "java"
            assert result["status"] == "project_detected"
            assert len(result["target_files"]) == 2


class TestDetectChangesNode:
    """detect_changes_node 测试."""

    @pytest.mark.asyncio
    @patch("ut_agent.graph.nodes.create_change_detector")
    async def test_detect_changes_with_changes(self, mock_create_detector):
        """测试检测代码变更."""
        mock_detector = Mock()
        mock_summary = Mock(
            added_methods=["method1"],
            modified_methods=["method2"],
            deleted_methods=["method3"],
        )
        mock_detector.analyze_changes.return_value = [mock_summary]
        mock_create_detector.return_value = mock_detector

        state: AgentState = {
            "project_path": "/project",
            "project_type": "java",
            "build_tool": "maven",
            "target_files": [],
            "coverage_target": 80.0,
            "max_iterations": 10,
            "iteration_count": 0,
            "status": "project_detected",
            "message": "",
            "analyzed_files": [],
            "generated_tests": [],
            "coverage_report": None,
            "current_coverage": 0.0,
            "coverage_gaps": [],
            "improvement_plan": None,
            "output_path": None,
            "summary": None,
            "code_changes": [Mock(file_path="/src/Main.java")],
        }

        config = {"configurable": {}}

        result = await detect_changes_node(state, config)

        assert result["status"] == "changes_detected"
        assert len(result["change_summaries"]) == 1

    @pytest.mark.asyncio
    async def test_detect_changes_no_changes(self):
        """测试无代码变更."""
        state: AgentState = {
            "project_path": "/project",
            "project_type": "java",
            "build_tool": "maven",
            "target_files": [],
            "coverage_target": 80.0,
            "max_iterations": 10,
            "iteration_count": 0,
            "status": "project_detected",
            "message": "",
            "analyzed_files": [],
            "generated_tests": [],
            "coverage_report": None,
            "current_coverage": 0.0,
            "coverage_gaps": [],
            "improvement_plan": None,
            "output_path": None,
            "summary": None,
            "code_changes": [],
        }

        config = {"configurable": {}}

        result = await detect_changes_node(state, config)

        assert result["status"] == "changes_detected"
        assert result["change_summaries"] == []


class TestAnalyzeCodeNode:
    """analyze_code_node 测试."""

    @pytest.mark.asyncio
    @patch("ut_agent.graph.nodes.analyze_java_file")
    async def test_analyze_code_java(self, mock_analyze):
        """测试分析 Java 代码."""
        mock_analyze.return_value = {
            "file_path": "/src/Main.java",
            "language": "java",
            "class_name": "Main",
        }

        state: AgentState = {
            "project_path": "/project",
            "project_type": "java",
            "build_tool": "maven",
            "target_files": ["/src/Main.java"],
            "coverage_target": 80.0,
            "max_iterations": 10,
            "iteration_count": 0,
            "status": "project_detected",
            "message": "",
            "analyzed_files": [],
            "generated_tests": [],
            "coverage_report": None,
            "current_coverage": 0.0,
            "coverage_gaps": [],
            "improvement_plan": None,
            "output_path": None,
            "summary": None,
        }

        config = {"configurable": {}}

        result = await analyze_code_node(state, config)

        assert result["status"] == "code_analyzed"
        assert len(result["analyzed_files"]) == 1

    @pytest.mark.asyncio
    @patch("ut_agent.graph.nodes.analyze_ts_file")
    async def test_analyze_code_typescript(self, mock_analyze):
        """测试分析 TypeScript 代码."""
        mock_analyze.return_value = {
            "file_path": "/src/app.ts",
            "language": "typescript",
            "functions": [{"name": "main"}],
        }

        state: AgentState = {
            "project_path": "/project",
            "project_type": "typescript",
            "build_tool": "npm",
            "target_files": ["/src/app.ts"],
            "coverage_target": 80.0,
            "max_iterations": 10,
            "iteration_count": 0,
            "status": "project_detected",
            "message": "",
            "analyzed_files": [],
            "generated_tests": [],
            "coverage_report": None,
            "current_coverage": 0.0,
            "coverage_gaps": [],
            "improvement_plan": None,
            "output_path": None,
            "summary": None,
        }

        config = {"configurable": {}}

        result = await analyze_code_node(state, config)

        assert result["status"] == "code_analyzed"


class TestGenerateTestsNode:
    """generate_tests_node 测试."""

    @pytest.mark.asyncio
    @patch("ut_agent.graph.nodes.get_llm")
    @patch("ut_agent.graph.nodes.generate_java_test")
    async def test_generate_tests_java(self, mock_generate, mock_get_llm):
        """测试生成 Java 测试."""
        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm

        mock_test = GeneratedTestFile(
            source_file="/src/Main.java",
            test_file_path="/src/test/MainTest.java",
            test_code="public class MainTest {}",
            language="java",
        )
        mock_generate.return_value = mock_test

        state: AgentState = {
            "project_path": "/project",
            "project_type": "java",
            "build_tool": "maven",
            "target_files": [],
            "coverage_target": 80.0,
            "max_iterations": 10,
            "iteration_count": 0,
            "status": "code_analyzed",
            "message": "",
            "analyzed_files": [{"file_path": "/src/Main.java", "class_name": "Main"}],
            "generated_tests": [],
            "coverage_report": None,
            "current_coverage": 0.0,
            "coverage_gaps": [],
            "improvement_plan": None,
            "output_path": None,
            "summary": None,
        }

        config = {"configurable": {}}

        result = await generate_tests_node(state, config)

        assert result["status"] == "tests_generated"
        assert len(result["generated_tests"]) == 1


class TestSaveTestsNode:
    """save_tests_node 测试."""

    @pytest.mark.asyncio
    async def test_save_tests_success(self):
        """测试保存测试文件成功."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = GeneratedTestFile(
                source_file=f"{tmpdir}/Main.java",
                test_file_path=f"{tmpdir}/test/MainTest.java",
                test_code="public class MainTest {}",
                language="java",
            )

            state: AgentState = {
                "project_path": tmpdir,
                "project_type": "java",
                "build_tool": "maven",
                "target_files": [],
                "coverage_target": 80.0,
                "max_iterations": 10,
                "iteration_count": 0,
                "status": "tests_generated",
                "message": "",
                "analyzed_files": [],
                "generated_tests": [test_file],
                "coverage_report": None,
                "current_coverage": 0.0,
                "coverage_gaps": [],
                "improvement_plan": None,
                "output_path": None,
                "summary": None,
            }

            config = {"configurable": {}}

            result = await save_tests_node(state, config)

            assert result["status"] == "tests_saved"
            assert Path(f"{tmpdir}/test/MainTest.java").exists()


class TestExecuteTestsNode:
    """execute_tests_node 测试."""

    @pytest.mark.asyncio
    @patch("ut_agent.graph.nodes.execute_java_tests")
    async def test_execute_tests_java_success(self, mock_execute):
        """测试执行 Java 测试成功."""
        mock_execute.return_value = (True, "Tests passed")

        state: AgentState = {
            "project_path": "/project",
            "project_type": "java",
            "build_tool": "maven",
            "target_files": [],
            "coverage_target": 80.0,
            "max_iterations": 10,
            "iteration_count": 0,
            "status": "tests_saved",
            "message": "",
            "analyzed_files": [],
            "generated_tests": [],
            "coverage_report": None,
            "current_coverage": 0.0,
            "coverage_gaps": [],
            "improvement_plan": None,
            "output_path": None,
            "summary": None,
        }

        config = {"configurable": {}}

        result = await execute_tests_node(state, config)

        assert result["status"] == "tests_executed"

    @pytest.mark.asyncio
    @patch("ut_agent.graph.nodes.execute_java_tests")
    async def test_execute_tests_java_failure(self, mock_execute):
        """测试执行 Java 测试失败."""
        mock_execute.return_value = (False, "Tests failed")

        state: AgentState = {
            "project_path": "/project",
            "project_type": "java",
            "build_tool": "maven",
            "target_files": [],
            "coverage_target": 80.0,
            "max_iterations": 10,
            "iteration_count": 0,
            "status": "tests_saved",
            "message": "",
            "analyzed_files": [],
            "generated_tests": [],
            "coverage_report": None,
            "current_coverage": 0.0,
            "coverage_gaps": [],
            "improvement_plan": None,
            "output_path": None,
            "summary": None,
        }

        config = {"configurable": {}}

        result = await execute_tests_node(state, config)

        assert result["status"] == "tests_failed"


class TestAnalyzeCoverageNode:
    """analyze_coverage_node 测试."""

    @pytest.mark.asyncio
    @patch("ut_agent.graph.nodes.parse_jacoco_report")
    @patch("ut_agent.graph.nodes.identify_coverage_gaps")
    async def test_analyze_coverage_java(self, mock_gaps, mock_parse):
        """测试分析 Java 覆盖率."""
        mock_report = CoverageReport(
            overall_coverage=75.0,
            line_coverage=80.0,
            branch_coverage=70.0,
            method_coverage=75.0,
            class_coverage=75.0,
            total_lines=100,
            covered_lines=80,
            total_branches=40,
            covered_branches=28,
        )
        mock_parse.return_value = mock_report
        mock_gaps.return_value = []

        state: AgentState = {
            "project_path": "/project",
            "project_type": "java",
            "build_tool": "maven",
            "target_files": [],
            "coverage_target": 80.0,
            "max_iterations": 10,
            "iteration_count": 0,
            "status": "tests_executed",
            "message": "",
            "analyzed_files": [],
            "generated_tests": [],
            "coverage_report": None,
            "current_coverage": 0.0,
            "coverage_gaps": [],
            "improvement_plan": None,
            "output_path": None,
            "summary": None,
        }

        config = {"configurable": {}}

        result = await analyze_coverage_node(state, config)

        assert result["status"] == "coverage_analyzed"
        assert result["current_coverage"] == 75.0
        assert result["coverage_report"] is not None


class TestCheckCoverageTargetNode:
    """check_coverage_target_node 测试."""

    @pytest.mark.asyncio
    async def test_check_target_reached(self):
        """测试达到覆盖率目标."""
        state: AgentState = {
            "project_path": "/project",
            "project_type": "java",
            "build_tool": "maven",
            "target_files": [],
            "coverage_target": 80.0,
            "max_iterations": 10,
            "iteration_count": 2,
            "status": "coverage_analyzed",
            "message": "",
            "analyzed_files": [],
            "generated_tests": [],
            "coverage_report": None,
            "current_coverage": 85.0,  # 超过目标
            "coverage_gaps": [],
            "improvement_plan": None,
            "output_path": None,
            "summary": None,
        }

        config = {"configurable": {}}
        result = await check_coverage_target_node(state, config)

        assert result["status"] == "target_reached"

    @pytest.mark.asyncio
    async def test_check_max_iterations_reached(self):
        """测试达到最大迭代次数."""
        state: AgentState = {
            "project_path": "/project",
            "project_type": "java",
            "build_tool": "maven",
            "target_files": [],
            "coverage_target": 80.0,
            "max_iterations": 3,
            "iteration_count": 3,
            "status": "coverage_analyzed",
            "message": "",
            "analyzed_files": [],
            "generated_tests": [],
            "coverage_report": None,
            "current_coverage": 70.0,  # 未达到目标
            "coverage_gaps": [],
            "improvement_plan": None,
            "output_path": None,
            "summary": None,
        }

        config = {"configurable": {}}
        result = await check_coverage_target_node(state, config)

        assert result["status"] == "max_iterations_reached"

    @pytest.mark.asyncio
    async def test_check_needs_improvement(self):
        """测试需要改进."""
        state: AgentState = {
            "project_path": "/project",
            "project_type": "java",
            "build_tool": "maven",
            "target_files": [],
            "coverage_target": 80.0,
            "max_iterations": 10,
            "iteration_count": 2,
            "status": "coverage_analyzed",
            "message": "",
            "analyzed_files": [],
            "generated_tests": [],
            "coverage_report": None,
            "current_coverage": 70.0,  # 未达到目标
            "coverage_gaps": [],
            "improvement_plan": None,
            "output_path": None,
            "summary": None,
        }

        config = {"configurable": {}}
        result = await check_coverage_target_node(state, config)

        assert result["status"] == "needs_improvement"
