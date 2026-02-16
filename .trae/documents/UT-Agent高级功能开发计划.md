# UT-Agent 高级功能开发计划

## 项目概述

**项目名称**: UT-Agent 高级功能增强  
**当前版本**: 0.1.0  
**目标版本**: 1.5.0  
**计划周期**: 2-3个月  
**制定日期**: 2026-02-16  

---

## 功能一：Multi-Agent 协作架构

### 1.1 功能概述

**任务描述**: 重构现有单 Agent 架构为 Multi-Agent 协作架构，实现 Analyzer/Generator/Reviewer/Fixer 四个专业 Agent 的协作

**优先级**: P0  
**时间预估**: 3周  
**计划完成时间**: 第3周  

### 1.2 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                      Orchestrator Agent                         │
│                    (任务调度与协调中心)                           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│    Analyzer   │   │   Generator   │   │   Reviewer    │
│    Agent      │   │    Agent      │   │    Agent      │
│  (代码分析)    │   │  (测试生成)    │   │  (质量检查)    │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │    Fixer      │
                    │    Agent      │
                    │  (自动修复)    │
                    └───────────────┘
```

### 1.3 Agent 角色定义

#### 1.3.1 Analyzer Agent（分析专家）

**职责**:
- 解析源代码结构（类、方法、字段、注解）
- 构建依赖关系图
- 识别可测试单元
- 分析代码复杂度和风险点
- 提供测试策略建议

**输入**: 源文件路径、项目上下文  
**输出**: CodeAnalysisResult（结构化分析结果）

**核心能力**:
```python
class AnalyzerAgent:
    capabilities = [
        "AST解析",           # Java/TypeScript/Python AST
        "依赖分析",          # 构造函数注入、字段注入
        "复杂度计算",        # 圈复杂度、认知复杂度
        "风险识别",          # 空指针、边界条件
        "测试策略推荐"       # 单元/集成/契约测试
    ]
```

#### 1.3.2 Generator Agent（生成专家）

**职责**:
- 基于分析结果生成测试代码
- 选择合适的测试模板
- 生成 Mock 对象和测试数据
- 确保测试可执行性

**输入**: CodeAnalysisResult、测试配置  
**输出**: GeneratedTest（测试代码 + 元数据）

**核心能力**:
```python
class GeneratorAgent:
    capabilities = [
        "模板选择",          # 基于代码类型选择模板
        "Mock生成",          # Mockito/Vitest mock
        "测试数据生成",      # 边界值、正常值
        "断言生成",          # 基于返回类型
        "场景覆盖"           # Happy path + Edge cases
    ]
```

#### 1.3.3 Reviewer Agent（审查专家）

**职责**:
- 检查测试代码质量
- 验证测试覆盖率
- 识别测试反模式
- 提供改进建议

**输入**: GeneratedTest、源代码  
**输出**: ReviewResult（评分 + 问题列表 + 建议）

**核心能力**:
```python
class ReviewerAgent:
    capabilities = [
        "代码质量检查",      # 命名、结构、可读性
        "覆盖率验证",        # 行覆盖、分支覆盖
        "反模式检测",        # 硬编码、重复断言
        "断言有效性",        # 避免无意义断言
        "最佳实践建议"       # 测试命名、隔离性
    ]
```

#### 1.3.4 Fixer Agent（修复专家）

**职责**:
- 根据审查结果修复问题
- 处理测试执行失败
- 优化测试性能
- 合并用户修改

**输入**: ReviewResult、执行结果  
**输出**: FixedTest（修复后的测试代码）

**核心能力**:
```python
class FixerAgent:
    capabilities = [
        "编译错误修复",      # 导入、类型错误
        "运行时错误修复",    # 空指针、Mock问题
        "断言修正",          # 预期值调整
        "性能优化",          # 减少重复初始化
        "冲突合并"           # 保留用户修改
    ]
```

### 1.4 详细任务分解

#### 任务 1.4.1: Agent 基类设计

**时间预估**: 2天  
**详细内容**:
1. 定义 `BaseAgent` 抽象类
2. 实现 Agent 生命周期管理
3. 定义 Agent 通信协议
4. 实现 Agent 能力注册机制

```python
# src/ut_agent/agents/base.py
class BaseAgent(ABC):
    name: str
    capabilities: List[str]
    memory: AgentMemory
    
    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        pass
    
    def register_capability(self, capability: str, handler: Callable):
        pass
```

#### 任务 1.4.2: Analyzer Agent 实现

**时间预估**: 3天  
**详细内容**:
1. 重构现有 `code_analyzer.py` 为 Agent 模式
2. 增强依赖分析能力
3. 实现测试策略推荐
4. 添加复杂度分析

#### 任务 1.4.3: Generator Agent 实现

**时间预估**: 3天  
**详细内容**:
1. 重构现有 `test_generator.py` 为 Agent 模式
2. 集成模板选择逻辑
3. 增强 Mock 生成能力
4. 实现测试数据生成器

#### 任务 1.4.4: Reviewer Agent 实现

**时间预估**: 3天  
**详细内容**:
1. 实现测试代码质量检查器
2. 实现反模式检测器
3. 实现覆盖率验证器
4. 实现改进建议生成器

#### 任务 1.4.5: Fixer Agent 实现

**时间预估**: 3天  
**详细内容**:
1. 实现错误诊断器
2. 实现自动修复策略
3. 实现冲突合并器
4. 实现性能优化器

#### 任务 1.4.6: Orchestrator 实现

**时间预估**: 4天  
**详细内容**:
1. 实现 Agent 调度器
2. 实现任务分配策略
3. 实现 Agent 间通信
4. 实现工作流编排

```python
# src/ut_agent/agents/orchestrator.py
class Orchestrator:
    agents: Dict[str, BaseAgent]
    workflow: WorkflowGraph
    
    async def run(self, task: Task) -> Result:
        # 1. Analyzer 分析代码
        analysis = await self.agents['analyzer'].execute(task)
        
        # 2. Generator 生成测试
        test = await self.agents['generator'].execute(analysis)
        
        # 3. Reviewer 审查质量
        review = await self.agents['reviewer'].execute(test)
        
        # 4. 如果需要修复，调用 Fixer
        if review.needs_fix:
            test = await self.agents['fixer'].execute(review)
        
        return test
```

### 1.5 依赖关系

```
1.4.1 (Agent基类) 
  ├── 1.4.2 (Analyzer)
  ├── 1.4.3 (Generator)
  ├── 1.4.4 (Reviewer)
  └── 1.4.5 (Fixer)
        └── 1.4.6 (Orchestrator)
```

### 1.6 完成标准

- [ ] 四个 Agent 可独立运行
- [ ] Agent 间通信正常
- [ ] Orchestrator 可协调工作流
- [ ] 支持 Agent 能力扩展
- [ ] 测试覆盖率 > 85%

### 1.7 测试用例

| ID | 测试场景 | 预期结果 |
|----|----------|----------|
| T1 | Analyzer 分析 Spring Service | 正确识别依赖和可测试方法 |
| T2 | Generator 生成测试 | 生成可编译执行的测试代码 |
| T3 | Reviewer 检测反模式 | 识别硬编码和重复断言 |
| T4 | Fixer 修复编译错误 | 正确添加缺失导入 |
| T5 | 完整工作流 | 从分析到生成测试全流程通过 |

---

## 功能二：Agent 记忆系统

### 2.1 功能概述

**任务描述**: 实现 Agent 记忆系统，支持学习历史生成偏好、上下文保持、错误恢复

**优先级**: P0  
**时间预估**: 2周  
**计划完成时间**: 第5周  

### 2.2 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Memory System                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Short-term │  │   Long-term  │  │   Semantic   │       │
│  │    Memory    │  │    Memory    │  │    Memory    │       │
│  │  (会话记忆)   │  │  (持久记忆)   │  │  (语义记忆)   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│         │                 │                 │                │
│         └─────────────────┼─────────────────┘                │
│                           │                                  │
│                    ┌──────▼──────┐                          │
│                    │   Memory    │                          │
│                    │   Manager   │                          │
│                    └──────┬──────┘                          │
│                           │                                  │
│  ┌────────────────────────┼────────────────────────┐        │
│  │                        │                        │        │
│  ▼                        ▼                        ▼        │
│ Analyzer            Generator               Reviewer        │
│ Memory              Memory                  Memory          │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 记忆类型定义

#### 2.3.1 短期记忆 (Short-term Memory)

**用途**: 当前会话上下文保持

**存储内容**:
```python
class ShortTermMemory:
    session_id: str
    current_task: Task
    conversation_history: List[Message]
    working_context: Dict[str, Any]
    temp_results: Dict[str, Any]
    
    # TTL: 会话结束自动清理
```

**实现方式**: 内存存储 + Redis 可选

#### 2.3.2 长期记忆 (Long-term Memory)

**用途**: 持久化历史经验和偏好

**存储内容**:
```python
class LongTermMemory:
    # 用户偏好
    user_preferences: Dict[str, Any]
    # 历史生成记录
    generation_history: List[GenerationRecord]
    # 错误修复记录
    fix_history: List[FixRecord]
    # 成功模式
    success_patterns: List[Pattern]
    
    # 持久化到本地文件
```

**实现方式**: SQLite + JSON 文件

#### 2.3.3 语义记忆 (Semantic Memory)

**用途**: 知识检索和相似性匹配

**存储内容**:
```python
class SemanticMemory:
    # 向量嵌入
    embeddings: np.ndarray
    # 代码片段库
    code_snippets: List[CodeSnippet]
    # 测试模式库
    test_patterns: List[TestPattern]
    # 相似度索引
    similarity_index: faiss.Index
```

**实现方式**: FAISS / Chroma 向量数据库

### 2.4 详细任务分解

#### 任务 2.4.1: 记忆数据结构设计

**时间预估**: 1天  
**详细内容**:
1. 定义 `MemoryEntry` 基类
2. 定义各类记忆的数据结构
3. 设计记忆索引结构
4. 定义记忆查询接口

```python
# src/ut_agent/memory/models.py
@dataclass
class MemoryEntry:
    id: str
    timestamp: datetime
    agent_name: str
    content: Any
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None

@dataclass
class GenerationRecord(MemoryEntry):
    source_file: str
    test_file: str
    coverage_achieved: float
    patterns_used: List[str]
    user_feedback: Optional[str]
```

#### 任务 2.4.2: 短期记忆实现

**时间预估**: 2天  
**详细内容**:
1. 实现会话管理
2. 实现上下文存储
3. 实现自动清理机制
4. 实现 LRU 淘汰策略

```python
# src/ut_agent/memory/short_term.py
class ShortTermMemoryManager:
    def __init__(self, max_sessions: int = 100):
        self.sessions: Dict[str, SessionContext] = {}
        self.max_sessions = max_sessions
    
    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = SessionContext()
        return session_id
    
    def get_context(self, session_id: str) -> SessionContext:
        return self.sessions.get(session_id)
    
    def add_message(self, session_id: str, message: Message):
        self.sessions[session_id].history.append(message)
```

#### 任务 2.4.3: 长期记忆实现

**时间预估**: 3天  
**详细内容**:
1. 实现持久化存储（SQLite）
2. 实现用户偏好学习
3. 实现历史记录管理
4. 实现模式提取和存储

```python
# src/ut_agent/memory/long_term.py
class LongTermMemoryManager:
    def __init__(self, storage_path: Path):
        self.db_path = storage_path / "memory.db"
        self._init_db()
    
    def save_generation(self, record: GenerationRecord):
        # 保存生成记录
        pass
    
    def learn_preference(self, key: str, value: Any):
        # 学习用户偏好
        pass
    
    def get_similar_generations(self, query: str, k: int = 5):
        # 检索相似历史记录
        pass
```

#### 任务 2.4.4: 语义记忆实现

**时间预估**: 3天  
**详细内容**:
1. 集成 Embedding 模型
2. 实现向量存储
3. 实现相似度检索
4. 实现知识库管理

```python
# src/ut_agent/memory/semantic.py
class SemanticMemoryManager:
    def __init__(self, embedding_model: str = "text-embedding-3-small"):
        self.embeddings = OpenAIEmbeddings(model=embedding_model)
        self.vector_store = Chroma(
            embedding_function=self.embeddings,
            persist_directory=".ut-agent/vectors"
        )
    
    def add_pattern(self, pattern: TestPattern):
        self.vector_store.add_texts(
            texts=[pattern.to_text()],
            metadatas=[pattern.metadata]
        )
    
    def find_similar_patterns(self, query: str, k: int = 5):
        return self.vector_store.similarity_search(query, k=k)
```

#### 任务 2.4.5: 记忆管理器集成

**时间预估**: 2天  
**详细内容**:
1. 实现统一记忆管理器
2. 实现记忆检索策略
3. 实现记忆更新机制
4. 集成到 Agent 基类

```python
# src/ut_agent/memory/manager.py
class MemoryManager:
    def __init__(self):
        self.short_term = ShortTermMemoryManager()
        self.long_term = LongTermMemoryManager()
        self.semantic = SemanticMemoryManager()
    
    def remember(self, agent: str, content: Any, memory_type: str):
        # 存储记忆
        pass
    
    def recall(self, agent: str, query: str, memory_types: List[str]):
        # 检索记忆
        pass
    
    def learn(self, feedback: Feedback):
        # 从反馈学习
        pass
```

#### 任务 2.4.6: 偏好学习系统

**时间预估**: 2天  
**详细内容**:
1. 实现偏好收集
2. 实现偏好分析
3. 实现偏好应用
4. 实现偏好可视化

```python
# src/ut_agent/memory/preference.py
class PreferenceLearner:
    def collect_preference(self, action: str, outcome: str, feedback: str):
        # 收集偏好数据
        pass
    
    def analyze_preferences(self) -> Dict[str, Any]:
        # 分析偏好模式
        pass
    
    def apply_preferences(self, context: Dict) -> Dict:
        # 应用偏好到生成过程
        pass
```

### 2.5 依赖关系

```
2.4.1 (数据结构)
  ├── 2.4.2 (短期记忆)
  ├── 2.4.3 (长期记忆)
  └── 2.4.4 (语义记忆)
        └── 2.4.5 (管理器集成)
              └── 2.4.6 (偏好学习)
```

### 2.6 完成标准

- [ ] 三种记忆类型正常工作
- [ ] 记忆持久化正确
- [ ] 相似性检索准确率 > 80%
- [ ] 偏好学习有效
- [ ] 支持 Agent 间记忆共享

### 2.7 测试用例

| ID | 测试场景 | 预期结果 |
|----|----------|----------|
| T1 | 会话上下文保持 | 多轮对话上下文正确传递 |
| T2 | 历史记录检索 | 检索到相似历史生成记录 |
| T3 | 偏好学习 | 用户偏好正确学习和应用 |
| T4 | 错误恢复 | 从中断点恢复执行 |
| T5 | 知识复用 | 相似代码复用历史测试模式 |

---

## 功能三：智能测试选择

### 3.1 功能概述

**任务描述**: 基于变更影响分析，智能选择需要生成/更新的测试，避免全量生成

**优先级**: P1  
**时间预估**: 2周  
**计划完成时间**: 第7周  

### 3.2 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│              Intelligent Test Selection System               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │    Change    │    │   Impact     │    │    Test      │   │
│  │   Detector   │───▶│   Analyzer   │───▶│   Selector   │   │
│  │  (变更检测)   │    │  (影响分析)   │    │  (测试选择)   │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│         │                   │                   │            │
│         └───────────────────┼───────────────────┘            │
│                             │                                │
│                      ┌──────▼──────┐                        │
│                      │  Priority   │                        │
│                      │  Calculator │                        │
│                      │ (优先级计算) │                        │
│                      └─────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 核心组件设计

#### 3.3.1 变更检测器 (Change Detector)

**职责**: 检测代码变更，识别变更的方法和类

```python
# src/ut_agent/selection/change_detector.py
class ChangeDetector:
    def __init__(self, repo_path: Path):
        self.repo = git.Repo(repo_path)
    
    def detect_changes(self, base_ref: str = "HEAD~1") -> ChangeSet:
        """检测相对于 base_ref 的变更"""
        changes = ChangeSet()
        
        for diff in self.repo.head.commit.diff(base_ref):
            if diff.a_path.endswith(('.java', '.ts', '.vue', '.py')):
                change = FileChange(
                    path=diff.a_path,
                    change_type=diff.change_type,
                    old_content=diff.a_blob.data_stream.read(),
                    new_content=diff.b_blob.data_stream.read()
                )
                changes.add(change)
        
        return changes
    
    def detect_method_changes(self, file_change: FileChange) -> List[MethodChange]:
        """检测方法级别的变更"""
        old_methods = self._parse_methods(file_change.old_content)
        new_methods = self._parse_methods(file_change.new_content)
        
        method_changes = []
        for method in new_methods:
            if method.signature not in old_methods:
                method_changes.append(MethodChange(method, ChangeType.ADDED))
            elif method.body != old_methods[method.signature].body:
                method_changes.append(MethodChange(method, ChangeType.MODIFIED))
        
        for method in old_methods:
            if method.signature not in new_methods:
                method_changes.append(MethodChange(method, ChangeType.DELETED))
        
        return method_changes
```

#### 3.3.2 影响分析器 (Impact Analyzer)

**职责**: 分析变更的影响范围，识别受影响的测试

```python
# src/ut_agent/selection/impact_analyzer.py
class ImpactAnalyzer:
    def __init__(self, project_index: ProjectIndex):
        self.index = project_index
    
    def analyze_impact(self, changes: ChangeSet) -> ImpactReport:
        """分析变更影响"""
        impact = ImpactReport()
        
        for change in changes:
            # 直接影响：变更文件本身
            direct_impact = self._analyze_direct_impact(change)
            impact.add_direct(direct_impact)
            
            # 间接影响：依赖此文件的代码
            indirect_impact = self._analyze_indirect_impact(change)
            impact.add_indirect(indirect_impact)
            
            # 测试影响：需要更新的测试
            test_impact = self._analyze_test_impact(change)
            impact.add_test_impact(test_impact)
        
        return impact
    
    def _analyze_indirect_impact(self, change: FileChange) -> List[IndirectImpact]:
        """分析间接影响 - 谁依赖了变更的代码"""
        dependents = self.index.find_dependents(change.path)
        impacts = []
        
        for dependent in dependents:
            # 分析调用关系
            call_sites = self._find_call_sites(dependent, change)
            if call_sites:
                impacts.append(IndirectImpact(
                    file=dependent,
                    reason=f"调用了变更的方法: {call_sites}"
                ))
        
        return impacts
    
    def _analyze_test_impact(self, change: FileChange) -> List[TestImpact]:
        """分析测试影响"""
        test_file = self._find_test_file(change.path)
        if not test_file:
            return []
        
        impacts = []
        for method_change in change.method_changes:
            test_method = self._find_test_method(test_file, method_change.method)
            if test_method:
                impacts.append(TestImpact(
                    test_file=test_file,
                    test_method=test_method,
                    reason=f"测试方法需要更新: {method_change.method.name}"
                ))
        
        return impacts
```

#### 3.3.3 测试选择器 (Test Selector)

**职责**: 根据影响分析结果选择需要生成/更新的测试

```python
# src/ut_agent/selection/test_selector.py
class TestSelector:
    def __init__(self, strategy: SelectionStrategy = SelectionStrategy.SMART):
        self.strategy = strategy
    
    def select_tests(self, impact: ImpactReport) -> SelectionResult:
        """选择需要执行的测试"""
        selection = SelectionResult()
        
        # 新增代码 → 需要生成新测试
        for change in impact.direct_impacts:
            if change.change_type == ChangeType.ADDED:
                selection.to_generate.append(TestTask(
                    source_file=change.path,
                    task_type=TaskType.GENERATE_NEW
                ))
        
        # 修改代码 → 需要更新测试
        for change in impact.direct_impacts:
            if change.change_type == ChangeType.MODIFIED:
                selection.to_update.append(TestTask(
                    source_file=change.path,
                    test_file=change.test_file,
                    task_type=TaskType.UPDATE_EXISTING
                ))
        
        # 删除代码 → 需要标记废弃测试
        for change in impact.direct_impacts:
            if change.change_type == ChangeType.DELETED:
                selection.to_deprecate.append(TestTask(
                    test_file=change.test_file,
                    task_type=TaskType.DEPRECATE
                ))
        
        # 间接影响 → 需要验证测试
        for indirect in impact.indirect_impacts:
            selection.to_verify.append(TestTask(
                source_file=indirect.file,
                task_type=TaskType.VERIFY
            ))
        
        return selection
    
    def prioritize(self, selection: SelectionResult) -> PrioritizedSelection:
        """优先级排序"""
        prioritized = PrioritizedSelection()
        
        for task in selection.all_tasks:
            priority = self._calculate_priority(task)
            prioritized.add(task, priority)
        
        return prioritized.sorted()
    
    def _calculate_priority(self, task: TestTask) -> Priority:
        """计算优先级"""
        score = 0
        
        # 核心模块优先
        if self._is_core_module(task.source_file):
            score += 30
        
        # 高复杂度优先
        if task.complexity > 10:
            score += 20
        
        # 最近修改优先
        if task.recently_modified:
            score += 15
        
        # 低覆盖率优先
        if task.current_coverage < 0.5:
            score += 25
        
        # 有测试失败历史优先
        if task.has_failure_history:
            score += 10
        
        return Priority(score)
```

#### 3.3.4 优先级计算器 (Priority Calculator)

**职责**: 综合多维度计算测试优先级

```python
# src/ut_agent/selection/priority.py
class PriorityCalculator:
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or {
            "complexity": 0.25,
            "coverage": 0.25,
            "change_frequency": 0.20,
            "business_value": 0.15,
            "failure_history": 0.15
        }
    
    def calculate(self, task: TestTask, context: SelectionContext) -> float:
        """计算综合优先级分数"""
        scores = {}
        
        # 复杂度分数 (越高越优先)
        scores["complexity"] = self._complexity_score(task)
        
        # 覆盖率分数 (越低越优先)
        scores["coverage"] = 1 - task.current_coverage
        
        # 变更频率分数 (越高越优先)
        scores["change_frequency"] = self._change_frequency_score(task, context)
        
        # 业务价值分数
        scores["business_value"] = self._business_value_score(task, context)
        
        # 失败历史分数
        scores["failure_history"] = self._failure_history_score(task, context)
        
        # 加权求和
        total = sum(
            scores[key] * self.weights[key]
            for key in self.weights
        )
        
        return total
```

### 3.4 详细任务分解

#### 任务 3.4.1: 变更检测实现

**时间预估**: 2天  
**详细内容**:
1. 集成 GitPython 进行差异分析
2. 实现文件级变更检测
3. 实现方法级变更检测
4. 实现变更类型分类

#### 任务 3.4.2: 影响分析实现

**时间预估**: 3天  
**详细内容**:
1. 实现依赖关系遍历
2. 实现调用链分析
3. 实现测试文件映射
4. 实现影响范围计算

#### 任务 3.4.3: 测试选择策略实现

**时间预估**: 2天  
**详细内容**:
1. 实现选择策略接口
2. 实现保守策略（影响范围最大化）
3. 实现激进策略（最小变更）
4. 实现智能策略（平衡模式）

```python
class SelectionStrategy(Enum):
    CONSERVATIVE = "conservative"  # 保守：影响范围最大化
    AGGRESSIVE = "aggressive"      # 激进：最小变更
    SMART = "smart"                # 智能：平衡模式
```

#### 任务 3.4.4: 优先级计算实现

**时间预估**: 2天  
**详细内容**:
1. 实现多维度评分
2. 实现权重配置
3. 实现优先级排序
4. 实现优先级可视化

#### 任务 3.4.5: CLI 集成

**时间预估**: 1天  
**详细内容**:
1. 添加 `--incremental` 参数
2. 添加 `--base-ref` 参数
3. 添加 `--strategy` 参数
4. 实现选择结果预览

```bash
# 使用示例
ut-agent generate --incremental --base-ref HEAD~5 --strategy smart
```

### 3.5 依赖关系

```
3.4.1 (变更检测)
  └── 3.4.2 (影响分析)
        └── 3.4.3 (选择策略)
              └── 3.4.4 (优先级计算)
                    └── 3.4.5 (CLI集成)
```

### 3.6 完成标准

- [ ] 变更检测准确率 > 95%
- [ ] 影响分析覆盖率 > 90%
- [ ] 选择策略可配置
- [ ] 优先级计算合理
- [ ] CLI 命令正常工作

### 3.7 测试用例

| ID | 测试场景 | 预期结果 |
|----|----------|----------|
| T1 | 新增方法检测 | 正确识别新增方法 |
| T2 | 修改方法检测 | 正确识别修改的方法 |
| T3 | 依赖影响分析 | 正确识别受影响的调用方 |
| T4 | 测试选择 | 选择正确的测试任务 |
| T5 | 优先级排序 | 高优先级任务排在前面 |

---

## 四、功能依赖关系图

```
┌─────────────────────────────────────────────────────────────┐
│                     功能依赖关系                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   功能一: Multi-Agent 架构                                   │
│        │                                                     │
│        ├──▶ 功能二: Agent 记忆系统                           │
│        │         (Agent 需要记忆能力)                        │
│        │                                                     │
│        └──▶ 功能三: 智能测试选择                             │
│                  (选择结果驱动 Agent 任务分配)                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 五、里程碑与交付物

| 里程碑 | 时间 | 交付物 |
|--------|------|--------|
| M1 | 第3周 | Multi-Agent 架构完成 |
| M2 | 第5周 | Agent 记忆系统完成 |
| M3 | 第7周 | 智能测试选择完成 |
| M4 | 第8周 | 集成测试与文档 |

---

## 六、风险与应对

| 风险 | 可能性 | 影响 | 应对措施 |
|------|--------|------|----------|
| Agent 通信复杂度 | 中 | 高 | 使用成熟的消息队列模式 |
| 记忆系统性能 | 中 | 中 | 实现分层缓存策略 |
| 变更检测误报 | 低 | 中 | 多维度验证机制 |
| LLM 调用成本 | 中 | 中 | 实现智能缓存和批处理 |

---

## 七、资源需求

**人力**:
- 核心开发：1人
- 测试：0.5人

**工具/服务**:
- OpenAI Embeddings API
- FAISS / Chroma 向量数据库
- SQLite 持久化存储

---

## 八、验收标准

**功能验收**:
- Multi-Agent 协作正常
- 记忆系统持久化正确
- 智能选择准确率 > 90%

**质量验收**:
- 代码覆盖率 > 80%
- 无严重 Bug
- 性能：选择计算 < 5s

**文档验收**:
- 架构设计文档完整
- API 文档完整
- 使用示例可用

---

**计划制定日期**: 2026-02-16  
**计划版本**: v1.0  
**下次评审**: 每周进行进度评审
