# UT-Agent VS Code Extension

AI驱动的单元测试生成 VS Code 插件 - 支持 Java/Vue/React/TypeScript

## 功能特性

- 🧪 **一键生成测试**: 右键点击文件即可生成单元测试
- 🎯 **覆盖率驱动**: 支持设置覆盖率目标并自动迭代优化
- 🤖 **多模型支持**: OpenAI GPT-4、DeepSeek、本地 Ollama
- 📊 **覆盖率报告**: 内置覆盖率报告查看器
- ⚙️ **灵活配置**: 丰富的配置选项，支持自定义测试框架

## 安装

### 从 VS Code 市场安装

1. 打开 VS Code
2. 进入扩展面板 (Ctrl+Shift+X)
3. 搜索 "UT-Agent"
4. 点击安装

### 从源码安装

```bash
cd vscode-extension
npm install
npm run compile
# 按 F5 启动调试
```

## 配置

打开 VS Code 设置 (Ctrl+,)，搜索 "UT-Agent" 进行配置：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `ut-agent.llm.provider` | LLM 提供商 | `openai` |
| `ut-agent.llm.apiKey` | API Key | - |
| `ut-agent.coverage.target` | 覆盖率目标 | `80` |
| `ut-agent.java.testFramework` | Java 测试框架 | `junit5` |
| `ut-agent.frontend.testFramework` | 前端测试框架 | `vitest` |

## 使用

### 生成单元测试

1. 在编辑器中右键点击 Java/TypeScript/Vue 文件
2. 选择 "Generate Unit Test"
3. 等待生成完成

或使用快捷键：`Ctrl+Shift+T`

### 查看覆盖率报告

1. 点击侧边栏 "UT-Agent" 图标
2. 点击 "查看覆盖率报告"
3. 选择要查看的报告

## 依赖

- 需要安装 [UT-Agent CLI](https://github.com/your-org/ut-agent) 工具
- Python 3.11+

```bash
pip install ut-agent
```

## 开发

```bash
# 安装依赖
npm install

# 编译
npm run compile

# 调试
按 F5 启动 Extension Development Host

# 打包
npm run package
```

## 许可证

MIT
