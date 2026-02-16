"""Agent 状态定义模块单元测试."""

from dataclasses import asdict

import pytest

from ut_agent.graph.state import AgentState, CoverageGap, CoverageReport, GeneratedTestFile


class TestGeneratedTestFile:
    """GeneratedTestFile 数据类测试."""

    def test_generated_test_file_creation(self):
        """测试 GeneratedTestFile 创建."""
        test_file = GeneratedTestFile(
            source_file="/project/src/UserService.java",
            test_file_path="/project/src/test/UserServiceTest.java",
            test_code="public class UserServiceTest {}",
            language="java",
        )

        assert test_file.source_file == "/project/src/UserService.java"
        assert test_file.test_file_path == "/project/src/test/UserServiceTest.java"
        assert test_file.test_code == "public class UserServiceTest {}"
        assert test_file.language == "java"
        assert test_file.status == "pending"
        assert test_file.error_message is None

    def test_generated_test_file_with_error(self):
        """测试带错误信息的 GeneratedTestFile."""
        test_file = GeneratedTestFile(
            source_file="/project/src/Error.java",
            test_file_path="/project/src/test/ErrorTest.java",
            test_code="",
            language="java",
            status="failed",
            error_message="Compilation error",
        )

        assert test_file.status == "failed"
        assert test_file.error_message == "Compilation error"

    def test_generated_test_file_asdict(self):
        """测试 GeneratedTestFile 转换为字典."""
        test_file = GeneratedTestFile(
            source_file="/src/Test.java",
            test_file_path="/src/TestTest.java",
            test_code="code",
            language="java",
        )

        d = asdict(test_file)
        assert d["source_file"] == "/src/Test.java"
        assert d["language"] == "java"


class TestCoverageGap:
    """CoverageGap 数据类测试."""

    def test_coverage_gap_creation(self):
        """测试 CoverageGap 创建."""
        gap = CoverageGap(
            file_path="/project/src/Service.java",
            line_number=42,
            line_content="if (condition) {",
            gap_type="branch",
        )

        assert gap.file_path == "/project/src/Service.java"
        assert gap.line_number == 42
        assert gap.line_content == "if (condition) {"
        assert gap.gap_type == "branch"
        assert gap.branch_info is None  # 默认值

    def test_coverage_gap_with_branch_info(self):
        """测试带分支信息的 CoverageGap."""
        gap = CoverageGap(
            file_path="/project/src/Service.java",
            line_number=50,
            line_content="return result;",
            gap_type="line",
            branch_info="true branch not covered",
        )

        assert gap.branch_info == "true branch not covered"


class TestCoverageReport:
    """CoverageReport 数据类测试."""

    def test_coverage_report_creation(self):
        """测试 CoverageReport 创建."""
        report = CoverageReport(
            overall_coverage=75.5,
            line_coverage=80.0,
            branch_coverage=70.0,
            method_coverage=85.0,
            class_coverage=75.0,
            total_lines=100,
            covered_lines=80,
            total_branches=40,
            covered_branches=28,
        )

        assert report.overall_coverage == 75.5
        assert report.line_coverage == 80.0
        assert report.branch_coverage == 70.0
        assert report.total_lines == 100
        assert report.covered_lines == 80

    def test_coverage_report_with_gaps(self):
        """测试带缺口的 CoverageReport."""
        gap1 = CoverageGap("file1.java", 10, "content1", "line")
        gap2 = CoverageGap("file2.java", 20, "content2", "branch")

        report = CoverageReport(
            overall_coverage=60.0,
            line_coverage=65.0,
            branch_coverage=55.0,
            method_coverage=70.0,
            class_coverage=60.0,
            total_lines=200,
            covered_lines=130,
            total_branches=80,
            covered_branches=44,
            gaps=[gap1, gap2],
        )

        assert len(report.gaps) == 2
        assert report.gaps[0].file_path == "file1.java"
        assert report.gaps[1].file_path == "file2.java"

    def test_coverage_report_with_raw_data(self):
        """测试带原始数据的 CoverageReport."""
        raw_data = {"line_covered": 80, "line_missed": 20, "custom_key": "value"}

        report = CoverageReport(
            overall_coverage=80.0,
            line_coverage=80.0,
            branch_coverage=75.0,
            method_coverage=85.0,
            class_coverage=80.0,
            total_lines=100,
            covered_lines=80,
            total_branches=40,
            covered_branches=30,
            raw_report=raw_data,
        )

        assert report.raw_report["custom_key"] == "value"
        assert report.raw_report["line_covered"] == 80

    def test_coverage_report_defaults(self):
        """测试 CoverageReport 默认值."""
        report = CoverageReport(
            overall_coverage=0.0,
            line_coverage=0.0,
            branch_coverage=0.0,
            method_coverage=0.0,
            class_coverage=0.0,
            total_lines=0,
            covered_lines=0,
            total_branches=0,
            covered_branches=0,
        )

        assert report.gaps == []
        assert report.raw_report == {}


class TestAgentState:
    """AgentState TypedDict 测试."""

    def test_agent_state_creation(self):
        """测试 AgentState 创建."""
        state: AgentState = {
            "project_path": "/project",
            "project_type": "java",
            "build_tool": "maven",
            "target_files": ["src/Main.java", "src/Service.java"],
            "coverage_target": 80.0,
            "max_iterations": 10,
            "iteration_count": 0,
            "status": "initialized",
            "message": "Starting...",
            "analyzed_files": [],
            "generated_tests": [],
            "coverage_report": None,
            "current_coverage": 0.0,
            "coverage_gaps": [],
            "improvement_plan": None,
            "output_path": None,
            "summary": None,
        }

        assert state["project_path"] == "/project"
        assert state["project_type"] == "java"
        assert state["coverage_target"] == 80.0

    def test_agent_state_with_coverage_report(self):
        """测试带覆盖率报告的 AgentState."""
        report = CoverageReport(
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

        state: AgentState = {
            "project_path": "/project",
            "project_type": "java",
            "build_tool": "maven",
            "target_files": [],
            "coverage_target": 80.0,
            "max_iterations": 10,
            "iteration_count": 1,
            "status": "coverage_analyzed",
            "message": "Coverage analyzed",
            "analyzed_files": [],
            "generated_tests": [],
            "coverage_report": report,
            "current_coverage": 75.0,
            "coverage_gaps": [],
            "improvement_plan": None,
            "output_path": None,
            "summary": None,
        }

        assert state["coverage_report"] is not None
        assert state["coverage_report"].overall_coverage == 75.0
        assert state["current_coverage"] == 75.0

    def test_agent_state_with_test_files(self):
        """测试带测试文件的 AgentState."""
        test_file1 = GeneratedTestFile(
            source_file="/src/Service.java",
            test_file_path="/src/test/ServiceTest.java",
            test_code="test code 1",
            language="java",
        )
        test_file2 = GeneratedTestFile(
            source_file="/src/Controller.java",
            test_file_path="/src/test/ControllerTest.java",
            test_code="test code 2",
            language="java",
        )

        state: AgentState = {
            "project_path": "/project",
            "project_type": "java",
            "build_tool": "maven",
            "target_files": [],
            "coverage_target": 80.0,
            "max_iterations": 10,
            "iteration_count": 1,
            "status": "tests_generated",
            "message": "Tests generated",
            "analyzed_files": [],
            "generated_tests": [test_file1, test_file2],
            "coverage_report": None,
            "current_coverage": 0.0,
            "coverage_gaps": [],
            "improvement_plan": None,
            "output_path": None,
            "summary": None,
        }

        assert len(state["generated_tests"]) == 2
        assert state["generated_tests"][0].source_file == "/src/Service.java"

    def test_agent_state_with_gaps(self):
        """测试带覆盖率缺口的 AgentState."""
        gaps = [
            CoverageGap("file1.java", 10, "content1", "line"),
            CoverageGap("file2.java", 20, "content2", "branch"),
        ]

        state: AgentState = {
            "project_path": "/project",
            "project_type": "java",
            "build_tool": "maven",
            "target_files": [],
            "coverage_target": 80.0,
            "max_iterations": 10,
            "iteration_count": 2,
            "status": "needs_improvement",
            "message": "Coverage needs improvement",
            "analyzed_files": [],
            "generated_tests": [],
            "coverage_report": None,
            "current_coverage": 60.0,
            "coverage_gaps": gaps,
            "improvement_plan": "Add more tests",
            "output_path": None,
            "summary": None,
        }

        assert len(state["coverage_gaps"]) == 2
        assert state["improvement_plan"] == "Add more tests"

    def test_agent_state_with_analyzed_files(self):
        """测试带分析文件的 AgentState."""
        analyzed = [
            {"file_path": "/src/Service.java", "language": "java", "methods": []},
            {"file_path": "/src/Controller.java", "language": "java", "methods": []},
        ]

        state: AgentState = {
            "project_path": "/project",
            "project_type": "java",
            "build_tool": "maven",
            "target_files": ["/src/Service.java", "/src/Controller.java"],
            "coverage_target": 80.0,
            "max_iterations": 10,
            "iteration_count": 1,
            "status": "code_analyzed",
            "message": "Code analyzed",
            "analyzed_files": analyzed,
            "generated_tests": [],
            "coverage_report": None,
            "current_coverage": 0.0,
            "coverage_gaps": [],
            "improvement_plan": None,
            "output_path": None,
            "summary": None,
        }

        assert len(state["analyzed_files"]) == 2
        assert state["analyzed_files"][0]["file_path"] == "/src/Service.java"


class TestStateTransitions:
    """状态转换测试."""

    def test_initial_to_project_detected(self):
        """测试从初始状态到项目检测状态的转换."""
        initial_state: AgentState = {
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

        # 模拟状态更新
        updated_state: AgentState = {
            **initial_state,
            "project_type": "java",
            "build_tool": "maven",
            "target_files": ["src/Main.java"],
            "status": "project_detected",
            "message": "Project detected",
        }

        assert updated_state["status"] == "project_detected"
        assert updated_state["project_type"] == "java"

    def test_coverage_target_reached(self):
        """测试达到覆盖率目标的状态."""
        report = CoverageReport(
            overall_coverage=85.0,
            line_coverage=90.0,
            branch_coverage=80.0,
            method_coverage=85.0,
            class_coverage=85.0,
            total_lines=100,
            covered_lines=90,
            total_branches=40,
            covered_branches=32,
        )

        state: AgentState = {
            "project_path": "/project",
            "project_type": "java",
            "build_tool": "maven",
            "target_files": [],
            "coverage_target": 80.0,
            "max_iterations": 10,
            "iteration_count": 3,
            "status": "target_reached",
            "message": "Target reached!",
            "analyzed_files": [],
            "generated_tests": [],
            "coverage_report": report,
            "current_coverage": 85.0,
            "coverage_gaps": [],
            "improvement_plan": None,
            "output_path": "/output",
            "summary": "Completed successfully",
        }

        assert state["current_coverage"] >= state["coverage_target"]
        assert state["status"] == "target_reached"

    def test_max_iterations_reached(self):
        """测试达到最大迭代次数的状态."""
        state: AgentState = {
            "project_path": "/project",
            "project_type": "java",
            "build_tool": "maven",
            "target_files": [],
            "coverage_target": 80.0,
            "max_iterations": 5,
            "iteration_count": 5,
            "status": "max_iterations_reached",
            "message": "Max iterations reached",
            "analyzed_files": [],
            "generated_tests": [],
            "coverage_report": None,
            "current_coverage": 70.0,
            "coverage_gaps": [],
            "improvement_plan": None,
            "output_path": None,
            "summary": None,
        }

        assert state["iteration_count"] >= state["max_iterations"]
        assert state["status"] == "max_iterations_reached"
