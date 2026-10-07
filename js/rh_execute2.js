import { app } from "/scripts/app.js";

const PARAM_PREFIX = "params_";
const PARAM_TYPE = "RH_PARAMS";

function isDynamicParamName(name) {
    return /^params_\d+$/.test(String(name || ""));
}

function dynamicParamNumber(name) {
    const match = String(name || "").match(/^params_(\d+)$/);
    return match ? Number(match[1]) : 0;
}

function getDynamicParams(node) {
    return (node.inputs || [])
        .filter((input) => isDynamicParamName(input.name))
        .sort((a, b) => dynamicParamNumber(a.name) - dynamicParamNumber(b.name));
}

function hasInput(node, name) {
    return (node.inputs || []).some((input) => input.name === name);
}

function addNextParamInput(node) {
    const existing = getDynamicParams(node);
    const nextNumber = existing.length ? dynamicParamNumber(existing[existing.length - 1].name) + 1 : 2;
    const name = PARAM_PREFIX + nextNumber;
    if (!hasInput(node, name)) {
        const slot = node.addInput(name, PARAM_TYPE);
        if (slot) slot.label = "params " + nextNumber;
    }
}

function ensureTrailingEmptyParam(node) {
    const base = (node.inputs || []).find((input) => input.name === "params");
    const dynamic = getDynamicParams(node);
    const allParamInputs = base ? [base, ...dynamic] : dynamic;
    if (!allParamInputs.length) return;

    const last = allParamInputs[allParamInputs.length - 1];
    if (last.link != null) {
        addNextParamInput(node);
    }

    let allParams = base ? [base, ...getDynamicParams(node)] : getDynamicParams(node);
    while (allParams.length >= 2) {
        const lastParam = allParams[allParams.length - 1];
        const previousParam = allParams[allParams.length - 2];
        if (
            isDynamicParamName(lastParam.name) &&
            lastParam.link == null &&
            previousParam.link == null
        ) {
            const index = node.inputs.indexOf(lastParam);
            if (index >= 0) node.removeInput(index);
            allParams = base ? [base, ...getDynamicParams(node)] : getDynamicParams(node);
        } else {
            break;
        }
    }
}

app.registerExtension({
    name: "RunningHub.Execute2",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "RH_Execute2") return;

        const originalConfigure = nodeType.prototype.configure;
        nodeType.prototype.configure = function (info) {
            const savedInputs = info?.inputs || [];
            const maxSaved = savedInputs
                .map((input) => dynamicParamNumber(input?.name))
                .reduce((max, value) => Math.max(max, value), 0);

            for (let number = 2; number <= maxSaved; number += 1) {
                const name = PARAM_PREFIX + number;
                if (!hasInput(this, name)) {
                    const slot = this.addInput(name, PARAM_TYPE);
                    if (slot) slot.label = "params " + number;
                }
            }

            const result = originalConfigure?.apply(this, arguments);
            setTimeout(() => ensureTrailingEmptyParam(this), 0);
            return result;
        };

        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = originalCreated?.apply(this, arguments);
            setTimeout(() => ensureTrailingEmptyParam(this), 0);
            return result;
        };

        const originalConnectionsChange = nodeType.prototype.onConnectionsChange;
        nodeType.prototype.onConnectionsChange = function () {
            const result = originalConnectionsChange?.apply(this, arguments);
            setTimeout(() => ensureTrailingEmptyParam(this), 0);
            return result;
        };
    },
});
