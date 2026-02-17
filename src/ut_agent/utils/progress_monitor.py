"""进度监控面板 - 提供实时进度展示."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.layout import Layout
from rich.text import Text
from rich import box

from ut_agent.utils.events import Event, EventType
from ut_agent.utils.event_bus import event_bus


@dataclass
class StageProgress:
    stage_name: str
    current: int = 0
    total: int = 0
    percentage: float = 0.0
    current_file: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: str = "pending"
    message: str = ""
    
    @property
    def duration_ms(self) -> float:
        if self.start_time:
            end = self.end_time or datetime.now()
            return (end - self.start_time).total_seconds() * 1000
        return 0.0
    
    def update(self, current: int, total: int, current_file: Optional[str] = None, message: str = ""):
        self.current = current
        self.total = total
        self.percentage = round(current / total * 100, 1) if total > 0 else 0
        self.current_file = current_file
        self.message = message
        if self.status == "pending":
            self.status = "running"
            self.start_time = datetime.now()


@dataclass
class WorkflowProgress:
    current_stage: str = ""
    stages: Dict[str, StageProgress] = field(default_factory=dict)
    total_files: int = 0
    processed_files: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    event_log: List[Dict[str, Any]] = field(default_factory=list)
    llm_stats: Dict[str, Any] = field(default_factory=dict)
    test_stats: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        default_stages = [
            "detect_project",
            "analyze_code",
            "generate_tests",
            "save_tests",
            "execute_tests",
            "analyze_coverage",
        ]
        for stage in default_stages:
            if stage not in self.stages:
                self.stages[stage] = StageProgress(stage_name=stage)
    
    @property
    def overall_percentage(self) -> float:
        completed_stages = sum(1 for s in self.stages.values() if s.status == "completed")
        total_stages = len(self.stages)
        if total_stages == 0:
            return 0.0
        
        base_percentage = (completed_stages / total_stages) * 100
        
        current = self.stages.get(self.current_stage)
        if current and current.status == "running":
            stage_weight = 100 / total_stages
            base_percentage = (completed_stages * stage_weight) + (current.percentage * stage_weight / 100)
        
        return round(base_percentage, 1)
    
    @property
    def duration_str(self) -> str:
        if self.start_time:
            end = self.end_time or datetime.now()
            delta = end - self.start_time
            total_seconds = int(delta.total_seconds())
            minutes, seconds = divmod(total_seconds, 60)
            return f"{minutes:02d}:{seconds:02d}"
        return "00:00"


class ProgressMonitor:
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.progress = WorkflowProgress()
        self._live: Optional[Live] = None
        self._subscribed = False
    
    def start(self) -> None:
        self.progress.start_time = datetime.now()
        
        if not self._subscribed:
            event_bus.subscribe_all(self._handle_event)
            self._subscribed = True
        
        self._live = Live(
            self._generate_layout(),
            console=self.console,
            refresh_per_second=4,
            transient=True,
        )
        self._live.start()
    
    def stop(self) -> None:
        self.progress.end_time = datetime.now()
        if self._live:
            self._live.stop()
            self._live = None
    
    def _handle_event(self, event: Event) -> None:
        event_type = event.event_type
        data = event.data
        
        if event_type == EventType.FILE_ANALYSIS_STARTED:
            self.progress.current_stage = "analyze_code"
            self.progress.stages["analyze_code"].status = "running"
            self.progress.stages["analyze_code"].start_time = datetime.now()
            self.progress.stages["analyze_code"].total = data.get("total_files", 0)
        
        elif event_type == EventType.FILE_ANALYSIS_COMPLETED:
            self.progress.stages["analyze_code"].status = "completed"
            self.progress.stages["analyze_code"].end_time = datetime.now()
        
        elif event_type == EventType.TEST_GENERATION_STARTED:
            self.progress.current_stage = "generate_tests"
            self.progress.stages["generate_tests"].status = "running"
            self.progress.stages["generate_tests"].start_time = datetime.now()
            self.progress.stages["generate_tests"].total = data.get("total_files", 0)
        
        elif event_type == EventType.TEST_GENERATION_COMPLETED:
            self.progress.stages["generate_tests"].status = "completed"
            self.progress.stages["generate_tests"].end_time = datetime.now()
        
        elif event_type == EventType.NODE_PROGRESS:
            stage = data.get("stage", "")
            current = data.get("current", 0)
            total = data.get("total", 0)
            current_file = data.get("current_file")
            message = data.get("message", "")
            
            if stage in self.progress.stages:
                self.progress.stages[stage].update(current, total, current_file, message)
        
        elif event_type == EventType.ERROR_OCCURRED:
            self.progress.event_log.append({
                "type": "error",
                "message": data.get("error_message", ""),
                "timestamp": datetime.now().isoformat(),
            })
        
        elif event_type == EventType.LLM_CALL_STARTED:
            self.progress.llm_stats["active_calls"] = self.progress.llm_stats.get("active_calls", 0) + 1
            self.progress.llm_stats["total_calls"] = self.progress.llm_stats.get("total_calls", 0) + 1
            self.progress.llm_stats["provider"] = data.get("provider", "unknown")
            self.progress.llm_stats["model"] = data.get("model", "unknown")
        
        elif event_type == EventType.LLM_CALL_STREAMING:
            self.progress.llm_stats["tokens_generated"] = data.get("tokens_generated", 0)
        
        elif event_type == EventType.LLM_CALL_COMPLETED:
            self.progress.llm_stats["active_calls"] = max(0, self.progress.llm_stats.get("active_calls", 1) - 1)
            self.progress.llm_stats["total_tokens"] = self.progress.llm_stats.get("total_tokens", 0) + data.get("total_tokens", 0)
            self.progress.llm_stats["last_duration_ms"] = data.get("duration_ms", 0)
            self.progress.llm_stats["tokens_per_second"] = data.get("tokens_per_second", 0)
        
        elif event_type == EventType.LLM_CALL_FAILED:
            self.progress.llm_stats["active_calls"] = max(0, self.progress.llm_stats.get("active_calls", 1) - 1)
            self.progress.llm_stats["failed_calls"] = self.progress.llm_stats.get("failed_calls", 0) + 1
        
        elif event_type == EventType.TEST_EXECUTION_STARTED:
            self.progress.current_stage = "execute_tests"
            self.progress.stages["execute_tests"].status = "running"
            self.progress.stages["execute_tests"].start_time = datetime.now()
        
        elif event_type == EventType.TEST_EXECUTION_PROGRESS:
            self.progress.test_stats["passed"] = data.get("passed", 0)
            self.progress.test_stats["failed"] = data.get("failed", 0)
            self.progress.test_stats["skipped"] = data.get("skipped", 0)
        
        elif event_type == EventType.TEST_EXECUTION_COMPLETED:
            self.progress.stages["execute_tests"].status = "completed"
            self.progress.stages["execute_tests"].end_time = datetime.now()
            self.progress.test_stats["passed"] = data.get("passed", 0)
            self.progress.test_stats["failed"] = data.get("failed", 0)
            self.progress.test_stats["skipped"] = data.get("skipped", 0)
        
        if self._live:
            self._live.update(self._generate_layout())
    
    def _generate_layout(self) -> Panel:
        layout = Layout()
        
        header = Text()
        header.append("🚀 UT-Agent 进度监控", style="bold cyan")
        header.append(f"  |  ⏱️ {self.progress.duration_str}", style="yellow")
        
        progress_bar = self._create_progress_bar()
        
        stages_table = self._create_stages_table()
        
        current_info = self._create_current_info()
        
        llm_panel = self._create_llm_panel()
        
        test_panel = self._create_test_panel()
        
        content = Table.grid(padding=1)
        content.add_row(header)
        content.add_row(progress_bar)
        content.add_row(stages_table)
        content.add_row(current_info)
        content.add_row(llm_panel)
        content.add_row(test_panel)
        
        return Panel(
            content,
            border_style="cyan",
            title="[bold]测试生成进度[/bold]",
            title_align="left",
        )
    
    def _create_progress_bar(self) -> Text:
        percentage = self.progress.overall_percentage
        filled = int(percentage / 5)
        empty = 20 - filled
        
        bar = Text()
        bar.append("进度: ", style="bold")
        bar.append("█" * filled, style="green")
        bar.append("░" * empty, style="dim")
        bar.append(f" {percentage}%", style="bold green")
        
        return bar
    
    def _create_stages_table(self) -> Table:
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("阶段", style="cyan", width=15)
        table.add_column("状态", width=10)
        table.add_column("进度", width=20)
        table.add_column("耗时", width=10)
        
        stage_names = {
            "detect_project": "🔍 项目检测",
            "analyze_code": "📊 代码分析",
            "generate_tests": "🧪 测试生成",
            "save_tests": "💾 保存测试",
            "execute_tests": "⚡ 执行测试",
            "analyze_coverage": "📈 覆盖率分析",
        }
        
        for stage_name, stage in self.progress.stages.items():
            display_name = stage_names.get(stage_name, stage_name)
            
            if stage.status == "completed":
                status = "✅ 完成"
                status_style = "green"
            elif stage.status == "running":
                status = "🔄 进行中"
                status_style = "yellow"
            else:
                status = "⏳ 等待"
                status_style = "dim"
            
            if stage.total > 0:
                progress_str = f"{stage.current}/{stage.total} ({stage.percentage}%)"
            else:
                progress_str = "-"
            
            duration_str = f"{stage.duration_ms:.0f}ms" if stage.duration_ms > 0 else "-"
            
            table.add_row(
                display_name,
                Text(status, style=status_style),
                progress_str,
                duration_str,
            )
        
        return table
    
    def _create_current_info(self) -> Text:
        current_stage = self.progress.stages.get(self.progress.current_stage)
        
        info = Text()
        if current_stage and current_stage.status == "running":
            info.append("当前: ", style="bold")
            if current_stage.current_file:
                file_name = current_stage.current_file.split("/")[-1].split("\\")[-1]
                info.append(f"{file_name}", style="cyan")
            if current_stage.message:
                info.append(f"  {current_stage.message}", style="dim")
        else:
            info.append("就绪", style="dim")
        
        return info
    
    def _create_llm_panel(self) -> Table:
        table = Table(show_header=True, header_style="bold", box=box.SIMPLE, padding=(0, 1))
        table.add_column("🤖 LLM状态", style="cyan", width=20)
        table.add_column("值", style="green", width=30)
        
        llm = self.progress.llm_stats
        if not llm:
            table.add_row("状态", "未启动")
            return table
        
        provider = llm.get("provider", "-")
        model = llm.get("model", "-")
        if provider != "-" or model != "-":
            table.add_row("提供商/模型", f"{provider}/{model}")
        
        active = llm.get("active_calls", 0)
        total = llm.get("total_calls", 0)
        status = "🔄 调用中" if active > 0 else "✅ 空闲"
        table.add_row("状态", f"{status} (活跃: {active}, 总计: {total})")
        
        tokens = llm.get("tokens_generated", 0)
        total_tokens = llm.get("total_tokens", 0)
        if tokens > 0 or total_tokens > 0:
            table.add_row("Token", f"当前: {tokens}, 总计: {total_tokens}")
        
        tps = llm.get("tokens_per_second", 0)
        if tps > 0:
            table.add_row("生成速度", f"{tps:.1f} tokens/s")
        
        failed = llm.get("failed_calls", 0)
        if failed > 0:
            table.add_row("失败次数", f"[red]{failed}[/red]")
        
        return table
    
    def _create_test_panel(self) -> Table:
        table = Table(show_header=True, header_style="bold", box=box.SIMPLE, padding=(0, 1))
        table.add_column("🧪 测试状态", style="cyan", width=20)
        table.add_column("值", style="green", width=30)
        
        test = self.progress.test_stats
        if not test:
            table.add_row("状态", "未执行")
            return table
        
        passed = test.get("passed", 0)
        failed = test.get("failed", 0)
        skipped = test.get("skipped", 0)
        
        if passed > 0 or failed > 0:
            total = passed + failed + skipped
            success_rate = (passed / total * 100) if total > 0 else 0
            
            status_text = f"✅ {passed} 通过"
            if failed > 0:
                status_text += f", ❌ {failed} 失败"
            if skipped > 0:
                status_text += f", ⏭️ {skipped} 跳过"
            
            table.add_row("测试结果", status_text)
            table.add_row("成功率", f"{success_rate:.1f}%")
        else:
            table.add_row("状态", "执行中...")
        
        return table
    
    def get_summary(self) -> Dict[str, Any]:
        return {
            "duration_ms": (self.progress.end_time - self.progress.start_time).total_seconds() * 1000
            if self.progress.start_time and self.progress.end_time else 0,
            "stages": {
                name: {
                    "duration_ms": stage.duration_ms,
                    "files_processed": stage.current,
                    "files_total": stage.total,
                    "status": stage.status,
                }
                for name, stage in self.progress.stages.items()
            },
            "event_count": len(self.progress.event_log),
            "llm_stats": self.progress.llm_stats,
            "test_stats": self.progress.test_stats,
        }


def create_progress_monitor(console: Optional[Console] = None) -> ProgressMonitor:
    return ProgressMonitor(console)
