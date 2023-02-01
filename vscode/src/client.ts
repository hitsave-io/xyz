
import * as path from 'path';
import { workspace, ExtensionContext } from 'vscode'
import * as vscode from 'vscode'
import { ChildProcessWithoutNullStreams, spawn } from 'child_process'
import {
    LanguageClient,
    LanguageClientOptions,
    ServerOptions,
    Executable,
    TransportKind,
    StreamInfo,
    TextDocumentPositionParams,
    NotificationType,
} from 'vscode-languageclient/node'
import * as net from 'net'

let client: LanguageClient


// ref: https://stackoverflow.com/questions/40284523/connect-external-language-server-to-vscode-extension
// https://nodejs.org/api/child_process.html#child_processspawncommand-args-options

export class HitsaveLanguageClient {
    client: LanguageClient

    constructor() {
        let port = 7797
        const serverOptions: ServerOptions = () => {
            let socket = net.connect({
                port: port, host: "localhost"
            })
            const si: StreamInfo = {
                reader: socket, writer: socket
            }
            return Promise.resolve(si)
        }
        const clientOptions: LanguageClientOptions = {
            documentSelector: [{ language: 'python' }]
        }
        this.client = new LanguageClient(
            'hitsave-server', 'HitSave Server',
            serverOptions, clientOptions,
        )
        this.client.start()
    }

    async notify_focus(tdpp: TextDocumentPositionParams | { symbol: string }) {
        console.log(tdpp)
        await this.client.sendNotification('hitsave/focus', tdpp)
    }
    // let cwd = vscode.workspace.workspaceFolders![0].uri.path
    // [todo] how to find the correct version of python?
    // let command = path.join(cwd, '.env', 'bin', 'python')
    // let args = ['-m', 'hitsave', 'serve']
    // let e: Executable = { command, args, transport }
    // serverOptions = {
    //     run: e, debug: e
    // }

    dispose() {
        client.stop()
        client.dispose()
    }
}
