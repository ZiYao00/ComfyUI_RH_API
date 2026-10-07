// Legacy workflow data adapter only. All new controls are constructed by ComfyUI.
export const GROUPS = Object.freeze({ RH_Params2: ["param_count", 16], RH_UploadImage2: ["image_count", 12] });
export const NATIVE_VERSION = 1;

const scalarText = (value) => value == null ? "" : String(value);
const slotOf = (name) => Number(String(name).match(/_(\d+)$/)?.[1] || 0);

export function isLegacyGroup(node) {
    const group = GROUPS[node.type];
    if (!group) return false;
    if (node.type === "RH_Params2") {
        const hasRemovedEnable = (node.inputs || []).some((input) => input.name.startsWith("param_count.enabled_")) ||
            Object.keys(node.widgets_values_named || {}).some((name) => name.startsWith("param_count.enabled_"));
        if (hasRemovedEnable) return true;
    }
    if (node.properties?.rh_native_ui_version === NATIVE_VERSION) return false;
    // The official group selector is serialized as a string; the oldest Params count was a number.
    return !(typeof node.widgets_values?.[0] === "string" && /^\d+$/.test(node.widgets_values[0]) &&
        (node.inputs || []).some((input) => input.name.startsWith(group[0] + ".")));
}

export function readLegacyRows(node) {
    const config = GROUPS[node.type];
    if (!config) throw new Error("Unsupported RH group migration: " + node.type);
    const [group, maximum] = config;
    const image = node.type === "RH_UploadImage2";
    const values = node.widgets_values || [];
    const named = node.widgets_values_named || {};
    const hasNativeEnable = !image && (node.inputs || []).some((input) => input.name.startsWith("param_count.enabled_"));
    const nativeValues = { ...named };
    if (hasNativeEnable && !Object.keys(nativeValues).length) {
        let valueIndex = 0;
        for (const input of node.inputs || []) {
            if (!input.widget || valueIndex >= values.length) continue;
            nativeValues[input.name] = values[valueIndex++];
        }
    }
    let rows = [];
    if (!image && nativeValues.param_count !== undefined) {
        const count = Number(nativeValues.param_count);
        if (!Number.isInteger(count) || count < 1 || count > maximum) throw new Error("Invalid native RH parameter count.");
        for (let slot = 1; slot <= count; slot++) {
            rows.push({
                slot_id: slot,
                enabled: nativeValues[`param_count.enabled_${slot}`] !== false,
                node_id: nativeValues[`param_count.node_id_${slot}`],
                field_name: nativeValues[`param_count.field_name_${slot}`],
                custom_field_name: nativeValues[`param_count.field_name_${slot}.custom_field_name_${slot}`],
                local_value: nativeValues[`param_count.value_${slot}`],
            });
        }
    }
    if (!rows.length) rows = values.filter((value) => value && typeof value === "object" && !Array.isArray(value) &&
        (value.kind === "rh_param2" || value.kind === "rh_upload_image2" || value.node_id !== undefined));
    if (!rows.length && !image) {
        for (const value of values) {
            if (typeof value !== "string" || !value.trim().startsWith("[")) continue;
            try {
                const parsed = JSON.parse(value);
                if (Array.isArray(parsed)) { rows = parsed; break; }
            } catch { /* A normal prompt can start with '['; it is not necessarily metadata. */ }
        }
    }
    if (!rows.length && !image && typeof values[0] === "number") {
        const count = values[0];
        if (!Number.isInteger(count) || count < 1 || count > maximum) throw new Error("Invalid legacy RH parameter count.");
        for (let slot = 1; slot <= count; slot++) {
            const offset = 1 + (slot - 1) * 4;
            rows.push({ slot_id: slot, node_id: values[offset], field_name: values[offset + 1],
                custom_field_name: values[offset + 2], local_value: values[offset + 3] });
        }
    }
    const bySlot = new Map();
    for (const [index, row] of rows.entries()) {
        const slot = Number(row.slot_id || index + 1);
        if (!Number.isInteger(slot) || slot < 1 || slot > maximum || bySlot.has(slot)) {
            throw new Error("RH migration stopped: invalid or duplicate slot " + slot + ". Original workflow is unchanged.");
        }
        const normalized = {
            slot, enabled: row.enabled !== false,
            node_id: scalarText(row.node_id), field_name: scalarText(row.field_name || (image ? "image" : "text")),
            custom_field_name: scalarText(row.custom_field_name),
            value: scalarText(row.local_value ?? row.field_value ?? ""),
        };
        if (!image && !normalized.enabled) {
            const hasLink = (node.inputs || []).some((input) => slotOf(input.name) === slot && input.link != null);
            const hasContent = normalized.node_id || normalized.custom_field_name || normalized.value ||
                (normalized.field_name && normalized.field_name !== "text") || hasLink;
            if (hasContent) {
                throw new Error(`RH migration stopped: disabled Params 2 row ${slot} contains saved data or a connection. Enable was removed from Params 2, so this row cannot be activated silently. Open the original workflow with the previous version and either enable or clear that row first.`);
            }
            normalized.enabled = true;
        }
        bySlot.set(slot, normalized);
    }
    const linkedSlots = (node.inputs || []).map((input) => slotOf(input.name));
    const count = Math.max(1, !image && typeof values[0] === "number" ? values[0] : 1,
        ...bySlot.keys(), ...linkedSlots);
    if (count > maximum) throw new Error("RH migration stopped: saved slots exceed the supported limit.");
    for (let slot = 1; slot <= count; slot++) {
        if (!bySlot.has(slot)) bySlot.set(slot, { slot, enabled: false, node_id: "", field_name: image ? "image" : "text", custom_field_name: "", value: "" });
    }
    return { group, count, image, rows: [...bySlot.values()].sort((a, b) => a.slot - b.slot) };
}

export function newInputName(name, group) {
    if (name === "config" || name === "previous_params") return name;
    if (name.startsWith(group + ".")) return name;
    const custom = /^custom_field_name_(\d+)$/.exec(name);
    if (custom) return `${group}.field_name_${custom[1]}.${name}`;
    if (/^local_value_\d+$/.test(name)) return group + "." + name.replace("local_value_", "value_");
    return group + "." + name;
}

export function applyRowValues(node, decoded) {
    const widget = (name) => node.widgets?.find((item) => item.name === name);
    const selector = widget(decoded.group);
    if (!selector) throw new Error("RH native schema is not loaded. Restart ComfyUI, then refresh this page.");
    selector.value = String(decoded.count);
    for (const row of decoded.rows) {
        const prefix = `${decoded.group}.`;
        const set = (name, value) => {
            const target = widget(prefix + name);
            if (!target) throw new Error("Missing native RH widget: " + name);
            target.value = value;
        };
        set(`node_id_${row.slot}`, row.node_id);
        const field = widget(`${prefix}field_name_${row.slot}`);
        const options = typeof field?.options?.values === "function" ? field.options.values() : field?.options?.values;
        const known = Array.isArray(options) && options.includes(row.field_name);
        const actual = known ? row.field_name : "custom";
        set(`field_name_${row.slot}`, actual);
        if (actual === "custom") set(`field_name_${row.slot}.custom_field_name_${row.slot}`, known ? row.custom_field_name : row.field_name);
        if (!decoded.image) set(`value_${row.slot}`, row.value);
        if (decoded.image) set(`enabled_${row.slot}`, row.enabled);
    }
}

function remapGraphLink(graph, nodeId, linkId, targetSlot) {
    const links = Array.isArray(graph.links) ? graph.links : Object.values(graph.links || {});
    const link = links.find((item) => String(Array.isArray(item) ? item[0] : item.id) === String(linkId));
    if (!link) throw new Error("RH migration stopped: missing graph link " + linkId);
    if (String(Array.isArray(link) ? link[3] : link.target_id) !== String(nodeId)) throw new Error("RH migration found an inconsistent link target.");
    if (Array.isArray(link)) link[4] = targetSlot;
    else link.target_slot = targetSlot;
}

export function migrateGraph(graphData, createNode) {
    // Work on a copy. Validation failure must not partially rewrite the supplied workflow.
    const staged = structuredClone(graphData);
    let migrated = 0;
    // ComfyUI 1.53 constructs subgraph definitions before this extension hook.
    // Do not partially migrate an already-instantiated legacy definition.
    for (const subgraph of staged.definitions?.subgraphs || []) {
        if ((subgraph.nodes || []).some(isLegacyGroup)) {
            throw new Error("RH migration stopped: this workflow contains a legacy RH group inside a subgraph. Migrate an expanded copy first; the original workflow is unchanged.");
        }
    }
    for (const old of staged.nodes || []) {
        if (!isLegacyGroup(old)) continue;
        const decoded = readLegacyRows(old);
        const temporary = createNode(old.type);
        if (!temporary) throw new Error("Cannot construct native RH node " + old.type);
        try {
            applyRowValues(temporary, decoded);
            const generated = temporary.serialize();
            const occupied = new Set();
            for (const input of old.inputs || []) {
                if (input.link == null) continue;
                const name = newInputName(input.name, decoded.group);
                const slot = (generated.inputs || []).findIndex((item) => item.name === name);
                if (slot < 0 || occupied.has(slot)) {
                    throw new Error("RH migration stopped: unsupported or conflicting connections at " + input.name + ". Keep the original workflow and resolve this input first.");
                }
                occupied.add(slot);
                generated.inputs[slot].link = input.link;
                remapGraphLink(staged, old.id, input.link, slot);
            }
            old.inputs = generated.inputs;
            old.widgets_values = generated.widgets_values;
            // Replace both official serialization forms; do not leave stale
            // named values that could override migrated positional values.
            if (generated.widgets_values_named) old.widgets_values_named = generated.widgets_values_named;
            else delete old.widgets_values_named;
            delete old.widget_values;
            old.properties = { ...old.properties, rh_native_ui_version: NATIVE_VERSION };
            migrated++;
        } finally {
            temporary.onRemoved?.();
        }
    }
    if (migrated) {
        graphData.nodes = staged.nodes;
        graphData.links = staged.links;
    }
    return migrated;
}
