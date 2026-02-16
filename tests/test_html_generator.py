"""HTML报告生成器测试."""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from ut_agent.reporting.html_generator import (
    HTMLReportGenerator,
    generate_coverage_report,
)
from ut_agent.reporting.html_templates import (
    FileCoverage,
    ReportData,
    HTMLTemplates,
)
from ut_agent.graph.state import CoverageReport, CoverageGap


class TestFileCoverage:
    """FileCoverage测试类."""

    def test_file_coverage_creation(self):
        """测试FileCoverage创建."""
        file_cov = FileCoverage(
            file_path="src/Main.java",
            line_coverage=85.5,
            branch_coverage=70.0,
            total_lines=100,
            covered_lines=85,
            uncovered_lines=[10, 20, 30],
        )

        assert file_cov.file_path == "src/Main.java"
        assert file_cov.line_coverage == 85.5
        assert file_cov.branch_coverage == 70.0
        assert file_cov.total_lines == 100
        assert file_cov.covered_lines == 85
        assert len(file_cov.uncovered_lines) == 3


class TestReportData:
    """ReportData测试类."""

    def test_report_data_creation(self):
        """测试ReportData创建."""
        report_data = ReportData(
            project_name="TestProject",
            generated_at=datetime.now(),
            overall_coverage=80.0,
            line_coverage=85.0,
            branch_coverage=75.0,
            method_coverage=90.0,
            class_coverage=80.0,
            total_lines=1000,
            covered_lines=850,
            total_branches=200,
            covered_branches=150,
        )

        assert report_data.project_name == "TestProject"
        assert report_data.overall_coverage == 80.0
        assert len(report_data.files) == 0
        assert len(report_data.gaps) == 0


class TestHTMLTemplates:
    """HTMLTemplates测试类."""

    def test_get_coverage_class_high(self):
        """测试高覆盖率CSS类."""
        assert HTMLTemplates.get_coverage_class(85) == "coverage-high"
        assert HTMLTemplates.get_coverage_class(80) == "coverage-high"

    def test_get_coverage_class_medium(self):
        """测试中等覆盖率CSS类."""
        assert HTMLTemplates.get_coverage_class(70) == "coverage-medium"
        assert HTMLTemplates.get_coverage_class(60) == "coverage-medium"

    def test_get_coverage_class_low(self):
        """测试低覆盖率CSS类."""
        assert HTMLTemplates.get_coverage_class(50) == "coverage-low"
        assert HTMLTemplates.get_coverage_class(30) == "coverage-low"

    def test_render_header(self):
        """测试渲染页头."""
        now = datetime.now()
        html = HTMLTemplates.render_header("TestProject", now)
        assert "TestProject" in html
        assert "UT-Agent" in html

    def test_render_summary_cards(self):
        """测试渲染摘要卡片."""
        report_data = ReportData(
            project_name="TestProject",
            generated_at=datetime.now(),
            overall_coverage=85.0,
            line_coverage=90.0,
            branch_coverage=80.0,
            method_coverage=95.0,
            class_coverage=85.0,
            total_lines=1000,
            covered_lines=900,
            total_branches=200,
            covered_branches=160,
        )

        html = HTMLTemplates.render_summary_cards(report_data)

        assert "85.0%" in html
        assert "90.0%" in html
        assert "80.0%" in html
        assert "95.0%" in html
        assert "coverage-high" in html

    def test_render_file_table(self):
        """测试渲染文件表格."""
        files = [
            FileCoverage(
                file_path="src/Main.java",
                line_coverage=90.0,
                branch_coverage=85.0,
                total_lines=100,
                covered_lines=90,
            ),
            FileCoverage(
                file_path="src/Utils.java",
                line_coverage=50.0,
                branch_coverage=40.0,
                total_lines=50,
                covered_lines=25,
            ),
        ]

        html = HTMLTemplates.render_file_table(files)

        assert "src/Main.java" in html
        assert "src/Utils.java" in html
        assert "90.0%" in html
        assert "50.0%" in html
        assert "badge-success" in html
        assert "badge-danger" in html

    def test_render_gaps_section(self):
        """测试渲染缺口部分."""
        gaps = [
            CoverageGap(
                file_path="src/Main.java",
                line_number=10,
                line_content="public void test() {}",
                gap_type="line",
            ),
            CoverageGap(
                file_path="src/Utils.java",
                line_number=20,
                line_content="if (condition) {",
                gap_type="branch",
            ),
        ]

        html = HTMLTemplates.render_gaps_section(gaps)

        assert "src/Main.java" in html
        assert "src/Utils.java" in html
        assert "public void test() {}" in html
        assert "gap-item" in html

    def test_render_gaps_section_empty(self):
        """测试渲染空缺口部分."""
        html = HTMLTemplates.render_gaps_section([])
        assert html == ""


class TestHTMLReportGenerator:
    """HTMLReportGenerator测试类."""

    def test_init(self, tmp_path):
        """测试初始化."""
        generator = HTMLReportGenerator(str(tmp_path))
        assert generator.project_path == tmp_path
        assert generator.report_dir == tmp_path / "ut-agent-reports"

    def test_generate_html_report(self, tmp_path):
        """测试生成HTML报告."""
        generator = HTMLReportGenerator(str(tmp_path))

        coverage_report = CoverageReport(
            overall_coverage=80.0,
            line_coverage=85.0,
            branch_coverage=75.0,
            method_coverage=90.0,
            class_coverage=80.0,
            total_lines=1000,
            covered_lines=850,
            total_branches=200,
            covered_branches=150,
            gaps=[
                CoverageGap(
                    file_path="src/Main.java",
                    line_number=10,
                    line_content="public void test() {}",
                    gap_type="line",
                )
            ],
            raw_report={
                "files": {
                    "src/Main.java": {
                        "lines": {"pct": 85, "total": 100, "covered": 85},
                        "branches": {"pct": 75, "total": 20, "covered": 15},
                    }
                }
            },
        )

        report_path = generator.generate(coverage_report, "TestProject")

        assert Path(report_path).exists()
        assert "coverage_report_" in report_path
        assert report_path.endswith(".html")

        content = Path(report_path).read_text(encoding="utf-8")
        assert "TestProject" in content
        assert "80.0" in content
        assert "85.0" in content
        assert "覆盖率报告" in content

    def test_generate_creates_latest_link(self, tmp_path):
        """测试生成latest链接."""
        generator = HTMLReportGenerator(str(tmp_path))

        coverage_report = CoverageReport(
            overall_coverage=80.0,
            line_coverage=85.0,
            branch_coverage=75.0,
            method_coverage=90.0,
            class_coverage=80.0,
            total_lines=1000,
            covered_lines=850,
            total_branches=200,
            covered_branches=150,
            gaps=[],
            raw_report={},
        )

        generator.generate(coverage_report, "TestProject")

        latest_file = tmp_path / "ut-agent-reports" / "coverage_report_latest.html"
        assert latest_file.exists()

    def test_save_and_load_history(self, tmp_path):
        """测试保存和加载历史数据."""
        generator = HTMLReportGenerator(str(tmp_path))

        report_data = ReportData(
            project_name="TestProject",
            generated_at=datetime.now(),
            overall_coverage=80.0,
            line_coverage=85.0,
            branch_coverage=75.0,
            method_coverage=90.0,
            class_coverage=80.0,
            total_lines=1000,
            covered_lines=850,
            total_branches=200,
            covered_branches=150,
        )

        generator._save_report_data(report_data, "20240101_120000")

        history = generator._load_history()

        assert len(history) == 1
        assert history[0]["overall_coverage"] == 80.0
        assert history[0]["line_coverage"] == 85.0

    def test_history_limit(self, tmp_path):
        """测试历史记录限制."""
        generator = HTMLReportGenerator(str(tmp_path))

        for i in range(25):
            report_data = ReportData(
                project_name="TestProject",
                generated_at=datetime.now(),
                overall_coverage=float(i),
                line_coverage=float(i),
                branch_coverage=float(i),
                method_coverage=float(i),
                class_coverage=float(i),
                total_lines=1000,
                covered_lines=850,
                total_branches=200,
                covered_branches=150,
            )
            generator._save_report_data(report_data, f"20240101_{i:06d}")

        history = generator._load_history()

        assert len(history) == 20
        assert history[-1]["overall_coverage"] == 24.0

    def test_parse_file_coverage(self, tmp_path):
        """测试解析文件覆盖率."""
        generator = HTMLReportGenerator(str(tmp_path))

        coverage_report = CoverageReport(
            overall_coverage=80.0,
            line_coverage=85.0,
            branch_coverage=75.0,
            method_coverage=90.0,
            class_coverage=80.0,
            total_lines=1000,
            covered_lines=850,
            total_branches=200,
            covered_branches=150,
            gaps=[],
            raw_report={
                "files": {
                    "src/Main.java": {
                        "lines": {"pct": 90, "total": 100, "covered": 90, "uncovered": [10, 20]},
                        "branches": {"pct": 80, "total": 20, "covered": 16},
                    },
                    "src/Utils.java": {
                        "lines": {"pct": 70, "total": 50, "covered": 35},
                        "branches": {"pct": 60, "total": 10, "covered": 6},
                    },
                }
            },
        )

        files = generator._parse_file_coverage(coverage_report)

        assert len(files) == 2
        assert files[0].file_path == "src/Utils.java"
        assert files[0].line_coverage == 70
        assert files[1].file_path == "src/Main.java"
        assert files[1].line_coverage == 90

    def test_render_trend_chart_with_history(self, tmp_path):
        """测试生成趋势图（有历史数据）."""
        generator = HTMLReportGenerator(str(tmp_path))

        report_data = ReportData(
            project_name="TestProject",
            generated_at=datetime.now(),
            overall_coverage=80.0,
            line_coverage=85.0,
            branch_coverage=75.0,
            method_coverage=90.0,
            class_coverage=80.0,
            total_lines=1000,
            covered_lines=850,
            total_branches=200,
            covered_branches=150,
            history=[
                {"timestamp": "20240101_120000", "overall_coverage": 70.0, "line_coverage": 75.0, "branch_coverage": 65.0},
                {"timestamp": "20240102_120000", "overall_coverage": 75.0, "line_coverage": 80.0, "branch_coverage": 70.0},
                {"timestamp": "20240103_120000", "overall_coverage": 80.0, "line_coverage": 85.0, "branch_coverage": 75.0},
            ],
        )

        html = generator._render_trend_chart(report_data)

        assert "trendChart" in html
        assert "20240101_120000" in html
        assert "总体覆盖率" in html
        assert "行覆盖率" in html

    def test_render_trend_chart_without_history(self, tmp_path):
        """测试生成趋势图（无历史数据）."""
        generator = HTMLReportGenerator(str(tmp_path))

        report_data = ReportData(
            project_name="TestProject",
            generated_at=datetime.now(),
            overall_coverage=80.0,
            line_coverage=85.0,
            branch_coverage=75.0,
            method_coverage=90.0,
            class_coverage=80.0,
            total_lines=1000,
            covered_lines=850,
            total_branches=200,
            covered_branches=150,
            history=[],
        )

        html = generator._render_trend_chart(report_data)

        assert html == ""


class TestGenerateCoverageReport:
    """generate_coverage_report便捷函数测试类."""

    def test_generate_coverage_report(self, tmp_path):
        """测试便捷函数."""
        coverage_report = CoverageReport(
            overall_coverage=80.0,
            line_coverage=85.0,
            branch_coverage=75.0,
            method_coverage=90.0,
            class_coverage=80.0,
            total_lines=1000,
            covered_lines=850,
            total_branches=200,
            covered_branches=150,
            gaps=[],
            raw_report={},
        )

        report_path = generate_coverage_report(
            project_path=str(tmp_path),
            coverage_report=coverage_report,
            project_name="TestProject",
        )

        assert Path(report_path).exists()
        assert "coverage_report_" in report_path
