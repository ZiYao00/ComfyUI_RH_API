// Small lifecycle guard around ComfyUI's own DynamicCombo. Business inputs stay native;
// the only custom widget is a 4px non-serializing visual spacer between Params rows.
const states = new WeakMap();
const bound = new WeakSet();
const PARAM_GAP_PX = 4;

const slotOf = (name) => Number(String(name).match(/_(\d+)(?:\.|$)/)?.[1] || 0);
const isParamSpacer = (widget) => widget?._rhParamGap === true;

function syncParamSpacers(node, state) {
    if (state.group !== "param_count" || !node.widgets) return;
    for (let index = node.widgets.length - 1; index >= 0; index--) {
        if (isParamSpacer(node.widgets[index])) node.widgets.splice(index, 1);
    }
    const count = Number(state.selector.value) || 1;
    for (let slot = count - 1; slot >= 1; slot--) {
        let insertAfter = -1;
        for (let index = 0; index < node.widgets.length; index++) {
            const name = node.widgets[index]?.name || "";
            if (name.startsWith(state.group + ".") && slotOf(name) === slot) insertAfter = index;
        }
        if (insertAfter < 0) continue;
        node.widgets.splice(insertAfter + 1, 0, {
            name: `__rh_param_gap_${slot}`,
            type: "custom",
            value: null,
            serialize: false,
            options: { serialize: false },
            _rhParamGap: true,
            node,
            draw() {},
            mouse() { return false; },
            computeSize(width) { return [Number(width) || 0, PARAM_GAP_PX]; },
        });
    }
}

export function labelNativeControls(node) {
    const labels = { param_count: "Param Count", image_count: "Image Count", node_id: "Node ID",
        field_name: "Field", custom_field_name: "Custom Field", audio_path: "Audio Path", file_path: "File Path" };
    const kinds = { node_id: "Node", field_name: "Field", custom_field_name: "Custom Field", value: "Value", image: "Image", enabled: "Enable" };
    for (const item of [...(node.widgets || []), ...(node.inputs || [])]) {
        const leaf = item.name?.split(".").at(-1);
        const match = /^(node_id|field_name|custom_field_name|value|image|enabled)_(\d+)$/.exec(leaf || "");
        if (match) item.label = `${kinds[match[1]]} ${match[2]}`;
        else if (labels[leaf]) item.label = labels[leaf];
    }
}

function capture(node, state) {
    const values = new Map(state.widgets.map((widget) => [widget.name, widget.value]));
    const links = [];
    // DynamicCombo has already detached the old slot views when onRemove runs.
    // Their .link accessors no longer resolve. Read the still-live graph links
    // against the input-name order captured before the native mutation instead.
    for (const link of node.graph?.links?.values() || []) {
        if (String(link.target_id) !== String(node.id)) continue;
        const name = state.inputNames[link.target_slot];
        if (name?.startsWith(state.group + '.')) links.push({ name, origin_id: link.origin_id, origin_slot: link.origin_slot });
    }
    return { values, links, count: state.count, size: [...node.size] };
}

function restore(node, snapshot, group, maximumSlot, restoreLinks) {
    // Restore selectors before their dependent custom-field widgets.
    const ordered = [...snapshot.values].sort(([a], [b]) => a.split(".").length - b.split(".").length);
    for (const [name, value] of ordered) {
        if (!name.startsWith(group + ".") || slotOf(name) > maximumSlot) continue;
        const widget = node.widgets?.find((item) => item.name === name);
        if (widget && widget.value !== value) widget.value = value;
    }
    if (restoreLinks) {
        for (const saved of snapshot.links) {
            const index = node.inputs?.findIndex((input) => input.name === saved.name);
            if (index < 0 || node.inputs[index].link != null) continue;
            const origin = node.graph?.getNodeById(saved.origin_id);
            if (!origin?.connect(saved.origin_slot, node, index)) {
                console.error("RH: unable to restore connection", saved.name);
            }
        }
    }
}

function reductionHasContent(snapshot, target) {
    if (snapshot.links.some((link) => slotOf(link.name) > target)) return true;
    for (const [name, value] of snapshot.values) {
        if (slotOf(name) <= target) continue;
        if (/(?:node_id|custom_field_name|value)_\d+$/.test(name) && value !== "" && value != null) return true;
    }
    return false;
}

function bindRows(node, state) {
    labelNativeControls(node);
    syncParamSpacers(node, state);
    state.widgets = (node.widgets || []).filter((widget) => widget.name.startsWith(state.group + "."));
    state.inputNames = (node.inputs || []).map((input) => input.name);
    for (const widget of state.widgets) {
        if (bound.has(widget)) continue;
        bound.add(widget);
        const removed = widget.onRemove;
        widget.onRemove = function () {
            // The native setter removes children before invoking the interaction
            // callback. Capture existing object references before link removal.
            if (!state.restoring && !state.pending && Number(state.selector.value) !== state.count) {
                state.pending = capture(node, state);
            }
            return removed?.apply(this, arguments);
        };
        if (/\.field_name_\d+$/.test(widget.name)) {
            const callback = widget.callback;
            widget.callback = function () {
                const result = callback?.apply(this, arguments);
                bindRows(node, state);
                return result;
            };
        }
    }
}

export function configureNativeGroup(node, group, { restored = false } = {}) {
    const selector = node.widgets?.find((widget) => widget.name === group);
    if (!selector || selector.type !== "combo") return;
    let state = states.get(node);
    if (!state || state.selector !== selector) {
        state = { selector, group, count: Number(selector.value), pending: null, restoring: false, widgets: [], inputs: [] };
        states.set(node, state);
        const callback = selector.callback;
        selector.callback = function () {
            if (state.restoring) return;
            const target = Number(selector.value);
            const snapshot = state.pending;
            state.pending = null;
            let accepted = true;
            if (snapshot && target < snapshot.count && reductionHasContent(snapshot, target)) {
                accepted = globalThis.confirm(
                    `Reduce from ${snapshot.count} to ${target} rows? Removed rows contain values or connections. Save your workflow first. Cancel keeps all rows.`
                );
            }
            state.restoring = true;
            try {
                if (snapshot) {
                    if (!accepted) selector.value = String(snapshot.count);
                    restore(node, snapshot, group, accepted ? target : snapshot.count, !accepted);
                }
                state.count = Number(selector.value);
                if (accepted) callback?.apply(this, arguments);
                else if (snapshot) node.setSize?.(snapshot.size);
            } finally {
                state.restoring = false;
                state.pending = null;
                bindRows(node, state);
            }
            node.setDirtyCanvas?.(true, true);
        };
    }
    if (restored) {
        state.pending = null;
        state.count = Number(selector.value);
    }
    bindRows(node, state);
}
