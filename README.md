# UT-Agent: AI驱动的单元测试生成Agent

基于最新 Python LangGraph 构建的智能 Agent，能够自动分析 Java/Vue/React/TypeScript 项目代码并生成高质量单元测试，支持设置覆盖率目标并持续迭代优化。

## 特性

- **多语言支持**: Java (JUnit 5)、Vue/React/TypeScript (Jest/Vitest)
- **智能迭代**: 根据覆盖率目标自动补充测试用例
- **多模型支持**: OpenAI GPT-4、DeepSeek、本地 Ollama 模型
- **双模式**: CLI 命令行 + Streamlit Web UI
- **覆盖率驱动**: 支持 JaCoCo、Istanbul/V8 覆盖率报告解析

## 快速开始

### 安装

```bash
pip install ut-agent
```

### CLI 使用

```bash
# Java 项目
ut-agent generate --project ./my-java-project --type java --coverage-target 80

# Vue 项目
ut-agent generate --project ./my-vue-app --type vue --coverage-target 70

# 交互式模式
ut-agent interactive
```

### Web UI

```bash
ut-agent ui
```

## 配置

创建 `.env` 文件:

```env
# OpenAI
OPENAI_API_KEY=your_openai_key

# DeepSeek
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_BASE_URL=https://api.deepseek.com

# Ollama (本地模型)
OLLAMA_BASE_URL=http://localhost:11434
```

## 架构

基于 LangGraph State Graph 实现迭代优化工作流:

```
[代码分析] → [测试生成] → [测试执行] → [覆盖率检查] → [决策节点]
                                              ↓
                                    [达标] → [结束]
                                    [未达标] → [分析缺口] → [补充测试] → [循环]
```

## 开发

```bash
poetry install
poetry run ut-agent --help
```

## License

MIT
