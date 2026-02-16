"""覆盖率分析模块."""

import xml.etree.ElementTree as ET
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from ut_agent.graph.state import CoverageReport, CoverageGap
from ut_agent.exceptions import CoverageAnalysisError


def parse_jacoco_report(project_path: str) -> Optional[CoverageReport]:
    """解析 JaCoCo 覆盖率报告.

    Args:
        project_path: 项目路径

    Returns:
        Optional[CoverageReport]: 覆盖率报告
    """
    # 查找 JaCoCo 报告文件
    possible_paths = [
        Path(project_path) / "target" / "site" / "jacoco" / "jacoco.xml",
        Path(project_path) / "build" / "reports" / "jacoco" / "test" / "jacocoTestReport.xml",
    ]

    report_path = None
    for path in possible_paths:
        if path.exists():
            report_path = path
            break

    if not report_path:
        return None

    try:
        tree = ET.parse(report_path)
        root = tree.getroot()

        # 解析覆盖率数据
        counters = root.findall("counter")

        line_covered = 0
        line_missed = 0
        branch_covered = 0
        branch_missed = 0
        method_covered = 0
        method_missed = 0
        class_covered = 0
        class_missed = 0

        for counter in counters:
            counter_type = counter.get("type")
            missed = int(counter.get("missed", 0))
            covered = int(counter.get("covered", 0))

            if counter_type == "LINE":
                line_missed = missed
                line_covered = covered
            elif counter_type == "BRANCH":
                branch_missed = missed
                branch_covered = covered
            elif counter_type == "METHOD":
                method_missed = missed
                method_covered = covered
            elif counter_type == "CLASS":
                class_missed = missed
                class_covered = covered

        total_lines = line_covered + line_missed
        total_branches = branch_covered + branch_missed
        total_methods = method_covered + method_missed
        total_classes = class_covered + class_missed

        line_coverage = (line_covered / total_lines * 100) if total_lines > 0 else 0
        branch_coverage = (branch_covered / total_branches * 100) if total_branches > 0 else 0
        method_coverage = (method_covered / total_methods * 100) if total_methods > 0 else 0
        class_coverage = (class_covered / total_classes * 100) if total_classes > 0 else 0

        # 计算总体覆盖率 (加权平均)
        overall_coverage = (line_coverage * 0.4 + branch_coverage * 0.4 + method_coverage * 0.2)

        return CoverageReport(
            overall_coverage=round(overall_coverage, 2),
            line_coverage=round(line_coverage, 2),
            branch_coverage=round(branch_coverage, 2),
            method_coverage=round(method_coverage, 2),
            class_coverage=round(class_coverage, 2),
            total_lines=total_lines,
            covered_lines=line_covered,
            total_branches=total_branches,
            covered_branches=branch_covered,
            gaps=[],
            raw_report={
                "line_covered": line_covered,
                "line_missed": line_missed,
                "branch_covered": branch_covered,
                "branch_missed": branch_missed,
            },
        )

    except ET.ParseError as e:
        raise CoverageAnalysisError(
            f"Failed to parse JaCoCo XML report: {e}",
            report_path=str(report_path),
            report_format="jacoco"
        )
    except Exception as e:
        raise CoverageAnalysisError(
            f"Unexpected error parsing JaCoCo report: {e}",
            report_path=str(report_path),
            report_format="jacoco"
        )


def parse_istanbul_report(project_path: str) -> Optional[CoverageReport]:
    """解析 Istanbul/V8 覆盖率报告.

    Args:
        project_path: 项目路径

    Returns:
        Optional[CoverageReport]: 覆盖率报告
    """
    # 查找覆盖率报告文件
    possible_paths = [
        Path(project_path) / "coverage" / "coverage-summary.json",
    ]

    report_path = None
    for path in possible_paths:
        if path.exists():
            report_path = path
            break

    if not report_path:
        # 尝试解析 lcov.info
        lcov_path = Path(project_path) / "coverage" / "lcov.info"
        if lcov_path.exists():
            return parse_lcov_report(str(lcov_path))
        return None

    try:
        import json
        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        total = data.get("total", {})

        lines = total.get("lines", {})
        statements = total.get("statements", {})
        functions = total.get("functions", {})
        branches = total.get("branches", {})

        line_pct = lines.get("pct", 0)
        statement_pct = statements.get("pct", 0)
        function_pct = functions.get("pct", 0)
        branch_pct = branches.get("pct", 0)

        # 计算总体覆盖率
        overall_coverage = (line_pct * 0.4 + branch_pct * 0.4 + function_pct * 0.2)

        return CoverageReport(
            overall_coverage=round(overall_coverage, 2),
            line_coverage=round(line_pct, 2),
            branch_coverage=round(branch_pct, 2),
            method_coverage=round(function_pct, 2),
            class_coverage=round(statement_pct, 2),
            total_lines=lines.get("total", 0),
            covered_lines=lines.get("covered", 0),
            total_branches=branches.get("total", 0),
            covered_branches=branches.get("covered", 0),
            gaps=[],
            raw_report=data,
        )

    except Exception as e:
        print(f"解析 Istanbul 报告出错: {e}")
        return None


def parse_lcov_report(lcov_path: str) -> Optional[CoverageReport]:
    """解析 LCOV 覆盖率报告.

    Args:
        lcov_path: LCOV 文件路径

    Returns:
        Optional[CoverageReport]: 覆盖率报告
    """
    try:
        with open(lcov_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines_found = 0
        lines_hit = 0
        functions_found = 0
        functions_hit = 0
        branches_found = 0
        branches_hit = 0

        for line in content.split("\n"):
            if line.startswith("LF:"):
                lines_found = int(line.split(":")[1])
            elif line.startswith("LH:"):
                lines_hit = int(line.split(":")[1])
            elif line.startswith("FNF:"):
                functions_found = int(line.split(":")[1])
            elif line.startswith("FNH:"):
                functions_hit = int(line.split(":")[1])
            elif line.startswith("BRF:"):
                branches_found = int(line.split(":")[1])
            elif line.startswith("BRH:"):
                branches_hit = int(line.split(":")[1])

        line_coverage = (lines_hit / lines_found * 100) if lines_found > 0 else 0
        method_coverage = (functions_hit / functions_found * 100) if functions_found > 0 else 0
        branch_coverage = (branches_hit / branches_found * 100) if branches_found > 0 else 0

        overall_coverage = (line_coverage * 0.5 + branch_coverage * 0.5)

        return CoverageReport(
            overall_coverage=round(overall_coverage, 2),
            line_coverage=round(line_coverage, 2),
            branch_coverage=round(branch_coverage, 2),
            method_coverage=round(method_coverage, 2),
            class_coverage=0.0,
            total_lines=lines_found,
            covered_lines=lines_hit,
            total_branches=branches_found,
            covered_branches=branches_hit,
            gaps=[],
            raw_report={},
        )

    except Exception as e:
        print(f"解析 LCOV 报告出错: {e}")
        return None


def identify_coverage_gaps(
    coverage_report: CoverageReport, project_path: str
) -> List[CoverageGap]:
    """识别覆盖率缺口.

    Args:
        coverage_report: 覆盖率报告
        project_path: 项目路径

    Returns:
        List[CoverageGap]: 覆盖率缺口列表
    """
    gaps = []

    # 解析原始报告中的未覆盖行
    raw_report = coverage_report.raw_report

    if "files" in raw_report:
        # Istanbul 格式
        for file_path, file_data in raw_report["files"].items():
            lines = file_data.get("lines", {})
            uncovered_lines = lines.get("uncovered", [])

            for line_num in uncovered_lines[:20]:  # 限制数量
                gaps.append(CoverageGap(
                    file_path=file_path,
                    line_number=line_num,
                    line_content=get_line_content(project_path, file_path, line_num),
                    gap_type="line",
                ))

    elif "packages" in raw_report:
        # JaCoCo 格式
        for package in raw_report.get("packages", []):
            for sourcefile in package.get("sourcefiles", []):
                file_path = sourcefile.get("name", "")
                for line in sourcefile.get("lines", []):
                    if line.get("ci", 0) == 0:  # 未覆盖
                        gaps.append(CoverageGap(
                            file_path=file_path,
                            line_number=line.get("nr", 0),
                            line_content=line.get("content", ""),
                            gap_type="line",
                        ))

    # 如果缺口太多，优先返回关键缺口
    return gaps[:30]


def get_line_content(project_path: str, file_path: str, line_number: int) -> str:
    """获取指定行的代码内容.

    Args:
        project_path: 项目路径
        file_path: 文件路径
        line_number: 行号

    Returns:
        str: 行内容
    """
    try:
        full_path = Path(project_path) / file_path
        if full_path.exists():
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if 0 < line_number <= len(lines):
                    return lines[line_number - 1].strip()
    except Exception:
        pass
    return ""


def generate_coverage_summary(coverage_report: CoverageReport) -> str:
    """生成覆盖率摘要.

    Args:
        coverage_report: 覆盖率报告

    Returns:
        str: 摘要文本
    """
    return f"""
覆盖率报告摘要:
================
总体覆盖率: {coverage_report.overall_coverage:.2f}%
行覆盖率: {coverage_report.line_coverage:.2f}% ({coverage_report.covered_lines}/{coverage_report.total_lines})
分支覆盖率: {coverage_report.branch_coverage:.2f}% ({coverage_report.covered_branches}/{coverage_report.total_branches})
方法覆盖率: {coverage_report.method_coverage:.2f}%
类覆盖率: {coverage_report.class_coverage:.2f}%

缺口数量: {len(coverage_report.gaps)}
"""


def check_coverage_threshold(
    coverage_report: CoverageReport, threshold: float
) -> Dict[str, Any]:
    """检查覆盖率是否达到阈值.

    Args:
        coverage_report: 覆盖率报告
        threshold: 阈值

    Returns:
        Dict: 检查结果
    """
    passed = coverage_report.overall_coverage >= threshold

    details = {
        "overall": {
            "actual": coverage_report.overall_coverage,
            "threshold": threshold,
            "passed": coverage_report.overall_coverage >= threshold,
        },
        "line": {
            "actual": coverage_report.line_coverage,
            "threshold": threshold,
            "passed": coverage_report.line_coverage >= threshold,
        },
        "branch": {
            "actual": coverage_report.branch_coverage,
            "threshold": threshold * 0.8,  # 分支覆盖率阈值稍低
            "passed": coverage_report.branch_coverage >= threshold * 0.8,
        },
    }

    return {
        "passed": passed,
        "details": details,
    }
