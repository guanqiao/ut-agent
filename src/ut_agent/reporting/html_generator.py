"""HTML报告生成器."""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ut_agent.graph.state import CoverageReport, CoverageGap


@dataclass
class FileCoverage:
    """文件覆盖率信息."""

    file_path: str
    line_coverage: float
    branch_coverage: float
    total_lines: int
    covered_lines: int
    uncovered_lines: List[int] = field(default_factory=list)
    partially_covered_lines: List[int] = field(default_factory=list)


@dataclass
class ReportData:
    """报告数据."""

    project_name: str
    generated_at: datetime
    overall_coverage: float
    line_coverage: float
    branch_coverage: float
    method_coverage: float
    class_coverage: float
    total_lines: int
    covered_lines: int
    total_branches: int
    covered_branches: int
    files: List[FileCoverage] = field(default_factory=list)
    gaps: List[CoverageGap] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)


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
        # 准备报告数据
        report_data = self._prepare_report_data(coverage_report, project_name)

        # 创建报告目录
        self.report_dir.mkdir(parents=True, exist_ok=True)

        # 生成报告文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.report_dir / f"coverage_report_{timestamp}.html"

        # 生成HTML
        html_content = self._generate_html(report_data)

        # 保存报告
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        # 保存JSON数据供历史趋势使用
        self._save_report_data(report_data, timestamp)

        # 更新最新报告链接
        latest_file = self.report_dir / "coverage_report_latest.html"
        if latest_file.exists():
            latest_file.unlink()
        latest_file.write_text(html_content, encoding="utf-8")

        return str(report_file)

    def _prepare_report_data(
        self, coverage_report: CoverageReport, project_name: str
    ) -> ReportData:
        """准备报告数据.

        Args:
            coverage_report: 覆盖率报告
            project_name: 项目名称

        Returns:
            报告数据
        """
        # 加载历史数据
        history = self._load_history()

        # 解析文件级覆盖率
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
            gaps=coverage_report.gaps[:50],  # 限制缺口数量
            history=history,
        )

    def _parse_file_coverage(self, coverage_report: CoverageReport) -> List[FileCoverage]:
        """解析文件级覆盖率.

        Args:
            coverage_report: 覆盖率报告

        Returns:
            文件覆盖率列表
        """
        files = []
        raw_report = coverage_report.raw_report

        if "files" in raw_report:
            # Istanbul 格式
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

        # 按覆盖率排序
        files.sort(key=lambda x: x.line_coverage)
        return files

    def _load_history(self) -> List[Dict[str, Any]]:
        """加载历史报告数据.

        Returns:
            历史数据列表
        """
        history_file = self.report_dir / "history.json"
        if history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_report_data(self, report_data: ReportData, timestamp: str) -> None:
        """保存报告数据.

        Args:
            report_data: 报告数据
            timestamp: 时间戳
        """
        # 确保报告目录存在
        self.report_dir.mkdir(parents=True, exist_ok=True)

        history_file = self.report_dir / "history.json"
        history = self._load_history()

        # 添加新记录
        history.append({
            "timestamp": timestamp,
            "overall_coverage": report_data.overall_coverage,
            "line_coverage": report_data.line_coverage,
            "branch_coverage": report_data.branch_coverage,
        })

        # 只保留最近20条记录
        history = history[-20:]

        try:
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            print(f"保存历史数据失败: {e}")

    def _generate_html(self, data: ReportData) -> str:
        """生成HTML内容.

        Args:
            data: 报告数据

        Returns:
            HTML内容
        """
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>覆盖率报告 - {data.project_name}</title>
    <style>{self._get_css_styles()}</style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container">
        {self._generate_header(data)}
        {self._generate_summary_cards(data)}
        {self._generate_trend_chart(data)}
        {self._generate_file_table(data)}
        {self._generate_gaps_section(data)}
        {self._generate_footer(data)}
    </div>
    <script>{self._get_javascript(data)}</script>
</body>
</html>"""

    def _get_css_styles(self) -> str:
        """获取CSS样式."""
        return """
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .header {{
            background: white;
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        
        .header h1 {{
            color: #2d3748;
            font-size: 28px;
            margin-bottom: 10px;
        }}
        
        .header .meta {{
            color: #718096;
            font-size: 14px;
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        
        .card {{
            background: white;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        
        .card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 8px 30px rgba(0,0,0,0.12);
        }}
        
        .card-title {{
            color: #718096;
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
        }}
        
        .card-value {{
            font-size: 36px;
            font-weight: 700;
            margin-bottom: 8px;
        }}
        
        .card-detail {{
            color: #a0aec0;
            font-size: 13px;
        }}
        
        .coverage-high {{ color: #48bb78; }}
        .coverage-medium {{ color: #ed8936; }}
        .coverage-low {{ color: #f56565; }}
        
        .chart-container {{
            background: white;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }}
        
        .chart-title {{
            color: #2d3748;
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 20px;
        }}
        
        .table-container {{
            background: white;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            overflow-x: auto;
        }}
        
        .table-title {{
            color: #2d3748;
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 20px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        th, td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }}
        
        th {{
            color: #4a5568;
            font-weight: 600;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            background: #f7fafc;
        }}
        
        tr:hover {{
            background: #f7fafc;
        }}
        
        .progress-bar {{
            width: 100%;
            height: 8px;
            background: #e2e8f0;
            border-radius: 4px;
            overflow: hidden;
        }}
        
        .progress-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s ease;
        }}
        
        .progress-high {{ background: linear-gradient(90deg, #48bb78, #38a169); }}
        .progress-medium {{ background: linear-gradient(90deg, #ed8936, #dd6b20); }}
        .progress-low {{ background: linear-gradient(90deg, #f56565, #e53e3e); }}
        
        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }}
        
        .badge-success {{
            background: #c6f6d5;
            color: #22543d;
        }}
        
        .badge-warning {{
            background: #feebc8;
            color: #744210;
        }}
        
        .badge-danger {{
            background: #fed7d7;
            color: #742a2a;
        }}
        
        .gaps-section {{
            background: white;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }}
        
        .gap-item {{
            padding: 16px;
            border-left: 4px solid #f56565;
            background: #fff5f5;
            margin-bottom: 12px;
            border-radius: 0 8px 8px 0;
        }}
        
        .gap-file {{
            font-weight: 600;
            color: #2d3748;
            margin-bottom: 4px;
        }}
        
        .gap-line {{
            color: #718096;
            font-size: 13px;
            margin-bottom: 4px;
        }}
        
        .gap-content {{
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 13px;
            color: #4a5568;
            background: white;
            padding: 8px;
            border-radius: 4px;
            margin-top: 8px;
        }}
        
        .footer {{
            text-align: center;
            color: rgba(255,255,255,0.8);
            padding: 20px;
            font-size: 13px;
        }}
        
        .export-buttons {{
            display: flex;
            gap: 12px;
            margin-top: 20px;
        }}
        
        .btn {{
            padding: 10px 20px;
            border-radius: 8px;
            border: none;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            text-decoration: none;
            display: inline-block;
        }}
        
        .btn-primary {{
            background: #4299e1;
            color: white;
        }}
        
        .btn-primary:hover {{
            background: #3182ce;
        }}
        
        .btn-secondary {{
            background: #edf2f7;
            color: #4a5568;
        }}
        
        .btn-secondary:hover {{
            background: #e2e8f0;
        }}
        """

    def _generate_header(self, data: ReportData) -> str:
        """生成页头."""
        return f"""
        <div class="header">
            <h1>🧪 UT-Agent 覆盖率报告</h1>
            <div class="meta">
                项目: <strong>{data.project_name}</strong> | 
                生成时间: {data.generated_at.strftime("%Y-%m-%d %H:%M:%S")}
            </div>
        </div>
        """

    def _generate_summary_cards(self, data: ReportData) -> str:
        """生成摘要卡片."""
        def get_coverage_class(value: float) -> str:
            if value >= 80:
                return "coverage-high"
            elif value >= 60:
                return "coverage-medium"
            return "coverage-low"

        def get_progress_class(value: float) -> str:
            if value >= 80:
                return "progress-high"
            elif value >= 60:
                return "progress-medium"
            return "progress-low"

        return f"""
        <div class="summary-grid">
            <div class="card">
                <div class="card-title">总体覆盖率</div>
                <div class="card-value {get_coverage_class(data.overall_coverage)}">
                    {data.overall_coverage:.1f}%
                </div>
                <div class="card-detail">
                    <div class="progress-bar">
                        <div class="progress-fill {get_progress_class(data.overall_coverage)}" 
                             style="width: {data.overall_coverage}%"></div>
                    </div>
                </div>
            </div>
            <div class="card">
                <div class="card-title">行覆盖率</div>
                <div class="card-value {get_coverage_class(data.line_coverage)}">
                    {data.line_coverage:.1f}%
                </div>
                <div class="card-detail">{data.covered_lines}/{data.total_lines} 行</div>
            </div>
            <div class="card">
                <div class="card-title">分支覆盖率</div>
                <div class="card-value {get_coverage_class(data.branch_coverage)}">
                    {data.branch_coverage:.1f}%
                </div>
                <div class="card-detail">{data.covered_branches}/{data.total_branches} 分支</div>
            </div>
            <div class="card">
                <div class="card-title">方法覆盖率</div>
                <div class="card-value {get_coverage_class(data.method_coverage)}">
                    {data.method_coverage:.1f}%
                </div>
                <div class="card-detail">已测试方法占比</div>
            </div>
        </div>
        """

    def _generate_trend_chart(self, data: ReportData) -> str:
        """生成趋势图."""
        if len(data.history) < 2:
            return ""

        history_json = json.dumps(data.history)

        return f"""
        <div class="chart-container">
            <div class="chart-title">📈 覆盖率趋势</div>
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

    def _generate_file_table(self, data: ReportData) -> str:
        """生成文件表格."""
        rows = ""
        for file in data.files[:50]:  # 限制显示50个文件
            status_class = "badge-success" if file.line_coverage >= 80 else (
                "badge-warning" if file.line_coverage >= 60 else "badge-danger"
            )
            status_text = "良好" if file.line_coverage >= 80 else (
                "需改进" if file.line_coverage >= 60 else "不足"
            )

            progress_class = "progress-high" if file.line_coverage >= 80 else (
                "progress-medium" if file.line_coverage >= 60 else "progress-low"
            )

            rows += f"""
                <tr>
                    <td>{file.file_path}</td>
                    <td>
                        <div class="progress-bar">
                            <div class="progress-fill {progress_class}" 
                                 style="width: {file.line_coverage}%"></div>
                        </div>
                    </td>
                    <td>{file.line_coverage:.1f}%</td>
                    <td>{file.branch_coverage:.1f}%</td>
                    <td><span class="badge {status_class}">{status_text}</span></td>
                </tr>
            """

        return f"""
        <div class="table-container">
            <div class="table-title">📁 文件覆盖率详情</div>
            <table>
                <thead>
                    <tr>
                        <th>文件路径</th>
                        <th style="width: 200px;">覆盖率</th>
                        <th>行覆盖</th>
                        <th>分支覆盖</th>
                        <th>状态</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        """

    def _generate_gaps_section(self, data: ReportData) -> str:
        """生成缺口部分."""
        if not data.gaps:
            return ""

        gaps_html = ""
        for gap in data.gaps[:20]:  # 限制显示20个缺口
            gaps_html += f"""
                <div class="gap-item">
                    <div class="gap-file">{gap.file_path}</div>
                    <div class="gap-line">第 {gap.line_number} 行 ({gap.gap_type})</div>
                    <div class="gap-content">{gap.line_content[:100]}</div>
                </div>
            """

        return f"""
        <div class="gaps-section">
            <div class="table-title">🔍 未覆盖代码缺口 (Top 20)</div>
            {gaps_html}
        </div>
        """

    def _generate_footer(self, data: ReportData) -> str:
        """生成页脚."""
        return f"""
        <div class="footer">
            <p>Generated by UT-Agent | {data.generated_at.strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
        """

    def _get_javascript(self, data: ReportData) -> str:
        """获取JavaScript代码."""
        return """
        // 可以在这里添加交互功能
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
