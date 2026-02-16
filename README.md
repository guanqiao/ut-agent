# UT-Agent: AI驱动的单元测试生成Agent

基于最新 Python LangGraph 构建的智能 Agent，能够自动分析 Java/Vue/React/TypeScript 项目代码并生成高质量单元测试，支持设置覆盖率目标并持续迭代优化。

## 特性

- **多语言支持**: Java (JUnit 5)、Vue/React/TypeScript (Jest/Vitest)
- **智能迭代**: 根据覆盖率目标自动补充测试用例
- **多模型支持**: OpenAI GPT-4、DeepSeek、本地 Ollama 模型
- **双模式**: CLI 命令行 + Streamlit Web UI
- **覆盖率驱动**: 支持 JaCoCo、Istanbul/V8 覆盖率报告解析
- **增量测试**: 基于 Git 变更智能选择需要测试的代码
- **变异测试**: 集成 PIT (Java) 和 Stryker (JS/TS) 变异测试
- **HTML 报告**: 生成美观的覆盖率 HTML 报告
- **智能缓存**: AST 缓存和 LLM 响应缓存提升性能
- **IDE 插件**: 支持 VSCode 和 JetBrains 系列 IDE

## 快速开始

### 安装

```bash
pip install ut-agent
```

或使用 Poetry:

```bash
poetry add ut-agent
```

### CLI 使用

```bash
# Java 项目
ut-agent generate --project ./my-java-project --type java --coverage-target 80

# Vue 项目
ut-agent generate --project ./my-vue-app --type vue --coverage-target 70

# 增量模式（仅对变更代码生成测试）
ut-agent generate --project ./my-project --incremental --base HEAD~1 --head HEAD

# 生成 HTML 报告
ut-agent generate --project ./my-project --html-report

# 交互式模式
ut-agent interactive

# CI 模式（非交互式，输出 JSON）
ut-agent ci --project ./my-project --output json --fail-on-coverage

# 运行变异测试
ut-agent mutation --project ./my-project --target-classes com.example.* --suggest
```

### Web UI

```bash
ut-agent ui
```

访问 http://localhost:8501 使用 Web 界面。

## 配置

创建 `.env` 文件:

```env
# OpenAI
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4

# DeepSeek
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# Ollama (本地模型)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# 默认配置
DEFAULT_LLM_PROVIDER=openai
DEFAULT_COVERAGE_TARGET=80
MAX_ITERATIONS=5

# 缓存配置
LLM_CACHE_MAX_SIZE=1000
LLM_CACHE_TTL=3600
AST_CACHE_MAX_SIZE=500
AST_CACHE_TTL=86400
```

## 架构

基于 LangGraph State Graph 实现迭代优化工作流:

```
[代码分析] → [测试生成] → [测试执行] → [覆盖率检查] → [决策节点]
                                              ↓
                                    [达标] → [结束]
                                    [未达标] → [分析缺口] → [补充测试] → [循环]
```

### 核心组件

- **Analyzer Agent**: 代码分析和可测试性评估
- **Generator Agent**: 基于 LLM 生成测试用例
- **Fixer Agent**: 自动修复失败的测试
- **Reviewer Agent**: 代码审查和质量评分
- **Orchestrator**: 工作流协调和状态管理

## 高级功能

### 1. 增量测试生成

仅对 Git 变更的代码生成测试，大幅提升效率：

```bash
ut-agent generate \
  --project ./my-project \
  --incremental \
  --base main \
  --head feature-branch
```

### 2. 变异测试

检测测试用例的有效性：

```bash
ut-agent mutation \
  --project ./my-java-project \
  --target-classes com.example.service.* \
  --target-tests *Test \
  --suggest
```

### 3. 测试选择

基于代码变更影响分析智能选择测试：

```python
from ut_agent.selection import TestSelector

selector = TestSelector(project_path="./my-project")
selected_tests = selector.select_tests_for_changes(
    base_ref="HEAD~5",
    head_ref="HEAD"
)
```

### 4. 内存系统

支持长期记忆和偏好学习：

- **短期记忆**: 当前会话的上下文
- **长期记忆**: 跨会话的用户偏好和项目知识
- **语义记忆**: 代码片段和测试模式的知识库

## CI/CD 集成

### GitHub Actions

```yaml
name: UT-Agent Test Generation

on:
  pull_request:
    branches: [ main ]

jobs:
  generate-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run UT-Agent
        uses: ut-agent/action@v1
        with:
          project-path: .
          coverage-target: 80
          incremental: true
          html-report: true
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

### GitLab CI

```yaml
generate-tests:
  stage: test
  image: python:3.11
  script:
    - pip install ut-agent
    - ut-agent ci --project . --coverage-target 80 --output json
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml
```

## IDE 插件

### VSCode

在 VSCode 扩展市场搜索 "UT-Agent" 安装。

功能：
- 侧边栏测试生成
- 覆盖率可视化
- 一键生成测试

### JetBrains

在插件市场搜索 "UT-Agent" 安装。

功能：
- 右键生成测试
- 工具窗口查看报告
- 覆盖率高亮显示

## API 使用

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

# 创建图并运行
graph = create_test_generation_graph()

async for event in graph.astream(initial_state):
    for node_name, node_data in event.items():
        print(f"[{node_name}] {node_data.get('message', '')}")
```

## 开发

```bash
# 克隆仓库
git clone https://github.com/your-org/ut-agent.git
cd ut-agent

# 安装依赖
poetry install

# 运行测试
poetry run pytest

# 代码检查
poetry run black src tests
poetry run isort src tests
poetry run mypy src

# 本地运行
poetry run ut-agent --help
```

## 项目结构

```
ut-agent/
├── src/ut_agent/          # 核心源代码
│   ├── agents/            # AI Agent 实现
│   ├── graph/             # LangGraph 工作流
│   ├── tools/             # 工具函数
│   ├── models/            # 数据模型
│   ├── memory/            # 记忆系统
│   ├── selection/         # 测试选择
│   ├── reporting/         # 报告生成
│   └── ui/                # Web UI
├── tests/                 # 测试代码
├── docs/                  # 文档
├── ci-templates/          # CI/CD 模板
├── vscode-extension/      # VSCode 插件
├── jetbrains-plugin/      # JetBrains 插件
└── README.md
```

## 版本历史

- **v0.1.0** (2024-02-17)
  - 初始版本发布
  - 支持 Java/Vue/React/TypeScript
  - CLI 和 Web UI
  - 增量测试生成
  - 变异测试支持
  - HTML 报告生成
  - IDE 插件支持

## 贡献

欢迎提交 Issue 和 Pull Request！

## License

MIT

---

**文档**: [docs/api.md](docs/api.md) | **问题反馈**: [GitHub Issues](https://github.com/your-org/ut-agent/issues)
