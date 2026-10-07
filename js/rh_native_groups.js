// Lifecycle support around ComfyUI's own DynamicCombo. Business inputs stay native;
// the only custom widget is a non-serializing 4px visual spacer between visible rows.
const states = new WeakMap();
const bound = new WeakSet();
const ROW_GAP_PX = 4;

const slotOf = (name) => Number(String(name).match(/_(\d+)(?:\.|$)/)?.[1] || 0);
const isGroupSpacer = (widget) => widget?._rhGroupGap === true;

function syncGroupSpacers(node, state) {
    if (!["param_count", "image_count"].includes(state.group) || !node.widgets) return;
    for (let index = node.widgets.length - 1; index >= 0; index--) {
        if (isGroupSpacer(node.widgets[index])) node.widgets.splice(index, 1);
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
            name: `__rh_group_gap_${state.group}_${slot}`,
            type: "custom",
            value: null,
            serialize: false,
            options: { serialize: false },
            _rhGroupGap: true,
            node,
            draw() {},
            mouse() { return false; },
            // LiteGraph adds its own 4px widget spacing. A zero-height custom
            // widget therefore produces an actual 4px visual row gap.
            computeSize(width) { return [Number(width) || 0, Math.max(0, ROW_GAP_PX - 4)]; },
        });
    }
}

export function labelNativeControls(node) {
    const labels = { param_count: "Param Count", image_count: "Image Count", node_id: "Node ID",
        field_name: "Field", custom_field_name: "Custom Field", audio_path: "Audio Path", file_path: "File Path" };
    const kinds = { node_id: "Node", field_name: "Field", custom_field_name: "Custom Field", value: "Value", image: "Image" };
    for (const item of [...(node.widgets || []), ...(node.inputs || [])]) {
        const leaf = item.name?.split(".").at(-1);
        const match = /^(node_id|field_name|custom_field_name|value|image)_(\d+)$/.exec(leaf || "");
        if (match) item.label = `${kinds[match[1]]} ${match[2]}`;
        else if (labels[leaf]) item.label = labels[leaf];
    }
}

function capture(node, state) {
    const values = new Map(state.widgets.map((widget) => [widget.name, widget.value]));
    const links = [];
    // DynamicCombo has already detached the old slot views when onRemove runs.
    // Read the still-live graph links against the input-name order captured
    // before the native mutation.
    for (const link of node.graph?.links?.values() || []) {
        if (String(link.target_id) !== String(node.id)) continue;
        const name = state.inputNames[link.target_slot];
        if (name?.startsWith(state.group + ".")) {
            links.push({ name, origin_id: link.origin_id, origin_slot: link.origin_slot });
        }
    }
    return { values, links, inputNames: [...state.inputNames] };
}

function mergeIntoCache(state, snapshot) {
    for (const [name, value] of snapshot.values) state.cache.values.set(name, value);

    // A visible input that is currently disconnected must clear any older
    // cached connection before the latest live links are recorded.
    for (const name of snapshot.inputNames) {
        if (name?.startsWith(state.group + ".")) state.cache.links.delete(name);
    }
    for (const saved of snapshot.links) state.cache.links.set(saved.name, saved);
}

function restoreFromCache(node, state, maximumSlot) {
    // Restore selectors before their dependent custom-field widgets.
    const ordered = [...state.cache.values].sort(([a], [b]) => a.split(".").length - b.split(".").length);
    for (const [name, value] of ordered) {
        if (!name.startsWith(state.group + ".") || slotOf(name) > maximumSlot) continue;
        const widget = node.widgets?.find((item) => item.name === name);
        if (widget && widget.value !== value) widget.value = value;
    }

    for (const saved of state.cache.links.values()) {
        if (slotOf(saved.name) > maximumSlot) continue;
        const index = node.inputs?.findIndex((input) => input.name === saved.name);
        if (index < 0 || node.inputs[index].link != null) continue;
        const origin = node.graph?.getNodeById(saved.origin_id);
        if (!origin) continue;
        if (!origin.connect(saved.origin_slot, node, index)) {
            console.error("RH: unable to restore cached connection", saved.name);
        }
    }
}

function bindRows(node, state) {
    labelNativeControls(node);
    syncGroupSpacers(node, state);
    state.widgets = (node.widgets || []).filter((widget) => widget.name.startsWith(state.group + "."));
    state.inputNames = (node.inputs || []).map((input) => input.name);
    for (const widget of state.widgets) {
        if (bound.has(widget)) continue;
        bound.add(widget);
        const removed = widget.onRemove;
        widget.onRemove = function () {
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
        state = {
            selector,
            group,
            count: Number(selector.value),
            pending: null,
            restoring: false,
            widgets: [],
            inputNames: [],
            cache: { values: new Map(), links: new Map() },
        };
        states.set(node, state);
        const callback = selector.callback;
        selector.callback = function () {
            if (state.restoring) return;
            const target = Number(selector.value);
            const snapshot = state.pending;
            state.pending = null;
            state.restoring = true;
            try {
                if (snapshot) mergeIntoCache(state, snapshot);
                restoreFromCache(node, state, target);
                state.count = target;
                callback?.apply(this, arguments);
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
        // Runtime cache is intentionally session-local. Saved workflows contain
        // the currently active DynamicCombo rows; hidden rows are restored while
        // toggling counts in the same editor session.
        state.cache.values.clear();
        state.cache.links.clear();
    }
    bindRows(node, state);
}
