# UT-Agent 缓存系统文档

## 1. 功能描述

UT-Agent 提供了一个高效的缓存系统，用于优化系统性能和减少 API 调用。缓存系统包含两个主要组件：

- **LLM 缓存**: 缓存 LLM 调用结果，减少重复的 API 调用，降低成本并提高响应速度
- **AST 缓存**: 缓存代码的抽象语法树 (AST)，减少重复的代码解析，提高代码分析速度

## 2. 缓存系统架构

### 核心组件

- **LLMCache**: 管理 LLM 调用结果的缓存
- **ASTCache**: 管理代码 AST 的缓存
- **配置系统**: 提供缓存相关的配置选项
- **指标收集**: 监控缓存性能和使用情况

### 缓存流程

#### LLM 缓存流程

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  LLM 调用请求   │ ──> │  检查缓存       │ ──> │ 缓存命中？      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                      │
                                                      ├───── 是 ──> ┌─────────────────┐
                                                      │              │ 返回缓存结果   │
                                                      │              └─────────────────┘
                                                      │
                                                      └───── 否 ──> ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
                                                                    │ 调用 LLM API    │ ──> │ 缓存结果       │ ──> │ 返回结果       │
                                                                    └─────────────────┘     └─────────────────┘     └─────────────────┘
```

#### AST 缓存流程

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  代码解析请求   │ ──> │  检查缓存       │ ──> │ 缓存命中？      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                      │
                                                      ├───── 是 ──> ┌─────────────────┐
                                                      │              │ 返回缓存 AST    │
                                                      │              └─────────────────┘
                                                      │
                                                      └───── 否 ──> ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
                                                                    │ 解析代码生成 AST│ ──> │ 缓存 AST        │ ──> │ 返回 AST        │
                                                                    └─────────────────┘     └─────────────────┘     └─────────────────┘
```

## 3. 配置选项

### LLM 缓存配置

在 `.env` 文件中配置 LLM 缓存选项：

```env
# LLM 缓存配置
LLM_CACHE_MAX_SIZE=1000      # 最大缓存条目数
LLM_CACHE_TTL=3600           # 缓存过期时间（秒）
LLM_MAX_RETRIES=3            # 最大重试次数
LLM_RETRY_BASE_DELAY=1       # 基础重试延迟（秒）
LLM_MAX_RETRY_DELAY=60       # 最大重试延迟（秒）
```

### AST 缓存配置

在 `.env` 文件中配置 AST 缓存选项：

```env
# AST 缓存配置
AST_CACHE_MAX_SIZE=500       # 最大缓存条目数
AST_CACHE_TTL=86400          # 缓存过期时间（秒）
```

### 性能配置

```env
# 性能配置
MAX_CONCURRENT_THREADS=4     # 最大并发线程数
```

## 4. 使用方法

### 代码中使用 LLM 缓存

```python
from ut_agent.utils.llm_cache import get_cached_llm
from ut_agent.utils.llm import get_llm

# 获取基础 LLM 实例
base_llm = get_llm(provider="openai")

# 获取带缓存的 LLM 实例
cached_llm = get_cached_llm(base_llm)

# 使用缓存的 LLM 实例
from langchain_core.messages import HumanMessage
response = cached_llm.invoke([HumanMessage(content="Hello, world!")])
print(response.content)
```

### 代码中使用 AST 缓存

```python
from ut_agent.tools.ast_cache import get_ast_cache

# 获取 AST 缓存实例
ast_cache = get_ast_cache()

# 解析代码并缓存
code = "def add(a, b): return a + b"
ast = ast_cache.get_or_parse("test.py", code, "python")

# 直接获取缓存的 AST
cached_ast = ast_cache.get("test.py", code)
if cached_ast:
    print("AST 缓存命中!")
else:
    print("AST 缓存未命中!")
```

### 命令行使用

缓存系统会自动应用于所有 LLM 调用和代码分析，无需额外的命令行参数。缓存配置通过环境变量或 `.env` 文件进行管理。

## 5. 缓存系统 API

### LLM 缓存 API

#### 获取缓存的 LLM 实例

```python
from ut_agent.utils.llm_cache import get_cached_llm

# 获取带缓存的 LLM 实例
cached_llm = get_cached_llm(base_llm)
```

#### 清空 LLM 缓存

```python
from ut_agent.utils.llm_cache import clear_llm_cache

# 清空全局 LLM 缓存
clear_llm_cache()
```

#### 获取 LLM 缓存大小

```python
from ut_agent.utils.llm_cache import get_llm_cache_size

# 获取全局 LLM 缓存大小
cache_size = get_llm_cache_size()
print(f"LLM 缓存大小: {cache_size}")
```

### AST 缓存 API

#### 获取 AST 缓存实例

```python
from ut_agent.tools.ast_cache import get_ast_cache

# 获取 AST 缓存实例
ast_cache = get_ast_cache()
```

#### 解析代码并缓存

```python
# 解析代码并缓存
ast = ast_cache.get_or_parse(file_path, code, language)
```

#### 检查缓存

```python
# 检查缓存
ast = ast_cache.get(file_path, code)
```

#### 清空 AST 缓存

```python
# 清空 AST 缓存
ast_cache.clear()
```

#### 获取 AST 缓存大小

```python
# 获取 AST 缓存大小
cache_size = ast_cache.size()
print(f"AST 缓存大小: {cache_size}")
```

## 6. 缓存系统指标

缓存系统集成了指标收集功能，可以监控缓存的性能和使用情况。

### 可用指标

#### LLM 缓存指标

- `llm.calls`: LLM 调用次数
- `llm.calls.success`: 成功的 LLM 调用次数
- `llm.calls.failed`: 失败的 LLM 调用次数
- `llm.response.time`: LLM 响应时间直方图
- `cache.get`: 缓存获取操作次数
- `cache.get.hit`: 缓存命中次数
- `cache.get.miss`: 缓存未命中次数
- `cache.set`: 缓存设置操作次数

#### AST 缓存指标

- `ast.parse.count`: AST 解析次数
- `ast.parse.time`: AST 解析时间直方图
- `cache.ast.get`: AST 缓存获取操作次数
- `cache.ast.get.hit`: AST 缓存命中次数
- `cache.ast.get.miss`: AST 缓存未命中次数
- `cache.ast.set`: AST 缓存设置操作次数

### 查看指标

```bash
# 查看当前指标
ut-agent metrics
```

## 7. 性能优化建议

### LLM 缓存优化

- **调整缓存大小**: 根据项目规模和预算调整 `LLM_CACHE_MAX_SIZE`
- **合理设置 TTL**: 根据代码变更频率调整 `LLM_CACHE_TTL`
- **监控缓存命中率**: 定期查看缓存命中率，调整缓存策略
- **使用批量请求**: 合并多个小请求为一个大请求，减少 API 调用次数

### AST 缓存优化

- **调整缓存大小**: 根据代码库大小调整 `AST_CACHE_MAX_SIZE`
- **合理设置 TTL**: 根据代码变更频率调整 `AST_CACHE_TTL`
- **避免频繁代码变更**: 在分析过程中避免频繁修改代码，减少缓存失效
- **使用增量分析**: 只分析变更的代码，减少重复的 AST 解析

### 系统性能优化

- **调整并发线程数**: 根据 CPU 核心数调整 `MAX_CONCURRENT_THREADS`
- **监控内存使用**: 确保缓存大小不会导致内存溢出
- **定期清理缓存**: 对于长期运行的系统，定期清理过期缓存

## 8. 缓存系统实现细节

### LLM 缓存实现

#### 缓存键计算

LLM 缓存使用以下因素计算缓存键：

- 提示文本
- LLM 提供商
- 模型名称
- 温度参数

```python
def _compute_cache_key(self, prompt: str, provider: str, model: str, temperature: float) -> str:
    """计算缓存键."""
    key_data = {
        "prompt": prompt,
        "provider": provider,
        "model": model,
        "temperature": temperature,
    }
    key_str = json.dumps(key_data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(key_str.encode()).hexdigest()
```

#### 缓存淘汰策略

当缓存达到最大大小时，LLM 缓存会淘汰最旧的缓存条目：

```python
if len(self._cache) >= self._max_size:
    # 清理最旧的缓存
    oldest_key = min(
        self._cache.keys(),
        key=lambda k: self._cache[k]["timestamp"]
    )
    del self._cache[oldest_key]
```

### AST 缓存实现

#### 缓存键计算

AST 缓存使用文件路径和代码内容的哈希值计算缓存键：

```python
def _compute_cache_key(self, file_path: str, code: str) -> str:
    """计算缓存键."""
    key_data = {
        "file_path": file_path,
        "code_hash": hashlib.sha256(code.encode()).hexdigest(),
    }
    return hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
```

#### 缓存淘汰策略

AST 缓存使用 LRU (最近最少使用) 淘汰策略：

```python
if len(self._cache) >= self._max_size:
    # 移除最旧的条目
    oldest_key = next(iter(self._cache))
    del self._cache[oldest_key]
```

## 9. 常见问题

### Q: 缓存系统会导致内存溢出吗？

**A:** 缓存系统有大小限制，当达到最大大小时会自动淘汰旧的缓存条目。建议根据系统内存情况合理设置缓存大小。

### Q: 如何处理缓存过期？

**A:** 缓存系统会自动检查缓存条目是否过期，过期的条目会被删除。可以通过 `LLM_CACHE_TTL` 和 `AST_CACHE_TTL` 配置过期时间。

### Q: 缓存系统会影响测试的准确性吗？

**A:** 缓存系统只会缓存相同输入的结果，不会影响测试的准确性。如果需要强制刷新缓存，可以使用 `clear_llm_cache()` 和 `ast_cache.clear()` 方法。

### Q: 如何调试缓存系统？

**A:** 可以通过以下方式调试缓存系统：

1. 查看缓存指标：`ut-agent metrics`
2. 启用调试日志：设置 `LOG_LEVEL=DEBUG`
3. 检查缓存目录：AST 缓存存储在 `.ut-agent/ast_cache/` 目录

### Q: 缓存系统支持哪些 LLM 提供商？

**A:** 缓存系统支持所有通过插件系统注册的 LLM 提供商，包括 OpenAI、DeepSeek、Ollama 等。

### Q: 如何在多进程环境中使用缓存系统？

**A:** 目前缓存系统是进程内缓存，不支持多进程共享。在多进程环境中，每个进程会维护自己的缓存。

## 10. 示例代码

### 示例 1: 自定义 LLM 缓存配置

```python
from ut_agent.utils.llm_cache import LLMCache
from ut_agent.utils.llm import get_llm

# 创建自定义配置的 LLM 缓存
custom_cache = LLMCache(max_size=500, ttl_seconds=1800)

# 获取基础 LLM 实例
base_llm = get_llm(provider="openai")

# 创建带自定义缓存的 LLM 包装器
class CustomCachedLLM:
    def __init__(self, llm, cache):
        self._llm = llm
        self._cache = cache
    
    def invoke(self, messages, **kwargs):
        # 构建提示文本
        prompt = "\n".join([msg.content for msg in messages if hasattr(msg, "content")])
        provider = getattr(self._llm, "_provider", "unknown")
        model = getattr(self._llm, "model_name", "unknown")
        temperature = kwargs.get("temperature", 0.7)
        
        # 检查缓存
        cached_result = self._cache.get(prompt, provider, model, temperature)
        if cached_result:
            return cached_result
        
        # 调用 LLM
        result = self._llm.invoke(messages, **kwargs)
        
        # 缓存结果
        self._cache.set(prompt, provider, model, temperature, result)
        
        return result

# 使用自定义缓存的 LLM
custom_cached_llm = CustomCachedLLM(base_llm, custom_cache)
```

### 示例 2: 监控缓存性能

```python
from ut_agent.utils.llm_cache import get_cached_llm
from ut_agent.utils.llm import get_llm
from ut_agent.utils.metrics import log_metrics_summary
from langchain_core.messages import HumanMessage

# 获取带缓存的 LLM
base_llm = get_llm(provider="openai")
cached_llm = get_cached_llm(base_llm)

# 执行多次相同的请求
for i in range(5):
    print(f"请求 {i+1}:")
    response = cached_llm.invoke([HumanMessage(content="Hello, world!")])
    print(f"响应: {response.content}")
    print()

# 查看缓存性能指标
log_metrics_summary()
```

### 示例 3: 优化 AST 缓存使用

```python
from ut_agent.tools.ast_cache import get_ast_cache

# 获取 AST 缓存实例
ast_cache = get_ast_cache()

# 批量解析多个文件
files = [
    ("file1.py", "def add(a, b): return a + b", "python"),
    ("file2.py", "def multiply(a, b): return a * b", "python"),
    ("file3.py", "def subtract(a, b): return a - b", "python"),
]

asts = []
for file_path, code, language in files:
    ast = ast_cache.get_or_parse(file_path, code, language)
    asts.append(ast)
    print(f"解析 {file_path}: 缓存命中 = {ast_cache.get(file_path, code) is not None}")

# 再次解析相同的文件，应该全部命中缓存
print("\n第二次解析:")
for file_path, code, language in files:
    ast = ast_cache.get_or_parse(file_path, code, language)
    print(f"解析 {file_path}: 缓存命中 = {ast_cache.get(file_path, code) is not None}")

# 查看缓存大小
print(f"\nAST 缓存大小: {ast_cache.size()}")
```

## 11. 版本信息

- **版本**: 1.0.0
- **更新日期**: 2024-01-15
- **作者**: UT-Agent 开发团队

## 12. 总结

UT-Agent 的缓存系统是一个高效的性能优化组件，通过缓存 LLM 调用结果和代码 AST，显著提高了系统性能和响应速度。缓存系统具有以下特点：

- **灵活的配置选项**: 通过环境变量或 `.env` 文件进行配置
- **智能的缓存策略**: 自动管理缓存大小和过期时间
- **详细的指标监控**: 提供缓存性能和使用情况的详细指标
- **易于集成和扩展**: 提供简洁的 API 接口，支持自定义缓存策略

通过合理配置和使用缓存系统，可以显著提高 UT-Agent 的性能，减少 API 调用成本，为用户提供更快速、更可靠的服务。
