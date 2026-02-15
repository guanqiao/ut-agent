# UT-Agent JetBrains Plugin

AI驱动的单元测试生成插件，支持 IntelliJ IDEA 和其他 JetBrains IDE。

## 功能特性

- **一键生成测试**: 右键菜单快速生成单元测试
- **多框架支持**: JUnit 5, JUnit 4, TestNG
- **智能 Mock**: 自动推荐 Mockito/PowerMock 配置
- **覆盖率驱动**: 设置目标覆盖率，自动迭代优化
- **Spring Boot 支持**: 自动识别 Spring 注解

## 安装

### 从 Marketplace 安装
1. 打开 `Settings > Plugins > Marketplace`
2. 搜索 "UT-Agent"
3. 点击 Install

### 手动安装
1. 下载最新的 [release](../../releases)
2. 打开 `Settings > Plugins > ⚙️ > Install Plugin from Disk`
3. 选择下载的 `.zip` 文件

## 配置

### LLM 提供商配置

打开 `Settings > Tools > UT-Agent`:

| 配置项 | 说明 |
|--------|------|
| Provider | OpenAI / DeepSeek / Ollama |
| API Key | API 密钥 |
| Base URL | 自定义 API 地址 (可选) |
| Model | 模型名称 |

### 生成设置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| Target Coverage | 80% | 覆盖率目标 |
| Max Iterations | 5 | 最大迭代次数 |
| Test Framework | JUnit 5 | 测试框架 |
| Mock Framework | Mockito | Mock 框架 |

## 使用方法

### 生成测试

1. 在 Java/Kotlin 文件上右键
2. 选择 `UT-Agent > Generate Unit Test`
3. 等待生成完成
4. 测试文件自动打开

### 快捷键

- `Ctrl+Shift+T` (Windows/Linux)
- `Cmd+Shift+T` (macOS)

### 工具窗口

1. 点击右侧边栏 "UT-Agent" 图标
2. 配置 LLM 和覆盖率目标
3. 点击 "Generate Tests" 开始生成

## 项目结构

```
jetbrains-plugin/
├── src/main/
│   ├── kotlin/com/utagent/
│   │   ├── actions/          # 菜单动作
│   │   ├── config/           # 配置界面
│   │   ├── service/          # 服务层
│   │   ├── toolwindow/       # 工具窗口
│   │   ├── ui/               # UI 组件
│   │   └── util/             # 工具类
│   └── resources/META-INF/
│       └── plugin.xml        # 插件配置
├── build.gradle.kts
└── README.md
```

## 开发

### 环境要求

- JDK 17+
- IntelliJ IDEA 2023.2+
- Gradle 8.x

### 构建

```bash
./gradlew buildPlugin
```

### 运行

```bash
./gradlew runIde
```

### 发布

```bash
./gradlew publishPlugin
```

## 版本历史

### 0.1.0
- 初始版本
- 支持基本的测试生成功能
- 支持 OpenAI/DeepSeek/Ollama

## License

MIT
