"""Agent 状态定义."""

from typing import Annotated, List, Optional, Dict, Any, Tuple
from typing_extensions import TypedDict
from dataclasses import dataclass, field
from datetime import datetime
from operator import add

from ut_agent.models.common import ChangeType, CodeChange, MethodInfo


@dataclass
class GeneratedTestFile:
    """生成的测试文件信息."""

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


@dataclass
class ChangeSummary:
    """变更摘要."""

    file_path: str
    change_type: ChangeType
    affected_classes: List[str] = field(default_factory=list)
    added_methods: List[MethodInfo] = field(default_factory=list)
    modified_methods: List[Tuple[MethodInfo, MethodInfo]] = field(default_factory=list)
    deleted_methods: List[MethodInfo] = field(default_factory=list)


@dataclass
class ProgressInfo:
    current: int = 0
    total: int = 0
    percentage: float = 0.0
    current_file: Optional[str] = None
    stage: str = ""
    message: str = ""
    
    def update(self, current: int, total: int, current_file: Optional[str] = None) -> None:
        self.current = current
        self.total = total
        self.percentage = round(current / total * 100, 1) if total > 0 else 0
        self.current_file = current_file


@dataclass
class StageMetrics:
    stage_name: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    files_processed: int = 0
    files_total: int = 0
    success_count: int = 0
    error_count: int = 0
    
    def start(self) -> None:
        self.start_time = datetime.now()
    
    def complete(self) -> None:
        self.end_time = datetime.now()
        if self.start_time:
            self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000


class AgentState(TypedDict):
    """Agent 状态定义."""

    project_path: str
    project_type: str
    build_tool: str

    target_files: List[str]
    coverage_target: float
    max_iterations: int

    incremental: bool
    base_ref: Optional[str]
    head_ref: Optional[str]

    iteration_count: int
    status: str
    message: str

    analyzed_files: Annotated[List[Dict[str, Any]], add]

    code_changes: List[CodeChange]
    change_summaries: List[ChangeSummary]

    generated_tests: Annotated[List[GeneratedTestFile], add]

    coverage_report: Optional[CoverageReport]
    current_coverage: float

    coverage_gaps: List[CoverageGap]
    improvement_plan: Optional[str]

    output_path: Optional[str]
    summary: Optional[str]
    html_report_path: Optional[str]
    
    progress: Dict[str, Any]
    stage_metrics: Dict[str, Any]
    event_log: Annotated[List[Dict[str, Any]], add]
