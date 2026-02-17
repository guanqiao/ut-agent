"""Streamlit Web UI."""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

import streamlit as st

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from ut_agent.graph import create_test_generation_graph, AgentState
from ut_agent.models import list_available_providers
from ut_agent.config import settings
from ut_agent.utils.events import Event, EventType
from ut_agent.utils.event_bus import event_bus


st.set_page_config(
    page_title="UT-Agent: AI单元测试生成器",
    page_icon="🧪",
    layout="wide",
)

st.markdown("""
<style>
.main-header {
    font-size: 2.5rem;
    font-weight: bold;
    color: #1f77b4;
}
.sub-header {
    font-size: 1.2rem;
    color: #666;
}
.status-box {
    padding: 1rem;
    border-radius: 0.5rem;
    margin: 1rem 0;
}
.success-box {
    background-color: #d4edda;
    border: 1px solid #c3e6cb;
    color: #155724;
}
.warning-box {
    background-color: #fff3cd;
    border: 1px solid #ffeeba;
    color: #856404;
}
.error-box {
    background-color: #f8d7da;
    border: 1px solid #f5c6cb;
    color: #721c24;
}
.stage-card {
    background-color: #f8f9fa;
    border-radius: 0.5rem;
    padding: 1rem;
    margin: 0.5rem 0;
}
.stage-running {
    border-left: 4px solid #ffc107;
}
.stage-completed {
    border-left: 4px solid #28a745;
}
.stage-pending {
    border-left: 4px solid #6c757d;
}
</style>
""", unsafe_allow_html=True)


def init_session_state() -> None:
    """初始化会话状态."""
    if "workflow_started" not in st.session_state:
        st.session_state.workflow_started = False
    if "workflow_result" not in st.session_state:
        st.session_state.workflow_result = None
    if "logs" not in st.session_state:
        st.session_state.logs = []
    if "stage_progress" not in st.session_state:
        st.session_state.stage_progress = {
            "detect_project": {"status": "pending", "current": 0, "total": 0, "message": ""},
            "analyze_code": {"status": "pending", "current": 0, "total": 0, "message": ""},
            "generate_tests": {"status": "pending", "current": 0, "total": 0, "message": ""},
            "save_tests": {"status": "pending", "current": 0, "total": 0, "message": ""},
            "execute_tests": {"status": "pending", "current": 0, "total": 0, "message": ""},
            "analyze_coverage": {"status": "pending", "current": 0, "total": 0, "message": ""},
        }
    if "current_stage" not in st.session_state:
        st.session_state.current_stage = ""
    if "start_time" not in st.session_state:
        st.session_state.start_time = None
    if "metrics" not in st.session_state:
        st.session_state.metrics = {}


def render_header() -> None:
    """渲染页面头部."""
    st.markdown('<p class="main-header">🧪 UT-Agent</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-header">AI驱动的单元测试生成器 - 支持 Java/Vue/React/TypeScript</p>',
        unsafe_allow_html=True
    )
    st.markdown("---")


def render_sidebar() -> dict:
    """渲染侧边栏."""
    with st.sidebar:
        st.header("⚙️ 配置")

        # LLM 提供商选择
        available_providers = list_available_providers()
        provider = st.selectbox(
            "选择 LLM 提供商",
            options=available_providers,
            index=0,
        )

        # 覆盖率目标
        coverage_target = st.slider(
            "覆盖率目标 (%)",
            min_value=0,
            max_value=100,
            value=int(settings.default_coverage_target),
        )

        # 最大迭代次数
        max_iterations = st.number_input(
            "最大迭代次数",
            min_value=1,
            max_value=20,
            value=5,
        )

        st.markdown("---")
        st.header("📊 系统状态")

        # 检查环境
        col1, col2 = st.columns(2)
        with col1:
            if provider == "ollama":
                st.info("🦙 Ollama 模式")
            else:
                st.success(f"🔌 {provider.upper()}")
        with col2:
            st.success("✅ 就绪")

        return {
            "provider": provider,
            "coverage_target": coverage_target,
            "max_iterations": max_iterations,
        }


def render_main_content(config: dict) -> None:
    """渲染主内容区."""
    st.header("📁 项目配置")

    # 项目路径
    project_path = st.text_input(
        "项目路径",
        placeholder="输入项目绝对路径，例如: /path/to/your/project",
        help="支持 Java Maven/Gradle 项目和前端 Vue/React/TypeScript 项目",
    )

    # 项目类型选择 (可选)
    project_type_override = st.selectbox(
        "项目类型 (可选，自动检测)",
        options=["auto", "java", "vue", "react", "typescript"],
        index=0,
        help="选择 auto 让系统自动检测项目类型",
    )

    st.markdown("---")

    # 开始按钮
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        start_button = st.button(
            "🚀 开始生成测试",
            type="primary",
            disabled=st.session_state.workflow_started,
            use_container_width=True,
        )
    with col2:
        clear_button = st.button(
            "🔄 重置",
            disabled=not st.session_state.workflow_started,
            use_container_width=True,
        )

    if clear_button:
        st.session_state.workflow_started = False
        st.session_state.workflow_result = None
        st.session_state.logs = []
        st.rerun()

    if start_button:
        if not project_path:
            st.error("请输入项目路径")
            return

        if not Path(project_path).exists():
            st.error("项目路径不存在")
            return

        st.session_state.workflow_started = True
        st.session_state.logs = []

        # 运行工作流
        run_workflow(project_path, project_type_override, config)

    # 显示日志
    if st.session_state.logs:
        st.markdown("---")
        st.header("📋 执行日志")
        for log in st.session_state.logs:
            st.text(log)

    # 显示结果
    if st.session_state.workflow_result:
        render_results(st.session_state.workflow_result)


def run_workflow(project_path: str, project_type: str, config: dict) -> None:
    """运行工作流."""
    try:
        event_bus.reset()
        
        st.session_state.stage_progress = {
            "detect_project": {"status": "pending", "current": 0, "total": 0, "message": ""},
            "analyze_code": {"status": "pending", "current": 0, "total": 0, "message": ""},
            "generate_tests": {"status": "pending", "current": 0, "total": 0, "message": ""},
            "save_tests": {"status": "pending", "current": 0, "total": 0, "message": ""},
            "execute_tests": {"status": "pending", "current": 0, "total": 0, "message": ""},
            "analyze_coverage": {"status": "pending", "current": 0, "total": 0, "message": ""},
        }
        st.session_state.current_stage = ""
        st.session_state.start_time = datetime.now()
        st.session_state.metrics = {}
        
        initial_state: AgentState = {
            "project_path": project_path,
            "project_type": project_type if project_type != "auto" else "",
            "build_tool": "",
            "target_files": [],
            "coverage_target": float(config["coverage_target"]),
            "max_iterations": int(config["max_iterations"]),
            "iteration_count": 0,
            "status": "started",
            "message": "开始执行...",
            "analyzed_files": [],
            "generated_tests": [],
            "coverage_report": None,
            "current_coverage": 0.0,
            "coverage_gaps": [],
            "improvement_plan": None,
            "output_path": None,
            "summary": None,
            "progress": {},
            "stage_metrics": {},
            "event_log": [],
            "code_changes": [],
            "change_summaries": [],
            "incremental": False,
            "base_ref": None,
            "head_ref": None,
            "html_report_path": None,
        }

        graph = create_test_generation_graph()

        with st.spinner("正在生成测试..."):
            result = asyncio.run(run_graph(graph, initial_state, config))

        st.session_state.workflow_result = result
        st.success("✅ 执行完成!")

    except Exception as e:
        st.error(f"执行出错: {e}")
        st.session_state.workflow_started = False


def handle_event(event: Event) -> None:
    """处理事件."""
    event_type = event.event_type
    data = event.data
    
    if event_type == EventType.FILE_ANALYSIS_STARTED:
        st.session_state.current_stage = "analyze_code"
        st.session_state.stage_progress["analyze_code"]["status"] = "running"
        st.session_state.stage_progress["analyze_code"]["total"] = data.get("total_files", 0)
    
    elif event_type == EventType.FILE_ANALYSIS_COMPLETED:
        st.session_state.stage_progress["analyze_code"]["status"] = "completed"
    
    elif event_type == EventType.TEST_GENERATION_STARTED:
        st.session_state.current_stage = "generate_tests"
        st.session_state.stage_progress["generate_tests"]["status"] = "running"
        st.session_state.stage_progress["generate_tests"]["total"] = data.get("total_files", 0)
    
    elif event_type == EventType.TEST_GENERATION_COMPLETED:
        st.session_state.stage_progress["generate_tests"]["status"] = "completed"
    
    elif event_type == EventType.NODE_PROGRESS:
        stage = data.get("stage", "")
        if stage in st.session_state.stage_progress:
            st.session_state.stage_progress[stage]["current"] = data.get("current", 0)
            st.session_state.stage_progress[stage]["total"] = data.get("total", 0)
            st.session_state.stage_progress[stage]["message"] = data.get("message", "")
    
    elif event_type == EventType.PERFORMANCE_METRIC:
        metric_name = data.get("metric_name", "")
        value = data.get("value", 0)
        st.session_state.metrics[metric_name] = value
    
    elif event_type == EventType.ERROR_OCCURRED:
        error_msg = data.get("error_message", "Unknown error")
        st.session_state.logs.append(f"❌ ERROR: {error_msg}")


async def run_graph(graph, initial_state: AgentState, config: dict) -> dict:
    """异步运行图."""
    event_bus.subscribe_all(handle_event)
    
    result = None
    progress_placeholder = st.empty()
    
    async for event in graph.astream(
        initial_state,
        config={"configurable": {"llm_provider": config["provider"]}},
    ):
        for node_name, node_data in event.items():
            if isinstance(node_data, dict):
                status = node_data.get("status", "")
                message = node_data.get("message", "")
                log_entry = f"[{node_name}] {status}: {message}"
                st.session_state.logs.append(log_entry)
                result = node_data
                
                if node_name in st.session_state.stage_progress:
                    st.session_state.stage_progress[node_name]["status"] = "completed"
                
                with progress_placeholder.container():
                    render_progress_panel()
    
    return result


def render_progress_panel() -> None:
    """渲染进度面板."""
    st.markdown("### 📊 执行进度")
    
    if st.session_state.start_time:
        elapsed = (datetime.now() - st.session_state.start_time).total_seconds()
        st.markdown(f"**已用时间:** {elapsed:.1f}秒")
    
    stage_names = {
        "detect_project": "🔍 项目检测",
        "analyze_code": "📊 代码分析",
        "generate_tests": "🧪 测试生成",
        "save_tests": "💾 保存测试",
        "execute_tests": "⚡ 执行测试",
        "analyze_coverage": "📈 覆盖率分析",
    }
    
    cols = st.columns(3)
    for idx, (stage_name, stage_data) in enumerate(st.session_state.stage_progress.items()):
        col = cols[idx % 3]
        with col:
            status = stage_data["status"]
            current = stage_data["current"]
            total = stage_data["total"]
            message = stage_data["message"]
            
            if status == "completed":
                st.success(f"{stage_names[stage_name]} ✅")
            elif status == "running":
                if total > 0:
                    progress = current / total
                    st.progress(progress, text=f"{stage_names[stage_name]} [{current}/{total}]")
                else:
                    st.info(f"{stage_names[stage_name]} 🔄")
            else:
                st.markdown(f"⏳ {stage_names[stage_name]}")


def render_results(result: dict) -> None:
    """渲染结果."""
    st.markdown("---")
    st.header("📈 执行结果")

    status = result.get("status", "")
    if status == "completed":
        st.success("✅ 测试生成完成!")
    elif status == "target_reached":
        st.success("🎯 覆盖率目标已达成!")
    elif status == "max_iterations_reached":
        st.warning("⏹️ 达到最大迭代次数")
    else:
        st.info(f"状态: {status}")

    coverage_report = result.get("coverage_report")
    if coverage_report:
        st.subheader("📊 覆盖率统计")

        cols = st.columns(4)
        with cols[0]:
            st.metric(
                "总体覆盖率",
                f"{coverage_report.overall_coverage:.1f}%",
            )
        with cols[1]:
            st.metric(
                "行覆盖率",
                f"{coverage_report.line_coverage:.1f}%",
            )
        with cols[2]:
            st.metric(
                "分支覆盖率",
                f"{coverage_report.branch_coverage:.1f}%",
            )
        with cols[3]:
            st.metric(
                "方法覆盖率",
                f"{coverage_report.method_coverage:.1f}%",
            )
    
    if st.session_state.metrics:
        st.subheader("⏱️ 性能指标")
        
        metric_names = {
            "analyze_code_duration_ms": "代码分析耗时",
            "test_generation_duration_ms": "测试生成耗时",
            "save_tests_duration_ms": "保存测试耗时",
            "tests_generated_count": "生成测试数量",
        }
        
        cols = st.columns(4)
        for idx, (metric_name, value) in enumerate(st.session_state.metrics.items()):
            col = cols[idx % 4]
            with col:
                display_name = metric_names.get(metric_name, metric_name)
                if "duration" in metric_name:
                    display_value = f"{value:.0f}ms"
                else:
                    display_value = str(value)
                st.metric(display_name, display_value)
    
    stage_metrics = result.get("stage_metrics", {})
    if stage_metrics:
        st.subheader("📋 阶段详情")
        
        for stage_name, metrics in stage_metrics.items():
            if metrics:
                with st.expander(f"📌 {stage_name}"):
                    for key, value in metrics.items():
                        if isinstance(value, float):
                            st.markdown(f"- **{key}:** {value:.2f}")
                        else:
                            st.markdown(f"- **{key}:** {value}")

    summary = result.get("summary")
    if summary:
        st.subheader("📝 摘要")
        st.text(summary)

    generated_tests = result.get("generated_tests", [])
    if generated_tests:
        st.subheader(f"🧪 生成的测试文件 ({len(generated_tests)}个)")
        for test_file in generated_tests:
            with st.expander(f"📄 {Path(test_file.test_file_path).name}"):
                st.code(test_file.test_code, language=test_file.language)


def main() -> None:
    """主函数."""
    init_session_state()
    render_header()
    config = render_sidebar()
    render_main_content(config)


if __name__ == "__main__":
    main()
