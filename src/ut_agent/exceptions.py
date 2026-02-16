"""UT-Agent 专用异常类.

提供细粒度的异常处理，便于错误诊断和恢复。
"""

from typing import Any, Optional


class UTAgentError(Exception):
    """UT-Agent 基础异常类."""

    def __init__(self, message: str, details: Optional[dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class ConfigurationError(UTAgentError):
    """配置错误."""

    def __init__(self, message: str, config_key: Optional[str] = None):
        details = {"config_key": config_key} if config_key else {}
        super().__init__(message, details)


class LLMError(UTAgentError):
    """LLM 相关错误基类."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        details = {}
        if provider:
            details["provider"] = provider
        if model:
            details["model"] = model
        super().__init__(message, details)


class LLMConnectionError(LLMError):
    """LLM 连接错误."""

    pass


class LLMRateLimitError(LLMError):
    """LLM 速率限制错误."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        retry_after: Optional[int] = None,
    ):
        super().__init__(message, provider, model)
        if retry_after:
            self.details["retry_after"] = retry_after


class LLMResponseError(LLMError):
    """LLM 响应错误."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        response: Optional[str] = None,
    ):
        super().__init__(message, provider, model)
        if response:
            self.details["response_preview"] = response[:500] if len(response) > 500 else response


class CodeAnalysisError(UTAgentError):
    """代码分析错误基类."""

    def __init__(self, message: str, file_path: Optional[str] = None):
        details = {"file_path": file_path} if file_path else {}
        super().__init__(message, details)


class ASTParseError(CodeAnalysisError):
    """AST 解析错误."""

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        line: Optional[int] = None,
        column: Optional[int] = None,
    ):
        super().__init__(message, file_path)
        if line is not None:
            self.details["line"] = line
        if column is not None:
            self.details["column"] = column


class FileReadError(CodeAnalysisError):
    """文件读取错误."""

    def __init__(self, message: str, file_path: str, reason: Optional[str] = None):
        super().__init__(message, file_path)
        if reason:
            self.details["reason"] = reason


class TestGenerationError(UTAgentError):
    """测试生成错误基类."""

    def __init__(
        self,
        message: str,
        source_file: Optional[str] = None,
        test_file: Optional[str] = None,
    ):
        details = {}
        if source_file:
            details["source_file"] = source_file
        if test_file:
            details["test_file"] = test_file
        super().__init__(message, details)


class TestCompilationError(TestGenerationError):
    """测试编译错误."""

    def __init__(
        self,
        message: str,
        source_file: Optional[str] = None,
        test_file: Optional[str] = None,
        compilation_output: Optional[str] = None,
    ):
        super().__init__(message, source_file, test_file)
        if compilation_output:
            self.details["compilation_output"] = compilation_output


class TestExecutionError(TestGenerationError):
    """测试执行错误."""

    def __init__(
        self,
        message: str,
        source_file: Optional[str] = None,
        test_file: Optional[str] = None,
        exit_code: Optional[int] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
    ):
        super().__init__(message, source_file, test_file)
        if exit_code is not None:
            self.details["exit_code"] = exit_code
        if stdout:
            self.details["stdout"] = stdout[:1000] if len(stdout) > 1000 else stdout
        if stderr:
            self.details["stderr"] = stderr[:1000] if len(stderr) > 1000 else stderr


class CoverageAnalysisError(UTAgentError):
    """覆盖率分析错误."""

    def __init__(
        self,
        message: str,
        report_path: Optional[str] = None,
        report_format: Optional[str] = None,
    ):
        details = {}
        if report_path:
            details["report_path"] = report_path
        if report_format:
            details["report_format"] = report_format
        super().__init__(message, details)


class TemplateError(UTAgentError):
    """模板错误基类."""

    def __init__(self, message: str, template_name: Optional[str] = None):
        details = {"template_name": template_name} if template_name else {}
        super().__init__(message, details)


class TemplateNotFoundError(TemplateError):
    """模板未找到错误."""

    pass


class TemplateRenderError(TemplateError):
    """模板渲染错误."""

    def __init__(
        self,
        message: str,
        template_name: Optional[str] = None,
        context: Optional[dict] = None,
    ):
        super().__init__(message, template_name)
        if context:
            self.details["context_keys"] = list(context.keys())


class MemoryError(UTAgentError):
    """记忆系统错误基类."""

    def __init__(self, message: str, operation: Optional[str] = None):
        details = {"operation": operation} if operation else {}
        super().__init__(message, details)


class DatabaseError(MemoryError):
    """数据库错误."""

    def __init__(self, message: str, operation: Optional[str] = None, query: Optional[str] = None):
        super().__init__(message, operation)
        if query:
            self.details["query"] = query


class GitError(UTAgentError):
    """Git 相关错误."""

    def __init__(self, message: str, operation: Optional[str] = None, repo_path: Optional[str] = None):
        details = {}
        if operation:
            details["operation"] = operation
        if repo_path:
            details["repo_path"] = repo_path
        super().__init__(message, details)


class ProjectDetectionError(UTAgentError):
    """项目检测错误."""

    def __init__(self, message: str, project_path: Optional[str] = None):
        details = {"project_path": project_path} if project_path else {}
        super().__init__(message, details)


class WorkflowError(UTAgentError):
    """工作流错误."""

    def __init__(
        self,
        message: str,
        workflow_stage: Optional[str] = None,
        task_id: Optional[str] = None,
    ):
        details = {}
        if workflow_stage:
            details["workflow_stage"] = workflow_stage
        if task_id:
            details["task_id"] = task_id
        super().__init__(message, details)


class ValidationError(UTAgentError):
    """验证错误."""

    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)[:100]
        super().__init__(message, details)


class TimeoutError(UTAgentError):
    """超时错误."""

    def __init__(self, message: str, timeout_seconds: Optional[float] = None):
        details = {}
        if timeout_seconds is not None:
            details["timeout_seconds"] = timeout_seconds
        super().__init__(message, details)


class RetryableError(UTAgentError):
    """可重试错误基类."""

    def __init__(
        self,
        message: str,
        max_retries: int = 3,
        retry_count: int = 0,
        details: Optional[dict] = None,
    ):
        super().__init__(message, details)
        self.max_retries = max_retries
        self.retry_count = retry_count

    def should_retry(self) -> bool:
        return self.retry_count < self.max_retries

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["max_retries"] = self.max_retries
        result["retry_count"] = self.retry_count
        result["should_retry"] = self.should_retry()
        return result
