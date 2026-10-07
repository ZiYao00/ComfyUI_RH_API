import { app } from "/scripts/app.js";

const MAX_ROWS = 12;
const FIELD_NAMES = [
    "image", "init_image", "control_image", "mask", "reference", "custom",
];

function slotFromName(name, prefix) {
    const match = String(name || "").match(new RegExp("^" + prefix + "(\\d+)$"));
    return match ? Number(match[1]) : 0;
}

function normalizeState(value = {}, fallbackSlot = 1) {
    return {
        kind: "rh_upload_image2",
        slot_id: Number(value.slot_id || fallbackSlot),
        enabled: value.enabled !== false,
        node_id: String(value.node_id ?? ""),
        field_name: FIELD_NAMES.includes(value.field_name) ? value.field_name : "image",
        custom_field_name: String(value.custom_field_name ?? ""),
    };
}

function makeTextInput(value, placeholder) {
    const input = document.createElement("input");
    input.type = "text";
    input.value = value;
    input.placeholder = placeholder;
    input.style.cssText = [
        "box-sizing:border-box",
        "width:100%",
        "min-width:0",
        "height:28px",
        "background:var(--comfy-input-bg,#222)",
        "color:var(--input-text,#ddd)",
        "border:1px solid color-mix(in srgb,var(--input-text,#ddd) 35%,transparent)",
        "border-radius:4px",
        "padding:3px 6px",
        "font-size:11px",
    ].join(";");
    return input;
}

function makeSelect(value) {
    const select = document.createElement("select");
    select.style.cssText = [
        "box-sizing:border-box",
        "width:100%",
        "min-width:0",
        "height:28px",
        "background:var(--comfy-input-bg,#222)",
        "color:var(--input-text,#ddd)",
        "border:1px solid color-mix(in srgb,var(--input-text,#ddd) 35%,transparent)",
        "border-radius:4px",
        "padding:2px 4px",
        "font-size:11px",
    ].join(";");

    for (const name of FIELD_NAMES) {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        select.appendChild(option);
    }
    select.value = value;
    return select;
}

function makeCheckbox(checked, title) {
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = checked;
    input.title = title;
    input.style.margin = "0";
    return input;
}

function makeRemoveButton(title) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "×";
    button.title = title;
    button.style.cssText = [
        "box-sizing:border-box",
        "width:24px",
        "height:24px",
        "padding:0",
        "border-radius:4px",
        "cursor:pointer",
    ].join(";");
    return button;
}

function getRowWidgets(node) {
    return (node.widgets || [])
        .filter((widget) => /^image_meta_\d+$/.test(widget.name || ""))
        .sort((a, b) => slotFromName(a.name, "image_meta_") - slotFromName(b.name, "image_meta_"));
}

function getUsedSlots(node) {
    return new Set(getRowWidgets(node).map((widget) => slotFromName(widget.name, "image_meta_")));
}

function nextFreeSlot(node) {
    const used = getUsedSlots(node);
    for (let slot = 1; slot <= MAX_ROWS; slot += 1) {
        if (!used.has(slot)) return slot;
    }
    return 0;
}

function resizeNode(node) {
    requestAnimationFrame(() => {
        const computed = node.computeSize?.();
        if (!computed) return;

        const currentWidth = Number(node.size?.[0]) || Number(computed[0]) || 340;
        const next = [
            Math.max(currentWidth, 340),
            Math.max(computed[1], 110),
        ];

        if (node.setSize) node.setSize(next);
        else node.size = next;
        node.setDirtyCanvas?.(true, true);
    });
}

function ensureImageInput(node, slot) {
    const name = "image_" + slot;
    let input = (node.inputs || []).find((item) => item.name === name);
    if (!input) input = node.addInput(name, "IMAGE");
    if (input) input.label = "image " + slot;
}

function removeImageInput(node, slot) {
    const name = "image_" + slot;
    const index = (node.inputs || []).findIndex((item) => item.name === name);
    if (index >= 0) node.removeInput(index);
}

function moveWidgetBeforeAddButton(node, widget) {
    const button = node._rhUploadImage2AddButton;
    if (!button || !node.widgets) return;

    const from = node.widgets.indexOf(widget);
    const to = node.widgets.indexOf(button);
    if (from < 0 || to < 0 || from < to) return;

    node.widgets.splice(from, 1);
    node.widgets.splice(to, 0, widget);
}

function addRow(node, slot, initialState = {}) {
    if (!slot || slot > MAX_ROWS) return null;
    if ((node.widgets || []).some((widget) => widget.name === "image_meta_" + slot)) return null;

    let state = normalizeState(initialState, slot);
    state.slot_id = slot;

    const root = document.createElement("div");
    root.style.cssText = [
        "box-sizing:border-box",
        "width:100%",
        "min-width:0",
        "display:grid",
        "grid-template-columns:44px minmax(0,.85fr) minmax(0,1.15fr) 24px",
        "column-gap:5px",
        "row-gap:4px",
        "align-items:center",
        "padding:2px",
        "overflow:hidden",
    ].join(";");

    const enabled = makeCheckbox(state.enabled, "Enable image");

    const slotCell = document.createElement("div");
    slotCell.style.cssText = [
        "display:flex",
        "align-items:center",
        "gap:4px",
        "min-width:0",
        "font-size:10px",
        "color:var(--descrip-text,#999)",
    ].join(";");

    const slotLabel = document.createElement("span");
    slotLabel.textContent = "#" + slot;
    slotCell.append(enabled, slotLabel);

    const nodeId = makeTextInput(state.node_id, "Node ID");
    nodeId.title = "RunningHub node ID";

    const fieldName = makeSelect(state.field_name);
    fieldName.title = "RunningHub field name";

    const remove = makeRemoveButton("Remove image");

    const customField = makeTextInput(state.custom_field_name, "Custom field name / ID");
    customField.title = "Used only when Field is custom";
    customField.style.gridColumn = "2 / 4";

    root.append(slotCell, nodeId, fieldName, remove, customField);

    let widget = null;

    function syncControls() {
        enabled.checked = state.enabled;
        nodeId.value = state.node_id;
        fieldName.value = state.field_name;
        customField.value = state.custom_field_name;
        customField.style.display = state.field_name === "custom" ? "block" : "none";
        root.style.opacity = state.enabled ? "1" : "0.6";
    }

    function touch() {
        node.setDirtyCanvas?.(true, true);
        resizeNode(node);
    }

    enabled.addEventListener("change", () => {
        state.enabled = enabled.checked;
        syncControls();
        touch();
    });

    nodeId.addEventListener("input", () => {
        state.node_id = nodeId.value;
        node.setDirtyCanvas?.(true, true);
    });

    fieldName.addEventListener("change", () => {
        state.field_name = fieldName.value;
        syncControls();
        touch();
    });

    customField.addEventListener("input", () => {
        state.custom_field_name = customField.value;
        node.setDirtyCanvas?.(true, true);
    });

    remove.addEventListener("click", () => {
        if (widget && node.widgets) {
            const index = node.widgets.indexOf(widget);
            if (index >= 0) node.removeWidget(index);
        }
        removeImageInput(node, slot);
        resizeNode(node);
    });

    widget = node.addDOMWidget("image_meta_" + slot, "rh_upload_image2_row", root, {
        serialize: true,
        hideOnZoom: false,
        getValue: () => ({ ...state }),
        setValue: (value) => {
            state = normalizeState(value, slot);
            state.slot_id = slot;
            syncControls();
        },
        getMinHeight: () => state.field_name === "custom" ? 66 : 36,
        getHeight: () => state.field_name === "custom" ? 66 : 36,
    });
    widget.serialize = true;

    ensureImageInput(node, slot);
    syncControls();
    moveWidgetBeforeAddButton(node, widget);
    resizeNode(node);
    return widget;
}

function addButton(node) {
    if (
        node._rhUploadImage2AddButton &&
        (node.widgets || []).includes(node._rhUploadImage2AddButton)
    ) {
        return;
    }

    const button = node.addWidget("button", "+ Add Image", null, () => {
        const slot = nextFreeSlot(node);
        if (!slot) {
            console.warn("RH Upload Image 2 supports up to " + MAX_ROWS + " images.");
            return;
        }
        addRow(node, slot);
    });

    button.serialize = false;
    node._rhUploadImage2AddButton = button;
}

function removeDynamicUi(node) {
    if (node.widgets) {
        for (let index = node.widgets.length - 1; index >= 0; index -= 1) {
            const name = node.widgets[index]?.name || "";
            if (/^image_meta_\d+$/.test(name) || name === "+ Add Image") {
                node.removeWidget(index);
            }
        }
    }
    node._rhUploadImage2AddButton = null;

    if (node.inputs) {
        for (let index = node.inputs.length - 1; index >= 0; index -= 1) {
            if (/^image_\d+$/.test(node.inputs[index]?.name || "")) {
                node.removeInput(index);
            }
        }
    }
}

function extractSavedRows(info) {
    const values = info?.widgets_values || [];
    const rows = [];

    for (const value of values) {
        if (value && typeof value === "object" && value.kind === "rh_upload_image2") {
            rows.push(normalizeState(value, rows.length + 1));
        }
    }

    const knownSlots = new Set(rows.map((row) => Number(row.slot_id)));
    for (const input of info?.inputs || []) {
        const slot = slotFromName(input?.name, "image_");
        if (slot && slot <= MAX_ROWS && !knownSlots.has(slot)) {
            rows.push(normalizeState({ slot_id: slot }, slot));
            knownSlots.add(slot);
        }
    }

    rows.sort((a, b) => Number(a.slot_id) - Number(b.slot_id));
    return rows.slice(0, MAX_ROWS);
}

app.registerExtension({
    name: "RunningHub.UploadImage2",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "RH_UploadImage2") return;

        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = originalCreated?.apply(this, arguments);
            this.serialize_widgets = true;
            addButton(this);
            if (!getRowWidgets(this).length) addRow(this, 1);
            resizeNode(this);
            return result;
        };

        const originalConfigure = nodeType.prototype.configure;
        nodeType.prototype.configure = function (info) {
            const rows = extractSavedRows(info);
            const normalizedRows = rows.length ? rows : [normalizeState({}, 1)];

            removeDynamicUi(this);
            for (const row of normalizedRows) {
                const slot = Number(row.slot_id || nextFreeSlot(this) || 1);
                addRow(this, slot, row);
            }

            addButton(this);
            this.serialize_widgets = true;

            const normalizedInfo = {
                ...info,
                widgets_values: normalizedRows.map((row) => ({ ...row })),
            };

            const result = originalConfigure?.call(this, normalizedInfo);
            resizeNode(this);
            return result;
        };
    },
});
