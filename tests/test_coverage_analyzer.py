"""覆盖率分析模块单元测试."""

import os
import tempfile
from pathlib import Path

import pytest

from ut_agent.graph.state import CoverageGap, CoverageReport
from ut_agent.tools.coverage_analyzer import (
    check_coverage_threshold,
    generate_coverage_summary,
    get_line_content,
    identify_coverage_gaps,
    parse_istanbul_report,
    parse_jacoco_report,
    parse_lcov_report,
)


class TestParseJacocoReport:
    """JaCoCo 报告解析测试."""

    @pytest.fixture
    def jacoco_report_file(self):
        """创建临时 JaCoCo 报告文件."""
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<report name="Test Project">
    <counter type="LINE" missed="20" covered="80"/>
    <counter type="BRANCH" missed="10" covered="40"/>
    <counter type="METHOD" missed="5" covered="20"/>
    <counter type="CLASS" missed="1" covered="4"/>
</report>'''
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir) / "target" / "site" / "jacoco"
            report_dir.mkdir(parents=True)
            report_file = report_dir / "jacoco.xml"
            report_file.write_text(content)
            yield str(tmpdir)

    def test_parse_jacoco_report_success(self, jacoco_report_file):
        """测试成功解析 JaCoCo 报告."""
        report = parse_jacoco_report(jacoco_report_file)

        assert report is not None
        assert report.line_coverage == 80.0  # 80/(80+20) * 100
        assert report.branch_coverage == 80.0  # 40/(40+10) * 100
        assert report.method_coverage == 80.0  # 20/(20+5) * 100
        assert report.class_coverage == 80.0  # 4/(4+1) * 100
        assert report.total_lines == 100
        assert report.covered_lines == 80

    def test_parse_jacoco_report_not_found(self):
        """测试 JaCoCo 报告文件不存在."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report = parse_jacoco_report(tmpdir)
            assert report is None

    def test_parse_jacoco_report_invalid_xml(self):
        """测试无效的 XML 报告."""
        from ut_agent.exceptions import CoverageAnalysisError
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir) / "target" / "site" / "jacoco"
            report_dir.mkdir(parents=True)
            report_file = report_dir / "jacoco.xml"
            report_file.write_text("invalid xml")

            with pytest.raises(CoverageAnalysisError):
                parse_jacoco_report(tmpdir)


class TestParseIstanbulReport:
    """Istanbul 报告解析测试."""

    @pytest.fixture
    def istanbul_report_file(self):
        """创建临时 Istanbul 报告文件."""
        content = '''{
            "total": {
                "lines": {"total": 100, "covered": 75, "pct": 75},
                "statements": {"total": 120, "covered": 90, "pct": 75},
                "functions": {"total": 20, "covered": 15, "pct": 75},
                "branches": {"total": 40, "covered": 28, "pct": 70}
            }
        }'''
        with tempfile.TemporaryDirectory() as tmpdir:
            coverage_dir = Path(tmpdir) / "coverage"
            coverage_dir.mkdir()
            report_file = coverage_dir / "coverage-summary.json"
            report_file.write_text(content)
            yield str(tmpdir)

    def test_parse_istanbul_report_success(self, istanbul_report_file):
        """测试成功解析 Istanbul 报告."""
        report = parse_istanbul_report(istanbul_report_file)

        assert report is not None
        assert report.line_coverage == 75.0
        assert report.branch_coverage == 70.0
        assert report.method_coverage == 75.0
        assert report.total_lines == 100
        assert report.covered_lines == 75

    def test_parse_istanbul_report_not_found(self):
        """测试 Istanbul 报告文件不存在."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report = parse_istanbul_report(tmpdir)
            assert report is None

    def test_parse_istanbul_report_invalid_json(self):
        """测试无效的 JSON 报告."""
        with tempfile.TemporaryDirectory() as tmpdir:
            coverage_dir = Path(tmpdir) / "coverage"
            coverage_dir.mkdir()
            report_file = coverage_dir / "coverage-summary.json"
            report_file.write_text("invalid json")

            report = parse_istanbul_report(tmpdir)
            assert report is None


class TestParseLcovReport:
    """LCOV 报告解析测试."""

    @pytest.fixture
    def lcov_report_file(self):
        """创建临时 LCOV 报告文件."""
        lines = [
            "SF:src/index.js",
            "FN:1,test",
            "FNF:1",
            "FNH:1",
            "LF:50",
            "LH:40",
            "BRF:20",
            "BRH:15",
            "end_of_record",
        ]
        content = "\n".join(lines)
        
        # 使用 tempfile.mkstemp 确保文件正确关闭
        fd, path = tempfile.mkstemp(suffix=".info")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            yield path
        finally:
            # 清理临时文件
            if os.path.exists(path):
                os.unlink(path)

    def test_parse_lcov_report_success(self, lcov_report_file):
        """测试成功解析 LCOV 报告."""
        report = parse_lcov_report(lcov_report_file)

        assert report is not None
        assert report.line_coverage == 80.0  # 40/50 * 100
        assert report.method_coverage == 100.0  # 1/1 * 100
        assert report.branch_coverage == 75.0  # 15/20 * 100
        assert report.total_lines == 50
        assert report.covered_lines == 40

    def test_parse_lcov_report_not_found(self):
        """测试 LCOV 报告文件不存在."""
        report = parse_lcov_report("/nonexistent/report.info")
        assert report is None

    def test_parse_lcov_report_empty(self):
        """测试空的 LCOV 报告."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".info", delete=False, encoding="utf-8"
        ) as f:
            f.write("")
            report = parse_lcov_report(f.name)
            assert report is not None
            assert report.line_coverage == 0.0


class TestIdentifyCoverageGaps:
    """覆盖率缺口识别测试."""

    def test_identify_gaps_from_istanbul_format(self):
        """测试从 Istanbul 格式识别缺口."""
        report = CoverageReport(
            overall_coverage=70.0,
            line_coverage=75.0,
            branch_coverage=65.0,
            method_coverage=80.0,
            class_coverage=75.0,
            total_lines=100,
            covered_lines=75,
            total_branches=40,
            covered_branches=26,
            raw_report={
                "files": {
                    "src/utils.js": {
                        "lines": {"uncovered": [10, 15, 20, 25, 30]}
                    }
                }
            },
        )

        gaps = identify_coverage_gaps(report, "/project")

        assert len(gaps) > 0
        assert all(isinstance(gap, CoverageGap) for gap in gaps)
        assert gaps[0].file_path == "src/utils.js"

    def test_identify_gaps_empty_report(self):
        """测试空报告的缺口识别."""
        report = CoverageReport(
            overall_coverage=100.0,
            line_coverage=100.0,
            branch_coverage=100.0,
            method_coverage=100.0,
            class_coverage=100.0,
            total_lines=100,
            covered_lines=100,
            total_branches=40,
            covered_branches=40,
            raw_report={},
        )

        gaps = identify_coverage_gaps(report, "/project")
        assert gaps == []

    def test_identify_gaps_limit(self):
        """测试缺口数量限制."""
        # 创建大量缺口
        raw_report = {
            "files": {
                "src/file1.js": {"lines": {"uncovered": list(range(1, 100))}},
            }
        }

        report = CoverageReport(
            overall_coverage=50.0,
            line_coverage=50.0,
            branch_coverage=50.0,
            method_coverage=50.0,
            class_coverage=50.0,
            total_lines=200,
            covered_lines=100,
            total_branches=40,
            covered_branches=20,
            raw_report=raw_report,
        )

        gaps = identify_coverage_gaps(report, "/project")
        assert len(gaps) <= 30  # 限制为 30 个


class TestGetLineContent:
    """行内容获取测试."""

    def test_get_line_content_success(self):
        """测试成功获取行内容."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.js"
            file_path.write_text("line1\nline2\nline3\n")

            content = get_line_content(tmpdir, "test.js", 2)
            assert content == "line2"

    def test_get_line_content_first_line(self):
        """测试获取第一行内容."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.js"
            file_path.write_text("first line\nsecond line\n")

            content = get_line_content(tmpdir, "test.js", 1)
            assert content == "first line"

    def test_get_line_content_out_of_range(self):
        """测试行号超出范围."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.js"
            file_path.write_text("line1\n")

            content = get_line_content(tmpdir, "test.js", 10)
            assert content == ""

    def test_get_line_content_file_not_found(self):
        """测试文件不存在."""
        content = get_line_content("/nonexistent", "file.js", 1)
        assert content == ""


class TestGenerateCoverageSummary:
    """覆盖率摘要生成测试."""

    def test_generate_summary(self):
        """测试生成摘要."""
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
            gaps=[CoverageGap("file.js", 10, "content", "line")],
        )

        summary = generate_coverage_summary(report)

        assert "75.50%" in summary
        assert "80/100" in summary
        assert "28/40" in summary
        assert "覆盖率报告摘要" in summary

    def test_generate_summary_with_zero_coverage(self):
        """测试零覆盖率的摘要."""
        report = CoverageReport(
            overall_coverage=0.0,
            line_coverage=0.0,
            branch_coverage=0.0,
            method_coverage=0.0,
            class_coverage=0.0,
            total_lines=100,
            covered_lines=0,
            total_branches=40,
            covered_branches=0,
            gaps=[],
        )

        summary = generate_coverage_summary(report)

        assert "0.00%" in summary
        assert "0/100" in summary


class TestCheckCoverageThreshold:
    """覆盖率阈值检查测试."""

    def test_check_threshold_passed(self):
        """测试阈值通过."""
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
            gaps=[],
        )

        result = check_coverage_threshold(report, 80.0)

        assert result["passed"] is True
        assert result["details"]["overall"]["passed"] is True
        assert result["details"]["line"]["passed"] is True

    def test_check_threshold_failed(self):
        """测试阈值未通过."""
        report = CoverageReport(
            overall_coverage=70.0,
            line_coverage=75.0,
            branch_coverage=65.0,
            method_coverage=70.0,
            class_coverage=70.0,
            total_lines=100,
            covered_lines=75,
            total_branches=40,
            covered_branches=26,
            gaps=[],
        )

        result = check_coverage_threshold(report, 80.0)

        assert result["passed"] is False
        assert result["details"]["overall"]["passed"] is False

    def test_check_branch_threshold_adjusted(self):
        """测试分支阈值调整."""
        report = CoverageReport(
            overall_coverage=85.0,
            line_coverage=90.0,
            branch_coverage=75.0,  # 80% * 0.8 = 64% 阈值
            method_coverage=85.0,
            class_coverage=85.0,
            total_lines=100,
            covered_lines=90,
            total_branches=40,
            covered_branches=30,
            gaps=[],
        )

        result = check_coverage_threshold(report, 80.0)

        # 分支阈值是 80% * 0.8 = 64%, 75% > 64%, 所以通过
        assert result["details"]["branch"]["passed"] is True
        assert result["details"]["branch"]["threshold"] == 64.0
