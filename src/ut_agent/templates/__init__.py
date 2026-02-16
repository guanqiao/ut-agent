"""测试模板模块.

提供可复用的测试模板系统，支持：
- 内置常用模板
- 用户自定义模板
- 模板热加载
"""

from .template_engine import TemplateEngine, UnitTestTemplate, TemplateManager

__all__ = ['TemplateEngine', 'UnitTestTemplate', 'TemplateManager']
