// Executed inside an async function by verify_native_ui.mjs, in a fresh test page.
const { app } = await import('/scripts/app.js');
const migration = await import('/extensions/ComfyUI_RH_API/rh_native_migration.js');
const passes = [], failures = [], diagnostics = {};
window.__rhTestReport = { passes, failures, diagnostics };
const check = (value, title) => (value ? passes : failures).push(title);
const wait = () => new Promise(resolve => setTimeout(resolve, 80));
const widget = (node, name) => node.widgets?.find(item => item.name === name);
const set = (node, name, value, callback = true) => {
    const target = widget(node, name);
    if (!target) throw new Error('Missing widget ' + name + ': ' + node.widgets?.map(w => w.name).join(', '));
    target.value = value;
    if (callback) target.callback?.call(target, value, app.canvas, node);
};
const create = (name, pos) => {
    const node = LiteGraph.createNode(name);
    if (!node) throw new Error('Missing node: ' + name);
    app.graph.add(node);
    node.pos = pos;
    return node;
};
await app.extensionManager.command.execute('Comfy.NewBlankWorkflow');
app.graph.clear();
const names = ['RH_Params2', 'RH_UploadImage2', 'RH_UploadImage', 'RH_UploadVideo', 'RH_UploadAudio',
    'RH_UploadFile', 'RH_UploadLatent', 'RH_BatchUploadImage', 'RH_MultiInputImage'];
let nodes = names.map((name, i) => create(name, [40 + (i % 3) * 430, 80 + Math.floor(i / 3) * 300]));
let params = nodes[0], images = nodes[1];
diagnostics.initial = nodes.map(node => ({ type: node.type, size: [...node.size],
    widgets: node.widgets?.map(w => ({ name: w.name, type: w.type, label: w.label, value: w.value })),
    inputs: node.inputs?.map(i => ({ name: i.name, type: i.type, widget: i.widget })) }));
check(nodes.length === 9 && nodes.every(n => !n.has_errors), 'All nine native nodes construct');
check(!params.inputs.some(i => /^value_\d+$/.test(i.name)), 'No standalone duplicate wildcard value socket');
check(params.inputs.some(i => i.name === 'param_count.value_1' && i.widget), 'Value input has the native widget association');
check(!images.widgets.some(w => w.name.startsWith('image_meta_')), 'Image 2 has no handwritten DOM metadata widget');
set(params, 'param_count', '4');
set(params, 'param_count.node_id_1', '12');
set(params, 'param_count.value_1', 'latest');
set(params, 'param_count.node_id_3', '33');
set(params, 'param_count.value_3', 'keep-three');
const source = create('RH_Test_INT', [10, 20]);
let index = params.inputs.findIndex(i => i.name === 'param_count.value_3');
check(!!source.connect(0, params, index), 'INT connects to native scalar input');
let confirmations = 0;
window.confirm = () => { confirmations++; return false; };
set(params, 'param_count', '2');
check(widget(params, 'param_count').value === '4', 'Cancel destructive reduction restores row count');
check(widget(params, 'param_count.value_3')?.value === 'keep-three', 'Cancel reduction restores row value');
check(params.inputs.find(i => i.name === 'param_count.value_3')?.link != null, 'Cancel reduction restores connection');
check(confirmations === 1, 'Destructive reduction requests confirmation once');
window.confirm = () => true;
set(params, 'param_count', '2');
set(params, 'param_count.value_1', 'newest-after-reduction');
set(params, 'param_count', '4');
check(widget(params, 'param_count.value_1')?.value === 'newest-after-reduction', 'Common rows keep latest values across count changes');
set(params, 'param_count.field_name_1', 'custom');
set(params, 'param_count.field_name_1.custom_field_name_1', 'prompt_text');
check(!!widget(params, 'param_count.field_name_1.custom_field_name_1'), 'Custom Field appears through native DynamicCombo');
params.setSize([420, 600]);
const size = [...params.size];
set(params, 'param_count.value_1', 'hello-world');
check(params.size.every((n, i) => n === size[i]), 'Typing a Value preserves width and height');
const paramsId = params.id;
const saved = structuredClone(app.graph.serialize());
diagnostics.saved = { paramsId, sourceId: source.id, nodes: saved.nodes.map(n => ({ id: n.id, type: n.type })) };
await app.loadGraphData(saved);
params = app.graph.getNodeById(paramsId);
check(widget(params, 'param_count.value_1')?.value === 'hello-world', 'Save/reload preserves values');
check(widget(params, 'param_count.field_name_1.custom_field_name_1')?.value === 'prompt_text', 'Save/reload preserves custom field');
check(params.size.every((n, i) => Math.abs(n - size[i]) < 1), 'Save/reload preserves user node size');
const clone = params.clone();
check(widget(clone, 'param_count.value_1')?.value === 'hello-world', 'Native clone preserves values');
clone.onRemoved?.();
const beforePaste = new Set(app.graph._nodes.map(n => String(n.id)));
app.canvas.copyToClipboard([params]);
app.canvas.pasteFromClipboard({ position: [600, 100] });
const pasted = app.graph._nodes.find(n => !beforePaste.has(String(n.id)) && n.type === 'RH_Params2');
check(pasted && widget(pasted, 'param_count.value_1')?.value === 'hello-world', 'Native clipboard copy/paste preserves values');
check(pasted && pasted.id != null && pasted.id !== 'undefined', 'Clipboard assigns a valid new node ID');
if (typeof app.extensionManager.command?.execute === 'function') {
    await wait();
    await app.extensionManager.command.execute('Comfy.Undo');
    await wait();
    check(app.graph._nodes.filter(n => n.type === 'RH_Params2').length === 1, 'Native Undo reverses clipboard paste');
    await app.extensionManager.command.execute('Comfy.Redo');
    await wait();
    check(app.graph._nodes.filter(n => n.type === 'RH_Params2').length === 2, 'Native Redo restores pasted node');
    check(app.graph._nodes.filter(n => n.type === 'RH_Params2').every(n => widget(n, 'param_count.value_1')?.value === 'hello-world'), 'Undo/Redo preserves dynamic widget values');
    params = app.graph.getNodeById(paramsId);
} else failures.push('Native command API is available for Undo/Redo regression');
const prompt = await app.graphToPrompt();
diagnostics.prompt = prompt.output;
check(!JSON.stringify(prompt.output).includes('local_value_'), 'API prompt has no second local-value field');

// Exercise actual legacy-workflow load, not a mocked widget factory.
const legacy = structuredClone(saved);
const old = legacy.nodes.find(n => String(n.id) === String(paramsId));
old.properties = {};
old.widgets_values = [2, '12', 'custom', 'prompt_text', 'legacy-text', '13', 'width', '', '1024'];
old.inputs = [{ name: 'previous_params', type: 'RH_PARAMS', link: null }, { name: 'value_1', type: '*', link: 9001 }, { name: 'value_2', type: '*', link: null }];
legacy.links = legacy.links.filter(link => String(Array.isArray(link) ? link[3] : link.target_id) !== String(paramsId));
const legacySource = legacy.nodes.find(n => String(n.id) === String(source.id));
legacySource.outputs[0].links = [9001];
legacy.links.push([9001, source.id, 0, paramsId, 1, 'INT']);
legacy.last_link_id = Math.max(9001, legacy.last_link_id || 0);
await app.loadGraphData(legacy);
params = app.graph.getNodeById(paramsId);
check(widget(params, 'param_count.value_1')?.value === 'legacy-text', 'Legacy flat fallback migrates to the one native Value');
check(params.inputs.find(i => i.name === 'param_count.value_1')?.link != null, 'Legacy external value link migrates to the same native Value');
check(widget(params, 'param_count.field_name_1.custom_field_name_1')?.value === 'prompt_text', 'Legacy custom field migrates');
check(widget(params, 'param_count.value_2')?.value === '1024', 'Legacy second row does not shift during migration');

// Exercise all scalar types, native reroute/primitive and media type rejection.
const valueSlot = () => params.inputs.findIndex(i => i.name === 'param_count.value_2');
for (const type of ['STRING', 'INT', 'FLOAT', 'BOOLEAN']) {
    const src = create('RH_Test_' + type, [20, 20]);
    check(!!src.connect(0, params, valueSlot()), type + ' connects to the same Value');
    params.disconnectInput(valueSlot());
}
check(widget(params, 'param_count.value_2').value === '1024', 'Disconnect restores the saved local Value');
const badSource = create('RH_Test_IMAGE', [20, 20]);
check(!badSource.connect(0, params, valueSlot()), 'IMAGE cannot connect to a scalar Value');
for (const type of ['Reroute', 'PrimitiveNode']) {
    if (!LiteGraph.registered_node_types[type]) { failures.push('Official ' + type + ' registered'); continue; }
    const src = create(type, [20, 20]);
    if (type === 'Reroute') {
        const intSource = create('RH_Test_INT', [0, 0]);
        intSource.connect(0, src, 0);
    }
    check(!!src.connect(0, params, valueSlot()), 'Official ' + type + ' connects to Value');
    params.disconnectInput(valueSlot());
}

// Sparse legacy Image 2 slots must retain independent mapping and links.
const sparse = structuredClone(app.graph.serialize());
const oldImage = sparse.nodes.find(n => n.type === 'RH_UploadImage2');
oldImage.properties = {};
delete oldImage.widgets_values_named;
oldImage.widgets_values = [
    { kind: 'rh_upload_image2', slot_id: 1, enabled: false, node_id: '81', field_name: 'image' },
    { kind: 'rh_upload_image2', slot_id: 3, enabled: true, node_id: '83', field_name: 'custom', custom_field_name: 'reference_image' },
];
oldImage.inputs = [{ name: 'config', type: 'RH_CONFIG', link: null }, { name: 'previous_params', type: 'RH_PARAMS', link: null },
    { name: 'image_1', type: 'IMAGE', link: null }, { name: 'image_3', type: 'IMAGE', link: 9101 }];
const sparseSource = sparse.nodes.find(n => String(n.id) === String(badSource.id));
sparseSource.outputs[0].links = [9101];
sparse.links.push([9101, badSource.id, 0, oldImage.id, 3, 'IMAGE']);
sparse.last_link_id = 9101;
await app.loadGraphData(sparse);
const restoredImage = app.graph.getNodeById(oldImage.id);
check(widget(restoredImage, 'image_count').value === '3', 'Sparse Image 2 slot IDs do not renumber');
check(widget(restoredImage, 'image_count.node_id_3').value === '83', 'Image 2 keeps independent target node');
check(widget(restoredImage, 'image_count.field_name_3.custom_field_name_3').value === 'reference_image', 'Image 2 custom field migrates');
check(widget(restoredImage, 'image_count.enabled_1').value === false && widget(restoredImage, 'image_count.enabled_2').value === false, 'Disabled and missing image slots remain inactive');
check(restoredImage.inputs.find(i => i.name === 'image_count.image_3')?.link != null, 'Image 2 media connection migrates');
const imageSaved = structuredClone(app.graph.serialize());
await app.loadGraphData(imageSaved);
check(app.graph.getNodeById(oldImage.id).inputs.find(i => i.name === 'image_count.image_3')?.link != null, 'Image 2 link survives another save/reload');

// Hook failures must not silently continue as runnable default-valued RH nodes.
const malformed = structuredClone(imageSaved);
const malformedParam = malformed.nodes.find(n => n.type === 'RH_Params2');
malformedParam.properties = {};
malformedParam.widgets_values = [99];
delete malformedParam.widgets_values_named;
const malformedBefore = JSON.stringify(malformed);
let migrationAlert = '';
window.alert = message => { migrationAlert = message; };
await app.loadGraphData(malformed);
check(app.graph._nodes.some(n => n.type === 'RH_MigrationRequired'), 'Invalid migration becomes a blocked missing-node placeholder');
check(migrationAlert.includes('original file'), 'Invalid migration displays an explicit warning');
check(JSON.stringify(malformed) === malformedBefore, 'Invalid migration does not mutate the supplied original workflow');

// Final compact scene contains the four most frequently used node types.
await app.extensionManager.command.execute('Comfy.NewBlankWorkflow');
app.graph.clear();
for (const [i, type] of ['RH_Params2', 'RH_UploadImage2', 'RH_UploadVideo', 'RH_UploadAudio'].entries()) {
    const node = create(type, [80 + i * 410, 180]);
    node.setSize([360, node.computeSize()[1]]);
    if (type === 'RH_Params2') { set(node, 'param_count.node_id_1', '12'); set(node, 'param_count.value_1', '23'); }
    if (type === 'RH_UploadImage2') set(node, 'image_count.node_id_1', '42');
}
app.canvas.ds.scale = 1;
app.canvas.ds.offset = [0, 0];
app.canvas.setDirty(true, true);
await wait();
return { passes, failures, diagnostics };
