import { app } from "/scripts/app.js";

function maskApiKeyElement(element) {
    if (!element) return false;

    const tagName = element.tagName?.toUpperCase();
    if (tagName === "INPUT") {
        try {
            element.type = "password";
        } catch (_) {
            // Some browser/widget combinations may not allow changing input type.
        }
        element.autocomplete = "new-password";
        element.spellcheck = false;
        return true;
    }

    if (tagName === "TEXTAREA") {
        // ComfyUI may render STRING widgets as textarea elements even when
        // multiline=false. Chromium supports text-security masking here.
        element.style.webkitTextSecurity = "disc";
        element.setAttribute("autocomplete", "new-password");
        element.spellcheck = false;
        return true;
    }

    return false;
}

function maskApiKeyWidget(node) {
    const widget = node.widgets?.find((item) => item.name === "api_key");
    if (!widget) return false;

    widget.options = widget.options || {};
    widget.options.password = true;

    let masked = false;
    masked = maskApiKeyElement(widget.inputEl) || masked;
    masked = maskApiKeyElement(widget.element) || masked;
    return masked;
}

app.registerExtension({
    name: "RunningHub.MaskApiKey",

    nodeCreated(node) {
        if (node.comfyClass !== "RH_Config") return;

        // STRING widgets can be mounted asynchronously in newer ComfyUI
        // frontends, so retry for a short period until the DOM input exists.
        let attempts = 0;
        const applyMask = () => {
            attempts += 1;
            if (maskApiKeyWidget(node) || attempts >= 30) return;
            requestAnimationFrame(applyMask);
        };

        applyMask();
        setTimeout(() => maskApiKeyWidget(node), 100);
        setTimeout(() => maskApiKeyWidget(node), 500);
    },
});
