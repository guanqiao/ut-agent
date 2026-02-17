# UT-Agent 持续迭代优化计划

## 优化方向概览

基于对项目的全面分析，识别出以下 6 大优化方向：

### Phase A: 代码质量优化 (高优先级)
1. **重构过长函数**
   - `code_analyzer.py` - `analyze_java_file` (141行)
   - `nodes.py` - `generate_tests_node` (155行)
   - `test_generator.py` - `generate_incremental_java_test` (158行)

2. **提取重复代码**
   - 创建 `BaseTestGenerator` 抽象基类
   - 统一 Go/Rust/C# 测试生成器的公共逻辑
   - 提取 AST 解析公共接口

3. **完善类型注解**
   - 为所有公共 API 添加完整类型注解
   - 用 TypedDict/Pydantic 替代 Dict[str, Any]
   - 启用 mypy 严格模式

### Phase B: 性能优化 (高优先级)
1. **缓存系统升级**
   - MD5 → SHA256 哈希算法
   - 添加缓存压缩 (gzip)
   - 实现多级缓存 (L1内存/L2磁盘/L3分布式)

2. **并发处理优化**
   - 自适应线程池
   - 背压机制
   - 信号量控制并发度

3. **LLM 调用优化**
   - HTTP 连接池
   - 请求批处理
   - 流式响应支持

### Phase C: 测试覆盖优化 (中优先级)
1. **补充缺失测试**
   - `tools/symbolic_executor.py`
   - `tools/mutation_analyzer.py`
   - `memory/semantic.py`

2. **测试质量提升**
   - 集成测试覆盖完整 LangGraph 工作流
   - 性能基准测试
   - 模糊测试 (fuzzing)

### Phase D: 架构优化 (中优先级)
1. **降低模块耦合**
   - 完善依赖注入容器
   - 定义清晰接口边界
   - 事件驱动架构

2. **配置管理统一**
   - 集中配置管理
   - 配置验证
   - 热更新支持

### Phase E: 安全性优化 (高优先级)
1. **关键安全修复**
   - AST 缓存 pickle → JSON/MessagePack
   - 路径遍历防护
   - 输入验证 (Pydantic)
   - 日志脱敏

### Phase F: 文档与维护 (低优先级)
1. **文档完善**
   - 架构决策记录 (ADR)
   - API 使用示例
   - 性能基准文档

2. **代码清理**
   - 处理 15 个 TODO
   - 依赖安全扫描
   - 多平台 CI 测试

## 执行计划

按优先级分阶段执行，每阶段遵循 TDD 模式：

| 阶段 | 预计时间 | 测试目标 |
|------|----------|----------|
| Phase A | 2-3 天 | 新增 50+ 测试 |
| Phase B | 3-4 天 | 新增 40+ 测试 |
| Phase C | 2-3 天 | 新增 60+ 测试 |
| Phase D | 2-3 天 | 新增 30+ 测试 |
| Phase E | 1-2 天 | 新增 20+ 测试 |
| Phase F | 1-2 天 | 文档更新 |

## 预期收益

- 代码质量: 函数复杂度降低 50%
- 性能: 缓存命中率提升 30%，响应时间降低 20%
- 测试覆盖: 从当前 85% 提升到 95%
- 安全性: 消除高危安全漏洞
- 可维护性: 代码重复率降低 40%

是否开始执行优化计划？