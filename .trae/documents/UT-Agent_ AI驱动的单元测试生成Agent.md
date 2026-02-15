# UT-Agent: AI驱动的单元测试生成Agent

## 项目概述
基于最新 Python LangChain/LangGraph 构建的智能 Agent，能够自动分析 Java/Vue/React/TypeScript 项目代码并生成高质量单元测试，支持设置覆盖率目标并持续迭代优化。

## 技术架构

### 核心框架
- **LangGraph State Graph**: 实现状态驱动的迭代优化工作流
- **多 LLM 支持**: OpenAI、DeepSeek、本地 Ollama 模型
- **工具链**: Python 3.11+, Pydantic, Typer

### Agent 工作流设计 (State Graph)
```
[开始] → [代码分析] → [测试生成] → [测试执行] → [覆盖率检查] → [决策节点]
                                              ↓
                                    [达标] → [结束]
                                    [未达标] → [分析缺口] → [补充测试] → [循环]
```

### 状态定义 (AgentState)
```python
class AgentState(TypedDict):
    project_path: str           # 项目路径
    project_type: str           # java/vue/react/ts
    target_files: List[str]     # 目标文件列表
    generated_tests: List[Dict] # 生成的测试
    coverage_report: Dict       # 覆盖率报告
    coverage_target: float      # 目标覆盖率
    current_coverage: float     # 当前覆盖率
    iteration_count: int        # 迭代次数
    max_iterations: int         # 最大迭代次数
    status: str                 # 当前状态
```

## 功能模块

### 1. 项目检测模块
- 自动识别项目类型 (Maven/Gradle/Spring Boot, Vue/React/Angular)
- 解析项目结构和依赖
- 识别需要测试的源代码文件

### 2. 代码分析模块
- Java: 使用 javalang 解析 AST
- TypeScript/Vue: 使用 tree-sitter 解析
- 提取类、方法、函数签名和依赖关系

### 3. 测试生成模块
- Java: 生成 JUnit 5 + Mockito 测试
- Frontend: 生成 Jest/Vitest 测试
- 智能 Prompt 工程，包含边界条件、异常处理

### 4. 测试执行模块
- Java: Maven/Gradle 集成，JaCoCo 覆盖率
- Frontend: npm/yarn/pnpm 执行， Istanbul/V8 覆盖率

### 5. 覆盖率迭代优化模块
- 解析 JaCoCo/Istanbul XML/HTML 报告
- 识别未覆盖的分支、行、方法
- 针对性补充测试用例

## 项目结构

```
ut-agent/
├── pyproject.toml              # 项目配置
├── README.md
├── src/
│   └── ut_agent/
│       ├── __init__.py
│       ├── main.py             # CLI 入口
│       ├── config.py           # 配置管理
│       ├── models.py           # LLM 模型管理
│       ├── graph/              # LangGraph 工作流
│       │   ├── __init__.py
│       │   ├── state.py        # 状态定义
│       │   ├── nodes.py        # 节点实现
│       │   └── graph.py        # 图构建
│       ├── tools/              # Agent 工具
│       │   ├── __init__.py
│       │   ├── code_analyzer.py
│       │   ├── test_generator.py
│       │   ├── test_executor.py
│       │   └── coverage_analyzer.py
│       ├── parsers/            # 代码解析器
│       │   ├── __init__.py
│       │   ├── java_parser.py
│       │   └── ts_parser.py
│       └── ui/                 # Web UI
│           ├── __init__.py
│           └── app.py          # Streamlit 应用
├── tests/                      # 项目测试
└── docs/                       # 文档
```

## 核心依赖
```toml
[tool.poetry.dependencies]
python = "^3.11"
langgraph = "^0.2.0"
langchain = "^0.3.0"
langchain-openai = "^0.2.0"
langchain-deepseek = "^0.1.0"
pydantic = "^2.0"
typer = "^0.12.0"
streamlit = "^1.40.0"
javalang = "^0.13.0"
tree-sitter = "^0.23.0"
tree-sitter-typescript = "^0.23.0"
xmltodict = "^0.14.0"
```

## 使用方式

### CLI 模式
```bash
# Java 项目
ut-agent generate --project ./my-java-project --type java --coverage-target 80

# Vue 项目
ut-agent generate --project ./my-vue-app --type vue --coverage-target 70

# 交互式模式
ut-agent interactive
```

### Web UI 模式
```bash
ut-agent ui
```

## 实现计划

### Phase 1: 基础框架 (Day 1-2)
1. 项目初始化和依赖配置
2. LangGraph State Graph 框架搭建
3. 多 LLM 模型管理

### Phase 2: 核心功能 (Day 3-5)
1. 项目类型检测和代码分析
2. 测试生成工具实现
3. 测试执行和覆盖率收集

### Phase 3: 迭代优化 (Day 6-7)
1. 覆盖率分析和缺口识别
2. 迭代补充测试逻辑
3. 状态持久化和恢复

### Phase 4: UI 和 polish (Day 8)
1. Streamlit Web UI
2. CLI 完善
3. 文档和测试

## 验收标准
- [x] 支持 Java + JUnit5 测试生成
- [x] 支持 Vue/React/TypeScript + Jest/Vitest 测试生成
- [x] 支持设置覆盖率目标 (0-100%)
- [x] 自动迭代直到达标或达到最大迭代次数
- [x] CLI 和 Web UI 双模式支持
- [x] 多 LLM 提供商支持