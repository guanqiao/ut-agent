import * as vscode from 'vscode';

export interface UTAgentConfig {
    llmProvider: string;
    llmApiKey: string;
    llmBaseUrl: string;
    llmModel: string;
    coverageTarget: number;
    maxIterations: number;
    autoSave: boolean;
    openAfterGenerate: boolean;
    javaTestFramework: string;
    javaMockFramework: string;
    frontendTestFramework: string;
    verbose: boolean;
    timeout: number;
}

export class ConfigManager {
    /**
     * 获取所有配置
     */
    getConfig(): UTAgentConfig {
        const config = vscode.workspace.getConfiguration('ut-agent');

        return {
            llmProvider: config.get<string>('llm.provider', 'openai'),
            llmApiKey: config.get<string>('llm.apiKey', ''),
            llmBaseUrl: config.get<string>('llm.baseUrl', ''),
            llmModel: config.get<string>('llm.model', 'gpt-4'),
            coverageTarget: config.get<number>('coverage.target', 80),
            maxIterations: config.get<number>('generation.maxIterations', 5),
            autoSave: config.get<boolean>('generation.autoSave', true),
            openAfterGenerate: config.get<boolean>('generation.openAfterGenerate', true),
            javaTestFramework: config.get<string>('java.testFramework', 'junit5'),
            javaMockFramework: config.get<string>('java.mockFramework', 'mockito'),
            frontendTestFramework: config.get<string>('frontend.testFramework', 'vitest'),
            verbose: config.get<boolean>('advanced.verbose', false),
            timeout: config.get<number>('advanced.timeout', 120),
        };
    }

    /**
     * 更新配置
     */
    async updateConfig(key: string, value: any): Promise<void> {
        const config = vscode.workspace.getConfiguration('ut-agent');
        await config.update(key, value, true);
    }

    /**
     * 检查配置是否有效
     */
    validateConfig(): { valid: boolean; message?: string } {
        const config = this.getConfig();

        // 检查 API Key
        if (config.llmProvider !== 'ollama' && !config.llmApiKey) {
            return {
                valid: false,
                message: `请配置 ${config.llmProvider} 的 API Key`
            };
        }

        // 检查覆盖率目标
        if (config.coverageTarget < 0 || config.coverageTarget > 100) {
            return {
                valid: false,
                message: '覆盖率目标必须在 0-100 之间'
            };
        }

        return { valid: true };
    }

    /**
     * 获取 LLM 配置
     */
    getLLMConfig(): {
        provider: string;
        apiKey: string;
        baseUrl: string;
        model: string;
    } {
        const config = this.getConfig();
        return {
            provider: config.llmProvider,
            apiKey: config.llmApiKey,
            baseUrl: config.llmBaseUrl,
            model: config.llmModel,
        };
    }

    /**
     * 获取生成配置
     */
    getGenerationConfig(): {
        coverageTarget: number;
        maxIterations: number;
        autoSave: boolean;
        openAfterGenerate: boolean;
    } {
        const config = this.getConfig();
        return {
            coverageTarget: config.coverageTarget,
            maxIterations: config.maxIterations,
            autoSave: config.autoSave,
            openAfterGenerate: config.openAfterGenerate,
        };
    }

    /**
     * 获取 Java 配置
     */
    getJavaConfig(): {
        testFramework: string;
        mockFramework: string;
    } {
        const config = this.getConfig();
        return {
            testFramework: config.javaTestFramework,
            mockFramework: config.javaMockFramework,
        };
    }

    /**
     * 获取前端配置
     */
    getFrontendConfig(): {
        testFramework: string;
    } {
        const config = this.getConfig();
        return {
            testFramework: config.frontendTestFramework,
        };
    }
}
