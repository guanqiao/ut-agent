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
