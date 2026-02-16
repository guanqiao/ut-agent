"""HTML报告生成器."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ut_agent.graph.state import CoverageReport, CoverageGap
from ut_agent.reporting.html_templates import (
    FileCoverage,
    ReportData,
    HTMLTemplates,
)


class HTMLReportGenerator:
    """HTML报告生成器."""

    def __init__(self, project_path: str):
        """初始化生成器.

        Args:
            project_path: 项目路径
        """
        self.project_path = Path(project_path)
        self.report_dir = self.project_path / "ut-agent-reports"

    def generate(
        self,
        coverage_report: CoverageReport,
        project_name: str = "",
    ) -> str:
        """生成HTML报告.

        Args:
            coverage_report: 覆盖率报告
            project_name: 项目名称

        Returns:
            报告文件路径
        """
        report_data = self._prepare_report_data(coverage_report, project_name)

        self.report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.report_dir / f"coverage_report_{timestamp}.html"

        html_content = self._generate_html(report_data)

        with open(report_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        self._save_report_data(report_data, timestamp)

        latest_file = self.report_dir / "coverage_report_latest.html"
        if latest_file.exists():
            latest_file.unlink()
        latest_file.write_text(html_content, encoding="utf-8")

        return str(report_file)

    def _prepare_report_data(
        self, coverage_report: CoverageReport, project_name: str
    ) -> ReportData:
        """准备报告数据."""
        history = self._load_history()
        files = self._parse_file_coverage(coverage_report)

        return ReportData(
            project_name=project_name or self.project_path.name,
            generated_at=datetime.now(),
            overall_coverage=coverage_report.overall_coverage,
            line_coverage=coverage_report.line_coverage,
            branch_coverage=coverage_report.branch_coverage,
            method_coverage=coverage_report.method_coverage,
            class_coverage=coverage_report.class_coverage,
            total_lines=coverage_report.total_lines,
            covered_lines=coverage_report.covered_lines,
            total_branches=coverage_report.total_branches,
            covered_branches=coverage_report.covered_branches,
            files=files,
            gaps=coverage_report.gaps[:50],
            history=history,
        )

    def _parse_file_coverage(self, coverage_report: CoverageReport) -> List[FileCoverage]:
        """解析文件级覆盖率."""
        files = []
        raw_report = coverage_report.raw_report

        if "files" in raw_report:
            for file_path, file_data in raw_report["files"].items():
                lines = file_data.get("lines", {})
                branches = file_data.get("branches", {})

                file_cov = FileCoverage(
                    file_path=file_path,
                    line_coverage=lines.get("pct", 0),
                    branch_coverage=branches.get("pct", 0),
                    total_lines=lines.get("total", 0),
                    covered_lines=lines.get("covered", 0),
                    uncovered_lines=lines.get("uncovered", []),
                )
                files.append(file_cov)

        files.sort(key=lambda x: x.line_coverage)
        return files

    def _load_history(self) -> List[Dict[str, Any]]:
        """加载历史报告数据."""
        history_file = self.report_dir / "history.json"
        if history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_report_data(self, report_data: ReportData, timestamp: str) -> None:
        """保存报告数据."""
        self.report_dir.mkdir(parents=True, exist_ok=True)

        history_file = self.report_dir / "history.json"
        history = self._load_history()

        history.append({
            "timestamp": timestamp,
            "overall_coverage": report_data.overall_coverage,
            "line_coverage": report_data.line_coverage,
            "branch_coverage": report_data.branch_coverage,
        })

        history = history[-20:]

        try:
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2)
        except Exception:
            pass

    def _generate_html(self, data: ReportData) -> str:
        """生成HTML内容."""
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>覆盖率报告 - {data.project_name}</title>
    <style>{HTMLTemplates.get_css_styles()}</style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container">
        {HTMLTemplates.render_header(data.project_name, data.generated_at)}
        {HTMLTemplates.render_summary_cards(data)}
        {self._render_trend_chart(data)}
        {HTMLTemplates.render_file_table(data.files)}
        {HTMLTemplates.render_gaps_section(data.gaps)}
        {HTMLTemplates.render_footer(data.generated_at)}
    </div>
    <script>{self._get_javascript(data)}</script>
</body>
</html>"""

    def _render_trend_chart(self, data: ReportData) -> str:
        """渲染趋势图."""
        if len(data.history) < 2:
            return ""

        history_json = json.dumps(data.history)

        return f"""
        <div class="chart-container">
            <div class="chart-title">覆盖率趋势</div>
            <canvas id="trendChart" style="max-height: 300px;"></canvas>
        </div>
        <script>
            (function() {{
                const history = {history_json};
                const ctx = document.getElementById('trendChart').getContext('2d');
                
                new Chart(ctx, {{
                    type: 'line',
                    data: {{
                        labels: history.map(h => h.timestamp),
                        datasets: [{{
                            label: '总体覆盖率',
                            data: history.map(h => h.overall_coverage),
                            borderColor: '#667eea',
                            backgroundColor: 'rgba(102, 126, 234, 0.1)',
                            tension: 0.4,
                            fill: true
                        }}, {{
                            label: '行覆盖率',
                            data: history.map(h => h.line_coverage),
                            borderColor: '#48bb78',
                            backgroundColor: 'rgba(72, 187, 120, 0.1)',
                            tension: 0.4,
                            fill: true
                        }}, {{
                            label: '分支覆盖率',
                            data: history.map(h => h.branch_coverage),
                            borderColor: '#ed8936',
                            backgroundColor: 'rgba(237, 137, 54, 0.1)',
                            tension: 0.4,
                            fill: true
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{
                                position: 'bottom'
                            }}
                        }},
                        scales: {{
                            y: {{
                                beginAtZero: true,
                                max: 100,
                                ticks: {{
                                    callback: function(value) {{
                                        return value + '%';
                                    }}
                                }}
                            }}
                        }}
                    }}
                }});
            }})();
        </script>
        """

    def _get_javascript(self, data: ReportData) -> str:
        """获取JavaScript代码."""
        return """
        document.addEventListener('DOMContentLoaded', function() {
            console.log('UT-Agent Coverage Report Loaded');
        });
        """


def generate_coverage_report(
    project_path: str,
    coverage_report: CoverageReport,
    project_name: str = "",
) -> str:
    """生成覆盖率报告的便捷函数.

    Args:
        project_path: 项目路径
        coverage_report: 覆盖率报告
        project_name: 项目名称

    Returns:
        报告文件路径
    """
    generator = HTMLReportGenerator(project_path)
    return generator.generate(coverage_report, project_name)
