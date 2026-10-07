import { app } from "/scripts/app.js";

const MAX_ROWS = 16;
const COUNT_WIDGET = "param_count";
const FIELD_NAMES = [
    "text", "image", "video", "mask", "seed", "steps", "cfg", "sampler_name",
    "scheduler", "denoise", "width", "height", "batch_size", "model", "vae",
    "lora", "control_net", "strength", "scale", "custom",
];

function clampCount(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return 1;
    return Math.max(1, Math.min(MAX_ROWS, Math.round(numeric)));
}

function slotFromName(name, prefix) {
    const match = String(name || "").match(new RegExp("^" + prefix + "(\\d+)$"));
    return match ? Number(match[1]) : 0;
}

function defaultState(slot) {
    return {
        slot_id: slot,
        node_id: "",
        field_name: "text",
        custom_field_name: "",
        local_value: "",
    };
}

function normalizeLegacyState(value = {}, fallbackSlot = 1) {
    if (value.enabled === false) return defaultState(fallbackSlot);
    return {
        slot_id: Number(value.slot_id || fallbackSlot),
        node_id: String(value.node_id ?? ""),
        field_name: FIELD_NAMES.includes(value.field_name) ? value.field_name : "text",
        custom_field_name: String(value.custom_field_name ?? ""),
        local_value: String(value.local_value ?? value.field_value ?? ""),
    };
}

function getCountWidget(node) {
    return (node.widgets || []).find((widget) => widget.name === COUNT_WIDGET);
}

function getWidget(node, name) {
    return (node.widgets || []).find((widget) => widget.name === name);
}

function widgetName(kind, slot) {
    return kind + "_" + slot;
}

function isDynamicWidgetName(name) {
    return /^(node_id|field_name|custom_field_name|local_value)_\d+$/.test(String(name || ""));
}

function resizeNode(node) {
    requestAnimationFrame(() => {
        const computed = node.computeSize?.();
        if (!computed) return;

        const currentWidth = Number(node.size?.[0]) || Number(computed[0]) || 360;
        const next = [
            Math.max(currentWidth, 360),
            Math.max(computed[1], 110),
        ];

        if (node.setSize) node.setSize(next);
        else node.size = next;
        node.setDirtyCanvas?.(true, true);
    });
}

function ensureValueInput(node, slot) {
    const name = "value_" + slot;
    let input = (node.inputs || []).find((item) => item.name === name);
    if (!input) input = node.addInput(name, "*");
    if (input) input.label = "value " + slot;
}

function removeValueInput(node, slot) {
    const name = "value_" + slot;
    const index = (node.inputs || []).findIndex((item) => item.name === name);
    if (index >= 0) node.removeInput(index);
}

function configureWidget(widget, label, tooltip) {
    if (!widget) return widget;
    widget.label = label;
    widget.tooltip = tooltip;
    widget.serialize = true;
    widget.options ??= {};
    widget.options.serialize = true;
    return widget;
}

function syncCustomVisibility(node, slot, resize = true) {
    const field = getWidget(node, widgetName("field_name", slot));
    const custom = getWidget(node, widgetName("custom_field_name", slot));
    if (!field || !custom) return;

    custom.hidden = field.value !== "custom";
    if (resize) resizeNode(node);
}

function addNativeSlot(node, slot, initialState = {}) {
    if (!slot || slot > MAX_ROWS) return;
    const state = { ...defaultState(slot), ...initialState, slot_id: slot };

    ensureValueInput(node, slot);

    if (!getWidget(node, widgetName("node_id", slot))) {
        configureWidget(
            node.addWidget(
                "text",
                widgetName("node_id", slot),
                String(state.node_id ?? ""),
                null,
                { serialize: true },
            ),
            "Node " + slot,
            "RunningHub node ID.",
        );
    }

    if (!getWidget(node, widgetName("field_name", slot))) {
        const fieldWidget = configureWidget(
            node.addWidget(
                "combo",
                widgetName("field_name", slot),
                FIELD_NAMES.includes(state.field_name) ? state.field_name : "text",
                () => syncCustomVisibility(node, slot),
                { values: FIELD_NAMES, serialize: true },
            ),
            "Field " + slot,
            "RunningHub field name.",
        );
        if (fieldWidget) fieldWidget.value = FIELD_NAMES.includes(state.field_name) ? state.field_name : "text";
    }

    if (!getWidget(node, widgetName("custom_field_name", slot))) {
        configureWidget(
            node.addWidget(
                "text",
                widgetName("custom_field_name", slot),
                String(state.custom_field_name ?? ""),
                null,
                { serialize: true },
            ),
            "Custom Field " + slot,
            "Used only when Field is custom.",
        );
    }

    if (!getWidget(node, widgetName("local_value", slot))) {
        configureWidget(
            node.addWidget(
                "text",
                widgetName("local_value", slot),
                String(state.local_value ?? ""),
                null,
                { serialize: true },
            ),
            "Value " + slot,
            "Local fallback used when the matching value socket is not connected.",
        );
    }

    syncCustomVisibility(node, slot, false);
}

function removeNativeSlot(node, slot) {
    const names = new Set([
        widgetName("node_id", slot),
        widgetName("field_name", slot),
        widgetName("custom_field_name", slot),
        widgetName("local_value", slot),
        "param_" + slot,
    ]);

    if (node.widgets) {
        for (let index = node.widgets.length - 1; index >= 0; index -= 1) {
            if (names.has(node.widgets[index]?.name || "")) {
                node.removeWidget(index);
            }
        }
    }
    removeValueInput(node, slot);
}

function setSlotCount(node, requestedCount, statesBySlot = null) {
    const target = clampCount(requestedCount);
    const countWidget = getCountWidget(node);
    if (countWidget && countWidget.value !== target) countWidget.value = target;

    for (let slot = MAX_ROWS; slot > target; slot -= 1) {
        removeNativeSlot(node, slot);
    }

    for (let slot = 1; slot <= target; slot += 1) {
        if (!getWidget(node, widgetName("node_id", slot))) {
            addNativeSlot(node, slot, statesBySlot?.get(slot) || defaultState(slot));
        } else {
            ensureValueInput(node, slot);
            syncCustomVisibility(node, slot, false);
        }
    }

    resizeNode(node);
}

function removeDynamicUi(node) {
    if (node.widgets) {
        for (let index = node.widgets.length - 1; index >= 0; index -= 1) {
            const name = node.widgets[index]?.name || "";
            if (isDynamicWidgetName(name) || /^param_\d+$/.test(name) || name === "+ Add Param") {
                node.removeWidget(index);
            }
        }
    }

    if (node.inputs) {
        for (let index = node.inputs.length - 1; index >= 0; index -= 1) {
            if (/^value_\d+$/.test(node.inputs[index]?.name || "")) {
                node.removeInput(index);
            }
        }
    }
}

function extractLegacyRows(info) {
    const values = info?.widgets_values || [];
    const rows = [];

    for (const value of values) {
        if (
            value &&
            typeof value === "object" &&
            (value.kind === "rh_param2" || value.node_id !== undefined)
        ) {
            rows.push(normalizeLegacyState(value, rows.length + 1));
        }
    }

    if (!rows.length) {
        for (const value of values) {
            if (typeof value !== "string" || !value.trim().startsWith("[")) continue;
            try {
                const legacy = JSON.parse(value);
                if (Array.isArray(legacy)) {
                    legacy.forEach((row, index) => rows.push(normalizeLegacyState(row, index + 1)));
                    break;
                }
            } catch (_) {
            }
        }
    }

    rows.sort((a, b) => Number(a.slot_id) - Number(b.slot_id));
    return rows.slice(0, MAX_ROWS);
}

function inferCountFromInputs(info) {
    let maxSlot = 0;
    for (const input of info?.inputs || []) {
        maxSlot = Math.max(maxSlot, slotFromName(input?.name, "value_"));
    }
    return maxSlot;
}

function extractSavedState(info) {
    const values = info?.widgets_values || [];
    const legacyRows = extractLegacyRows(info);

    if (legacyRows.length) {
        const firstCount = typeof values[0] === "number" ? clampCount(values[0]) : 0;
        const rowCount = legacyRows.reduce(
            (max, row) => Math.max(max, Number(row.slot_id) || 0),
            0,
        );
        const count = clampCount(Math.max(firstCount, rowCount, inferCountFromInputs(info), 1));
        return {
            count,
            statesBySlot: new Map(legacyRows.map((row) => [Number(row.slot_id), row])),
        };
    }

    if (typeof values[0] === "number") {
        const count = clampCount(values[0]);
        const statesBySlot = new Map();
        let offset = 1;

        for (let slot = 1; slot <= count; slot += 1) {
            statesBySlot.set(slot, {
                slot_id: slot,
                node_id: String(values[offset++] ?? ""),
                field_name: FIELD_NAMES.includes(values[offset]) ? values[offset] : "text",
                custom_field_name: String(values[offset + 1] ?? ""),
                local_value: String(values[offset + 2] ?? ""),
            });
            offset += 3;
        }
        return { count, statesBySlot };
    }

    const count = clampCount(Math.max(inferCountFromInputs(info), 1));
    return { count, statesBySlot: new Map() };
}

function buildWidgetValues(count, statesBySlot) {
    const values = [count];
    for (let slot = 1; slot <= count; slot += 1) {
        const state = { ...defaultState(slot), ...(statesBySlot.get(slot) || {}) };
        values.push(
            String(state.node_id ?? ""),
            FIELD_NAMES.includes(state.field_name) ? state.field_name : "text",
            String(state.custom_field_name ?? ""),
            String(state.local_value ?? ""),
        );
    }
    return values;
}

function captureLiveState(node, count) {
    const statesBySlot = new Map();
    for (let slot = 1; slot <= count; slot += 1) {
        statesBySlot.set(slot, {
            slot_id: slot,
            node_id: String(getWidget(node, widgetName("node_id", slot))?.value ?? ""),
            field_name: String(getWidget(node, widgetName("field_name", slot))?.value ?? "text"),
            custom_field_name: String(getWidget(node, widgetName("custom_field_name", slot))?.value ?? ""),
            local_value: String(getWidget(node, widgetName("local_value", slot))?.value ?? ""),
        });
    }
    return statesBySlot;
}

function setupCountWidget(node) {
    const widget = getCountWidget(node);
    if (!widget || widget._rhParams2CountBound) return widget;

    widget.label = "Param Count";
    const originalCallback = widget.callback;
    widget.callback = function (value) {
        const result = originalCallback?.apply(this, arguments);
        if (!node._rhParams2Configuring) {
            setTimeout(() => setSlotCount(node, value), 0);
        }
        return result;
    };
    widget._rhParams2CountBound = true;
    return widget;
}

app.registerExtension({
    name: "RunningHub.Params2",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "RH_Params2") return;

        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = originalCreated?.apply(this, arguments);
            this.serialize_widgets = true;
            const countWidget = setupCountWidget(this);
            setSlotCount(this, countWidget?.value ?? 1);
            return result;
        };

        const originalConfigure = nodeType.prototype.configure;
        nodeType.prototype.configure = function (info) {
            const saved = extractSavedState(info);

            removeDynamicUi(this);
            for (let slot = 1; slot <= saved.count; slot += 1) {
                addNativeSlot(this, slot, saved.statesBySlot.get(slot) || defaultState(slot));
            }

            const normalizedInfo = {
                ...info,
                widgets_values: buildWidgetValues(saved.count, saved.statesBySlot),
            };

            this._rhParams2Configuring = true;
            let result;
            try {
                result = originalConfigure?.call(this, normalizedInfo);
            } finally {
                this._rhParams2Configuring = false;
            }

            this.serialize_widgets = true;
            const countWidget = setupCountWidget(this);
            if (countWidget) countWidget.value = saved.count;

            const liveState = captureLiveState(this, saved.count);
            for (let slot = 1; slot <= saved.count; slot += 1) {
                syncCustomVisibility(this, slot, false);
            }
            setSlotCount(this, saved.count, liveState);
            return result;
        };
    },
});
