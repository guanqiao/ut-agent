"""统一日志模块."""

import logging
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler


console = Console()


class UTAgentLogger:
    """UT-Agent 日志管理器."""

    _instance: Optional["UTAgentLogger"] = None
    _logger: Optional[logging.Logger] = None

    def __new__(cls) -> "UTAgentLogger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._logger is None:
            self._logger = self._create_logger()

    def _create_logger(self) -> logging.Logger:
        """创建日志器."""
        logger = logging.getLogger("ut_agent")
        logger.setLevel(logging.DEBUG)

        logger.handlers.clear()

        console_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=True,
            rich_tracebacks=True,
            markup=True,
        )
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(console_handler)

        return logger

    def add_file_handler(self, log_file: str, level: int = logging.DEBUG) -> None:
        """添加文件日志处理器.

        Args:
            log_file: 日志文件路径
            level: 日志级别
        """
        if self._logger is None:
            self._logger = self._create_logger()
            
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        self._logger.addHandler(file_handler)

    def add_structured_file_handler(self, log_file: str, level: int = logging.INFO) -> None:
        """添加结构化日志文件处理器.

        Args:
            log_file: 日志文件路径
            level: 日志级别
        """
        if self._logger is None:
            self._logger = self._create_logger()
            
        from logging.handlers import TimedRotatingFileHandler
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        class StructuredFormatter(logging.Formatter):
            """结构化日志格式化器."""
            def format(self, record: logging.LogRecord) -> str:
                import json
                log_data = {
                    "timestamp": self.formatTime(record, self.datefmt),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno
                }
                if hasattr(record, "extra"):
                    log_data.update(record.extra)
                return json.dumps(log_data, ensure_ascii=False)

        file_handler = TimedRotatingFileHandler(
            log_file,
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(StructuredFormatter())
        self._logger.addHandler(file_handler)

    def set_level(self, level: int) -> None:
        """设置日志级别.

        Args:
            level: 日志级别
        """
        if self._logger is None:
            self._logger = self._create_logger()
            
        self._logger.setLevel(level)
        for handler in self._logger.handlers:
            if isinstance(handler, RichHandler):
                handler.setLevel(level)

    @property
    def logger(self) -> logging.Logger:
        """获取日志器."""
        if self._logger is None:
            self._logger = self._create_logger()
        return self._logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """获取日志器.

    Args:
        name: 模块名称 (可选)

    Returns:
        logging.Logger: 日志器实例
    """
    ut_logger = UTAgentLogger()
    if name:
        return ut_logger.logger.getChild(name)
    return ut_logger.logger


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """设置日志配置.

    Args:
        level: 日志级别
        log_file: 日志文件路径 (可选)

    Returns:
        logging.Logger: 配置好的日志器
    """
    ut_logger = UTAgentLogger()
    ut_logger.set_level(level)

    if log_file:
        ut_logger.add_file_handler(log_file)

    return ut_logger.logger


logger = get_logger()
