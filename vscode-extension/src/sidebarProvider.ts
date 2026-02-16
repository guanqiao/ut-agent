import * as vscode from 'vscode';
import { Logger } from './utils/logger';

export class SidebarProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'ut-agent.sidebar';
    private _view?: vscode.WebviewView;
    private logger: Logger;

    constructor(
        private readonly _extensionUri: vscode.Uri,
        logger: Logger
    ) {
        this.logger = logger;
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [
                this._extensionUri
            ]
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        // 处理来自 webview 的消息
        webviewView.webview.onDidReceiveMessage(
            async (message) => {
                switch (message.command) {
                    case 'generateTest':
                        vscode.commands.executeCommand('ut-agent.generateTest');
                        return;
                    case 'showCoverage':
                        vscode.commands.executeCommand('ut-agent.showCoverage');
                        return;
                    case 'openSettings':
                        vscode.commands.executeCommand('ut-agent.openSettings');
                        return;
                    case 'refresh':
                        this.refresh();
                        return;
                }
            },
            undefined,
            []
        );

        // 初始刷新
        this.refresh();
    }

    public refresh() {
        if (this._view) {
            const config = vscode.workspace.getConfiguration('ut-agent');
            const provider = config.get<string>('llm.provider', 'openai');
            const coverageTarget = config.get<number>('coverage.target', 80);

            this._view.webview.postMessage({
                command: 'updateStatus',
                provider: provider,
                coverageTarget: coverageTarget,
                status: 'ready'
            });
        }
    }

    private _getHtmlForWebview(webview: vscode.Webview): string {
        return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UT-Agent</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            color: var(--vscode-foreground);
            padding: 10px;
        }
        .header {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
        }
        .header h2 {
            margin: 0;
            font-size: 16px;
        }
        .header .icon {
            font-size: 20px;
            margin-right: 8px;
        }
        .section {
            margin-bottom: 20px;
        }
        .section-title {
            font-weight: bold;
            margin-bottom: 10px;
            color: var(--vscode-descriptionForeground);
            font-size: 11px;
            text-transform: uppercase;
        }
        .btn {
            display: flex;
            align-items: center;
            width: 100%;
            padding: 8px 12px;
            margin-bottom: 8px;
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
            transition: background 0.2s;
        }
        .btn:hover {
            background: var(--vscode-button-hoverBackground);
        }
        .btn .icon {
            margin-right: 8px;
        }
        .btn-secondary {
            background: var(--vscode-secondaryButton-background);
            color: var(--vscode-secondaryButton-foreground);
        }
        .btn-secondary:hover {
            background: var(--vscode-secondaryButton-hoverBackground);
        }
        .info-item {
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            border-bottom: 1px solid var(--vscode-panel-border);
        }
        .info-item:last-child {
            border-bottom: none;
        }
        .info-label {
            color: var(--vscode-descriptionForeground);
        }
        .info-value {
            font-weight: 500;
        }
        .status-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            background: var(--vscode-badge-background);
            color: var(--vscode-badge-foreground);
        }
        .status-badge.ready {
            background: #238636;
        }
        .quick-actions {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
        }
        .quick-actions .btn {
            justify-content: center;
            font-size: 12px;
            padding: 6px;
        }
        .help-text {
            font-size: 12px;
            color: var(--vscode-descriptionForeground);
            margin-top: 10px;
            line-height: 1.5;
        }
        .divider {
            height: 1px;
            background: var(--vscode-panel-border);
            margin: 15px 0;
        }
    </style>
</head>
<body>
    <div class="header">
        <span class="icon">🧪</span>
        <h2>UT-Agent</h2>
    </div>

    <div class="section">
        <div class="section-title">快速操作</div>
        <button class="btn" onclick="generateTest()">
            <span class="icon">⚡</span>
            生成单元测试
        </button>
        <button class="btn" onclick="showCoverage()">
            <span class="icon">📊</span>
            查看覆盖率报告
        </button>
    </div>

    <div class="divider"></div>

    <div class="section">
        <div class="section-title">当前配置</div>
        <div class="info-item">
            <span class="info-label">LLM 提供商</span>
            <span class="info-value" id="provider">-</span>
        </div>
        <div class="info-item">
            <span class="info-label">覆盖率目标</span>
            <span class="info-value" id="coverageTarget">-</span>
        </div>
        <div class="info-item">
            <span class="info-label">状态</span>
            <span class="status-badge" id="status">初始化中</span>
        </div>
    </div>

    <div class="divider"></div>

    <div class="section">
        <div class="section-title">快捷设置</div>
        <div class="quick-actions">
            <button class="btn btn-secondary" onclick="openSettings()">
                <span class="icon">⚙️</span>
                设置
            </button>
            <button class="btn btn-secondary" onclick="refresh()">
                <span class="icon">🔄</span>
                刷新
            </button>
        </div>
    </div>

    <div class="section">
        <div class="help-text">
            💡 <strong>提示：</strong>在编辑器中右键点击文件，选择 "Generate Unit Test" 即可生成测试。
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();

        function generateTest() {
            vscode.postMessage({ command: 'generateTest' });
        }

        function showCoverage() {
            vscode.postMessage({ command: 'showCoverage' });
        }

        function openSettings() {
            vscode.postMessage({ command: 'openSettings' });
        }

        function refresh() {
            vscode.postMessage({ command: 'refresh' });
        }

        // 监听来自扩展的消息
        window.addEventListener('message', event => {
            const message = event.data;
            switch (message.command) {
                case 'updateStatus':
                    document.getElementById('provider').textContent = message.provider;
                    document.getElementById('coverageTarget').textContent = message.coverageTarget + '%';
                    const statusEl = document.getElementById('status');
                    statusEl.textContent = message.status === 'ready' ? '就绪' : '未就绪';
                    statusEl.className = 'status-badge ' + message.status;
                    break;
            }
        });
    </script>
</body>
</html>`;
    }
}
