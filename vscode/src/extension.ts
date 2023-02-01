// The module 'vscode' contains the VS Code extensibility API
// Import the module and reference it with the alias vscode in your code below
import * as vscode from 'vscode';
import { HitsaveLanguageClient } from './client';
import { join } from 'path';
// This method is called when your extension is activated
// Your extension is activated the very first time the command is executed
export function activate(context: vscode.ExtensionContext) {
    const infoview = new Infoview(context)
    context.subscriptions.push(infoview)
    // Use the console to output diagnostic information (console.log) and errors (console.error)
    // This line of code will only be executed once when your extension is activated
    console.log('Congratulations, your extension "hitsave" is now active!');

    // The command has been defined in the package.json file
    // Now provide the implementation of the command with registerCommand
    // The commandId parameter must match the command field in package.json
    let disposable = vscode.commands.registerCommand('hitsave.helloWorld', () => {
        // The code you place here will be executed every time your command is executed
        // Display a message box to the user
        vscode.window.showInformationMessage('Hello World from hitsave!');
    });

    context.subscriptions.push(disposable);

    let hslc = new HitsaveLanguageClient()
    context.subscriptions.push(hslc)

    context.subscriptions.push(
        vscode.commands.registerCommand('hitsave.openInfo', () => infoview.open())
    )
    context.subscriptions.push(
        vscode.commands.registerCommand('hitsave.showFunction', (symbol: string) => {
            infoview.open()
            hslc.notify_focus({ symbol })
        })
    )
}

class Infoview {
    public current: vscode.WebviewPanel | undefined = undefined
    subscriptions: vscode.Disposable[] = []
    constructor(readonly context: vscode.ExtensionContext) {

    }

    dispose() {
        if (this.current) {
            this.current.dispose()
        }
        for (let subscription of this.subscriptions) {
            subscription.dispose()
        }
        this.subscriptions.length == 0
    }

    open() {
        if (this.current) {
            this.current.reveal()
        } else {
            this.current = vscode.window.createWebviewPanel(
                'hitsave',
                'HitSave Viewer',
                vscode.ViewColumn.Beside,
                {
                    enableScripts: true,
                }
            );
            this.current.webview.html = this.getWebviewContent()
            this.current.onDidDispose(() => {
                this.current = undefined
            }, undefined, this.subscriptions)
            this.current.webview.onDidReceiveMessage(
                msg => this.handleMessage(msg), undefined, this.subscriptions
            );
        }
    }

    handleMessage(msg: any) {
        if (msg.command === "reload") {
            console.log('extension: reloading')
            vscode.commands.executeCommand("workbench.action.webview.reloadWebviewAction")
        }
    }

    getLocalPath(path: string): string | undefined {

        const devmode = true // [todo] set in a config somewhere.
        if (devmode) {
            return `${devserver}/${path}`
        }
        if (this.current) {
            return this.current.webview.asWebviewUri(
                vscode.Uri.file(join(this.context.extensionPath, path))).toString();
        }
        throw new Error('current is undefineed')
    }

    getWebviewContent() {
        const workspaceFolder = vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0]
        const workspacePath = workspaceFolder ? workspaceFolder.uri.fsPath : undefined
        const appPath = this.getLocalPath('out/app.js')
        const eventSource = `${devserver}/onReload`
        const livereloader = `<script>
            console.log('making live reloader')
            const vscode = acquireVsCodeApi();
            es = new EventSource('${eventSource}', {withCredentials: false})
            es.onmessage = () => {
                console.log('webview: requesting reload')
                vscode.postMessage({command: "reload"})
            }
        </script>`
        return `<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Cat Coding</title>
        </head>
        <body>
            <div id="react_root"></div>
            ${livereloader}
            <script>
                workspace_dir = "${workspacePath}"
            </script>
            <script src="${appPath}"></script>
        </body>
        </html>`
    }
}

const devserver = 'http://localhost:7777'

// This method is called when your extension is deactivated
export function deactivate() { }
