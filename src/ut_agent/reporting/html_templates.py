"""HTML报告模板."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


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
    generated_at: Any
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
    gaps: List[Any] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)


class HTMLTemplates:
    """HTML模板类."""

    @staticmethod
    def get_css_styles() -> str:
        """获取CSS样式."""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .header {
            background: white;
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }
        
        .header h1 {
            color: #2d3748;
            font-size: 28px;
            margin-bottom: 10px;
        }
        
        .header .meta {
            color: #718096;
            font-size: 14px;
        }
        
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .card {
            background: white;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .card:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 30px rgba(0,0,0,0.12);
        }
        
        .card-title {
            color: #718096;
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
        }
        
        .card-value {
            font-size: 36px;
            font-weight: 700;
            margin-bottom: 8px;
        }
        
        .card-detail {
            color: #a0aec0;
            font-size: 13px;
        }
        
        .coverage-high { color: #48bb78; }
        .coverage-medium { color: #ed8936; }
        .coverage-low { color: #f56565; }
        
        .chart-container {
            background: white;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }
        
        .chart-title {
            color: #2d3748;
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 20px;
        }
        
        .table-container {
            background: white;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            overflow-x: auto;
        }
        
        .table-title {
            color: #2d3748;
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 20px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th, td {
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }
        
        th {
            color: #4a5568;
            font-weight: 600;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            background: #f7fafc;
        }
        
        tr:hover {
            background: #f7fafc;
        }
        
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e2e8f0;
            border-radius: 4px;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s ease;
        }
        
        .progress-high { background: linear-gradient(90deg, #48bb78, #38a169); }
        .progress-medium { background: linear-gradient(90deg, #ed8936, #dd6b20); }
        .progress-low { background: linear-gradient(90deg, #f56565, #e53e3e); }
        
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }
        
        .badge-success {
            background: #c6f6d5;
            color: #22543d;
        }
        
        .badge-warning {
            background: #feebc8;
            color: #744210;
        }
        
        .badge-danger {
            background: #fed7d7;
            color: #742a2a;
        }
        
        .gaps-section {
            background: white;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }
        
        .gap-item {
            padding: 16px;
            border-left: 4px solid #f56565;
            background: #fff5f5;
            margin-bottom: 12px;
            border-radius: 0 8px 8px 0;
        }
        
        .gap-file {
            font-weight: 600;
            color: #2d3748;
            margin-bottom: 4px;
        }
        
        .gap-line {
            color: #718096;
            font-size: 13px;
            margin-bottom: 4px;
        }
        
        .gap-content {
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 13px;
            color: #4a5568;
            background: white;
            padding: 8px;
            border-radius: 4px;
            margin-top: 8px;
        }
        
        .footer {
            text-align: center;
            color: rgba(255,255,255,0.8);
            padding: 20px;
            font-size: 13px;
        }
        """

    @staticmethod
    def get_coverage_class(value: float) -> str:
        """获取覆盖率CSS类名."""
        if value >= 80:
            return "coverage-high"
        elif value >= 60:
            return "coverage-medium"
        return "coverage-low"

    @staticmethod
    def get_progress_class(value: float) -> str:
        """获取进度条CSS类名."""
        if value >= 80:
            return "progress-high"
        elif value >= 60:
            return "progress-medium"
        return "progress-low"

    @staticmethod
    def get_status_badge(value: float) -> tuple:
        """获取状态徽章."""
        if value >= 80:
            return "badge-success", "良好"
        elif value >= 60:
            return "badge-warning", "需改进"
        return "badge-danger", "不足"

    @staticmethod
    def render_header(project_name: str, generated_at: Any) -> str:
        """渲染页头."""
        return f"""
        <div class="header">
            <h1>UT-Agent 覆盖率报告</h1>
            <div class="meta">
                项目: <strong>{project_name}</strong> | 
                生成时间: {generated_at.strftime("%Y-%m-%d %H:%M:%S")}
            </div>
        </div>
        """

    @staticmethod
    def render_summary_cards(data: ReportData) -> str:
        """渲染摘要卡片."""
        return f"""
        <div class="summary-grid">
            <div class="card">
                <div class="card-title">总体覆盖率</div>
                <div class="card-value {HTMLTemplates.get_coverage_class(data.overall_coverage)}">
                    {data.overall_coverage:.1f}%
                </div>
                <div class="card-detail">
                    <div class="progress-bar">
                        <div class="progress-fill {HTMLTemplates.get_progress_class(data.overall_coverage)}" 
                             style="width: {data.overall_coverage}%"></div>
                    </div>
                </div>
            </div>
            <div class="card">
                <div class="card-title">行覆盖率</div>
                <div class="card-value {HTMLTemplates.get_coverage_class(data.line_coverage)}">
                    {data.line_coverage:.1f}%
                </div>
                <div class="card-detail">{data.covered_lines}/{data.total_lines} 行</div>
            </div>
            <div class="card">
                <div class="card-title">分支覆盖率</div>
                <div class="card-value {HTMLTemplates.get_coverage_class(data.branch_coverage)}">
                    {data.branch_coverage:.1f}%
                </div>
                <div class="card-detail">{data.covered_branches}/{data.total_branches} 分支</div>
            </div>
            <div class="card">
                <div class="card-title">方法覆盖率</div>
                <div class="card-value {HTMLTemplates.get_coverage_class(data.method_coverage)}">
                    {data.method_coverage:.1f}%
                </div>
                <div class="card-detail">已测试方法占比</div>
            </div>
        </div>
        """

    @staticmethod
    def render_file_table(files: List[FileCoverage], max_files: int = 50) -> str:
        """渲染文件表格."""
        rows = ""
        for file in files[:max_files]:
            status_class, status_text = HTMLTemplates.get_status_badge(file.line_coverage)
            progress_class = HTMLTemplates.get_progress_class(file.line_coverage)

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
            <div class="table-title">文件覆盖率详情</div>
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

    @staticmethod
    def render_gaps_section(gaps: List[Any], max_gaps: int = 20) -> str:
        """渲染缺口部分."""
        if not gaps:
            return ""

        gaps_html = ""
        for gap in gaps[:max_gaps]:
            gaps_html += f"""
                <div class="gap-item">
                    <div class="gap-file">{gap.file_path}</div>
                    <div class="gap-line">第 {gap.line_number} 行 ({gap.gap_type})</div>
                    <div class="gap-content">{gap.line_content[:100]}</div>
                </div>
            """

        return f"""
        <div class="gaps-section">
            <div class="table-title">未覆盖代码缺口 (Top {min(len(gaps), max_gaps)})</div>
            {gaps_html}
        </div>
        """

    @staticmethod
    def render_footer(generated_at: Any) -> str:
        """渲染页脚."""
        return f"""
        <div class="footer">
            <p>Generated by UT-Agent | {generated_at.strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
        """
