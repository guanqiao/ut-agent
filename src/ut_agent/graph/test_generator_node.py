"""测试生成节点 - 重构版.

将 generate_tests_node 拆分为多个小函数，提高可维护性。
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from ut_agent.graph.state import AgentState, GeneratedTestFile
from ut_agent.models import get_llm
from ut_agent.utils import get_logger
from ut_agent.utils.event_bus import event_bus, emit_progress, emit_metric
from ut_agent.utils.events import EventType
from ut_agent.tools.test_mapper import TestFileMapper

logger = get_logger("test_generator_node")


class TestGenerationContext:
    """测试生成上下文.
    
    封装测试生成所需的所有信息和状态。
    """
    
    def __init__(
        self,
        state: AgentState,
        config: Dict[str, Any],
        max_workers: int,
    ):
        """初始化上下文.
        
        Args:
            state: Agent 状态
            config: 配置
            max_workers: 最大工作线程数
        """
        self.project_type = state["project_type"]
        self.analyzed_files = state["analyzed_files"]
        self.project_path = state["project_path"]
        self.incremental = state.get("incremental", False)
        self.change_summaries = state.get("change_summaries", [])
        self.llm_provider = config.get("configurable", {}).get("llm_provider", "openai")
        self.max_workers = max_workers
        
        self.llm = get_llm(self.llm_provider)
        self.change_dict = {s.file_path: s for s in self.change_summaries}
        
        # 统计信息
        self.completed_count = 0
        self.success_count = 0
        self.error_count = 0
        self.lock = asyncio.Lock()
        
        # 阶段计时
        self.stage_start = datetime.now()


class TestGenerationStrategy:
    """测试生成策略.
    
    定义不同项目类型的测试生成逻辑。
    """
    
    @staticmethod
    def get_generator(project_type: str) -> Callable:
        """获取测试生成器.
        
        Args:
            project_type: 项目类型
            
        Returns:
            Callable: 测试生成函数
        """
        from ut_agent.tools.test_generator import (
            generate_java_test,
            generate_frontend_test,
        )
        
        if project_type == "java":
            return generate_java_test
        elif project_type in ["vue", "react", "typescript"]:
            return generate_frontend_test
        else:
            return None
    
    @staticmethod
    def get_incremental_generator(project_type: str) -> Callable:
        """获取增量测试生成器.
        
        Args:
            project_type: 项目类型
            
        Returns:
            Callable: 增量测试生成函数
        """
        from ut_agent.tools.test_generator import (
            generate_incremental_java_test,
            generate_incremental_frontend_test,
        )
        
        if project_type == "java":
            return generate_incremental_java_test
        elif project_type in ["vue", "react", "typescript"]:
            return generate_incremental_frontend_test
        else:
            return None


class TestGenerationExecutor:
    """测试生成执行器.
    
    负责执行单个文件的测试生成。
    """
    
    def __init__(self, context: TestGenerationContext):
        """初始化执行器.
        
        Args:
            context: 测试生成上下文
        """
        self.context = context
        self.total_files = len(context.analyzed_files)
    
    async def execute(self, file_analysis: Dict[str, Any]) -> Optional[GeneratedTestFile]:
        """执行测试生成.
        
        Args:
            file_analysis: 文件分析结果
            
        Returns:
            Optional[GeneratedTestFile]: 生成的测试文件
        """
        file_path = file_analysis.get("file_path", "unknown")
        
        try:
            loop = asyncio.get_event_loop()
            
            # 根据模式选择生成策略
            if self.context.incremental and file_path in self.context.change_dict:
                result = await self._generate_incremental(loop, file_analysis)
            else:
                result = await self._generate_full(loop, file_analysis)
            
            # 更新统计信息
            await self._update_progress(file_path, result is not None)
            
            return result
            
        except Exception as e:
            logger.error(f"生成测试失败: {e}")
            await self._update_progress(file_path, False)
            return None
    
    async def _generate_full(
        self,
        loop: asyncio.AbstractEventLoop,
        file_analysis: Dict[str, Any],
    ) -> Optional[GeneratedTestFile]:
        """生成完整测试.
        
        Args:
            loop: 事件循环
            file_analysis: 文件分析结果
            
        Returns:
            Optional[GeneratedTestFile]: 生成的测试文件
        """
        generator = TestGenerationStrategy.get_generator(self.context.project_type)
        if generator is None:
            return None
        
        if self.context.project_type == "java":
            return await loop.run_in_executor(
                None,
                generator,
                file_analysis,
                self.context.llm,
            )
        else:
            return await loop.run_in_executor(
                None,
                generator,
                file_analysis,
                self.context.project_type,
                self.context.llm,
            )
    
    async def _generate_incremental(
        self,
        loop: asyncio.AbstractEventLoop,
        file_analysis: Dict[str, Any],
    ) -> Optional[GeneratedTestFile]:
        """生成增量测试.
        
        Args:
            loop: 事件循环
            file_analysis: 文件分析结果
            
        Returns:
            Optional[GeneratedTestFile]: 生成的测试文件
        """
        file_path = file_analysis.get("file_path", "unknown")
        change_summary = self.context.change_dict[file_path]
        
        # 提取变更的方法
        added_methods = [m.name for m in change_summary.added_methods]
        modified_methods = [m.name for m, _ in change_summary.modified_methods]
        
        # 查找现有测试文件
        test_mapper = TestFileMapper(self.context.project_path, self.context.project_type)
        existing_test_path = test_mapper.find_test_file(file_path)
        existing_test_full = str(Path(self.context.project_path) / existing_test_path) if existing_test_path else None
        
        # 获取增量生成器
        generator = TestGenerationStrategy.get_incremental_generator(self.context.project_type)
        if generator is None:
            return None
        
        # 执行增量生成
        if self.context.project_type == "java":
            return await loop.run_in_executor(
                None,
                generator,
                file_analysis,
                self.context.llm,
                existing_test_full,
                added_methods,
                modified_methods,
            )
        else:
            return await loop.run_in_executor(
                None,
                generator,
                file_analysis,
                self.context.project_type,
                self.context.llm,
                existing_test_full,
                added_methods,
                modified_methods,
            )
    
    async def _update_progress(self, file_path: str, success: bool) -> None:
        """更新进度.
        
        Args:
            file_path: 文件路径
            success: 是否成功
        """
        async with self.context.lock:
            self.context.completed_count += 1
            if success:
                self.context.success_count += 1
            
            emit_progress(
                stage="generate_tests",
                current=self.context.completed_count,
                total=self.total_files,
                message=f"生成测试 [{self.context.completed_count}/{self.total_files}]",
                current_file=file_path,
                source="generate_tests_node",
            )


class TestGenerationReporter:
    """测试生成报告器.
    
    负责生成测试生成结果的报告。
    """
    
    def __init__(self, context: TestGenerationContext):
        """初始化报告器.
        
        Args:
            context: 测试生成上下文
        """
        self.context = context
    
    def emit_start_event(self) -> None:
        """发送开始事件."""
        event_bus.emit_simple(EventType.TEST_GENERATION_STARTED, {
            "total_files": len(self.context.analyzed_files),
            "llm_provider": self.context.llm_provider,
            "incremental": self.context.incremental,
        }, source="generate_tests_node")
    
    def emit_complete_event(self, generated_tests: List[GeneratedTestFile]) -> None:
        """发送完成事件.
        
        Args:
            generated_tests: 生成的测试文件列表
        """
        stage_duration = (datetime.now() - self.context.stage_start).total_seconds() * 1000
        
        event_bus.emit_simple(EventType.TEST_GENERATION_COMPLETED, {
            "generated_count": len(generated_tests),
            "total_files": len(self.context.analyzed_files),
            "success_count": self.context.success_count,
            "error_count": self.context.error_count,
            "duration_ms": stage_duration,
            "incremental": self.context.incremental,
        }, source="generate_tests_node")
        
        # 发送指标
        emit_metric(
            metric_name="test_generation_duration_ms",
            value=stage_duration,
            unit="ms",
            tags={
                "project_type": self.context.project_type,
                "llm_provider": self.context.llm_provider,
                "incremental": str(self.context.incremental),
            },
            source="generate_tests_node",
        )
        
        emit_metric(
            metric_name="tests_generated_count",
            value=len(generated_tests),
            unit="files",
            tags={
                "project_type": self.context.project_type,
                "incremental": str(self.context.incremental),
            },
            source="generate_tests_node",
        )
    
    def build_result(
        self,
        generated_tests: List[GeneratedTestFile],
    ) -> Dict[str, Any]:
        """构建结果.
        
        Args:
            generated_tests: 生成的测试文件列表
            
        Returns:
            Dict[str, Any]: 结果字典
        """
        stage_duration = (datetime.now() - self.context.stage_start).total_seconds() * 1000
        total_files = len(self.context.analyzed_files)
        mode_str = "增量" if self.context.incremental else "全量"
        
        progress_info = {
            "stage": "generate_tests",
            "current": total_files,
            "total": total_files,
            "percentage": 100.0,
            "message": f"{mode_str}模式成功生成 {len(generated_tests)} 个测试文件",
        }
        
        return {
            "generated_tests": generated_tests,
            "status": "tests_generated",
            "message": f"{mode_str}模式成功生成 {len(generated_tests)} 个测试文件",
            "progress": progress_info,
            "stage_metrics": {
                "generate_tests": {
                    "duration_ms": stage_duration,
                    "files_processed": len(generated_tests),
                    "files_total": total_files,
                    "success_count": self.context.success_count,
                    "error_count": self.context.error_count,
                    "incremental": self.context.incremental,
                }
            },
            "event_log": [{
                "event_type": "test_generation_completed",
                "timestamp": datetime.now().isoformat(),
                "data": {"count": len(generated_tests), "incremental": self.context.incremental},
            }],
        }


async def generate_tests_node_refactored(
    state: AgentState,
    config: Dict[str, Any],
    max_workers: int = 4,
) -> Dict[str, Any]:
    """生成单元测试 - 重构版.
    
    Args:
        state: Agent 状态
        config: 配置
        max_workers: 最大工作线程数
        
    Returns:
        Dict[str, Any]: 结果字典
    """
    # 创建上下文
    context = TestGenerationContext(state, config, max_workers)
    
    # 创建报告器并发送开始事件
    reporter = TestGenerationReporter(context)
    reporter.emit_start_event()
    
    # 创建执行器
    executor = TestGenerationExecutor(context)
    
    # 并行执行所有测试生成任务
    tasks = [
        executor.execute(file_analysis)
        for file_analysis in context.analyzed_files
    ]
    results = await asyncio.gather(*tasks)
    
    # 过滤成功的结果
    generated_tests = [r for r in results if r is not None]
    
    # 发送完成事件
    reporter.emit_complete_event(generated_tests)
    
    # 返回结果
    return reporter.build_result(generated_tests)


# 保持向后兼容
async def generate_tests_node(state: AgentState, config: Dict[str, Any]) -> Dict[str, Any]:
    """生成单元测试（原始函数，调用重构版）."""
    max_workers = config.get("configurable", {}).get("max_workers", 4)
    return await generate_tests_node_refactored(state, config, max_workers)
