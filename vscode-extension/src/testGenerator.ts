import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { spawn } from 'child_process';
import { Logger } from './utils/logger';
import { ConfigManager } from './utils/configManager';

export class TestGenerator {
    private logger: Logger;
    private configManager: ConfigManager;

    constructor(logger: Logger) {
        this.logger = logger;
        this.configManager = new ConfigManager();
    }

    /**
     * 为指定文件生成单元测试
     */
    async generateTest(fileUri: vscode.Uri): Promise<void> {
        this.logger.info(`开始为文件生成测试: ${fileUri.fsPath}`);

        // 检查文件类型
        const fileExt = path.extname(fileUri.fsPath);
        const supportedExts = ['.java', '.ts', '.js', '.vue'];
        if (!supportedExts.includes(fileExt)) {
            throw new Error(`不支持的文件类型: ${fileExt}`);
        }

        // 获取配置
        const config = this.configManager.getConfig();
        this.logger.info(`使用配置: ${JSON.stringify(config)}`);

        // 查找项目根目录
        const projectRoot = await this.findProjectRoot(fileUri);
        if (!projectRoot) {
            throw new Error('无法找到项目根目录');
        }

        // 显示进度
        await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: 'UT-Agent: 正在生成单元测试...',
            cancellable: true
        }, async (progress, token) => {
            // 构建命令
            const command = this.buildCommand(projectRoot, fileUri, config);
            this.logger.info(`执行命令: ${command}`);

            try {
                const result = await this.executeCommand(command, token);
                this.logger.info('测试生成完成');

                // 解析结果并打开生成的测试文件
                await this.handleGenerationResult(result, fileUri, config);
            } catch (error) {
                this.logger.error('命令执行失败', error);
                throw error;
            }
        });
    }

    /**
     * 为选中代码生成测试
     */
    async generateTestForSelection(fileUri: vscode.Uri, selectedCode: string): Promise<void> {
        this.logger.info(`为选中代码生成测试: ${fileUri.fsPath}`);
        // TODO: 实现选中代码的测试生成
        vscode.window.showInformationMessage('选中代码生成测试功能开发中...');
    }

    /**
     * 构建 ut-agent 命令
     */
    private buildCommand(projectRoot: string, fileUri: vscode.Uri, config: any): string {
        const args: string[] = [
            'ut-agent',
            'generate',
            `"${projectRoot}"`,
            '--type', 'auto',
            '--coverage-target', config.coverageTarget.toString(),
            '--max-iterations', config.maxIterations.toString(),
            '--llm', config.llmProvider
        ];

        return args.join(' ');
    }

    /**
     * 执行命令
     */
    private executeCommand(command: string, token: vscode.CancellationToken): Promise<string> {
        return new Promise((resolve, reject) => {
            const child = spawn(command, { shell: true });
            let output = '';
            let errorOutput = '';

            child.stdout.on('data', (data) => {
                output += data.toString();
            });

            child.stderr.on('data', (data) => {
                errorOutput += data.toString();
            });

            child.on('close', (code) => {
                if (code === 0) {
                    resolve(output);
                } else {
                    reject(new Error(`命令执行失败 (exit code: ${code}): ${errorOutput}`));
                }
            });

            // 处理取消
            token.onCancellationRequested(() => {
                child.kill();
                reject(new Error('用户取消了操作'));
            });
        });
    }

    /**
     * 处理生成结果
     */
    private async handleGenerationResult(
        result: string,
        sourceUri: vscode.Uri,
        config: any
    ): Promise<void> {
        // 推断测试文件路径
        const testFilePath = this.inferTestFilePath(sourceUri);

        if (fs.existsSync(testFilePath)) {
            if (config.openAfterGenerate) {
                const document = await vscode.workspace.openTextDocument(testFilePath);
                await vscode.window.showTextDocument(document);
            }

            vscode.window.showInformationMessage(
                `测试文件已生成: ${path.basename(testFilePath)}`,
                '打开文件', '查看覆盖率'
            ).then((selection) => {
                if (selection === '查看覆盖率') {
                    vscode.commands.executeCommand('ut-agent.showCoverage');
                }
            });
        } else {
            vscode.window.showWarningMessage('测试生成完成，但无法定位测试文件');
        }
    }

    /**
     * 推断测试文件路径
     */
    private inferTestFilePath(sourceUri: vscode.Uri): string {
        const sourcePath = sourceUri.fsPath;
        const dir = path.dirname(sourcePath);
        const basename = path.basename(sourcePath, path.extname(sourcePath));
        const ext = path.extname(sourcePath);

        if (ext === '.java') {
            // Java: src/main/java -> src/test/java
            const testPath = sourcePath
                .replace('/src/main/java/', '/src/test/java/')
                .replace('\\src\\main\\java\\', '\\src\\test\\java\\');
            return testPath.replace('.java', 'Test.java');
        } else if (ext === '.ts' || ext === '.js') {
            // TypeScript/JavaScript: .ts -> .spec.ts
            return path.join(dir, `${basename}.spec${ext}`);
        } else if (ext === '.vue') {
            // Vue: .vue -> .spec.ts
            return path.join(dir, `${basename}.spec.ts`);
        }

        return path.join(dir, `${basename}Test${ext}`);
    }

    /**
     * 查找项目根目录
     */
    private async findProjectRoot(fileUri: vscode.Uri): Promise<string | null> {
        let currentDir = path.dirname(fileUri.fsPath);

        while (currentDir !== path.dirname(currentDir)) {
            // 检查 Maven 项目
            if (fs.existsSync(path.join(currentDir, 'pom.xml'))) {
                return currentDir;
            }

            // 检查 Gradle 项目
            if (fs.existsSync(path.join(currentDir, 'build.gradle')) ||
                fs.existsSync(path.join(currentDir, 'build.gradle.kts'))) {
                return currentDir;
            }

            // 检查 Node.js 项目
            if (fs.existsSync(path.join(currentDir, 'package.json'))) {
                return currentDir;
            }

            currentDir = path.dirname(currentDir);
        }

        // 如果没有找到，返回工作区根目录
        const workspaceFolder = vscode.workspace.getWorkspaceFolder(fileUri);
        return workspaceFolder?.uri.fsPath || null;
    }
}
