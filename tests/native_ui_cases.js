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
const names = ['RH_Execute', 'RH_Params2', 'RH_UploadImage2', 'RH_UploadImage', 'RH_UploadVideo', 'RH_UploadAudio',
    'RH_UploadFile', 'RH_UploadLatent', 'RH_BatchUploadImage', 'RH_MultiInputImage'];
let nodes = names.map((name, i) => create(name, [40 + (i % 3) * 430, 80 + Math.floor(i / 3) * 300]));
let execute = nodes[0], params = nodes[1], images = nodes[2];
diagnostics.initial = nodes.map(node => ({ type: node.type, size: [...node.size],
    widgets: node.widgets?.map(w => ({ name: w.name, type: w.type, label: w.label, value: w.value })),
    inputs: node.inputs?.map(i => ({ name: i.name, type: i.type, widget: i.widget })) }));
check(nodes.length === 10 && nodes.every(n => !n.has_errors), 'All ten native nodes construct');
check(execute.title === '▶️ RH Execute', 'V2 execution logic is exposed as RH Execute');
check(params.title === '⚙️ RH Params V2', 'Params node uses the RH Params V2 display name');
check(images.title === '📤 RH Upload Image V2', 'Grouped image node uses the RH Upload Image V2 display name');
check(nodes[3].title === '📤 RH Upload Image', 'Legacy single-image node keeps the RH Upload Image display name');
check(execute.inputs.filter(i => i.name.startsWith('params.')).map(i => i.name).join(',') === 'params.params', 'RH Execute starts with only params');
check(execute.inputs.find(i => i.name === 'params.params')?.localized_name === 'params', 'First RH Execute input is displayed as params');
check(['timeout', 'use_high_performance', 'save_to_local', 'output_prefix'].every(name => widget(execute, name)), 'RH Execute fixed controls use native widgets');
const paramsSourceA = create('RH_Test_RH_PARAMS', [20, 20]);
const paramsSourceB = create('RH_Test_RH_PARAMS', [20, 120]);
check(!!paramsSourceA.connect(0, execute, execute.inputs.findIndex(i => i.name === 'params.params')), 'RH Execute params remains connectable');
await wait();
check(execute.inputs.some(i => i.name === 'params.params_1') && !execute.inputs.some(i => i.name === 'params.params_2'), 'Connecting params reveals only params_1');
check(execute.inputs.find(i => i.name === 'params.params_1')?.localized_name === 'params_1', 'Second RH Execute input is displayed as params_1');
check(!!paramsSourceB.connect(0, execute, execute.inputs.findIndex(i => i.name === 'params.params_1')), 'RH Execute params_1 accepts the second source');
await wait();
check(execute.inputs.some(i => i.name === 'params.params_2'), 'Connecting params_1 reveals params_2');
check(execute.inputs.find(i => i.name === 'params.params_2')?.localized_name === 'params_2', 'Third RH Execute input is displayed as params_2');
check(!params.inputs.some(i => /^value_\d+$/.test(i.name)), 'No standalone duplicate wildcard value socket');
check(params.inputs.some(i => i.name === 'param_count.value_1' && i.widget), 'Value input has the native widget association');
check(!params.widgets.some(w => /param_count\.enabled_\d+$/.test(w.name)), 'Params V2 has no Enable control');
check(!images.widgets.some(w => /image_count\.enabled_\d+$/.test(w.name)), 'Upload Image V2 has no Enable control');
check(!images.widgets.some(w => w.name.startsWith('image_meta_')), 'Image V2 has no handwritten DOM metadata widget');
set(params, 'param_count', '4');
await wait();
const paramGaps = params.widgets.filter(w => w._rhGroupGap === true);
check(paramGaps.length === 3, 'Four Params rows create three visual spacers');
check(paramGaps.every(w => w.computeSize(params.size[0])[1] === 0 && w.computedHeight === 4 && w.serialize === false), 'Params row spacers render as actual 4px gaps and do not serialize');
set(params, 'param_count.node_id_1', '12');
set(params, 'param_count.value_1', 'latest');
set(params, 'param_count.node_id_3', '33');
set(params, 'param_count.value_3', 'keep-three');
const source = create('RH_Test_INT', [10, 20]);
let index = params.inputs.findIndex(i => i.name === 'param_count.value_3');
check(!!source.connect(0, params, index), 'INT connects to native scalar input');
window.confirm = () => { throw new Error('Count reduction must not show a confirmation dialog'); };
set(params, 'param_count', '2');
check(widget(params, 'param_count').value === '2', 'Reducing Params count applies immediately without a dialog');
check(!widget(params, 'param_count.value_3'), 'Reduced Params rows disappear from the active UI');
set(params, 'param_count.value_1', 'newest-after-reduction');
set(params, 'param_count', '4');
check(widget(params, 'param_count.value_3')?.value === 'keep-three', 'Re-expanding Params restores hidden row values');
check(params.inputs.find(i => i.name === 'param_count.value_3')?.link != null, 'Re-expanding Params restores hidden row connections');
check(widget(params, 'param_count.value_1')?.value === 'newest-after-reduction', 'Visible Params rows keep latest values across count changes');
set(params, 'param_count.field_name_1', 'custom');
set(params, 'param_count.field_name_1.custom_field_name_1', 'prompt_text');
check(!!widget(params, 'param_count.field_name_1.custom_field_name_1'), 'Custom Field appears through native DynamicCombo');
params.setSize([420, 600]);
const size = [...params.size];
set(params, 'param_count.value_1', 'hello-world');
check(params.size.every((n, i) => n === size[i]), 'Typing a Value preserves width and height');

check(widget(images, 'image_count')?.hidden === true, 'Upload Image V2 hides Image Count in native widget visibility');
check(widget(images, 'image_count')?.value === '1' && images.inputs.some(i => i.name === 'image_count.image_1'), 'Upload Image V2 initially shows one IMAGE port');
const imageSource1 = create('RH_Test_IMAGE', [20, 420]);
check(!!imageSource1.connect(0, images, images.inputs.findIndex(i => i.name === 'image_count.image_1')), 'Image 1 accepts an IMAGE source');
await wait();
check(widget(images, 'image_count').value === '2' && images.inputs.some(i => i.name === 'image_count.image_2'), 'Connecting Image 1 automatically reveals Image 2');
set(images, 'image_count.node_id_1', '81');
const imageSource2 = create('RH_Test_IMAGE', [20, 470]);
check(!!imageSource2.connect(0, images, images.inputs.findIndex(i => i.name === 'image_count.image_2')), 'Image 2 accepts an IMAGE source');
await wait();
check(widget(images, 'image_count').value === '3' && images.inputs.some(i => i.name === 'image_count.image_3'), 'Connecting Image 2 automatically reveals Image 3');
set(images, 'image_count.node_id_2', '82');
set(images, 'image_count.node_id_3', '83');
set(images, 'image_count.field_name_3', 'custom');
set(images, 'image_count.field_name_3.custom_field_name_3', 'reference_image');
const imageSource3 = create('RH_Test_IMAGE', [20, 520]);
check(!!imageSource3.connect(0, images, images.inputs.findIndex(i => i.name === 'image_count.image_3')), 'Image 3 accepts an IMAGE source');
await wait();
check(widget(images, 'image_count').value === '4' && images.inputs.some(i => i.name === 'image_count.image_4'), 'Connecting Image 3 reveals one unused Image 4 port');
const imageGaps = images.widgets.filter(w => w._rhGroupGap === true);
check(imageGaps.length === 3 && imageGaps.every(w => w.computedHeight === 4 && w.serialize === false), 'Four Image rows retain three non-serializing 4px gaps');
images.disconnectInput(images.inputs.findIndex(i => i.name === 'image_count.image_2'));
await wait();
check(widget(images, 'image_count').value === '4' && images.inputs.find(i => i.name === 'image_count.image_3')?.link != null, 'Disconnecting Image 2 does not shift or sever Image 3');
check(widget(images, 'image_count.node_id_3')?.value === '83' && widget(images, 'image_count.field_name_3.custom_field_name_3')?.value === 'reference_image', 'Sparse image routes retain their own Node ID and custom Field');
const vacantImages = create('RH_UploadImage2', [1350, 70]);
const vacantSource = create('RH_Test_IMAGE', [1360, 440]);
check(!!vacantSource.connect(0, vacantImages, vacantImages.inputs.findIndex(i => i.name === 'image_count.image_1')), 'Temporary Image V2 test source connects');
await wait();
check(widget(vacantImages, 'image_count').value === '2', 'Unconfigured image connection still grows the next port');
vacantImages.disconnectInput(vacantImages.inputs.findIndex(i => i.name === 'image_count.image_1'));
await wait();
check(widget(vacantImages, 'image_count').value === '1' && !vacantImages.inputs.some(i => i.name === 'image_count.image_2'), 'Disconnecting an unconfigured trailing image safely shrinks the port count');
app.graph.remove(vacantImages);
app.graph.remove(vacantSource);

// Exercise all supported dynamic slots. The 12th connection is a hard cap,
// not an invitation to create an unsupported 13th graph socket.
const limitImages = create('RH_UploadImage2', [1350, 70]);
const limitSources = [];
for (let slot = 1; slot <= 12; slot++) {
    const src = create('RH_Test_IMAGE', [1360, 100 + 35 * slot]);
    limitSources.push(src);
    const inputIndex = limitImages.inputs.findIndex(i => i.name === `image_count.image_${slot}`);
    check(inputIndex >= 0 && !!src.connect(0, limitImages, inputIndex), `Image ${slot} connects at the native capacity limit`);
    await wait();
}
check(widget(limitImages, 'image_count').value === '12' &&
    limitImages.inputs.filter(i => /^image_count\.image_\d+$/.test(i.name)).length === 12 &&
    !limitImages.inputs.some(i => i.name === 'image_count.image_13'), 'Autogrow never exposes more than 12 IMAGE sockets');
app.graph.remove(limitImages);
for (const src of limitSources) app.graph.remove(src);

const paramsId = params.id;
const imagesId = images.id;
const executeId = execute.id;
const saved = structuredClone(app.graph.serialize());
diagnostics.saved = { paramsId, sourceId: source.id, nodes: saved.nodes.map(n => ({ id: n.id, type: n.type })) };

// A saved pre-V2 RH_Execute node must keep its widget values and primary params link.
const legacyExecuteGraph = structuredClone(saved);
const legacyExecute = legacyExecuteGraph.nodes.find(n => String(n.id) === String(executeId));
const primaryLegacyInput = (legacyExecute.inputs || []).find(i => i.name === 'params.params');
const removedExecuteLinks = new Set((legacyExecute.inputs || []).filter(i => i.name.startsWith('params.') && i.name !== 'params.params' && i.link != null).map(i => String(i.link)));
primaryLegacyInput.name = 'params';
primaryLegacyInput.label = 'params';
legacyExecute.inputs = (legacyExecute.inputs || []).filter(i => i.name === 'config' || i === primaryLegacyInput);
legacyExecute.widgets_values = [777, true, true, 'OLD'];
delete legacyExecute.widgets_values_named;
legacyExecuteGraph.links = (legacyExecuteGraph.links || []).filter(link => !removedExecuteLinks.has(String(Array.isArray(link) ? link[0] : link.id)));
for (const n of legacyExecuteGraph.nodes) for (const output of n.outputs || []) {
    if (Array.isArray(output.links)) output.links = output.links.filter(id => !removedExecuteLinks.has(String(id)));
}
await app.loadGraphData(legacyExecuteGraph);
execute = app.graph.getNodeById(executeId);
check(widget(execute, 'timeout')?.value === 777 && widget(execute, 'use_high_performance')?.value === true && widget(execute, 'save_to_local')?.value === true && widget(execute, 'output_prefix')?.value === 'OLD', 'Legacy RH Execute widget values load into the new implementation without shifting');
check(execute.inputs.find(i => i.name === 'params.params')?.link != null, 'Legacy RH Execute params link migrates to the new Autogrow chain');

// The immediately previous V2 graph used fixed params + extra_params.params_2...
const previousV2Graph = structuredClone(saved);
const previousV2Execute = previousV2Graph.nodes.find(n => String(n.id) === String(executeId));
for (const input of previousV2Execute.inputs || []) {
    if (input.name === 'params.params') input.name = 'params';
    else {
        const match = /^params\.params_(\d+)$/.exec(input.name);
        if (match) input.name = `extra_params.params_${Number(match[1]) + 1}`;
    }
}
await app.loadGraphData(previousV2Graph);
execute = app.graph.getNodeById(executeId);
check(execute.inputs.find(i => i.name === 'params.params')?.link != null, 'Previous V2 params migrates without losing its link');
check(execute.inputs.find(i => i.name === 'params.params_1')?.link != null, 'Previous V2 params_2 shifts to params_1 without losing its link');
check(execute.inputs.find(i => i.name === 'params.params_1')?.localized_name === 'params_1', 'Previous V2 migrated input is displayed as params_1');

// Deprecated RH_Execute2 graphs use the same shift: params, params_2, params_3 -> params, params_1, params_2.
const execute2Graph = structuredClone(saved);
const execute2 = execute2Graph.nodes.find(n => String(n.id) === String(executeId));
execute2.type = 'RH_Execute2';
for (const input of execute2.inputs || []) {
    if (input.name === 'params.params') input.name = 'params';
    else {
        const match = /^params\.params_(\d+)$/.exec(input.name);
        if (match) input.name = `params_${Number(match[1]) + 1}`;
    }
}
await app.loadGraphData(execute2Graph);
execute = app.graph.getNodeById(executeId);
check(execute.type === 'RH_Execute', 'Deprecated RH Execute 2 graph migrates to RH Execute');
check(execute.inputs.find(i => i.name === 'params.params_1')?.link != null, 'Deprecated RH Execute 2 params_2 shifts to params_1');

await app.loadGraphData(saved);
execute = app.graph.getNodeById(executeId);
params = app.graph.getNodeById(paramsId);
images = app.graph.getNodeById(imagesId);
check(widget(images, 'image_count')?.hidden === true && widget(images, 'image_count')?.value === '4', 'Image Count stays hidden and restores its automatic row state on reload');
check(images.inputs.find(i => i.name === 'image_count.image_3')?.link != null && widget(images, 'image_count.node_id_3')?.value === '83', 'Image 3 connection and its routing survive save/reload without reindexing');
check(widget(images, 'image_count.field_name_3.custom_field_name_3')?.value === 'reference_image', 'Image 3 custom Field survives save/reload');
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
check(!JSON.stringify(saved).includes('__rh_group_gap_'), 'Visual row spacers are not serialized into the workflow');

// Native-v1 Params briefly had Enable controls. They must migrate without shifting values.
const nativeV1 = structuredClone(saved);
const v1Param = nativeV1.nodes.find(n => String(n.id) === String(paramsId));
v1Param.widgets_values_named ??= {};
for (let slot = 1; slot <= 4; slot++) {
    v1Param.widgets_values_named[`param_count.enabled_${slot}`] = true;
    v1Param.inputs.push({ name: `param_count.enabled_${slot}`, type: 'BOOLEAN', widget: { name: `param_count.enabled_${slot}` }, link: null });
}
await app.loadGraphData(nativeV1);
params = app.graph.getNodeById(paramsId);
check(!params.widgets.some(w => /param_count\.enabled_\d+$/.test(w.name)), 'Native-v1 Params Enable controls are removed during migration');
check(widget(params, 'param_count.value_1')?.value === 'hello-world' && widget(params, 'param_count.value_3')?.value === 'keep-three', 'Native-v1 Params values survive Enable removal');

// Exercise actual legacy-workflow load, not a mocked widget factory.
const legacy = structuredClone(saved);
const old = legacy.nodes.find(n => String(n.id) === String(paramsId));
old.properties = {};
delete old.widgets_values_named;
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
    { kind: 'rh_upload_image2', slot_id: 1, enabled: false },
    { kind: 'rh_upload_image2', slot_id: 3, enabled: true, node_id: '83', field_name: 'custom', custom_field_name: 'reference_image' },
];
oldImage.inputs = [{ name: 'config', type: 'RH_CONFIG', link: null }, { name: 'previous_params', type: 'RH_PARAMS', link: null },
    { name: 'image_1', type: 'IMAGE', link: null }, { name: 'image_3', type: 'IMAGE', link: 9101 }];
// This test replaces the saved image-node inputs: also remove the original
// graph links and source backlinks, otherwise stale target slots could point
// at unrelated new inputs and produce a graph that ComfyUI never saved.
const staleIds = new Set(sparse.links.filter(link => String(Array.isArray(link) ? link[3] : link.target_id) === String(oldImage.id))
    .map(link => String(Array.isArray(link) ? link[0] : link.id)));
sparse.links = sparse.links.filter(link => !staleIds.has(String(Array.isArray(link) ? link[0] : link.id)));
for (const node of sparse.nodes) for (const output of node.outputs || []) {
    if (Array.isArray(output.links)) output.links = output.links.filter(id => !staleIds.has(String(id)));
}
const sparseSource = sparse.nodes.find(n => String(n.id) === String(badSource.id));
sparseSource.outputs[0].links = [9101];
sparse.links.push([9101, badSource.id, 0, oldImage.id, 3, 'IMAGE']);
sparse.last_link_id = 9101;
await app.loadGraphData(sparse);
await wait();
const restoredImage = app.graph.getNodeById(oldImage.id);
diagnostics.sparseImage = { count: widget(restoredImage, 'image_count').value, inputs: restoredImage.inputs?.map(i => [i.name, i.link]), node3: widget(restoredImage, 'image_count.node_id_3')?.value };
check(widget(restoredImage, 'image_count').value === '4' && restoredImage.inputs.some(i => i.name === 'image_count.image_3'), 'Sparse Image V2 retains slot 3 and adds only a trailing empty Image 4');
check(widget(restoredImage, 'image_count.node_id_3').value === '83', 'Image V2 keeps independent target node');
check(widget(restoredImage, 'image_count.field_name_3.custom_field_name_3').value === 'reference_image', 'Image V2 custom field migrates');
check(widget(restoredImage, 'image_count.node_id_1').value === '' && !restoredImage.widgets.some(w => /image_count\.enabled_\d+$/.test(w.name)), 'Empty disabled legacy image rows migrate without an Enable control');
check(restoredImage.inputs.find(i => i.name === 'image_count.image_3')?.link != null, 'Image V2 media connection migrates');
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
