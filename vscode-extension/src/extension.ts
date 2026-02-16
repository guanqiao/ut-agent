import * as vscode from 'vscode';
import { TestGenerator } from './testGenerator';
import { SidebarProvider } from './sidebarProvider';
import { CoverageViewer } from './coverageViewer';
import { Logger } from './utils/logger';

export function activate(context: vscode.ExtensionContext) {
    const logger = new Logger();
    logger.info('UT-Agent extension is now active!');

    const testGenerator = new TestGenerator(logger);
    const coverageViewer = new CoverageViewer(logger);

    // 注册侧边栏
    const sidebarProvider = new SidebarProvider(context.extensionUri, logger);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('ut-agent.sidebar', sidebarProvider)
    );

    // 注册命令：生成单元测试
    const generateTestCommand = vscode.commands.registerCommand(
        'ut-agent.generateTest',
        async (uri: vscode.Uri) => {
            const targetUri = uri || vscode.window.activeTextEditor?.document.uri;
            if (!targetUri) {
                vscode.window.showErrorMessage('请先选择或打开一个文件');
                return;
            }

            try {
                await testGenerator.generateTest(targetUri);
            } catch (error) {
                logger.error('生成测试失败', error);
                vscode.window.showErrorMessage(`生成测试失败: ${error}`);
            }
        }
    );

    // 注册命令：为选中代码生成测试
    const generateTestForSelectionCommand = vscode.commands.registerCommand(
        'ut-agent.generateTestForSelection',
        async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showErrorMessage('请先打开一个文件');
                return;
            }

            const selection = editor.selection;
            if (selection.isEmpty) {
                vscode.window.showErrorMessage('请先选中要测试的代码');
                return;
            }

            const selectedText = editor.document.getText(selection);
            try {
                await testGenerator.generateTestForSelection(editor.document.uri, selectedText);
            } catch (error) {
                logger.error('生成测试失败', error);
                vscode.window.showErrorMessage(`生成测试失败: ${error}`);
            }
        }
    );

    // 注册命令：打开设置
    const openSettingsCommand = vscode.commands.registerCommand(
        'ut-agent.openSettings',
        () => {
            vscode.commands.executeCommand(
                'workbench.action.openSettings',
                'ut-agent'
            );
        }
    );

    // 注册命令：显示覆盖率报告
    const showCoverageCommand = vscode.commands.registerCommand(
        'ut-agent.showCoverage',
        async () => {
            try {
                await coverageViewer.showCoverageReport();
            } catch (error) {
                logger.error('显示覆盖率报告失败', error);
                vscode.window.showErrorMessage(`显示覆盖率报告失败: ${error}`);
            }
        }
    );

    // 注册命令：刷新侧边栏
    const refreshSidebarCommand = vscode.commands.registerCommand(
        'ut-agent.refreshSidebar',
        () => {
            sidebarProvider.refresh();
        }
    );

    // 注册所有命令
    context.subscriptions.push(
        generateTestCommand,
        generateTestForSelectionCommand,
        openSettingsCommand,
        showCoverageCommand,
        refreshSidebarCommand
    );

    // 监听配置变更
    context.subscriptions.push(
        vscode.workspace.onDidChangeConfiguration((e) => {
            if (e.affectsConfiguration('ut-agent')) {
                logger.info('配置已更新');
                sidebarProvider.refresh();
            }
        })
    );

    // 监听文件保存事件（可选：自动生成测试）
    context.subscriptions.push(
        vscode.workspace.onDidSaveTextDocument((document) => {
            const config = vscode.workspace.getConfiguration('ut-agent');
            const autoGenerate = config.get<boolean>('generation.autoGenerateOnSave');
            if (autoGenerate) {
                // 可选：保存时自动生成测试
                // testGenerator.generateTest(document.uri);
            }
        })
    );

    logger.info('UT-Agent commands registered successfully');
}

export function deactivate() {
    console.log('UT-Agent extension is now deactivated');
}
