# UT-Agent CI/CD 集成指南

本目录包含 UT-Agent 的 CI/CD 集成模板，支持 GitHub Actions 和 GitLab CI。

## 目录结构

```
ci-templates/
├── github/
│   └── ut-agent.yml          # GitHub Actions 工作流模板
├── gitlab/
│   └── .gitlab-ci.yml        # GitLab CI 配置模板
└── README.md                  # 本文档
```

## GitHub Actions 集成

### 快速开始

1. 将 `github/ut-agent.yml` 复制到项目的 `.github/workflows/` 目录：

```bash
mkdir -p .github/workflows
cp ci-templates/github/ut-agent.yml .github/workflows/ut-agent.yml
```

2. 配置 GitHub Secrets：

| Secret 名称 | 说明 |
|------------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 (可选) |

3. 推送代码，工作流将自动运行。

### 工作流说明

工作流包含以下阶段：

1. **detect-changes**: 检测变更的文件
2. **generate-java-tests**: 为 Java 文件生成测试
3. **generate-frontend-tests**: 为前端文件生成测试
4. **coverage-badge**: 更新覆盖率徽章

### 触发条件

- Pull Request 到 `main` 或 `develop` 分支
- Push 到 `main` 分支
- 手动触发 (`workflow_dispatch`)

### 手动触发参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `coverage_target` | 80 | 覆盖率目标 |
| `max_iterations` | 5 | 最大迭代次数 |

### PR 评论示例

工作流会在 PR 中自动评论覆盖率报告：

```markdown
## 🧪 UT-Agent Test Generation Report

| Metric | Value |
|--------|-------|
| **Coverage** | 85.5% |
| **Target** | 80% |
| **Status** | ✅ Passed |

### Generated Tests
- `src/test/java/com/example/UserServiceTest.java`
- `src/test/java/com/example/OrderServiceTest.java`
```

## GitLab CI 集成

### 快速开始

1. 将 `gitlab/.gitlab-ci.yml` 复制到项目根目录：

```bash
cp ci-templates/gitlab/.gitlab-ci.yml .gitlab-ci.yml
```

2. 配置 GitLab CI/CD Variables：

| 变量名称 | 说明 |
|---------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 (可选) |
| `GITLAB_TOKEN` | GitLab 访问令牌 (用于 MR 评论) |

3. 推送代码，流水线将自动运行。

### 流水线阶段

1. **detect**: 检测变更文件
2. **generate**: 生成测试
3. **test**: 运行测试
4. **report**: 生成报告

### 配置变量

可在 `.gitlab-ci.yml` 中修改以下变量：

```yaml
variables:
  COVERAGE_TARGET: "80"      # 覆盖率目标
  MAX_ITERATIONS: "5"        # 最大迭代次数
  UT_AGENT_VERSION: "latest" # UT-Agent 版本
```

## CLI CI 模式

UT-Agent 提供专门的 CI 模式命令：

### 基本用法

```bash
ut-agent ci ./my-project \
  --coverage-target 80 \
  --output json \
  --output-file result.json
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `--coverage-target, -c` | 覆盖率目标 (默认: 80) |
| `--output, -o` | 输出格式: json/markdown/summary |
| `--output-file` | 输出文件路径 |
| `--fail-on-coverage` | 覆盖率低于目标时返回非零退出码 |
| `--incremental, -inc` | 增量模式：仅对变更代码生成测试 |
| `--base, -b` | 基准 Git 引用 |

### 输出示例

```json
{
  "status": "completed",
  "success": true,
  "coverage": 85.5,
  "target_coverage": 80.0,
  "generated_tests": [
    {
      "test_file_path": "src/test/java/com/example/UserServiceTest.java",
      "source_file": "src/main/java/com/example/UserService.java"
    }
  ],
  "coverage_gaps": [],
  "timestamp": "2026-02-16T10:30:00",
  "duration_seconds": 45.2
}
```

### 退出码

| 退出码 | 说明 |
|--------|------|
| 0 | 成功 |
| 1 | 测试生成失败 |
| 2 | 覆盖率低于目标 (使用 `--fail-on-coverage`) |
| 3 | 配置错误 |
| 4 | 环境错误 |

## 变异测试集成

### CLI 命令

```bash
ut-agent mutation ./my-project \
  --target-classes "com.example.*" \
  --target-tests "*Test" \
  --suggest
```

### CI 集成

在 GitHub Actions 中添加变异测试步骤：

```yaml
- name: Run Mutation Tests
  run: |
    ut-agent mutation . --output json > mutation-result.json
    
- name: Upload Mutation Report
  uses: actions/upload-artifact@v4
  with:
    name: mutation-report
    path: mutation-result.json
```

## 最佳实践

### 1. 增量模式

对于大型项目，使用增量模式只对变更代码生成测试：

```bash
ut-agent ci ./my-project --incremental --base origin/main
```

### 2. 覆盖率门禁

在 CI 中设置覆盖率门禁：

```yaml
- name: Check Coverage
  run: |
    ut-agent ci . --fail-on-coverage --coverage-target 80
```

### 3. 缓存依赖

在 GitHub Actions 中缓存依赖：

```yaml
- name: Cache Maven packages
  uses: actions/cache@v4
  with:
    path: ~/.m2
    key: ${{ runner.os }}-m2-${{ hashFiles('**/pom.xml') }}
```

### 4. 并行执行

对于多模块项目，可以并行执行：

```yaml
strategy:
  matrix:
    module: [module-a, module-b, module-c]
steps:
  - name: Generate tests for ${{ matrix.module }}
    run: ut-agent ci ./${{ matrix.module }}
```

## 故障排除

### 常见问题

1. **API 密钥未配置**
   ```
   Error: OPENAI_API_KEY not set
   ```
   解决：在 CI/CD 变量中配置 API 密钥。

2. **覆盖率报告未找到**
   ```
   No coverage report found
   ```
   解决：确保项目配置了 JaCoCo (Java) 或 Istanbul (前端)。

3. **超时错误**
   ```
   Timeout waiting for test generation
   ```
   解决：增加 `--max-iterations` 或检查 LLM API 状态。

### 调试模式

启用详细日志：

```bash
ut-agent ci ./my-project --verbose
```

或在 CI 中设置环境变量：

```yaml
env:
  UT_AGENT_DEBUG: "true"
```

## 相关链接

- [UT-Agent 文档](../README.md)
- [JetBrains 插件](../jetbrains-plugin/README.md)
- [变异测试](../docs/mutation-testing.md)
