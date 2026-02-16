# UT-Agent API 文档

## 1. 命令行接口 (CLI)

UT-Agent 提供了一个功能丰富的命令行接口，用于执行各种任务。

### 1.1 基础命令

#### `ut-agent generate`

生成单元测试。

```bash
# 基本用法
ut-agent generate --project ./my-project

# 完整选项
ut-agent generate \
  --project ./my-project \
  --type java \
  --coverage-target 80 \
  --max-iterations 5 \
  --llm openai \
  --dry-run \
  --incremental \
  --base HEAD~1 \
  --head HEAD \
  --html-report
```

**参数说明：**

- `--project`: 项目路径（必需）
- `--type`: 项目类型 (auto/java/vue/react/typescript)
- `--coverage-target`: 覆盖率目标 (0-100)
- `--max-iterations`: 最大迭代次数
- `--llm`: LLM 提供商 (openai/deepseek/ollama)
- `--dry-run`: 仅生成测试，不保存
- `--incremental`: 增量模式，仅对变更代码生成测试
- `--base`: 基准Git引用
- `--head`: 目标Git引用
- `--html-report`: 生成HTML覆盖率报告

#### `ut-agent interactive`

交互式模式，通过问答方式配置参数。

```bash
ut-agent interactive
```

#### `ut-agent ui`

启动 Web UI。

```bash
# 基本用法
ut-agent ui

# 自定义端口和主机
ut-agent ui --port 8501 --host 127.0.0.1
```

**参数说明：**

- `--port`: 端口号 (默认: 8501)
- `--host`: 主机地址 (默认: 127.0.0.1)

#### `ut-agent ci`

CI模式，非交互式运行，输出JSON结果。

```bash
ut-agent ci \
  --project ./my-project \
  --type java \
  --coverage-target 80 \
  --max-iterations 5 \
  --llm openai \
  --output json \
  --output-file ci-result.json \
  --fail-on-coverage \
  --incremental \
  --base HEAD~1
```

**参数说明：**

- `--project`: 项目路径（必需）
- `--type`: 项目类型
- `--coverage-target`: 覆盖率目标
- `--max-iterations`: 最大迭代次数
- `--llm`: LLM 提供商
- `--output`: 输出格式 (json/markdown/summary)
- `--output-file`: 输出文件路径
- `--fail-on-coverage`: 覆盖率低于目标时返回非零退出码
- `--incremental`: 增量模式
- `--base`: 基准Git引用

#### `ut-agent check`

检查环境配置。

```bash
ut-agent check
```

#### `ut-agent mutation`

运行变异测试并分析结果。

```bash
ut-agent mutation \
  --project ./my-project \
  --target-classes com.example.* \
  --target-tests *Test \
  --mutators DEFAULTS \
  --output json \
  --suggest
```

**参数说明：**

- `--project`: 项目路径（必需）
- `--target-classes`: 目标类 (逗号分隔)
- `--target-tests`: 目标测试类 (逗号分隔)
- `--mutators`: 变异算子 (逗号分隔)
- `--output`: 输出格式 (json/summary)
- `--suggest`: 生成测试建议

#### `ut-agent config`

显示当前配置。

```bash
ut-agent config
```

#### `ut-agent metrics`

显示当前监控指标。

```bash
ut-agent metrics
```

### 1.2 全局选项

- `--version`, `-v`: 显示版本信息
- `--help`: 显示帮助信息

## 2. Python API

UT-Agent 提供了丰富的 Python API，用于在代码中集成和扩展功能。

### 2.1 核心 API

#### `get_llm(provider=None)`

获取 LLM 模型实例。

```python
from ut_agent.utils.llm import get_llm

# 获取默认提供商的 LLM 实例
llm = get_llm()

# 获取指定提供商的 LLM 实例
llm = get_llm(provider="openai")
```

**参数：**
- `provider`: LLM 提供商名称 (可选)

**返回值：**
- LLM 模型实例

#### `list_available_providers()`

列出可用的 LLM 提供商。

```python
from ut_agent.utils.llm import list_available_providers

available_providers = list_available_providers()
print(f"可用提供商: {available_providers}")
```

**返回值：**
- 可用提供商名称列表

#### `register_provider(provider)`

注册自定义 LLM 提供商。

```python
from ut_agent.utils.llm import register_provider, LLMProvider

class MyCustomProvider(LLMProvider):
    name = "my_custom"
    # ... 实现方法 ...

# 注册提供商
register_provider(MyCustomProvider())
```

**参数：**
- `provider`: LLMProvider 实例

### 2.2 缓存 API

#### `get_cached_llm(llm)`

获取带缓存的 LLM 实例。

```python
from ut_agent.utils.llm_cache import get_cached_llm
from ut_agent.utils.llm import get_llm

# 获取基础 LLM 实例
base_llm = get_llm()

# 获取带缓存的 LLM 实例
cached_llm = get_cached_llm(base_llm)
```

**参数：**
- `llm`: 基础 LLM 实例

**返回值：**
- 带缓存的 LLM 实例

#### `clear_llm_cache()`

清空全局 LLM 缓存。

```python
from ut_agent.utils.llm_cache import clear_llm_cache

# 清空缓存
clear_llm_cache()
```

#### `get_llm_cache_size()`

获取全局 LLM 缓存大小。

```python
from ut_agent.utils.llm_cache import get_llm_cache_size

# 获取缓存大小
size = get_llm_cache_size()
print(f"LLM 缓存大小: {size}")
```

**返回值：**
- 缓存大小（整数）

#### `get_ast_cache()`

获取 AST 缓存实例。

```python
from ut_agent.tools.ast_cache import get_ast_cache

# 获取 AST 缓存实例
ast_cache = get_ast_cache()
```

**返回值：**
- AST 缓存实例

### 2.3 监控 API

#### `get_metrics_collector()`

获取指标收集器实例。

```python
from ut_agent.utils.metrics import get_metrics_collector

# 获取指标收集器
collector = get_metrics_collector()
```

**返回值：**
- MetricsCollector 实例

#### `get_metrics_summary()`

获取指标摘要。

```python
from ut_agent.utils.metrics import get_metrics_summary

# 获取指标摘要
metrics = get_metrics_summary()
print(f"指标摘要: {metrics}")
```

**返回值：**
- 指标摘要字典

#### `log_metrics_summary()`

记录指标摘要到日志。

```python
from ut_agent.utils.metrics import log_metrics_summary

# 记录指标摘要
log_metrics_summary()
```

### 2.4 配置 API

#### `settings`

全局配置对象。

```python
from ut_agent.config import settings

# 访问配置
print(f"默认 LLM 提供商: {settings.default_llm_provider}")
print(f"LLM 缓存最大大小: {settings.llm_cache_max_size}")
```

**主要配置项：**

| 配置项 | 描述 | 默认值 |
|--------|------|--------|
| `default_llm_provider` | 默认 LLM 提供商 | "openai" |
| `openai_api_key` | OpenAI API 密钥 | "" |
| `openai_model` | OpenAI 模型 | "gpt-4" |
| `deepseek_api_key` | DeepSeek API 密钥 | "" |
| `deepseek_model` | DeepSeek 模型 | "deepseek-chat" |
| `ollama_model` | Ollama 模型 | "llama3" |
| `ollama_base_url` | Ollama 基础 URL | "http://localhost:11434" |
| `default_coverage_target` | 默认覆盖率目标 | 80.0 |
| `max_iterations` | 最大迭代次数 | 5 |
| `temperature` | 温度参数 | 0.7 |
| `llm_cache_max_size` | LLM 缓存最大大小 | 1000 |
| `llm_cache_ttl` | LLM 缓存过期时间（秒） | 3600 |
| `ast_cache_max_size` | AST 缓存最大大小 | 500 |
| `ast_cache_ttl` | AST 缓存过期时间（秒） | 86400 |
| `llm_max_retries` | LLM 最大重试次数 | 3 |
| `llm_retry_base_delay` | LLM 基础重试延迟（秒） | 1 |
| `llm_max_retry_delay` | LLM 最大重试延迟（秒） | 60 |
| `max_concurrent_threads` | 最大并发线程数 | CPU核心数 |

### 2.5 工具 API

#### `TestExecutor`

测试执行器。

```python
from ut_agent.tools.test_executor import TestExecutor

# 创建测试执行器
executor = TestExecutor(project_path="./my-project", project_type="java")

# 执行测试
result = executor.run_tests()
print(f"测试结果: {result}")

# 获取覆盖率报告
coverage_report = executor.get_coverage_report()
print(f"覆盖率: {coverage_report.overall_coverage}%")
```

#### `CodeAnalyzer`

代码分析器。

```python
from ut_agent.tools.code_analyzer import CodeAnalyzer

# 创建代码分析器
analyzer = CodeAnalyzer(project_path="./my-project", project_type="java")

# 分析代码
analysis = analyzer.analyze()
print(f"分析结果: {analysis}")
```

#### `TestGenerator`

测试生成器。

```python
from ut_agent.tools.test_generator import TestGenerator

# 创建测试生成器
generator = TestGenerator(project_path="./my-project", project_type="java")

# 生成测试
tests = generator.generate_tests(target_files=["./src/main/java/com/example/MyClass.java"])
print(f"生成的测试: {tests}")
```

## 3. 配置系统

UT-Agent 使用 Pydantic 进行配置管理，支持从环境变量和 `.env` 文件加载配置。

### 3.1 环境变量配置

在 `.env` 文件中配置：

```env
# LLM 配置
DEFAULT_LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4

# 覆盖率配置
DEFAULT_COVERAGE_TARGET=80
MAX_ITERATIONS=5

# 缓存配置
LLM_CACHE_MAX_SIZE=1000
LLM_CACHE_TTL=3600
AST_CACHE_MAX_SIZE=500
AST_CACHE_TTL=86400

# 重试配置
LLM_MAX_RETRIES=3
LLM_RETRY_BASE_DELAY=1
LLM_MAX_RETRY_DELAY=60

# 性能配置
MAX_CONCURRENT_THREADS=4
```

### 3.2 运行时配置

可以在运行时修改配置：

```python
from ut_agent.config import settings

# 修改配置
settings.default_llm_provider = "ollama"
settings.temperature = 0.5

# 注意：运行时修改的配置仅在当前会话有效
```

## 4. 插件系统 API

UT-Agent 提供了一个灵活的插件系统，用于扩展 LLM 提供商的支持。

### 4.1 创建自定义提供商

```python
from ut_agent.utils.llm import LLMProvider
from ut_agent.exceptions import ConfigurationError

class MyCustomProvider(LLMProvider):
    """自定义 LLM 提供商"""

    name = "my_custom"
    requires_api_key = True
    api_key_setting = "MY_CUSTOM_API_KEY"
    model_setting = "MY_CUSTOM_MODEL"
    base_url_setting = "MY_CUSTOM_BASE_URL"

    def create_model(self, config):
        """创建模型实例"""
        api_key = getattr(config, self.api_key_setting)
        model = getattr(config, self.model_setting)
        base_url = getattr(config, self.base_url_setting, "https://api.my-custom.com")

        if not api_key:
            raise ConfigurationError(
                "My Custom API Key 未配置",
                config_key=self.api_key_setting
            )

        # 导入 LangChain 模型
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=config.temperature,
        )

    def is_available(self, config):
        """检查提供商是否可用"""
        return bool(getattr(config, self.api_key_setting, None))
```

### 4.2 注册提供商

```python
from ut_agent.utils.llm import register_provider

# 注册自定义提供商
register_provider(MyCustomProvider())

# 现在可以在命令行中使用
# ut-agent generate --project ./my-project --llm my_custom
```

## 5. 监控系统 API

### 5.1 指标收集

#### `record_llm_call(provider, model, response_time, success)`

记录 LLM 调用指标。

```python
from ut_agent.utils.metrics import record_llm_call

# 记录 LLM 调用
record_llm_call("openai", "gpt-4", 1.5, True)
```

**参数：**
- `provider`: LLM 提供商
- `model`: 模型名称
- `response_time`: 响应时间（秒）
- `success`: 是否成功

#### `record_cache_operation(cache_type, operation, hit=False)`

记录缓存操作指标。

```python
from ut_agent.utils.metrics import record_cache_operation

# 记录缓存操作
record_cache_operation("llm", "get", hit=True)
```

**参数：**
- `cache_type`: 缓存类型 (llm/ast)
- `operation`: 操作类型 (get/set)
- `hit`: 是否命中

#### `record_ast_parse(file_path, language, parse_time)`

记录 AST 解析指标。

```python
from ut_agent.utils.metrics import record_ast_parse

# 记录 AST 解析
record_ast_parse("file.py", "python", 0.1)
```

**参数：**
- `file_path`: 文件路径
- `language`: 语言
- `parse_time`: 解析时间（秒）

### 5.2 上下文管理器

#### `llm_call(provider, model)`

LLM 调用上下文管理器，自动记录指标。

```python
from ut_agent.utils.metrics import llm_call

# 使用上下文管理器
with llm_call("openai", "gpt-4"):
    # 执行 LLM 调用
    response = llm.invoke([HumanMessage(content="Hello")])
```

#### `ast_parse(file_path, language)`

AST 解析上下文管理器，自动记录指标。

```python
from ut_agent.utils.metrics import ast_parse

# 使用上下文管理器
with ast_parse("file.py", "python"):
    # 执行 AST 解析
    ast = parse_code(code)
```

## 6. 示例代码

### 6.1 基本用法示例

#### 生成测试

```python
from ut_agent.graph import create_test_generation_graph
from ut_agent.models import AgentState

# 创建初始状态
initial_state: AgentState = {
    "project_path": "./my-project",
    "project_type": "java",
    "coverage_target": 80.0,
    "max_iterations": 5,
    "incremental": False,
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
    "html_report_path": None,
}

# 创建图
graph = create_test_generation_graph()

# 运行
import asyncio

async def run_workflow():
    async for event in graph.astream(
        initial_state,
        config={"configurable": {"llm_provider": "openai"}},
    ):
        for node_name, node_data in event.items():
            if isinstance(node_data, dict):
                status = node_data.get("status", "")
                message = node_data.get("message", "")
                print(f"[{node_name}] {message}")
                if status == "completed":
                    print(f"工作流完成! 覆盖率: {node_data.get('current_coverage', 0)}%")

asyncio.run(run_workflow())
```

### 6.2 高级用法示例

#### 自定义工作流

```python
from ut_agent.agents.analyzer import CodeAnalyzerAgent
from ut_agent.agents.generator import TestGeneratorAgent
from ut_agent.agents.fixer import TestFixerAgent
from ut_agent.tools.test_executor import TestExecutor

# 创建代理
analyzer = CodeAnalyzerAgent()
 generator = TestGeneratorAgent()
fixer = TestFixerAgent()

# 创建测试执行器
executor = TestExecutor(project_path="./my-project", project_type="java")

# 1. 分析代码
analysis = analyzer.analyze(project_path="./my-project", project_type="java")
print(f"代码分析完成: {len(analysis.target_files)} 个文件")

# 2. 生成测试
tests = generator.generate_tests(
    project_path="./my-project",
    project_type="java",
    target_files=analysis.target_files
)
print(f"生成测试完成: {len(tests)} 个测试")

# 3. 执行测试
result = executor.run_tests()
print(f"测试执行完成: {result}")

# 4. 修复失败的测试
fixed_tests = fixer.fix_tests(
    project_path="./my-project",
    project_type="java",
    failed_tests=result.failed_tests
)
print(f"修复测试完成: {len(fixed_tests)} 个测试")

# 5. 再次执行测试
final_result = executor.run_tests()
print(f"最终测试结果: {final_result}")

# 6. 获取覆盖率报告
coverage_report = executor.get_coverage_report()
print(f"最终覆盖率: {coverage_report.overall_coverage}%")
```

#### 插件开发示例

```python
"""自定义 LLM 提供商插件"""

from ut_agent.utils.llm import LLMProvider, register_provider
from ut_agent.exceptions import ConfigurationError

class AnthropicProvider(LLMProvider):
    """Anthropic LLM 提供商"""

    name = "anthropic"
    requires_api_key = True
    api_key_setting = "ANTHROPIC_API_KEY"
    model_setting = "ANTHROPIC_MODEL"
    base_url_setting = "ANTHROPIC_BASE_URL"

    def create_model(self, config):
        """创建模型实例"""
        api_key = getattr(config, self.api_key_setting)
        model = getattr(config, self.model_setting, "claude-3-opus-20240229")
        base_url = getattr(config, self.base_url_setting, "https://api.anthropic.com")

        if not api_key:
            raise ConfigurationError(
                "Anthropic API Key 未配置",
                config_key=self.api_key_setting
            )

        # 导入 LangChain 模型
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=config.temperature,
        )

    def is_available(self, config):
        """检查提供商是否可用"""
        return bool(getattr(config, self.api_key_setting, None))

# 注册提供商
if __name__ == "__main__":
    register_provider(AnthropicProvider())
    print("Anthropic provider registered successfully!")
    print("请在 .env 文件中添加 ANTHROPIC_API_KEY 配置")
```

## 7. 错误处理

UT-Agent 定义了多种异常类型，用于处理不同的错误情况。

### 7.1 异常类型

#### `UTAgentError`

基础异常类。

#### `ConfigurationError`

配置错误。

#### `LLMError`

LLM 相关错误。

#### `LLMRateLimitError`

LLM 速率限制错误。

#### `RetryableError`

可重试的错误。

#### `AnalysisError`

代码分析错误。

#### `GenerationError`

测试生成错误。

#### `ExecutionError`

测试执行错误。

### 7.2 异常处理示例

```python
from ut_agent.utils.llm import get_llm
from ut_agent.exceptions import ConfigurationError, LLMError

try:
    # 获取 LLM 实例
    llm = get_llm(provider="openai")
    
    # 使用 LLM
    from langchain_core.messages import HumanMessage
    response = llm.invoke([HumanMessage(content="Hello")])
    print(response.content)
    
except ConfigurationError as e:
    print(f"配置错误: {e}")
except LLMError as e:
    print(f"LLM 错误: {e}")
except Exception as e:
    print(f"未知错误: {e}")
```

## 8. 版本信息

- **版本**: 0.1.0
- **更新日期**: 2024-02-17
- **作者**: UT-Agent 开发团队

## 9. 总结

UT-Agent 提供了丰富的 API 接口，支持从命令行、Python 代码和配置文件等多个层面使用和扩展功能。通过这些 API，用户可以：

- 生成和执行单元测试
- 分析代码和覆盖率
- 集成自定义 LLM 提供商
- 配置和监控系统性能
- 扩展系统功能

UT-Agent 的 API 设计注重灵活性和可扩展性，使用户可以根据自己的需求定制和扩展系统功能，同时保持了简洁易用的接口设计。

## 10. 常见问题

### Q: 如何获取更详细的日志？

**A:** 设置环境变量 `LOG_LEVEL=DEBUG` 或在代码中使用 `setup_logging(level=logging.DEBUG)`。

### Q: 如何自定义 LLM 模型参数？

**A:** 在 `.env` 文件中配置相应的模型参数，或在代码中修改 `settings` 对象。

### Q: 如何集成自定义工具？

**A:** 继承相应的基类（如 `Tool`），实现必要的方法，然后在工作流中使用。

### Q: 如何监控系统性能？

**A:** 使用 `ut-agent metrics` 命令查看指标，或在代码中使用 `log_metrics_summary()` 记录指标。

### Q: 如何处理大型项目？

**A:** 使用增量模式 (`--incremental`) 只处理变更的代码，或调整缓存大小和并发线程数以优化性能。
