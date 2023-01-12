
const esb = require('esbuild')

const watch = process.argv.includes('--watch')
const prod = process.argv.includes('--prod')

function watcher(item) {
    function onRebuild(error, result) {
        if (error) { console.error(`watch build ${item} failed:`, error) }
        else { console.log('built', item) }
    }
    return { onRebuild }
}


esb.build({
    entryPoints: ['./src/extension.ts'],
    bundle: true,
    outfile: 'out/main.js',
    external: ['vscode'],
    format: "cjs",
    platform: 'node',
    watch: watch && watcher('extension'),
})

esb.build({
    entryPoints: ['./webview/app.tsx'],
    bundle: true,
    outfile: 'out/app.js',
    platform: 'browser',
    watch: watch && watcher('webview'),
})
