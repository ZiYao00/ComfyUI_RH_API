/** Real installed-frontend tests, served directly from the installed frontend package.
 * No npm dependencies, no RH requests, and no running ComfyUI backend required.
 * Run after verify_native_schema.py --export. Browser data stays in .ui-test/.
 */
import http from 'node:http';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import { readFile, writeFile, mkdir, access, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const OUT = path.join(ROOT, '.ui-test');
const FRONTEND_ROOT = process.env.RH_UI_FRONTEND_ROOT ||
    'G:/AIGC/ComfyUI/python_embeded/Lib/site-packages/comfyui_frontend_package/static';
await mkdir(OUT, { recursive: true });
const definitions = JSON.parse(await readFile(path.join(OUT, 'native-object-info.json'), 'utf8'));
const coreExtensions = ['/extensions/core/widgetInputs.js'];
await access(path.join(FRONTEND_ROOT, 'index.html'));
await access(path.join(FRONTEND_ROOT, 'scripts', 'app.js'));
await access(path.join(FRONTEND_ROOT, 'extensions', 'core', 'widgetInputs.js'));
const events = [], requests = [], blocked = [];
const mime = new Map([
    ['.html', 'text/html; charset=utf-8'], ['.js', 'text/javascript; charset=utf-8'],
    ['.css', 'text/css; charset=utf-8'], ['.json', 'application/json; charset=utf-8'],
    ['.svg', 'image/svg+xml'], ['.png', 'image/png'], ['.jpg', 'image/jpeg'], ['.jpeg', 'image/jpeg'],
    ['.ico', 'image/x-icon'], ['.woff', 'font/woff'], ['.woff2', 'font/woff2'], ['.webp', 'image/webp'],
]);
const json = (res, value, status = 200) => {
    res.writeHead(status, { 'content-type': 'application/json', 'cache-control': 'no-store' });
    res.end(JSON.stringify(value));
};
const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://localhost');
    const apiPath = url.pathname.replace(/^\/api(?=\/)/, '');
    requests.push(`${req.method} ${url.pathname}`);
    // No write request is forwarded. Settings/userdata are ephemeral test-only mocks.
    if (req.method !== 'GET' && req.method !== 'HEAD') {
        blocked.push(`${req.method} ${url.pathname}`);
        if (apiPath.startsWith('/userdata') || apiPath.startsWith('/settings')) return json(res, {});
        return json(res, { error: 'Blocked by RH UI test sandbox' }, 403);
    }
    try {
        if (apiPath === '/object_info') return json(res, definitions);
        if (apiPath.startsWith('/object_info/')) {
            const name = decodeURIComponent(apiPath.slice('/object_info/'.length));
            return json(res, definitions[name] ? { [name]: definitions[name] } : {});
        }
        if (apiPath === '/extensions') return json(res, [...coreExtensions, '/extensions/ComfyUI_RH_API/rh_native_ui.js']);
        if (apiPath === '/users') return json(res, { storage: 'server', migrated: true });
        if (apiPath === '/settings') return json(res, { 'Comfy.UseNewMenu': 'Top', 'Comfy.TutorialCompleted': true });
        if (apiPath === '/userdata') return json(res, []);
        if (apiPath.startsWith('/userdata/')) return json(res, { error: 'not found' }, 404);
        if (apiPath === '/queue') return json(res, { queue_running: [], queue_pending: [] });
        if (apiPath === '/jobs') return json(res, { jobs: [] });
        if (apiPath === '/history') return json(res, {});
        if (apiPath === '/prompt') return json(res, { exec_info: { queue_remaining: 0 } });
        if (apiPath === '/workflow_templates') return json(res, {});
        if (apiPath === '/models' || apiPath.startsWith('/models/')) return json(res, []);
        if (apiPath.startsWith('/extensions/ComfyUI_RH_API/')) {
            const filename = path.basename(apiPath);
            if (!/^rh_[a-z0-9_]+\.js$/.test(filename)) return json(res, {}, 404);
            res.writeHead(200, { 'content-type': 'text/javascript', 'cache-control': 'no-store' });
            return res.end(await readFile(path.join(ROOT, 'js', filename)));
        }
        if (url.pathname === '/user.css') { res.writeHead(200, { 'content-type': 'text/css; charset=utf-8' }); return res.end(''); }
        if (apiPath === '/system_stats') return json(res, { system: {}, devices: [] });
        if (apiPath === '/features') return json(res, {});
        if (apiPath === '/embeddings') return json(res, []);
        const staticFile = url.pathname === '/' || /^\/(assets|scripts|lib|extensions|locales|fonts|images|icons|templates|cursor)\//.test(url.pathname) || /\.(js|css|json|svg|png|ico|woff2?|html|webp)$/.test(url.pathname);
        if (!staticFile) return json(res, {}, 404);
        const root = path.resolve(FRONTEND_ROOT);
        const relative = url.pathname === '/' ? 'index.html' : decodeURIComponent(url.pathname).replace(/^\/+/, '');
        let file = path.resolve(root, relative);
        if (file !== root && !file.startsWith(root + path.sep)) return json(res, { error: 'invalid static path' }, 403);
        const info = await stat(file);
        if (info.isDirectory()) file = path.join(file, 'index.html');
        const body = await readFile(file);
        res.writeHead(200, { 'content-type': mime.get(path.extname(file).toLowerCase()) || 'application/octet-stream', 'cache-control': 'no-store' });
        res.end(body);
    } catch (error) {
        events.push({ proxy: req.url, error: String(error) });
        json(res, { error: 'Read-only test proxy failed' }, 502);
    }
});
const sockets = new Set();
server.on('connection', socket => { sockets.add(socket); socket.on('close', () => sockets.delete(socket)); });
server.on('upgrade', (req, socket) => {
    const key = req.headers['sec-websocket-key'];
    if (!key) return socket.end();
    const accept = createHash('sha1').update(key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64');
    socket.write('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ' + accept + '\r\n\r\n');
    const payload = Buffer.from(JSON.stringify({ type: 'status', data: { status: { exec_info: { queue_remaining: 0 } }, sid: 'rh-isolated-ui-test' } }));
    const header = payload.length < 126 ? Buffer.from([129, payload.length]) : Buffer.from([129, 126, payload.length >> 8, payload.length & 255]);
    socket.write(Buffer.concat([header, payload]));
    socket.on('error', () => {});
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const browserCandidates = [process.env.RH_UI_BROWSER,
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Google/Chrome/Application/chrome.exe'].filter(Boolean);
let executable;
for (const candidate of browserCandidates) { try { await access(candidate); executable = candidate; break; } catch {} }
if (!executable) throw new Error('No existing Edge/Chrome found. Set RH_UI_BROWSER; nothing was installed.');
const browser = spawn(executable, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--disable-background-networking', '--remote-debugging-port=0', '--remote-allow-origins=*',
    '--window-size=1920,1080', `--user-data-dir=${path.join(OUT, 'browser-profile')}`, 'about:blank'], { stdio: ['ignore', 'ignore', 'pipe'] });
let stderr = '';
const debuggerUrl = await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Browser debugging endpoint timeout: ' + stderr.slice(-1000))), 20000);
    browser.stderr.on('data', chunk => {
        stderr += chunk;
        const match = /DevTools listening on (ws:\/\/[^\s]+)/.exec(stderr);
        if (match) { clearTimeout(timeout); resolve(match[1]); }
    });
    browser.on('error', reject);
});
const ws = new WebSocket(debuggerUrl);
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
let sequence = 0, session;
const pending = new Map();
ws.onmessage = ({ data }) => {
    const message = JSON.parse(data);
    if (message.id) {
        const item = pending.get(message.id);
        if (item) { clearTimeout(item.timer); pending.delete(message.id); message.error ? item.reject(new Error(JSON.stringify(message.error))) : item.resolve(message.result); }
    } else if (message.method === 'Runtime.exceptionThrown') events.push(message.params.exceptionDetails);
    else if (message.method === 'Runtime.consoleAPICalled' && ['error', 'warn'].includes(message.params.type)) events.push({ console: message.params.type, text: message.params.args.map(x => x.value || x.description).join(' ') });
};
function cdp(method, params = {}, useSession = true) {
    const id = ++sequence;
    return new Promise((resolve, reject) => {
        const timer = setTimeout(() => { pending.delete(id); reject(new Error('CDP timeout: ' + method)); }, 30000);
        pending.set(id, { resolve, reject, timer });
        ws.send(JSON.stringify({ id, method, params, ...(useSession && session ? { sessionId: session } : {}) }));
    });
}
async function evaluate(expression) {
    const result = await cdp('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    return result.result?.value;
}
let failure;
try {
    const target = await cdp('Target.createTarget', { url: 'about:blank' }, false);
    ({ sessionId: session } = await cdp('Target.attachToTarget', { targetId: target.targetId, flatten: true }, false));
    await cdp('Runtime.enable');
    await cdp('Page.enable');
    await cdp('Emulation.setDeviceMetricsOverride', { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
    await cdp('Page.addScriptToEvaluateOnNewDocument', { source: "window.confirm=()=>false; localStorage.setItem('Comfy.TutorialCompleted','true');" });
    await cdp('Page.navigate', { url: origin });
    let ready = false;
    for (let attempt = 0; attempt < 60; attempt++) {
        await new Promise(resolve => setTimeout(resolve, 500));
        try {
            ready = await evaluate("!!(globalThis.app?.graph && globalThis.LiteGraph?.registered_node_types?.RH_Params2)");
            if (!ready) ready = await evaluate("(async()=>{const {app}=await import('/scripts/app.js'); window.__rhApp=app; return !!(app.graph && globalThis.LiteGraph?.registered_node_types?.RH_Params2)})()");
            if (ready) break;
        } catch { /* Frontend is still mounting. */ }
    }
    if (!ready) {
        const info = await evaluate("({title:document.title,text:document.body.innerText.slice(0,2000),globals:Object.keys(window).filter(k=>/comfy|graph|app/i.test(k))})");
        throw new Error('Frontend not ready: ' + JSON.stringify(info));
    }
    const script = await readFile(path.join(ROOT, 'tests', 'native_ui_cases.js'), 'utf8');
    const result = await evaluate(`(async()=>{${script}\n})()`);
    const screenshot = await cdp('Page.captureScreenshot', { format: 'png' });
    await writeFile(path.join(OUT, 'native-nodes-1920x1080.png'), Buffer.from(screenshot.data, 'base64'));
    const preview = await cdp('Page.captureScreenshot', { format: 'jpeg', quality: 45, clip: { x: 60, y: 180, width: 1700, height: 340, scale: 0.6 } });
    await writeFile(path.join(OUT, 'preview-base64.txt'), preview.data, 'utf8');
    const visual = await evaluate(`(async()=>{
        const {app}=await import('/scripts/app.js');
        const before=JSON.stringify(app.graph._nodes.map(n=>[n.size,[...(n.widgets||[])].map(w=>[w.name,w.value])]));
        const themeBefore=app.ui.settings.getSettingValue('Comfy.ColorPalette');
        await app.extensionManager.command.execute('Comfy.ToggleTheme');
        await new Promise(r=>setTimeout(r,120));
        const themeAfter=app.ui.settings.getSettingValue('Comfy.ColorPalette');
        const after=JSON.stringify(app.graph._nodes.map(n=>[n.size,[...(n.widgets||[])].map(w=>[w.name,w.value])]));
        return {themeBefore,themeAfter,preserved:before===after};
    })()`);
    (visual.themeBefore !== visual.themeAfter ? result.passes : result.failures).push('Native dark/light theme toggles');
    (visual.preserved ? result.passes : result.failures).push('Theme change preserves node sizes and values');
    const light = await cdp('Page.captureScreenshot', { format: 'png' });
    await writeFile(path.join(OUT, 'native-nodes-theme-toggled.png'), Buffer.from(light.data, 'base64'));
    await evaluate(`(async()=>{const {app}=await import('/scripts/app.js'); app.canvas.ds.scale=0.6; app.canvas.setDirty(true,true); await new Promise(r=>setTimeout(r,100));})()`);
    const zoomed = await cdp('Page.captureScreenshot', { format: 'png' });
    await writeFile(path.join(OUT, 'native-nodes-zoom60.png'), Buffer.from(zoomed.data, 'base64'));
    result.diagnostics.visual = visual;
    console.log(JSON.stringify({ frontend: 'installed ComfyUI frontend package served directly in isolation', passes: result.passes, failures: result.failures }, null, 2));
    await writeFile(path.join(OUT, 'ui-result.json'), JSON.stringify({ result, events, blocked, requests }, null, 2));
    if (result.failures?.length) throw new Error('UI assertions failed: ' + result.failures.join('; '));
} catch (error) {
    failure = error;
    try {
        const report = await evaluate('window.__rhTestReport');
        await writeFile(path.join(OUT, 'ui-partial-result.json'), JSON.stringify(report || {}, null, 2));
        console.error(JSON.stringify({ partial: { passes: report?.passes, failures: report?.failures, saved: report?.diagnostics?.saved } }, null, 2));
    } catch {}
    try {
        const screenshot = await cdp('Page.captureScreenshot', { format: 'png' });
        await writeFile(path.join(OUT, 'native-ui-failure.png'), Buffer.from(screenshot.data, 'base64'));
    } catch {}
    await writeFile(path.join(OUT, 'ui-result.json'), JSON.stringify({ error: String(error), events, blocked, requests }, null, 2));
    console.error(String(error));
    console.error(JSON.stringify({ events: events.slice(-8), requests: requests.slice(-12) }, null, 2));
} finally {
    try { await cdp('Browser.close', {}, false); } catch {}
    ws.close();
    for (const socket of sockets) socket.destroy();
    server.close();
}
if (failure) process.exitCode = 1;
