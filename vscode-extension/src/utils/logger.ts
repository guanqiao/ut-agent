import * as vscode from 'vscode';

export class Logger {
    private outputChannel: vscode.OutputChannel;

    constructor() {
        this.outputChannel = vscode.window.createOutputChannel('UT-Agent');
    }

    info(message: string): void {
        const timestamp = new Date().toISOString();
        this.outputChannel.appendLine(`[INFO] ${timestamp}: ${message}`);
        console.log(`[UT-Agent] ${message}`);
    }

    error(message: string, error?: any): void {
        const timestamp = new Date().toISOString();
        this.outputChannel.appendLine(`[ERROR] ${timestamp}: ${message}`);
        if (error) {
            this.outputChannel.appendLine(`  Details: ${error}`);
            if (error.stack) {
                this.outputChannel.appendLine(`  Stack: ${error.stack}`);
            }
        }
        console.error(`[UT-Agent] ${message}`, error);
    }

    warn(message: string): void {
        const timestamp = new Date().toISOString();
        this.outputChannel.appendLine(`[WARN] ${timestamp}: ${message}`);
        console.warn(`[UT-Agent] ${message}`);
    }

    debug(message: string): void {
        const config = vscode.workspace.getConfiguration('ut-agent');
        const verbose = config.get<boolean>('advanced.verbose', false);
        if (verbose) {
            const timestamp = new Date().toISOString();
            this.outputChannel.appendLine(`[DEBUG] ${timestamp}: ${message}`);
            console.log(`[UT-Agent:DEBUG] ${message}`);
        }
    }

    show(): void {
        this.outputChannel.show();
    }

    dispose(): void {
        this.outputChannel.dispose();
    }
}
