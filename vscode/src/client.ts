
import * as path from 'path';
import { workspace, ExtensionContext} from 'vscode'
import * as vscode from 'vscode'
import {ChildProcessWithoutNullStreams, spawn} from 'child_process'
import {client as WebSocketClient } from 'websocket'
import {
    LanguageClient,
    LanguageClientOptions,
    ServerOptions,
    Executable,
    TransportKind,
} from 'vscode-languageclient/node'

let client : LanguageClient


// ref: https://stackoverflow.com/questions/40284523/connect-external-language-server-to-vscode-extension
// https://nodejs.org/api/child_process.html#child_processspawncommand-args-options

export class HitsaveLanguageClient {
    client : LanguageClient
    constructor() {
        // [todo] how to find the correct version of python?
        let cwd = vscode.workspace.workspaceFolders![0].uri.path
        let port = 5455
        let command = path.join(cwd, '.env', 'bin', 'python')
        let args = ['-m', 'hitsave']
        let e : Executable = {command, args}
        let serverOptions : ServerOptions = {
            run : e, debug : e
        }
        let clientOptions : LanguageClientOptions = {
            documentSelector: [{language: 'python'}]
        }
        this.client = new LanguageClient(
            'hitsave-server',
            'HitSave Server',
            serverOptions,
            clientOptions,
        )
        this.client.start()
    }
    dispose() {
        return client.stop()
    }
}
