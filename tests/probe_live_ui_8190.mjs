/** Real ComfyUI 8190 UI smoke, using local Edge/Chrome CDP (no npm package).
 * Test-only browser profile; no saved workflow and no Queue/paid RH requests.
 */
import { spawn } from 'node:child_process';
import { access, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(root, '.ui-test');
const profile = path.join(out, 'real-8190-profile');
await mkdir(out, { recursive: true });
const candidates = [
    process.env.RH_UI_BROWSER,
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
].filter(Boolean);
let exe;
for (const file of candidates) { try { await access(file); exe = file; break; } catch {} }
if (!exe) throw new Error('Install-free UI test needs an existing Edge or Chrome browser.');

const chrome = spawn(exe, [
    '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--disable-background-networking', '--remote-debugging-port=0', '--remote-allow-origins=*',
    '--window-size=1920,1080', '--user-data-dir=' + profile, 'about:blank',
], { stdio: ['ignore', 'ignore', 'pipe'] });
let stderr = '';
const endpoint = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Browser did not start')), 20000);
    chrome.stderr.on('data', data => {
        stderr += data.toString('utf8');
        const match = /DevTools listening on (ws:\/\/[^\s]+)/.exec(stderr);
        if (match) { clearTimeout(timer); resolve(match[1]); }
    });
    chrome.on('error', reject);
});
const ws = new WebSocket(endpoint);
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
let seq = 0;
let session;
const pending = new Map();
ws.onmessage = e => {
    const message = JSON.parse(e.data);
    if (!message.id) return;
    const target = pending.get(message.id);
    if (!target) return;
    clearTimeout(target.timer);
    pending.delete(message.id);
    if (message.error) target.reject(new Error(JSON.stringify(message.error)));
    else target.resolve(message.result);
};
const cdp = (method, params = {}, useSession = true) => new Promise((resolve, reject) => {
    const id = ++seq;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('CDP timeout: ' + method)); }, 35000);
    pending.set(id, { resolve, reject, timer });
    ws.send(JSON.stringify({ id, method, params, ...(session && useSession ? { sessionId: session } : {}) }));
});
async function evalJS(script) {
    const result = await cdp('Runtime.evaluate', {
        expression: script, awaitPromise: true, returnByValue: true,
    });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    return result.result?.value;
}
const checks = [];
let failure;
try {
    const tab = await cdp('Target.createTarget', { url: 'about:blank' }, false);
    ({ sessionId: session } = await cdp('Target.attachToTarget',
        { targetId: tab.targetId, flatten: true }, false));
    await cdp('Runtime.enable');
    await cdp('Page.enable');
    await cdp('Emulation.setDeviceMetricsOverride',
        { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
    await cdp('Page.addScriptToEvaluateOnNewDocument', {
        source: "localStorage.setItem('Comfy.TutorialCompleted','true'); window.confirm=()=>false;",
    });
    await cdp('Page.navigate', { url: 'http://127.0.0.1:8190/' });
    let ready = false;
    for (let attempt = 0; attempt < 90; attempt++) {
        await new Promise(resolve => setTimeout(resolve, 500));
        try {
            ready = await evalJS("(async()=>{const {app}=await import('/scripts/app.js');return !!(app.graph && app.canvas?.canvas && app.canvas.canvas.isConnected && window.LiteGraph?.registered_node_types?.RH_Execute && window.LiteGraph?.registered_node_types?.RH_WorkflowInspect)})()");
            if (ready) break;
        } catch { /* startup in progress */ }
    }
    if (!ready) {
        const state = await evalJS("(async()=>{const {app}=await import('/scripts/app.js');return {graph:!!app.graph,canvas:!!app.canvas,canvasElement:!!app.canvas?.canvas,connected:!!app.canvas?.canvas?.isConnected,nodes:!!window.LiteGraph?.registered_node_types?.RH_Execute}})()");
        throw new Error('Real 8190 frontend failed to mount canvas and RH nodes: '+JSON.stringify(state));
    }

    const setupState = await evalJS("(async()=>{const {app}=await import('/scripts/app.js');return {canvas:!!app.canvas?.canvas,rootGraph:!!app.rootGraph,workflowService:!!app.extensionManager?.workflow,activeWorkflow:!!app.extensionManager?.workflow?.activeWorkflow,workflowLoadComplete:!!app.extensionManager?.workflow?.activeWorkflow?.path,layout:!!document.querySelector('canvas'),groupsInitialized:!!window.Workspace2CanvasGroups?.initialized}})()");
    console.log('8190 frontend initial state:', JSON.stringify(setupState));
    const result = await evalJS(`(async()=>{
        const {app}=await import('/scripts/app.js');
        const original=structuredClone(app.graph.serialize());
        const assert=(value,msg)=>{if(!value)throw new Error(msg);return msg;};
        const passes=[];
        const widget=(node,name)=>node.widgets?.find(w=>w.name===name);
        const add=(type,x)=>{const n=LiteGraph.createNode(type);assert(n,'Missing '+type);app.graph.add(n);n.pos=[x,130];return n;};
        try {
            // Fresh headless profile has no active official workflow. Do
            // not force the official save/load path while CanvasStore is unset.
            // Use native LiteGraph configure to validate serialization here;
            // full app.loadGraphData is separately tested in the isolated UI.
            app.graph.clear();
            const run=add('RH_Execute',60), inspect=add('RH_WorkflowInspect',540), download=add('RH_Download',1040);
            const runId=run.id, inspectId=inspect.id;
            passes.push(assert(widget(run,'instance_type')?.value==='auto','New Execute default is auto'));
            passes.push(assert(widget(run,'video_frame_mode')?.value==='all_frames','Old-compatible frame mode default'));
            passes.push(assert(widget(download,'video_frame_mode')?.value==='all_frames','Download video-frame control'));
            const slot=run.inputs.findIndex(x=>x.name==='workflow_schema');
            passes.push(assert(slot>=0 && !!inspect.connect(0,run,slot),'Workflow inspector connects to Execute'));
            const instance=widget(run,'instance_type');
            instance.value='plus';instance.callback?.call(instance,'plus',app.canvas,run);
            const frames=widget(run,'video_frame_mode');
            frames.value='disabled';frames.callback?.call(frames,'disabled',app.canvas,run);
            const saved=structuredClone(app.graph.serialize());
            app.graph.configure(saved);
            const reloaded=app.graph.getNodeById(runId);
            passes.push(assert(widget(reloaded,'instance_type')?.value==='plus','Plus survives LiteGraph snapshot restore'));
            passes.push(assert(widget(reloaded,'video_frame_mode')?.value==='disabled','Disabled frame mode survives LiteGraph snapshot restore'));
            passes.push(assert(reloaded.inputs.find(x=>x.name==='workflow_schema')?.link!=null,'Inspector link survives LiteGraph snapshot restore'));
            const old=structuredClone(saved);
            const oldExec=old.nodes.find(n=>String(n.id)===String(runId));
            oldExec.widgets_values=[777,true,true,'OLD'];
            delete oldExec.widgets_values_named;
            const oldInput=oldExec.inputs?.find(x=>x.name==='instance_type');
            if(oldInput){oldInput.name='use_high_performance';oldInput.type='BOOLEAN';if(oldInput.widget)oldInput.widget.name='use_high_performance';}
            const migration=await import('/extensions/ComfyUI_RH_API/rh_native_migration.js');
            passes.push(assert(migration.migrateGraph(old,()=>null)>0,'Live migration module decodes old Boolean graph'));
            app.graph.configure(old);
            const migrated=app.graph.getNodeById(runId);
            passes.push(assert(widget(migrated,'instance_type')?.value==='plus','Legacy Boolean true migrated to plus'));
            passes.push(assert(widget(migrated,'timeout')?.value===777,'Legacy timeout preserved'));
            passes.push(assert(widget(migrated,'output_prefix')?.value==='OLD','Legacy output prefix preserved'));
            passes.push(assert(widget(migrated,'video_frame_mode')?.value==='all_frames','Missing legacy frame mode remains all_frames'));
            return {checks:passes,originalNodes:original.nodes?.length||0,localOnly:true};
        } finally {
            app.graph.configure(original);
        }
    })()`);
    for (const check of result.checks) checks.push(check);
    const png = await cdp('Page.captureScreenshot', { format: 'png' });
    await writeFile(path.join(out, 'real-8190-ui-smoke.png'), Buffer.from(png.data, 'base64'));
    console.log(JSON.stringify({ test: 'real ComfyUI 8190 live browser', checks, failures: [] }, null, 2));
    await writeFile(path.join(out, 'real-8190-ui-result.json'), JSON.stringify({ checks, failures: [] }, null, 2));
} catch (err) {
    failure = err;
    console.error('REAL 8190 UI FAILED:', String(err));
    await writeFile(path.join(out, 'real-8190-ui-result.json'), JSON.stringify({ checks, error: String(err) }, null, 2));
} finally {
    try { await cdp('Browser.close', {}, false); } catch { chrome.kill(); }
    try { ws.close(); } catch {}
}
if (failure) process.exitCode = 1;
