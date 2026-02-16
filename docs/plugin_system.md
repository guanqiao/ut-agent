# UT-Agent 插件系统文档

## 1. 功能描述

UT-Agent 提供了一个灵活的插件系统，用于扩展 LLM（大语言模型）提供商的支持。通过插件系统，用户可以：

- 使用内置的 LLM 提供商（OpenAI、DeepSeek、Ollama）
- 注册自定义的 LLM 提供商
- 动态切换不同的 LLM 提供商

## 2. 插件系统架构

### 核心组件

- **LLMProvider**: 抽象基类，定义了 LLM 提供商的接口
- **具体提供商实现**: 继承自 LLMProvider 的具体类
- **LLMProviderRegistry**: 提供商注册表，管理所有注册的提供商

### 类图

```
┌─────────────────┐
│  LLMProvider   │
├─────────────────┤
│ + name: str     │
│ + requires_api_key: bool │
│ + api_key_setting: str   │
│ + model_setting: str     │
│ + base_url_setting: str  │
│ ─────────────── │
│ + create_model() │
│ + is_available() │
│ + get_config()   │
└─────────────────┘
        ↑
        ├─────────────────────┐
        │                     │
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│OpenAIProvider│     │DeepSeekProvider│     │OllamaProvider│
└───────────────┘     └───────────────┘     └───────────────┘
```

## 3. 使用内置提供商

### 配置

在 `.env` 文件中配置相应的 API 密钥和参数：

```env
# OpenAI
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4

# DeepSeek
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_MODEL=deepseek-chat

# Ollama
OLLAMA_MODEL=llama3
OLLAMA_BASE_URL=http://localhost:11434
```

### 命令行使用

```bash
# 使用默认提供商 (在配置中设置)
ut-agent generate --project ./my-project

# 明确指定提供商
ut-agent generate --project ./my-project --llm openai
ut-agent generate --project ./my-project --llm deepseek
ut-agent generate --project ./my-project --llm ollama
```

## 4. 开发自定义插件

### 步骤 1: 继承 LLMProvider 基类

```python
from ut_agent.utils.llm import LLMProvider

class MyCustomProvider(LLMProvider):
    name = "my_custom"
    requires_api_key = True
    api_key_setting = "my_custom_api_key"
    model_setting = "my_custom_model"
    base_url_setting = "my_custom_base_url"

    def create_model(self, config):
        # 创建并返回 LangChain 聊天模型实例
        api_key = getattr(config, self.api_key_setting)
        model = getattr(config, self.model_setting)
        base_url = getattr(config, self.base_url_setting)
        
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=config.temperature,
        )

    def is_available(self, config):
        # 检查提供商是否可用
        return bool(getattr(config, self.api_key_setting, None))
```

### 步骤 2: 注册提供商

```python
from ut_agent.utils.llm import register_provider

# 注册自定义提供商
register_provider(MyCustomProvider())

# 现在可以在命令行中使用
# ut-agent generate --project ./my-project --llm my_custom
```

### 步骤 3: 配置自定义提供商

在 `.env` 文件中添加自定义提供商的配置：

```env
# 自定义提供商
MY_CUSTOM_API_KEY=your_custom_api_key
MY_CUSTOM_MODEL=your_model_name
MY_CUSTOM_BASE_URL=https://api.your-provider.com
```

## 5. 插件系统 API

### 获取可用提供商

```python
from ut_agent.utils.llm import list_available_providers

# 列出所有可用的提供商
available_providers = list_available_providers()
print(f"可用提供商: {available_providers}")
```

### 获取 LLM 实例

```python
from ut_agent.utils.llm import get_llm

# 获取默认提供商的 LLM 实例
llm = get_llm()

# 获取指定提供商的 LLM 实例
llm = get_llm(provider="openai")
```

## 6. 内置提供商详情

### OpenAIProvider

- **名称**: `openai`
- **API 密钥**: `OPENAI_API_KEY`
- **模型**: `OPENAI_MODEL` (默认为 `gpt-4`)
- **基础 URL**: `OPENAI_BASE_URL` (可选)

### DeepSeekProvider

- **名称**: `deepseek`
- **API 密钥**: `DEEPSEEK_API_KEY`
- **模型**: `DEEPSEEK_MODEL` (默认为 `deepseek-chat`)
- **基础 URL**: `DEEPSEEK_BASE_URL` (默认为 `https://api.deepseek.com`)

### OllamaProvider

- **名称**: `ollama`
- **API 密钥**: 不需要
- **模型**: `OLLAMA_MODEL` (默认为 `llama3`)
- **基础 URL**: `OLLAMA_BASE_URL` (默认为 `http://localhost:11434`)

## 7. 注意事项

- **API 密钥安全**: 不要将 API 密钥硬编码在代码中，应使用环境变量或配置文件
- **模型兼容性**: 确保自定义提供商返回的模型实例实现了 LangChain 的 BaseChatModel 接口
- **错误处理**: 在 create_model 方法中应适当处理配置错误和 API 错误
- **性能考虑**: 对于高频调用，建议使用缓存机制减少 API 调用

## 8. 版本信息

- **版本**: 1.0.0
- **更新日期**: 2024-01-15
- **作者**: UT-Agent 开发团队

## 9. 示例代码

### 完整的自定义提供商示例

```python
"""示例自定义 LLM 提供商"""

from ut_agent.utils.llm import LLMProvider
from ut_agent.exceptions import ConfigurationError

class ExampleProvider(LLMProvider):
    """示例 LLM 提供商"""

    name = "example"
    requires_api_key = True
    api_key_setting = "EXAMPLE_API_KEY"
    model_setting = "EXAMPLE_MODEL"
    base_url_setting = "EXAMPLE_BASE_URL"

    def create_model(self, config):
        """创建模型实例"""
        api_key = getattr(config, self.api_key_setting)
        model = getattr(config, self.model_setting)
        base_url = getattr(config, self.base_url_setting, "https://api.example.com")

        if not api_key:
            raise ConfigurationError(
                "Example API Key 未配置",
                config_key=self.api_key_setting
            )

        # 导入 LangChain 模型
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=config.temperature,
        )

    def is_available(self, config):
        """检查提供商是否可用"""
        return bool(getattr(config, self.api_key_setting, None))

# 注册提供商
if __name__ == "__main__":
    from ut_agent.utils.llm import register_provider
    register_provider(ExampleProvider())
    print("Example provider registered successfully!")
```

### 使用自定义提供商

```python
"""使用自定义提供商示例"""

from ut_agent.utils.llm import get_llm, list_available_providers

# 注册自定义提供商
from my_custom_provider import ExampleProvider
from ut_agent.utils.llm import register_provider

register_provider(ExampleProvider())

# 查看可用提供商
print("可用提供商:", list_available_providers())

# 使用自定义提供商
llm = get_llm(provider="example")

# 测试模型调用
from langchain_core.messages import HumanMessage

response = llm.invoke([HumanMessage(content="Hello, world!")])
print("模型响应:", response.content)
```

## 10. 常见问题

### Q: 如何调试自定义提供商？

**A:** 可以在 `create_model` 和 `is_available` 方法中添加日志，使用 `ut_agent.utils.get_logger` 获取日志器。

### Q: 自定义提供商返回的模型需要实现哪些方法？

**A:** 自定义提供商返回的模型需要实现 LangChain 的 `BaseChatModel` 接口，至少需要实现 `invoke` 方法。

### Q: 如何处理不同模型的参数差异？

**A:** 可以在 `create_model` 方法中根据模型类型和配置动态调整参数，确保兼容性。

### Q: 插件系统是否支持非 LangChain 模型？

**A:** 目前插件系统设计为返回 LangChain 的 `BaseChatModel` 实例，如需支持其他模型，需要编写适配器来包装非 LangChain 模型。

## 11. 扩展建议

- **添加模型参数配置**: 为每个提供商添加更多的模型特定参数配置
- **支持模型切换**: 在运行时动态切换不同的模型
- **添加模型性能评估**: 评估不同模型的生成质量和性能
- **支持模型微调**: 集成模型微调功能，提高生成质量

## 12. 总结

UT-Agent 的插件系统提供了一种灵活的方式来扩展 LLM 提供商的支持，使用户可以根据自己的需求选择合适的模型，也可以通过自定义插件集成新的模型提供商。通过插件系统，UT-Agent 可以不断适应新的 LLM 技术和提供商，保持系统的可扩展性和先进性。
