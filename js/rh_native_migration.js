// Legacy workflow data adapter only. All new controls are constructed by ComfyUI.
export const GROUPS = Object.freeze({ RH_Params2: ["param_count", 16], RH_UploadImage2: ["image_count", 12] });
export const NATIVE_VERSION = 2;

const scalarText = (value) => value == null ? "" : String(value);
const slotOf = (name) => Number(String(name).match(/_(\d+)$/)?.[1] || 0);

export function isLegacyExecute(node) {
    if (node.type === "RH_Execute2") return true;
    if (node.type !== "RH_Execute") return false;
    return (node.inputs || []).some((input) => input.name === "params" || input.name.startsWith("extra_params."));
}

function newExecuteInputName(nodeType, name) {
    if (name === "params") return "params.params";
    if (nodeType === "RH_Execute") {
        const match = /^extra_params\.params_(\d+)$/.exec(name);
        if (!match) {
            if (name.startsWith("extra_params.")) throw new Error("RH Execute migration stopped: unsupported input " + name + ".");
            return name;
        }
        const oldIndex = Number(match[1]);
        if (oldIndex < 2 || oldIndex > 16) throw new Error("RH Execute migration stopped: unsupported params index " + oldIndex + ".");
        return `params.params_${oldIndex - 1}`;
    }
    if (nodeType === "RH_Execute2") {
        const match = /^params_(\d+)$/.exec(name);
        if (!match) return name;
        const oldIndex = Number(match[1]);
        if (oldIndex < 2 || oldIndex > 16) throw new Error("RH Execute 2 migration stopped: unsupported params index " + oldIndex + ".");
        return `params.params_${oldIndex - 1}`;
    }
    return name;
}

export function migrateExecuteNode(node) {
    if (!isLegacyExecute(node)) return false;
    const sourceType = node.type;
    const mapped = new Set();
    const planned = (node.inputs || []).map((input) => {
        const name = newExecuteInputName(sourceType, input.name);
        if (mapped.has(name)) throw new Error("RH Execute migration stopped: conflicting input " + name + ".");
        mapped.add(name);
        return { input, name };
    });
    for (const { input, name } of planned) {
        input.name = name;
        const displayName = name.split(".").at(-1);
        if (input.label && /^params(?:[ _]\d+)?$/.test(input.label)) input.label = displayName;
        if (input.localized_name && /^params(?:[ _]\d+)?$/.test(input.localized_name)) input.localized_name = displayName;
    }
    node.type = "RH_Execute";
    return true;
}

// Execute instance migration is separate from Params/Image UI migrations.
// Keep NATIVE_VERSION unchanged; this version only governs the instance selector.
export const INSTANCE_VERSION = 1;

export function isLegacyInstance(node) {
    if (!["RH_Execute", "RH_Execute2"].includes(node.type)) return false;
    const named = node.widgets_values_named || {};
    return typeof node.widgets_values?.[1] === "boolean" ||
        Object.prototype.hasOwnProperty.call(named, "use_high_performance") ||
        (node.inputs || []).some(input => input.name === "use_high_performance");
}

export function migrateExecuteInstance(node) {
    if (!isLegacyInstance(node)) return false;
    if (node.properties?.rh_instance_type_version === INSTANCE_VERSION) {
        throw new Error("RH instance migration stopped: already-migrated Execute contains a legacy Boolean value.");
    }
    const values = node.widgets_values;
    if (!Array.isArray(values) || values.length !== 4 || typeof values[1] !== "boolean") {
        throw new Error("RH instance migration stopped: cannot safely decode old High Performance widget values. Keep the original workflow.");
    }
    if (typeof values[0] !== "number" || typeof values[2] !== "boolean" ||
        typeof values[3] !== "string") {
        throw new Error("RH instance migration stopped: legacy Execute widget order is ambiguous. Keep the original workflow.");
    }
    const named = node.widgets_values_named || {};
    if (Object.prototype.hasOwnProperty.call(named, "instance_type")) {
        throw new Error("RH instance migration stopped: both old and new instance fields are present.");
    }
    if (Object.prototype.hasOwnProperty.call(named, "use_high_performance") &&
        named.use_high_performance !== values[1]) {
        throw new Error("RH instance migration stopped: conflicting positional and named Boolean values.");
    }
    const inputs = node.inputs || [];
    if (inputs.some(input => input.name === "instance_type")) {
        throw new Error("RH instance migration stopped: duplicate instance input mapping.");
    }
    for (const input of inputs) {
        if (input.name !== "use_high_performance") continue;
        if (input.link != null) {
            throw new Error("RH instance migration stopped: an external Boolean link controls High Performance. Disconnect it in the old version or migrate manually; no links were changed.");
        }
    }
    const selected = values[1] ? "plus" : "auto";
    values[1] = selected;
    if (Object.prototype.hasOwnProperty.call(named, "use_high_performance")) {
        delete named.use_high_performance;
        named.instance_type = selected;
    }
    for (const input of inputs) {
        if (input.name !== "use_high_performance") continue;
        input.name = "instance_type";
        input.type = "COMBO";
        if (input.widget) input.widget.name = "instance_type";
        if (input.label === "High Performance") input.label = "Instance Type";
        if (input.localized_name === "High Performance") input.localized_name = "Instance Type";
    }
    node.properties = { ...node.properties, rh_instance_type_version: INSTANCE_VERSION };
    return true;
}

export function isLegacyGroup(node) {
    const group = GROUPS[node.type];
    if (!group) return false;
    const groupName = group[0];
    const hasRemovedEnable = (node.inputs || []).some((input) => input.name.startsWith(groupName + ".enabled_")) ||
        Object.keys(node.widgets_values_named || {}).some((name) => name.startsWith(groupName + ".enabled_"));
    if (hasRemovedEnable) return true;
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
    const hasNativeEnable = (node.inputs || []).some((input) => input.name.startsWith(group + ".enabled_")) ||
        Object.keys(named).some((name) => name.startsWith(group + ".enabled_"));
    const nativeValues = { ...named };
    if (hasNativeEnable && !Object.keys(nativeValues).length) {
        let valueIndex = 0;
        for (const input of node.inputs || []) {
            if (!input.widget || valueIndex >= values.length) continue;
            nativeValues[input.name] = values[valueIndex++];
        }
    }
    let rows = [];
    if (hasNativeEnable && nativeValues[group] !== undefined) {
        const count = Number(nativeValues[group]);
        if (!Number.isInteger(count) || count < 1 || count > maximum) throw new Error("Invalid native RH group count.");
        for (let slot = 1; slot <= count; slot++) {
            rows.push({
                slot_id: slot,
                enabled: nativeValues[`${group}.enabled_${slot}`] !== false,
                node_id: nativeValues[`${group}.node_id_${slot}`],
                field_name: nativeValues[`${group}.field_name_${slot}`],
                custom_field_name: nativeValues[`${group}.field_name_${slot}.custom_field_name_${slot}`],
                local_value: image ? "" : nativeValues[`${group}.value_${slot}`],
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
        if (!normalized.enabled) {
            const hasLink = (node.inputs || []).some((input) => slotOf(input.name) === slot && input.link != null);
            const defaultField = image ? "image" : "text";
            const hasContent = normalized.node_id || normalized.custom_field_name || normalized.value ||
                (normalized.field_name && normalized.field_name !== defaultField) || hasLink;
            if (hasContent) {
                const label = image ? "Upload Image V2" : "Params V2";
                throw new Error(`RH migration stopped: disabled ${label} row ${slot} contains saved data or a connection. Enable was removed, so this row cannot be activated silently. Open the original workflow with the previous version and either enable or clear that row first.`);
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
        if (!bySlot.has(slot)) bySlot.set(slot, { slot, enabled: true, node_id: "", field_name: image ? "image" : "text", custom_field_name: "", value: "" });
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
        if ((subgraph.nodes || []).some((node) => isLegacyGroup(node) || isLegacyExecute(node) || isLegacyInstance(node))) {
            throw new Error("RH migration stopped: this workflow contains a legacy RH node inside a subgraph. Migrate an expanded copy first; the original workflow is unchanged.");
        }
    }
    for (const old of staged.nodes || []) {
        if (migrateExecuteNode(old)) migrated++;
    }
    for (const old of staged.nodes || []) {
        if (migrateExecuteInstance(old)) migrated++;
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
