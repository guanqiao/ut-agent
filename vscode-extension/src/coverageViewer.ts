import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { Logger } from './utils/logger';

export class CoverageViewer {
    private logger: Logger;

    constructor(logger: Logger) {
        this.logger = logger;
    }

    /**
     * 显示覆盖率报告
     */
    async showCoverageReport(): Promise<void> {
        this.logger.info('显示覆盖率报告');

        // 查找覆盖率报告文件
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) {
            vscode.window.showErrorMessage('请先打开一个工作区');
            return;
        }

        const coverageFiles = await this.findCoverageFiles(workspaceFolders[0].uri.fsPath);

        if (coverageFiles.length === 0) {
            const action = await vscode.window.showWarningMessage(
                '未找到覆盖率报告文件',
                '生成测试', '取消'
            );
            if (action === '生成测试') {
                vscode.commands.executeCommand('ut-agent.generateTest');
            }
            return;
        }

        // 如果有多个报告，让用户选择
        let selectedFile = coverageFiles[0];
        if (coverageFiles.length > 1) {
            const items = coverageFiles.map(f => ({
                label: path.basename(f),
                description: f,
                path: f
            }));
            const selected = await vscode.window.showQuickPick(items, {
                placeHolder: '选择要查看的覆盖率报告'
            });
            if (!selected) {
                return;
            }
            selectedFile = selected.path;
        }

        // 打开报告
        await this.openCoverageReport(selectedFile);
    }

    /**
     * 查找覆盖率报告文件
     */
    private async findCoverageFiles(projectRoot: string): Promise<string[]> {
        const coverageFiles: string[] = [];
        const possiblePaths = [
            'target/site/jacoco/index.html',
            'build/reports/jacoco/test/html/index.html',
            'coverage/index.html',
            'coverage/lcov-report/index.html',
            'htmlReport/index.html'
        ];

        for (const relPath of possiblePaths) {
            const fullPath = path.join(projectRoot, relPath);
            if (fs.existsSync(fullPath)) {
                coverageFiles.push(fullPath);
            }
        }

        return coverageFiles;
    }

    /**
     * 打开覆盖率报告
     */
    private async openCoverageReport(reportPath: string): Promise<void> {
        // 创建 Webview 面板
        const panel = vscode.window.createWebviewPanel(
            'coverageReport',
            '覆盖率报告',
            vscode.ViewColumn.One,
            {
                enableScripts: true,
                localResourceRoots: [
                    vscode.Uri.file(path.dirname(reportPath))
                ]
            }
        );

        // 读取并处理 HTML 内容
        let htmlContent = fs.readFileSync(reportPath, 'utf-8');

        // 转换资源路径
        const reportDir = path.dirname(reportPath);
        htmlContent = this.processHtmlContent(htmlContent, reportDir, panel.webview);

        panel.webview.html = htmlContent;
    }

    /**
     * 处理 HTML 内容，转换资源路径
     */
    private processHtmlContent(
        html: string,
        baseDir: string,
        webview: vscode.Webview
    ): string {
        // 转换 CSS 链接
        html = html.replace(
            /<link[^>]*href=["']([^"']+)["'][^>]*>/g,
            (match, href) => {
                if (href.startsWith('http')) {
                    return match;
                }
                const fullPath = path.join(baseDir, href);
                if (fs.existsSync(fullPath)) {
                    const uri = webview.asWebviewUri(vscode.Uri.file(fullPath));
                    return match.replace(href, uri.toString());
                }
                return match;
            }
        );

        // 转换 JS 链接
        html = html.replace(
            /<script[^>]*src=["']([^"']+)["'][^>]*>/g,
            (match, src) => {
                if (src.startsWith('http')) {
                    return match;
                }
                const fullPath = path.join(baseDir, src);
                if (fs.existsSync(fullPath)) {
                    const uri = webview.asWebviewUri(vscode.Uri.file(fullPath));
                    return match.replace(src, uri.toString());
                }
                return match;
            }
        );

        // 转换图片链接
        html = html.replace(
            /<img[^>]*src=["']([^"']+)["'][^>]*>/g,
            (match, src) => {
                if (src.startsWith('http')) {
                    return match;
                }
                const fullPath = path.join(baseDir, src);
                if (fs.existsSync(fullPath)) {
                    const uri = webview.asWebviewUri(vscode.Uri.file(fullPath));
                    return match.replace(src, uri.toString());
                }
                return match;
            }
        );

        // 添加基础标签
        if (!html.includes('<base')) {
            html = html.replace(
                '<head>',
                `<head>\n    <base href="${webview.asWebviewUri(vscode.Uri.file(baseDir))}/">`
            );
        }

        return html;
    }

    /**
     * 生成简单的覆盖率摘要
     */
    async generateCoverageSummary(projectRoot: string): Promise<string | null> {
        // 尝试解析 JaCoCo XML 报告
        const jacocoXmlPath = path.join(projectRoot, 'target/site/jacoco/jacoco.xml');
        if (fs.existsSync(jacocoXmlPath)) {
            return this.parseJacocoXml(jacocoXmlPath);
        }

        // 尝试解析 lcov 报告
        const lcovPath = path.join(projectRoot, 'coverage/lcov.info');
        if (fs.existsSync(lcovPath)) {
            return this.parseLcov(lcovPath);
        }

        return null;
    }

    /**
     * 解析 JaCoCo XML 报告
     */
    private parseJacocoXml(xmlPath: string): string {
        // 简化实现，实际应该使用 XML 解析器
        const content = fs.readFileSync(xmlPath, 'utf-8');
        // 提取总体覆盖率
        const match = content.match(/<counter type="INSTRUCTION"[^>]*missed="(\d+)"[^>]*covered="(\d+)"/);
        if (match) {
            const missed = parseInt(match[1]);
            const covered = parseInt(match[2]);
            const total = missed + covered;
            const percentage = ((covered / total) * 100).toFixed(2);
            return `指令覆盖率: ${percentage}% (${covered}/${total})`;
        }
        return '无法解析覆盖率报告';
    }

    /**
     * 解析 LCOV 报告
     */
    private parseLcov(lcovPath: string): string {
        const content = fs.readFileSync(lcovPath, 'utf-8');
        const lines = content.split('\n');
        let totalLines = 0;
        let hitLines = 0;

        for (const line of lines) {
            if (line.startsWith('LF:')) {
                totalLines = parseInt(line.substring(3));
            } else if (line.startsWith('LH:')) {
                hitLines = parseInt(line.substring(3));
            }
        }

        if (totalLines > 0) {
            const percentage = ((hitLines / totalLines) * 100).toFixed(2);
            return `行覆盖率: ${percentage}% (${hitLines}/${totalLines})`;
        }

        return '无法解析覆盖率报告';
    }
}
