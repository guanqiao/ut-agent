## 增量UT生成功能优化计划

### 目标
实现真正的增量UT生成，充分利用已有UT，只在需要时生成新的测试用例。

### 改进方案

#### 1. 新增增量测试生成函数
**文件**: `src/ut_agent/tools/test_generator.py`

- 新增 `generate_incremental_java_test()` 函数
- 新增 `generate_incremental_frontend_test()` 函数
- 只为新增/修改的方法生成测试
- 将已有测试作为上下文提供给LLM

#### 2. 新增测试分析器
**文件**: `src/ut_agent/tools/test_analyzer.py` (新建)

- `analyze_existing_tests()` - 分析已有测试覆盖的方法和场景
- `identify_test_gaps()` - 识别需要补充的测试场景
- `extract_test_patterns()` - 提取已有测试的模式和风格

#### 3. 优化测试合并策略
**文件**: `src/ut_agent/tools/test_mapper.py`

- 改进 `_merge_tests()` 方法
- 支持智能插入位置（按方法名排序）
- 保留手工修改的测试代码
- 支持测试方法去重

#### 4. 更新工作流节点
**文件**: `src/ut_agent/graph/nodes.py`

- 修改 `generate_tests_node()` 支持增量生成
- 在增量模式下调用新的增量生成函数

#### 5. 编写测试用例
**文件**: `tests/test_tools_test_generator.py`, `tests/test_tools_test_analyzer.py`

- 测试增量生成函数
- 测试测试分析器
- 测试合并策略

### 实现顺序
1. 新建 `test_analyzer.py` 测试分析器
2. 修改 `test_generator.py` 添加增量生成函数
3. 优化 `test_mapper.py` 合并策略
4. 更新 `nodes.py` 工作流节点
5. 编写/更新测试用例
6. 运行测试验证