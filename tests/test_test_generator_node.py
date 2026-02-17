"""测试生成节点重构版测试."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from ut_agent.graph.test_generator_node import (
    TestGenerationContext,
    TestGenerationStrategy,
    TestGenerationExecutor,
    TestGenerationReporter,
    generate_tests_node_refactored,
)
from ut_agent.graph.state import GeneratedTestFile


class TestTestGenerationContext:
    """测试生成上下文测试."""

    def test_context_creation(self):
        """测试上下文创建."""
        state = {
            "project_type": "java",
            "analyzed_files": [{"file_path": "Test.java"}],
            "project_path": "/test",
            "incremental": False,
            "change_summaries": [],
        }
        config = {"configurable": {"llm_provider": "openai"}}
        
        with patch("ut_agent.graph.test_generator_node.get_llm") as mock_get_llm:
            mock_get_llm.return_value = Mock()
            context = TestGenerationContext(state, config, max_workers=4)
        
        assert context.project_type == "java"
        assert len(context.analyzed_files) == 1
        assert context.max_workers == 4
        assert context.completed_count == 0

    def test_context_with_incremental(self):
        """测试增量模式上下文."""
        change_summary = Mock()
        change_summary.file_path = "Test.java"
        
        state = {
            "project_type": "java",
            "analyzed_files": [{"file_path": "Test.java"}],
            "project_path": "/test",
            "incremental": True,
            "change_summaries": [change_summary],
        }
        config = {"configurable": {"llm_provider": "openai"}}
        
        with patch("ut_agent.graph.test_generator_node.get_llm") as mock_get_llm:
            mock_get_llm.return_value = Mock()
            context = TestGenerationContext(state, config, max_workers=4)
        
        assert context.incremental is True
        assert "Test.java" in context.change_dict


class TestTestGenerationStrategy:
    """测试生成策略测试."""

    def test_get_generator_java(self):
        """测试获取 Java 生成器."""
        generator = TestGenerationStrategy.get_generator("java")
        assert generator is not None

    def test_get_generator_frontend(self):
        """测试获取前端生成器."""
        generator = TestGenerationStrategy.get_generator("vue")
        assert generator is not None
        
        generator = TestGenerationStrategy.get_generator("react")
        assert generator is not None
        
        generator = TestGenerationStrategy.get_generator("typescript")
        assert generator is not None

    def test_get_generator_unknown(self):
        """测试未知类型返回 None."""
        generator = TestGenerationStrategy.get_generator("unknown")
        assert generator is None

    def test_get_incremental_generator_java(self):
        """测试获取 Java 增量生成器."""
        generator = TestGenerationStrategy.get_incremental_generator("java")
        assert generator is not None

    def test_get_incremental_generator_frontend(self):
        """测试获取前端增量生成器."""
        generator = TestGenerationStrategy.get_incremental_generator("vue")
        assert generator is not None

    def test_get_incremental_generator_unknown(self):
        """测试未知类型返回 None."""
        generator = TestGenerationStrategy.get_incremental_generator("unknown")
        assert generator is None


class TestTestGenerationExecutor:
    """测试生成执行器测试."""

    @pytest.fixture
    def mock_context(self):
        """创建模拟上下文."""
        context = Mock()
        context.project_type = "java"
        context.analyzed_files = [{"file_path": "Test.java"}]
        context.incremental = False
        context.change_dict = {}
        context.llm = Mock()
        context.project_path = "/test"
        # 创建异步锁
        import asyncio
        context.lock = asyncio.Lock()
        context.completed_count = 0
        context.success_count = 0
        return context

    @pytest.mark.asyncio
    async def test_execute_full_generation(self, mock_context):
        """测试完整生成."""
        executor = TestGenerationExecutor(mock_context)
        
        # 直接测试内部方法
        with patch.object(executor, '_generate_full') as mock_gen:
            mock_test_file = Mock(spec=GeneratedTestFile)
            mock_gen.return_value = mock_test_file
            
            result = await executor.execute({"file_path": "Test.java"})
        
        assert result == mock_test_file
        mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_incremental_generation(self, mock_context):
        """测试增量生成."""
        mock_context.incremental = True
        
        change_summary = Mock()
        change_summary.added_methods = [Mock(name="method1")]
        change_summary.modified_methods = [(Mock(name="method2"), None)]
        mock_context.change_dict = {"Test.java": change_summary}
        
        executor = TestGenerationExecutor(mock_context)
        
        # 直接测试内部方法
        with patch.object(executor, '_generate_incremental') as mock_gen:
            mock_test_file = Mock(spec=GeneratedTestFile)
            mock_gen.return_value = mock_test_file
            
            result = await executor.execute({"file_path": "Test.java"})
        
        assert result == mock_test_file
        mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, mock_context):
        """测试错误处理."""
        executor = TestGenerationExecutor(mock_context)
        
        with patch.object(TestGenerationStrategy, 'get_generator') as mock_get_gen:
            mock_get_gen.return_value = None
            
            result = await executor.execute({"file_path": "Test.java"})
        
        assert result is None


class TestTestGenerationReporter:
    """测试生成报告器测试."""

    @pytest.fixture
    def mock_context(self):
        """创建模拟上下文."""
        context = Mock()
        context.project_type = "java"
        context.analyzed_files = [{"file_path": "Test.java"}]
        context.incremental = False
        context.llm_provider = "openai"
        context.stage_start = datetime.now()
        context.success_count = 5
        context.error_count = 1
        return context

    def test_emit_start_event(self, mock_context):
        """测试发送开始事件."""
        reporter = TestGenerationReporter(mock_context)
        
        with patch("ut_agent.graph.test_generator_node.event_bus") as mock_bus:
            reporter.emit_start_event()
            
            mock_bus.emit_simple.assert_called_once()
            args = mock_bus.emit_simple.call_args[0]
            assert args[0].value == "test_generation_started"

    def test_emit_complete_event(self, mock_context):
        """测试发送完成事件."""
        reporter = TestGenerationReporter(mock_context)
        
        mock_tests = [Mock(spec=GeneratedTestFile) for _ in range(5)]
        
        with patch("ut_agent.graph.test_generator_node.event_bus") as mock_bus:
            with patch("ut_agent.graph.test_generator_node.emit_metric") as mock_metric:
                reporter.emit_complete_event(mock_tests)
                
                mock_bus.emit_simple.assert_called_once()
                assert mock_metric.call_count == 2

    def test_build_result(self, mock_context):
        """测试构建结果."""
        reporter = TestGenerationReporter(mock_context)
        
        mock_tests = [Mock(spec=GeneratedTestFile) for _ in range(5)]
        
        result = reporter.build_result(mock_tests)
        
        assert result["status"] == "tests_generated"
        assert len(result["generated_tests"]) == 5
        assert "stage_metrics" in result
        assert "event_log" in result

    def test_build_result_incremental(self, mock_context):
        """测试增量模式结果."""
        mock_context.incremental = True
        reporter = TestGenerationReporter(mock_context)
        
        mock_tests = [Mock(spec=GeneratedTestFile) for _ in range(3)]
        
        result = reporter.build_result(mock_tests)
        
        assert "增量" in result["message"]


class TestGenerateTestsNodeRefactored:
    """重构版测试生成节点测试."""

    @pytest.mark.asyncio
    async def test_full_generation_flow(self):
        """测试完整生成流程."""
        state = {
            "project_type": "java",
            "analyzed_files": [
                {"file_path": "Test1.java"},
                {"file_path": "Test2.java"},
            ],
            "project_path": "/test",
            "incremental": False,
            "change_summaries": [],
        }
        config = {"configurable": {"llm_provider": "openai"}}
        
        mock_test_file = Mock(spec=GeneratedTestFile)
        
        with patch("ut_agent.graph.test_generator_node.get_llm") as mock_get_llm:
            mock_get_llm.return_value = Mock()
            
            with patch.object(TestGenerationExecutor, 'execute') as mock_execute:
                mock_execute.return_value = mock_test_file
                
                with patch.object(TestGenerationReporter, 'emit_start_event'):
                    with patch.object(TestGenerationReporter, 'emit_complete_event'):
                        result = await generate_tests_node_refactored(state, config)
        
        assert result["status"] == "tests_generated"
        assert len(result["generated_tests"]) == 2

    @pytest.mark.asyncio
    async def test_incremental_generation_flow(self):
        """测试增量生成流程."""
        change_summary = Mock()
        change_summary.file_path = "Test1.java"
        change_summary.added_methods = [Mock(name="newMethod")]
        change_summary.modified_methods = []
        
        state = {
            "project_type": "java",
            "analyzed_files": [{"file_path": "Test1.java"}],
            "project_path": "/test",
            "incremental": True,
            "change_summaries": [change_summary],
        }
        config = {"configurable": {"llm_provider": "openai"}}
        
        mock_test_file = Mock(spec=GeneratedTestFile)
        
        with patch("ut_agent.graph.test_generator_node.get_llm") as mock_get_llm:
            mock_get_llm.return_value = Mock()
            
            with patch.object(TestGenerationExecutor, 'execute') as mock_execute:
                mock_execute.return_value = mock_test_file
                
                with patch.object(TestGenerationReporter, 'emit_start_event'):
                    with patch.object(TestGenerationReporter, 'emit_complete_event'):
                        result = await generate_tests_node_refactored(state, config)
        
        assert result["status"] == "tests_generated"
        assert "incremental" in result["stage_metrics"]["generate_tests"]

    @pytest.mark.asyncio
    async def test_partial_failure_handling(self):
        """测试部分失败处理."""
        state = {
            "project_type": "java",
            "analyzed_files": [
                {"file_path": "Test1.java"},
                {"file_path": "Test2.java"},
            ],
            "project_path": "/test",
            "incremental": False,
            "change_summaries": [],
        }
        config = {"configurable": {"llm_provider": "openai"}}
        
        mock_test_file = Mock(spec=GeneratedTestFile)
        
        with patch("ut_agent.graph.test_generator_node.get_llm") as mock_get_llm:
            mock_get_llm.return_value = Mock()
            
            with patch.object(TestGenerationExecutor, 'execute') as mock_execute:
                # 第一个成功，第二个失败
                mock_execute.side_effect = [mock_test_file, None]
                
                with patch.object(TestGenerationReporter, 'emit_start_event'):
                    with patch.object(TestGenerationReporter, 'emit_complete_event'):
                        result = await generate_tests_node_refactored(state, config)
        
        assert result["status"] == "tests_generated"
        assert len(result["generated_tests"]) == 1


class TestRefactoringBenefits:
    """重构收益测试."""

    def test_single_responsibility_context(self):
        """测试上下文类单一职责."""
        # 上下文只负责存储状态
        state = {
            "project_type": "java",
            "analyzed_files": [],
            "project_path": "/test",
            "incremental": False,
            "change_summaries": [],
        }
        config = {"configurable": {}}
        
        with patch("ut_agent.graph.test_generator_node.get_llm") as mock_get_llm:
            mock_get_llm.return_value = Mock()
            context = TestGenerationContext(state, config, max_workers=4)
        
        # 上下文不应该有执行业务逻辑的方法
        assert not hasattr(context, 'execute')
        assert not hasattr(context, 'generate')

    def test_single_responsibility_strategy(self):
        """测试策略类单一职责."""
        # 策略只负责选择生成器
        generator = TestGenerationStrategy.get_generator("java")
        assert generator is not None
        
        # 策略不应该有执行逻辑
        assert not hasattr(TestGenerationStrategy, 'execute')

    def test_single_responsibility_executor(self):
        """测试执行器单一职责."""
        # 执行器只负责执行
        mock_context = Mock()
        mock_context.analyzed_files = [{"file_path": "Test.java"}]
        executor = TestGenerationExecutor(mock_context)
        
        # 执行器不应该有报告逻辑
        assert not hasattr(executor, 'emit_start_event')
        assert not hasattr(executor, 'build_result')

    def test_single_responsibility_reporter(self):
        """测试报告器单一职责."""
        # 报告器只负责报告
        mock_context = Mock()
        reporter = TestGenerationReporter(mock_context)
        
        # 报告器不应该有执行逻辑
        assert not hasattr(reporter, 'execute')
        assert not hasattr(reporter, 'generate')
