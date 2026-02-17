# UT-Agent 架构重构计划 (TDD方式)

**版本**: 1.0  
**创建日期**: 2026-02-17  
**状态**: 规划中

---

## 一、重构概述

### 1.1 重构目标

将 UT-Agent 架构进行全面优化，提升系统的：
- **架构一致性**：统一 Agent 和 Graph 模块的职责边界
- **性能**：全面异步化、优化并行处理策略
- **可维护性**：Prompt 模板外部化、配置分组管理
- **可靠性**：增强错误处理和恢复机制
- **可测试性**：引入依赖注入容器

### 1.2 重构原则

1. **TDD 开发**：先写测试，再写实现
2. **增量重构**：每个模块独立重构，确保测试通过
3. **向后兼容**：保持 API 接口稳定
4. **文档同步**：重构完成后更新相关文档

---

## 二、重构任务清单

### 阶段一：高优先级重构 (P0)

#### 任务 1：Agent 与 Graph 模块整合重构

**问题描述**：
- `agents/` 模块定义了 Agent 基类，但 `graph/nodes.py` 直接实现业务逻辑，未复用 Agent 体系
- 导致代码重复，职责不清

**重构目标**：
- Graph 节点调用 Agent 执行具体任务
- Agent 作为能力提供者，Graph 作为编排层
- 统一 Agent 的执行入口

**TDD 开发步骤**：

| 步骤 | 任务 | 测试文件 |
|------|------|----------|
| 1.1 | 编写 Agent 执行器接口测试 | `tests/test_agent_executor.py` |
| 1.2 | 实现 `AgentExecutor` 类 | `src/ut_agent/agents/executor.py` |
| 1.3 | 编写 Graph 节点调用 Agent 的测试 | `tests/test_graph_agent_integration.py` |
| 1.4 | 重构 `analyze_code_node` 使用 AnalyzerAgent | `src/ut_agent/graph/nodes.py` |
| 1.5 | 重构 `generate_tests_node` 使用 GeneratorAgent | `src/ut_agent/graph/nodes.py` |
| 1.6 | 重构其他节点使用对应 Agent | `src/ut_agent/graph/nodes.py` |
| 1.7 | 集成测试验证工作流完整性 | `tests/test_workflow_integration.py` |

**验收标准**：
- [ ] 所有现有测试通过
- [ ] 新增测试覆盖率 >= 90%
- [ ] Graph 节点代码行数减少 >= 30%
- [ ] Agent 执行可追踪、可调试

---

#### 任务 2：LLM 异步调用优化

**问题描述**：
- `tools/test_generator.py` 中 LLM 调用是同步的
- 缺乏重试和超时控制
- 速率限制处理不完善

**重构目标**：
- 统一使用异步调用 `llm.ainvoke()`
- 添加指数退避重试机制
- 实现请求/响应日志记录

**TDD 开发步骤**：

| 步骤 | 任务 | 测试文件 |
|------|------|----------|
| 2.1 | 编写异步 LLM 调用器测试 | `tests/test_async_llm_caller.py` |
| 2.2 | 实现 `AsyncLLMCaller` 类 | `src/ut_agent/utils/async_llm.py` |
| 2.3 | 编写重试机制测试 | `tests/test_llm_retry.py` |
| 2.4 | 实现指数退避重试装饰器 | `src/ut_agent/utils/retry.py` |
| 2.5 | 编写速率限制器测试 | `tests/test_rate_limiter.py` |
| 2.6 | 实现 `RateLimiter` 类 | `src/ut_agent/utils/rate_limiter.py` |
| 2.7 | 重构 `test_generator.py` 使用异步调用 | `src/ut_agent/tools/test_generator.py` |
| 2.8 | 集成测试验证 LLM 调用稳定性 | `tests/test_llm_integration.py` |

**验收标准**：
- [ ] 所有 LLM 调用改为异步
- [ ] 重试机制测试覆盖率 100%
- [ ] 速率限制器可配置
- [ ] 请求日志完整记录

---

### 阶段二：中优先级重构 (P1)

#### 任务 3：并行处理策略优化

**问题描述**：
- 使用 `ThreadPoolExecutor` 进行并行处理
- LLM 调用是 I/O 密集型，线程池效率有限
- 缺乏并发控制

**重构目标**：
- 使用 `asyncio.gather` 替代线程池
- 添加信号量控制并发数
- 实现请求批处理

**TDD 开发步骤**：

| 步骤 | 任务 | 测试文件 |
|------|------|----------|
| 3.1 | 编写异步并行处理器测试 | `tests/test_async_parallel_processor.py` |
| 3.2 | 实现 `AsyncParallelProcessor` 类 | `src/ut_agent/utils/parallel.py` |
| 3.3 | 编写并发控制测试 | `tests/test_concurrency_control.py` |
| 3.4 | 实现信号量并发控制 | `src/ut_agent/utils/concurrency.py` |
| 3.5 | 重构 `analyze_code_node` 使用异步并行 | `src/ut_agent/graph/nodes.py` |
| 3.6 | 重构 `generate_tests_node` 使用异步并行 | `src/ut_agent/graph/nodes.py` |
| 3.7 | 性能基准测试 | `tests/benchmarks/test_parallel_performance.py` |

**验收标准**：
- [ ] 移除 ThreadPoolExecutor
- [ ] 并发数可配置
- [ ] 性能提升 >= 20%
- [ ] 内存使用稳定

---

#### 任务 4：错误处理增强

**问题描述**：
- Graph 节点缺乏统一的错误处理策略
- 错误恢复机制不完善
- 错误上下文信息不足

**重构目标**：
- 实现全局异常处理器
- 添加错误恢复策略
- 记录完整错误上下文

**TDD 开发步骤**：

| 步骤 | 任务 | 测试文件 |
|------|------|----------|
| 4.1 | 编写错误处理器测试 | `tests/test_error_handler.py` |
| 4.2 | 实现 `NodeErrorHandler` 类 | `src/ut_agent/utils/error_handler.py` |
| 4.3 | 编写错误恢复策略测试 | `tests/test_recovery_strategy.py` |
| 4.4 | 实现恢复策略工厂 | `src/ut_agent/utils/recovery.py` |
| 4.5 | 编写错误上下文记录测试 | `tests/test_error_context.py` |
| 4.6 | 实现错误上下文管理器 | `src/ut_agent/utils/error_context.py` |
| 4.7 | 集成到 Graph 节点 | `src/ut_agent/graph/nodes.py` |

**验收标准**：
- [ ] 所有异常都有统一处理
- [ ] 可配置恢复策略
- [ ] 错误日志包含完整上下文
- [ ] 支持错误追踪 ID

---

#### 任务 5：Prompt 模板外部化

**问题描述**：
- Prompt 模板硬编码在代码中
- 难以维护和优化
- 缺乏版本管理

**重构目标**：
- 将 Prompt 模板移至外部文件
- 支持模板热更新
- 实现模板版本管理

**TDD 开发步骤**：

| 步骤 | 任务 | 测试文件 |
|------|------|----------|
| 5.1 | 编写模板加载器测试 | `tests/test_prompt_loader.py` |
| 5.2 | 实现 `PromptTemplateLoader` 类 | `src/ut_agent/prompts/loader.py` |
| 5.3 | 编写模板渲染器测试 | `tests/test_prompt_renderer.py` |
| 5.4 | 实现模板渲染器 | `src/ut_agent/prompts/renderer.py` |
| 5.5 | 创建外部模板文件 | `src/ut_agent/prompts/templates/` |
| 5.6 | 重构 `test_generator.py` 使用外部模板 | `src/ut_agent/tools/test_generator.py` |
| 5.7 | 实现模板热更新机制 | `src/ut_agent/prompts/hot_reload.py` |

**验收标准**：
- [ ] 所有 Prompt 模板外部化
- [ ] 模板文件结构清晰
- [ ] 支持模板变量注入
- [ ] 模板更新无需重启

---

### 阶段三：低优先级重构 (P2)

#### 任务 6：配置管理重构

**问题描述**：
- 所有配置项在一个类中
- 缺乏分组和验证逻辑分离
- 不支持配置热重载

**重构目标**：
- 使用 Pydantic 嵌套模型进行配置分组
- 添加配置热重载支持
- 实现配置验证器链

**TDD 开发步骤**：

| 步骤 | 任务 | 测试文件 |
|------|------|----------|
| 6.1 | 编写分组配置模型测试 | `tests/test_config_groups.py` |
| 6.2 | 实现 `LLMConfig`、`CacheConfig` 等分组 | `src/ut_agent/config.py` |
| 6.3 | 编写配置验证器测试 | `tests/test_config_validators.py` |
| 6.4 | 实现验证器链 | `src/ut_agent/config/validators.py` |
| 6.5 | 编写配置热重载测试 | `tests/test_config_reload.py` |
| 6.6 | 实现配置热重载机制 | `src/ut_agent/config/reload.py` |

**验收标准**：
- [ ] 配置按功能分组
- [ ] 验证逻辑独立
- [ ] 支持配置热重载
- [ ] 配置变更可追踪

---

#### 任务 7：依赖注入容器实现

**问题描述**：
- 多处使用全局单例
- 不利于测试和模块隔离
- Mock 替换困难

**重构目标**：
- 使用依赖注入容器
- 支持测试时 Mock 替换
- 实现生命周期管理

**TDD 开发步骤**：

| 步骤 | 任务 | 测试文件 |
|------|------|----------|
| 7.1 | 编写依赖注入容器测试 | `tests/test_container.py` |
| 7.2 | 实现 `Container` 类 | `src/ut_agent/container.py` |
| 7.3 | 编写服务注册测试 | `tests/test_service_registration.py` |
| 7.4 | 实现服务注册机制 | `src/ut_agent/container/registry.py` |
| 7.5 | 重构现有代码使用容器 | 全局重构 |
| 7.6 | 编写测试 Mock 支持测试 | `tests/test_container_mock.py` |

**验收标准**：
- [ ] 核心服务通过容器注入
- [ ] 支持单例和瞬态生命周期
- [ ] 测试可轻松 Mock
- [ ] 移除全局单例

---

#### 任务 8：性能监控增强

**问题描述**：
- 缺乏细粒度的性能追踪
- 无法识别性能瓶颈
- 缺乏分布式追踪能力

**重构目标**：
- 添加 OpenTelemetry 集成
- 实现分布式追踪
- 添加性能瓶颈自动识别

**TDD 开发步骤**：

| 步骤 | 任务 | 测试文件 |
|------|------|----------|
| 8.1 | 编写 OpenTelemetry 集成测试 | `tests/test_telemetry.py` |
| 8.2 | 实现 Telemetry 配置和初始化 | `src/ut_agent/telemetry/__init__.py` |
| 8.3 | 编写性能追踪器测试 | `tests/test_performance_tracker.py` |
| 8.4 | 实现性能追踪装饰器 | `src/ut_agent/telemetry/tracing.py` |
| 8.5 | 编写瓶颈识别测试 | `tests/test_bottleneck_detector.py` |
| 8.6 | 实现瓶颈自动识别 | `src/ut_agent/telemetry/bottleneck.py` |
| 8.7 | 集成到关键路径 | 全局集成 |

**验收标准**：
- [ ] OpenTelemetry 集成完成
- [ ] 关键路径有追踪
- [ ] 性能瓶颈可识别
- [ ] 支持导出到主流后端

---

## 三、重构时间线

```
Week 1-2:  阶段一 - Agent与Graph整合 + LLM异步优化
Week 3-4:  阶段二 - 并行处理优化 + 错误处理增强
Week 5:    阶段二 - Prompt模板外部化
Week 6-7:  阶段三 - 配置管理重构 + 依赖注入
Week 8:    阶段三 - 性能监控增强 + 集成测试
```

---

## 四、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 重构影响现有功能 | 高 | 增量重构，每步验证测试 |
| TDD 增加开发时间 | 中 | 先写核心测试，逐步补充 |
| 依赖注入改动范围大 | 高 | 分阶段迁移，保持兼容 |
| 性能优化效果不明显 | 中 | 基准测试验证 |

---

## 五、验收检查清单

### 整体验收

- [ ] 所有测试通过 (`pytest tests/ -v`)
- [ ] 测试覆盖率 >= 85% (`pytest --cov`)
- [ ] 类型检查通过 (`mypy src/`)
- [ ] 代码风格检查通过 (`flake8 src/`)
- [ ] 文档更新完成
- [ ] 性能基准测试通过

### 模块验收

- [ ] Agent 模块重构完成
- [ ] Graph 模块重构完成
- [ ] LLM 异步调用完成
- [ ] 并行处理优化完成
- [ ] 错误处理增强完成
- [ ] Prompt 模板外部化完成
- [ ] 配置管理重构完成
- [ ] 依赖注入完成
- [ ] 性能监控完成

---

## 六、参考资源

- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [Pydantic 文档](https://docs.pydantic.dev/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
- [dependency-injector](https://python-dependency-injector.ets-labs.org/)
