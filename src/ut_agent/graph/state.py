"""Agent 状态定义."""

from typing import Annotated, List, Optional, Dict, Any
from typing_extensions import TypedDict
from dataclasses import dataclass, field
from operator import add


@dataclass
class TestFile:
    """测试文件信息."""

    source_file: str
    test_file_path: str
    test_code: str
    language: str
    status: str = "pending"
    error_message: Optional[str] = None


@dataclass
class CoverageGap:
    """覆盖率缺口信息."""

    file_path: str
    line_number: int
    line_content: str
    gap_type: str
    branch_info: Optional[str] = None


@dataclass
class CoverageReport:
    """覆盖率报告."""

    overall_coverage: float
    line_coverage: float
    branch_coverage: float
    method_coverage: float
    class_coverage: float
    total_lines: int
    covered_lines: int
    total_branches: int
    covered_branches: int
    gaps: List[CoverageGap] = field(default_factory=list)
    raw_report: Dict[str, Any] = field(default_factory=dict)


class AgentState(TypedDict):
    """Agent 状态定义."""

    # 项目信息
    project_path: str
    project_type: str
    build_tool: str

    # 目标配置
    target_files: List[str]
    coverage_target: float
    max_iterations: int

    # 执行状态
    iteration_count: int
    status: str
    message: str

    # 代码分析结果
    analyzed_files: Annotated[List[Dict[str, Any]], add]

    # 生成的测试
    generated_tests: Annotated[List[TestFile], add]

    # 覆盖率结果
    coverage_report: Optional[CoverageReport]
    current_coverage: float

    # 迭代优化
    coverage_gaps: List[CoverageGap]
    improvement_plan: Optional[str]

    # 最终输出
    output_path: Optional[str]
    summary: Optional[str]
