"""CLI 入口模块."""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import box

from ut_agent.graph import create_test_generation_graph, AgentState
from ut_agent.models import list_available_providers, get_llm
from ut_agent.config import settings
from ut_agent.tools.test_executor import (
    check_java_environment,
    check_maven_environment,
    check_node_environment,
)

app = typer.Typer(
    name="ut-agent",
    help="AI驱动的单元测试生成Agent",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool) -> None:
    """版本回调."""
    if value:
        console.print("[bold blue]UT-Agent[/bold blue] version 0.1.0")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
) -> None:
    """UT-Agent: AI驱动的单元测试生成器."""
    pass


@app.command(name="generate")
def generate_tests(
    project: Path = typer.Argument(
        ..., help="项目路径", exists=True, file_okay=False, dir_okay=True
    ),
    project_type: str = typer.Option(
        "auto", "--type", "-t", help="项目类型 (auto/java/vue/react/typescript)"
    ),
    coverage_target: float = typer.Option(
        settings.default_coverage_target, "--coverage-target", "-c",
        help="覆盖率目标 (0-100)"
    ),
    max_iterations: int = typer.Option(
        settings.max_iterations, "--max-iterations", "-i",
        help="最大迭代次数"
    ),
    llm_provider: str = typer.Option(
        settings.default_llm_provider, "--llm", "-l",
        help="LLM 提供商"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="仅生成测试，不保存"
    ),
    incremental: bool = typer.Option(
        False, "--incremental", "-inc",
        help="增量模式：仅对变更代码生成测试"
    ),
    base_ref: Optional[str] = typer.Option(
        None, "--base", "-b",
        help="基准Git引用 (默认: HEAD~1)"
    ),
    head_ref: Optional[str] = typer.Option(
        None, "--head",
        help="目标Git引用 (默认: HEAD)"
    ),
    html_report: bool = typer.Option(
        False, "--html-report", "-r",
        help="生成HTML覆盖率报告"
    ),
) -> None:
    """生成单元测试."""
    console.print(Panel.fit(
        "[bold blue]🧪 UT-Agent[/bold blue] - AI驱动的单元测试生成器",
        border_style="blue"
    ))

    # 验证参数
    if coverage_target < 0 or coverage_target > 100:
        console.print("[red]错误: 覆盖率目标必须在 0-100 之间[/red]")
        raise typer.Exit(1)

    # 显示配置
    config_table = Table(box=box.ROUNDED)
    config_table.add_column("配置项", style="cyan")
    config_table.add_column("值", style="green")
    config_table.add_row("项目路径", str(project))
    config_table.add_row("项目类型", project_type)
    config_table.add_row("覆盖率目标", f"{coverage_target}%")
    config_table.add_row("最大迭代次数", str(max_iterations))
    config_table.add_row("LLM 提供商", llm_provider)
    config_table.add_row("Dry Run", "是" if dry_run else "否")
    config_table.add_row("增量模式", "是" if incremental else "否")
    if incremental:
        config_table.add_row("基准引用", base_ref or "HEAD~1")
        config_table.add_row("目标引用", head_ref or "HEAD")
    config_table.add_row("HTML报告", "是" if html_report else "否")
    console.print(config_table)
    console.print()

    # 运行工作流
    asyncio.run(run_generation_workflow(
        project_path=str(project),
        project_type=project_type,
        coverage_target=coverage_target,
        max_iterations=max_iterations,
        llm_provider=llm_provider,
        dry_run=dry_run,
        incremental=incremental,
        base_ref=base_ref,
        head_ref=head_ref,
        html_report=html_report,
    ))


@app.command(name="interactive")
def interactive_mode() -> None:
    """交互式模式."""
    console.print(Panel.fit(
        "[bold blue]🧪 UT-Agent[/bold blue] - 交互式模式",
        border_style="blue"
    ))

    # 项目路径
    project_path = typer.prompt("请输入项目路径")
    project = Path(project_path)
    if not project.exists():
        console.print(f"[red]错误: 路径不存在 {project_path}[/red]")
        raise typer.Exit(1)

    # 项目类型
    project_type = typer.prompt(
        "项目类型 (auto/java/vue/react/typescript)",
        default="auto"
    )

    # 覆盖率目标
    coverage_target = float(typer.prompt(
        "覆盖率目标 (%)",
        default=str(settings.default_coverage_target)
    ))

    # 最大迭代次数
    max_iterations = int(typer.prompt(
        "最大迭代次数",
        default=str(settings.max_iterations)
    ))

    # LLM 提供商
    available_providers = list_available_providers()
    llm_provider = typer.prompt(
        f"LLM 提供商 ({'/'.join(available_providers)})",
        default=settings.default_llm_provider
    )

    # 运行
    asyncio.run(run_generation_workflow(
        project_path=str(project),
        project_type=project_type,
        coverage_target=coverage_target,
        max_iterations=max_iterations,
        llm_provider=llm_provider,
        dry_run=False,
    ))


@app.command(name="ui")
def launch_ui(
    port: int = typer.Option(8501, "--port", "-p", help="端口号"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="主机地址"),
) -> None:
    """启动 Web UI."""
    console.print(Panel.fit(
        "[bold blue]🚀 启动 UT-Agent Web UI[/bold blue]",
        border_style="green"
    ))

    try:
        import streamlit.web.cli as stcli
        import sys

        ui_file = Path(__file__).parent / "ui" / "app.py"

        sys.argv = [
            "streamlit",
            "run",
            str(ui_file),
            "--server.port", str(port),
            "--server.address", host,
        ]

        console.print(f"[green]UI 启动在 http://{host}:{port}[/green]")
        stcli.main()

    except ImportError:
        console.print("[red]错误: 未安装 streamlit，请运行: pip install streamlit[/red]")
        raise typer.Exit(1)


@app.command(name="ci")
def ci_mode(
    project: Path = typer.Argument(
        ..., help="项目路径", exists=True, file_okay=False, dir_okay=True
    ),
    project_type: str = typer.Option(
        "auto", "--type", "-t", help="项目类型 (auto/java/vue/react/typescript)"
    ),
    coverage_target: float = typer.Option(
        80.0, "--coverage-target", "-c",
        help="覆盖率目标 (0-100)"
    ),
    max_iterations: int = typer.Option(
        5, "--max-iterations", "-i",
        help="最大迭代次数"
    ),
    llm_provider: str = typer.Option(
        "openai", "--llm", "-l",
        help="LLM 提供商"
    ),
    output_format: str = typer.Option(
        "json", "--output", "-o",
        help="输出格式 (json/markdown/summary)"
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output-file",
        help="输出文件路径"
    ),
    fail_on_coverage: bool = typer.Option(
        False, "--fail-on-coverage",
        help="覆盖率低于目标时返回非零退出码"
    ),
    incremental: bool = typer.Option(
        False, "--incremental", "-inc",
        help="增量模式：仅对变更代码生成测试"
    ),
    base_ref: Optional[str] = typer.Option(
        None, "--base", "-b",
        help="基准Git引用"
    ),
) -> None:
    """CI模式：非交互式运行，输出JSON结果."""
    from ut_agent.ci import CIRunner
    
    runner = CIRunner(
        project_path=str(project),
        project_type=project_type,
        coverage_target=coverage_target,
        max_iterations=max_iterations,
        llm_provider=llm_provider,
        output_format=output_format,
        output_file=str(output_file) if output_file else None,
        fail_on_coverage=fail_on_coverage,
        incremental=incremental,
        base_ref=base_ref,
    )
    
    exit_code = runner.run_sync()
    raise typer.Exit(exit_code)


@app.command(name="check")
def check_environment() -> None:
    """检查环境配置."""
    console.print(Panel.fit(
        "[bold blue]🔍 环境检查[/bold blue]",
        border_style="blue"
    ))

    table = Table(box=box.ROUNDED)
    table.add_column("组件", style="cyan")
    table.add_column("状态", style="green")
    table.add_column("信息", style="yellow")

    java_ok, java_msg = check_java_environment()
    table.add_row(
        "Java",
        "[green]✓[/green]" if java_ok else "[red]✗[/red]",
        java_msg
    )

    maven_ok, maven_msg = check_maven_environment()
    table.add_row(
        "Maven",
        "[green]✓[/green]" if maven_ok else "[red]✗[/red]",
        maven_msg
    )

    node_ok, node_msg = check_node_environment()
    table.add_row(
        "Node.js",
        "[green]✓[/green]" if node_ok else "[red]✗[/red]",
        node_msg
    )

    available_providers = list_available_providers()
    table.add_row(
        "LLM 提供商",
        "[green]✓[/green]" if available_providers else "[red]✗[/red]",
        f"可用: {', '.join(available_providers)}"
    )

    console.print(table)


@app.command(name="mutation")
def run_mutation_tests(
    project: Path = typer.Argument(
        ..., help="项目路径", exists=True, file_okay=False, dir_okay=True
    ),
    target_classes: Optional[str] = typer.Option(
        None, "--target-classes", "-tc",
        help="目标类 (逗号分隔, 默认: *)"
    ),
    target_tests: Optional[str] = typer.Option(
        None, "--target-tests", "-tt",
        help="目标测试类 (逗号分隔, 默认: *Test)"
    ),
    mutators: Optional[str] = typer.Option(
        None, "--mutators", "-m",
        help="变异算子 (逗号分隔, 默认: DEFAULTS)"
    ),
    output_format: str = typer.Option(
        "summary", "--output", "-o",
        help="输出格式 (json/summary)"
    ),
    suggest_tests: bool = typer.Option(
        True, "--suggest",
        help="生成测试建议"
    ),
) -> None:
    """运行变异测试并分析结果."""
    from ut_agent.tools.mutation_analyzer import MutationAnalyzer
    
    console.print(Panel.fit(
        "[bold purple]🧬 变异测试分析[/bold purple]",
        border_style="purple"
    ))
    
    analyzer = MutationAnalyzer(
        project_path=str(project),
        target_classes=target_classes.split(",") if target_classes else None,
        target_tests=target_tests.split(",") if target_tests else None,
        mutators=mutators.split(",") if mutators else None,
    )
    
    console.print("[cyan]正在运行变异测试...[/cyan]")
    
    try:
        report = analyzer.run_mutation_tests()
        
        if output_format == "json":
            console.print_json(data=report.to_dict())
        else:
            console.print(analyzer.get_report_summary())
        
        if suggest_tests and report.survived_mutations:
            console.print()
            console.print("[bold yellow]📝 测试建议[/bold yellow]")
            
            suggestions = analyzer.generate_test_suggestions()
            for i, suggestion in enumerate(suggestions[:10], 1):
                console.print(f"\n{i}. [cyan]{suggestion['source_file']}:{suggestion['line_number']}[/cyan]")
                console.print(f"   方法: {suggestion['method_name']}")
                console.print(f"   变异类型: {suggestion['mutation_type']}")
                console.print(f"   建议: {suggestion['suggested_test']}")
            
            if len(suggestions) > 10:
                console.print(f"\n   ... 还有 {len(suggestions) - 10} 个建议")
        
        if report.survived > 0:
            raise typer.Exit(1)
        
    except Exception as e:
        console.print(f"[red]变异测试执行失败: {e}[/red]")
        raise typer.Exit(2)


@app.command(name="config")
def show_config() -> None:
    """显示当前配置."""
    console.print(Panel.fit(
        "[bold blue]⚙️ 当前配置[/bold blue]",
        border_style="blue"
    ))

    table = Table(box=box.ROUNDED)
    table.add_column("配置项", style="cyan")
    table.add_column("值", style="green")

    table.add_row("默认 LLM 提供商", settings.default_llm_provider)
    table.add_row("OpenAI 模型", settings.openai_model)
    table.add_row("DeepSeek 模型", settings.deepseek_model)
    table.add_row("Ollama 模型", settings.ollama_model)
    table.add_row("Ollama 地址", settings.ollama_base_url)
    table.add_row("默认覆盖率目标", f"{settings.default_coverage_target}%")
    table.add_row("最大迭代次数", str(settings.max_iterations))
    table.add_row("Temperature", str(settings.temperature))

    console.print(table)


@app.command(name="metrics")
def show_metrics() -> None:
    """显示当前监控指标."""
    from ut_agent.utils.metrics import get_metrics_summary, log_metrics_summary
    
    console.print(Panel.fit(
        "[bold green]📊 监控指标[/bold green]",
        border_style="green"
    ))

    metrics = get_metrics_summary()
    
    # 打印 LLM 指标
    llm_metrics = metrics.get("llm", {})
    if llm_metrics:
        console.print("\n[bold cyan]LLM Metrics[/bold cyan]")
        table = Table(box=box.ROUNDED)
        table.add_column("指标", style="cyan")
        table.add_column("值", style="green")
        
        for key, value in llm_metrics.items():
            if isinstance(value, dict) and "value" in value:
                table.add_row(value.get("name", key), str(value.get("value")))
            elif isinstance(value, dict) and "summary" in value:
                table.add_row(value.get("name", key), "")
                summary = value.get("summary", {})
                for stat_name, stat_value in summary.items():
                    table.add_row(f"  {stat_name}", f"{stat_value:.2f}")
        
        console.print(table)
    
    # 打印缓存指标
    cache_metrics = metrics.get("cache", {})
    if cache_metrics:
        console.print("\n[bold cyan]Cache Metrics[/bold cyan]")
        table = Table(box=box.ROUNDED)
        table.add_column("指标", style="cyan")
        table.add_column("值", style="green")
        
        for key, value in cache_metrics.items():
            if isinstance(value, dict) and "value" in value:
                table.add_row(value.get("name", key), str(value.get("value")))
        
        console.print(table)
    
    # 打印性能指标
    perf_metrics = metrics.get("performance", {})
    if perf_metrics:
        console.print("\n[bold cyan]Performance Metrics[/bold cyan]")
        table = Table(box=box.ROUNDED)
        table.add_column("指标", style="cyan")
        table.add_column("值", style="green")
        
        for key, value in perf_metrics.items():
            if isinstance(value, dict) and "summary" in value:
                table.add_row(value.get("name", key), "")
                summary = value.get("summary", {})
                for stat_name, stat_value in summary.items():
                    table.add_row(f"  {stat_name}", f"{stat_value:.2f}")
        
        console.print(table)
    
    # 记录到日志
    log_metrics_summary()


@app.command(name="testability")
def analyze_testability(
    source_file: Path = typer.Argument(
        ..., help="源文件路径", exists=True, file_okay=True, dir_okay=False
    ),
    output_format: str = typer.Option(
        "summary", "--output", "-o",
        help="输出格式 (summary/json/detailed)"
    ),
    show_refactoring: bool = typer.Option(
        True, "--refactoring", "-r",
        help="显示重构建议"
    ),
) -> None:
    """分析代码可测试性."""
    from ut_agent.tools.testability_analyzer import (
        TestabilityAnalyzer,
        RefactoringAdvisor,
    )
    
    console.print(Panel.fit(
        "[bold cyan]🔍 可测试性分析[/bold cyan]",
        border_style="cyan"
    ))
    
    analyzer = TestabilityAnalyzer(str(source_file.parent))
    
    with open(source_file, 'r', encoding='utf-8') as f:
        source_code = f.read()
    
    score = analyzer.analyze_file(str(source_file), source_code)
    
    if output_format == "json":
        console.print_json(data=score.to_dict())
    else:
        console.print(f"\n[bold]可测试性评分: {score.overall_score:.1f}/100[/bold]")
        
        table = Table(box=box.ROUNDED)
        table.add_column("维度", style="cyan")
        table.add_column("评分", style="green")
        
        table.add_row("依赖管理", f"{score.dependency_score:.1f}")
        table.add_row("耦合度", f"{score.coupling_score:.1f}")
        table.add_row("复杂度", f"{score.complexity_score:.1f}")
        table.add_row("设计质量", f"{score.design_score:.1f}")
        
        console.print(table)
        
        if score.issues:
            console.print(f"\n[bold yellow]发现 {len(score.issues)} 个问题[/bold yellow]")
            
            for issue in score.issues[:10]:
                severity_color = {
                    "critical": "red",
                    "high": "yellow",
                    "medium": "cyan",
                    "low": "blue",
                }.get(issue.severity.value, "white")
                
                console.print(f"\n[{severity_color}]{issue.severity.value.upper()}[/{severity_color}] {issue.issue_type.value}")
                console.print(f"  位置: {source_file.name}:{issue.line_number}")
                console.print(f"  描述: {issue.description}")
                
                if show_refactoring:
                    console.print(f"  [green]建议: {issue.refactoring_suggestion}[/green]")
        
        if show_refactoring and score.issues:
            console.print("\n[bold cyan]🔧 重构建议[/bold cyan]")
            advisor = RefactoringAdvisor()
            report = advisor.generate_refactoring_report(score.issues)
            
            for refactoring in report["refactorings"][:5]:
                console.print(f"\n[cyan]{refactoring['suggestion']['description']}[/cyan]")
                for step in refactoring['suggestion']['applies_to']:
                    console.print(f"  - {step}")


@app.command(name="stability")
def analyze_stability(
    project: Path = typer.Argument(
        ..., help="项目路径", exists=True, file_okay=False, dir_okay=True
    ),
    history_file: Optional[Path] = typer.Option(
        None, "--history", "-h",
        help="测试执行历史文件路径"
    ),
    runs: int = typer.Option(
        5, "--runs", "-n",
        help="稳定性检测运行次数"
    ),
    output_format: str = typer.Option(
        "summary", "--output", "-o",
        help="输出格式 (summary/json)"
    ),
) -> None:
    """分析测试稳定性."""
    from ut_agent.tools.flaky_detector import (
        StabilityAnalyzer,
        FlakyTestDetector,
    )
    
    console.print(Panel.fit(
        "[bold yellow]⚡ 测试稳定性分析[/bold yellow]",
        border_style="yellow"
    ))
    
    detector = FlakyTestDetector(
        history_file=str(history_file) if history_file else None
    )
    
    analyzer = StabilityAnalyzer(
        str(project),
        history_file=str(history_file) if history_file else None,
    )
    
    flaky_tests = detector.detect_flaky_tests()
    
    if output_format == "json":
        result = {
            "total_flaky": len(flaky_tests),
            "flaky_tests": [t.to_dict() for t in flaky_tests],
        }
        console.print_json(data=result)
    else:
        if flaky_tests:
            console.print(f"\n[bold red]发现 {len(flaky_tests)} 个不稳定测试[/bold red]")
            
            for test in flaky_tests:
                console.print(f"\n[yellow]⚠️ {test.test_class}.{test.test_method}[/yellow]")
                console.print(f"  Flaky评分: {test.flaky_score:.2f}")
                console.print(f"  通过/失败: {test.pass_count}/{test.fail_count}")
                console.print(f"  原因: {', '.join(c.value for c in test.detected_causes)}")
                
                if test.suggested_fixes:
                    console.print("  [green]修复建议:[/green]")
                    for fix in test.suggested_fixes[:3]:
                        console.print(f"    - {fix}")
        else:
            console.print("\n[bold green]✅ 未发现不稳定测试[/bold green]")


@app.command(name="debt")
def manage_debt(
    project: Path = typer.Argument(
        ..., help="项目路径", exists=True, file_okay=False, dir_okay=True
    ),
    action: str = typer.Argument(
        "report", help="操作: report/add/resolve/summary"
    ),
    debt_type: Optional[str] = typer.Option(
        None, "--type", "-t",
        help="债务类型 (missing_tests/low_coverage/flaky_tests等)"
    ),
    description: Optional[str] = typer.Option(
        None, "--description", "-d",
        help="债务描述"
    ),
    priority: str = typer.Option(
        "medium", "--priority", "-p",
        help="优先级 (critical/high/medium/low)"
    ),
    debt_id: Optional[str] = typer.Option(
        None, "--id",
        help="债务ID (用于resolve操作)"
    ),
) -> None:
    """管理测试债务."""
    from ut_agent.tools.test_debt_tracker import (
        TestDebtTracker,
        DebtType,
        DebtPriority,
    )
    
    storage_path = str(project / ".ut-agent" / "debt")
    tracker = TestDebtTracker(str(project), storage_path=storage_path)
    
    if action == "report":
        console.print(Panel.fit(
            "[bold red]📋 测试债务报告[/bold red]",
            border_style="red"
        ))
        
        report = tracker.get_debt_report()
        
        table = Table(box=box.ROUNDED)
        table.add_column("指标", style="cyan")
        table.add_column("值", style="green")
        
        table.add_row("总债务评分", f"{report.total_debt_score:.2f}")
        table.add_row("总债务项", str(report.total_items))
        table.add_row("待处理项", str(report.open_items))
        table.add_row("关键项", str(report.critical_items))
        
        console.print(table)
        
        if report.recommendations:
            console.print("\n[bold cyan]💡 建议[/bold cyan]")
            for rec in report.recommendations:
                console.print(f"  - {rec}")
        
    elif action == "add":
        if not debt_type or not description:
            console.print("[red]错误: add操作需要 --type 和 --description 参数[/red]")
            raise typer.Exit(1)
        
        try:
            dtype = DebtType(debt_type)
            dpriority = DebtPriority(priority)
        except ValueError as e:
            console.print(f"[red]错误: 无效的债务类型或优先级 - {e}[/red]")
            raise typer.Exit(1)
        
        item = tracker.add_debt_item(
            debt_type=dtype,
            file_path=str(project),
            description=description,
            impact_score=5.0,
            priority=dpriority,
        )
        
        console.print(f"[green]✓ 已添加债务项: {item.debt_id}[/green]")
        
    elif action == "resolve":
        if not debt_id:
            console.print("[red]错误: resolve操作需要 --id 参数[/red]")
            raise typer.Exit(1)
        
        if tracker.resolve_debt(debt_id):
            console.print(f"[green]✓ 已解决债务项: {debt_id}[/green]")
        else:
            console.print(f"[red]错误: 未找到债务项: {debt_id}[/red]")
            raise typer.Exit(1)
    
    elif action == "summary":
        summary = tracker.get_debt_summary()
        console.print_json(data=summary)
    
    else:
        console.print(f"[red]错误: 未知操作 '{action}'[/red]")
        console.print("可用操作: report, add, resolve, summary")
        raise typer.Exit(1)


@app.command(name="quality")
def analyze_quality(
    test_file: Path = typer.Argument(
        ..., help="测试文件路径", exists=True, file_okay=True, dir_okay=False
    ),
    source_file: Optional[Path] = typer.Option(
        None, "--source", "-s",
        help="对应源文件路径"
    ),
    mutation_report: Optional[Path] = typer.Option(
        None, "--mutation", "-m",
        help="变异测试报告路径 (JSON)"
    ),
    coverage_report: Optional[Path] = typer.Option(
        None, "--coverage", "-c",
        help="覆盖率报告路径 (JSON)"
    ),
    output_format: str = typer.Option(
        "summary", "--output", "-o",
        help="输出格式 (summary/json/detailed)"
    ),
) -> None:
    """分析测试质量."""
    from ut_agent.tools.enhanced_quality_scorer import EnhancedQualityScorer
    import json
    
    console.print(Panel.fit(
        "[bold green]📊 测试质量分析[/bold green]",
        border_style="green"
    ))
    
    with open(test_file, 'r', encoding='utf-8') as f:
        test_code = f.read()
    
    source_code = ""
    if source_file and source_file.exists():
        with open(source_file, 'r', encoding='utf-8') as f:
            source_code = f.read()
    
    mutation_data = None
    if mutation_report and mutation_report.exists():
        with open(mutation_report, 'r', encoding='utf-8') as f:
            mutation_data = json.load(f)
    
    coverage_data = None
    if coverage_report and coverage_report.exists():
        with open(coverage_report, 'r', encoding='utf-8') as f:
            coverage_data = json.load(f)
    
    scorer = EnhancedQualityScorer()
    report = scorer.generate_comprehensive_report(
        test_code=test_code,
        source_code=source_code,
        test_file=str(test_file),
        source_file=str(source_file) if source_file else None,
        mutation_report=mutation_data,
        coverage_report=coverage_data,
    )
    
    if output_format == "json":
        console.print_json(data=report.to_dict())
    else:
        console.print(f"\n[bold]整体质量评分: {report.overall_score:.1f}/100 ({report.grade})[/bold]")
        
        table = Table(box=box.ROUNDED)
        table.add_column("维度", style="cyan")
        table.add_column("评分", style="green")
        table.add_column("状态", style="yellow")
        
        scores = [
            ("有效性", report.effectiveness_score),
            ("代码质量", report.code_quality_score),
            ("覆盖深度", report.coverage_depth_score),
            ("变异测试", report.mutation_score),
            ("稳定性", report.stability_score),
            ("可测试性", report.testability_score),
        ]
        
        for name, score in scores:
            status = "✓" if score >= 70 else "⚠" if score >= 50 else "✗"
            table.add_row(name, f"{score:.1f}", status)
        
        console.print(table)
        
        if report.critical_issues:
            console.print(f"\n[bold red]🚨 关键问题[/bold red]")
            for issue in report.critical_issues:
                console.print(f"  - {issue}")
        
        if report.recommendations:
            console.print(f"\n[bold cyan]💡 改进建议[/bold cyan]")
            for rec in report.recommendations:
                console.print(f"  - {rec}")
        
        if report.improvement_priorities:
            console.print(f"\n[bold yellow]🎯 优先改进项[/bold yellow]")
            for item in report.improvement_priorities:
                console.print(f"  {item['priority']}. {item['action']} (当前: {item['current_score']:.1f}, 目标: {item['target_score']})")


async def run_generation_workflow(
    project_path: str,
    project_type: str,
    coverage_target: float,
    max_iterations: int,
    llm_provider: str,
    dry_run: bool,
    incremental: bool = False,
    base_ref: Optional[str] = None,
    head_ref: Optional[str] = None,
    html_report: bool = False,
) -> None:
    """运行生成工作流."""
    # 创建初始状态
    initial_state: AgentState = {
        "project_path": project_path,
        "project_type": project_type if project_type != "auto" else "",
        "build_tool": "",
        "target_files": [],
        "coverage_target": coverage_target,
        "max_iterations": max_iterations,
        "incremental": incremental,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "iteration_count": 0,
        "status": "started",
        "message": "开始执行...",
        "analyzed_files": [],
        "code_changes": [],
        "change_summaries": [],
        "generated_tests": [],
        "coverage_report": None,
        "current_coverage": 0.0,
        "coverage_gaps": [],
        "improvement_plan": None,
        "output_path": None,
        "summary": None,
        "html_report_path": None,
    }

    # 创建图
    graph = create_test_generation_graph()

    # 运行
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]正在生成测试...", total=None)

        result = None
        async for event in graph.astream(
            initial_state,
            config={"configurable": {"llm_provider": llm_provider}},
        ):
            for node_name, node_data in event.items():
                if isinstance(node_data, dict):
                    status = node_data.get("status", "")
                    message = node_data.get("message", "")
                    progress.update(task, description=f"[cyan][{node_name}] {message}")
                    result = node_data

        progress.update(task, description="[green]✓ 完成!")

    # 显示结果
    if result:
        display_results(result)


def display_results(result: dict) -> None:
    """显示结果."""
    console.print()
    console.print(Panel.fit(
        "[bold green]📈 执行结果[/bold green]",
        border_style="green"
    ))

    status = result.get("status", "")
    if status == "completed":
        console.print("[bold green]✅ 测试生成完成![/bold green]")
    elif status == "target_reached":
        console.print("[bold green]🎯 覆盖率目标已达成![/bold green]")
    elif status == "max_iterations_reached":
        console.print("[bold yellow]⏹️ 达到最大迭代次数[/bold yellow]")
    else:
        console.print(f"状态: {status}")

    # 覆盖率报告
    coverage_report = result.get("coverage_report")
    if coverage_report:
        console.print()
        console.print("[bold cyan]📊 覆盖率统计[/bold cyan]")

        table = Table(box=box.ROUNDED)
        table.add_column("指标", style="cyan")
        table.add_column("覆盖率", style="green")
        table.add_column("详情", style="yellow")

        table.add_row(
            "总体覆盖率",
            f"{coverage_report.overall_coverage:.2f}%",
            ""
        )
        table.add_row(
            "行覆盖率",
            f"{coverage_report.line_coverage:.2f}%",
            f"{coverage_report.covered_lines}/{coverage_report.total_lines}"
        )
        table.add_row(
            "分支覆盖率",
            f"{coverage_report.branch_coverage:.2f}%",
            f"{coverage_report.covered_branches}/{coverage_report.total_branches}"
        )
        table.add_row(
            "方法覆盖率",
            f"{coverage_report.method_coverage:.2f}%",
            ""
        )
        table.add_row(
            "类覆盖率",
            f"{coverage_report.class_coverage:.2f}%",
            ""
        )

        console.print(table)

    # 生成的测试文件
    generated_tests = result.get("generated_tests", [])
    if generated_tests:
        console.print()
        console.print(f"[bold cyan]🧪 生成的测试文件 ({len(generated_tests)}个)[/bold cyan]")

        for test_file in generated_tests:
            console.print(f"  [green]✓[/green] {test_file.test_file_path}")

    # 摘要
    summary = result.get("summary")
    if summary:
        console.print()
        console.print("[bold cyan]📝 摘要[/bold cyan]")
        console.print(summary)


if __name__ == "__main__":
    app()
