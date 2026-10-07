import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { readLegacyRows, newInputName, isLegacyGroup, migrateGraph } from '../js/rh_native_migration.js';

const legacy = (values, inputs = []) => ({ type: 'RH_Params2', widgets_values: values, inputs });

test('flat count format preserves field and value positions', () => {
    const data = readLegacyRows(legacy([2, '12', 'custom', 'prompt', 'hello', '13', 'width', '', 0]));
    assert.equal(data.count, 2);
    assert.equal(data.rows[0].custom_field_name, 'prompt');
    assert.equal(data.rows[1].value, '0');
});
test('disabled legacy Params rows with saved data stop instead of becoming active', () => {
    assert.throws(
        () => readLegacyRows(legacy([JSON.stringify([{ slot_id: 1, enabled: false, node_id: '12', field_value: false }])])),
        /Enable was removed/
    );
});
test('empty disabled legacy Params row can migrate as an empty row', () => {
    const data = readLegacyRows(legacy([JSON.stringify([{ slot_id: 1, enabled: false }])]));
    assert.equal(data.rows[0].enabled, true);
    assert.equal(data.rows[0].node_id, '');
});
test('native v1 Params with Enable is detected and decoded by named widget values', () => {
    const node = {
        type: 'RH_Params2',
        inputs: [{ name: 'param_count.enabled_1', link: null }],
        widgets_values: ['1', '12', 'width', '1024', true],
        widgets_values_named: {
            param_count: '1',
            'param_count.node_id_1': '12',
            'param_count.field_name_1': 'width',
            'param_count.value_1': '1024',
            'param_count.enabled_1': true,
        },
    };
    assert.equal(isLegacyGroup(node), true);
    const data = readLegacyRows(node);
    assert.equal(data.rows[0].node_id, '12');
    assert.equal(data.rows[0].field_name, 'width');
    assert.equal(data.rows[0].value, '1024');
});
test('native v1 Params can decode positional widget values when named values are missing', () => {
    const node = {
        type: 'RH_Params2',
        inputs: [
            { name: 'previous_params', link: null },
            { name: 'param_count', widget: { name: 'param_count' }, link: null },
            { name: 'param_count.node_id_1', widget: { name: 'param_count.node_id_1' }, link: null },
            { name: 'param_count.field_name_1', widget: { name: 'param_count.field_name_1' }, link: null },
            { name: 'param_count.value_1', widget: { name: 'param_count.value_1' }, link: null },
            { name: 'param_count.enabled_1', widget: { name: 'param_count.enabled_1' }, link: null },
        ],
        widgets_values: ['1', '12', 'width', '1024', true],
    };
    const data = readLegacyRows(node);
    assert.equal(data.rows[0].node_id, '12');
    assert.equal(data.rows[0].field_name, 'width');
    assert.equal(data.rows[0].value, '1024');
});
test('sparse images keep IDs and inactive gaps', () => {
    const data = readLegacyRows({ type: 'RH_UploadImage2', widgets_values: [
        { kind: 'rh_upload_image2', slot_id: 3, node_id: '31', field_name: 'reference' }
    ], inputs: [{ name: 'image_3', link: 1 }] });
    assert.equal(data.count, 3);
    assert.deepEqual(data.rows.map(x => [x.slot, x.enabled]), [[1, false], [2, false], [3, true]]);
});
test('duplicate and oversized slots fail rather than silently overwrite', () => {
    assert.throws(() => readLegacyRows(legacy([{ node_id: '1', slot_id: 1 }, { node_id: '2', slot_id: 1 }])), /duplicate/);
    assert.throws(() => readLegacyRows(legacy([17])), /Invalid/);
});
test('input mappings preserve the single effective value and custom field path', () => {
    assert.equal(newInputName('value_2', 'param_count'), 'param_count.value_2');
    assert.equal(newInputName('local_value_2', 'param_count'), 'param_count.value_2');
    assert.equal(newInputName('custom_field_name_2', 'param_count'), 'param_count.field_name_2.custom_field_name_2');
    assert.equal(newInputName('previous_params', 'param_count'), 'previous_params');
});
test('new workflows are not migrated twice', () => {
    assert.equal(isLegacyGroup({ type: 'RH_Params2', properties: { rh_native_ui_version: 1 } }), false);
    assert.equal(isLegacyGroup({ type: 'RH_Params2', widgets_values: ['1'], inputs: [{ name: 'param_count.value_1' }] }), false);
});
test('migration failure leaves original workflow untouched', () => {
    const graph = { nodes: [legacy([{ node_id: '1', slot_id: 99 }])], links: [] };
    const before = structuredClone(graph);
    assert.throws(() => migrateGraph(graph, () => { throw new Error('must not construct'); }), /invalid/);
    assert.deepEqual(graph, before);
});
test('legacy subgraphs require explicit migration instead of silently losing data', () => {
    const graph = { nodes: [], links: [], definitions: { subgraphs: [{ id: 'sub', nodes: [legacy([1])] }] } };
    const before = structuredClone(graph);
    assert.throws(() => migrateGraph(graph, () => null), /subgraph/);
    assert.deepEqual(graph, before);
});
test('new frontend does not rebuild controls or replace prototype.configure', async () => {
    for (const filename of ['rh_params2.js', 'rh_upload_image2.js', 'rh_native_ui.js', 'rh_native_groups.js']) {
        const source = await readFile(new URL('../js/' + filename, import.meta.url), 'utf8');
        assert.doesNotMatch(source, /addDOMWidget\s*\(|\.addInput\s*\(|prototype\.configure\s*=/);
    }
});
