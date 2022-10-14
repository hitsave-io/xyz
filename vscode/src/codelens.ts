import * as vscode from 'vscode';
import {CancellationToken, TextDocument, CodeLens} from 'vscode'

export class CodeLensProvider implements vscode.CodeLensProvider {
    public async provideCodeLenses(document : TextDocument, token : vscode.CancellationToken) : Promise<CodeLens[]> {
        return []
    }
}