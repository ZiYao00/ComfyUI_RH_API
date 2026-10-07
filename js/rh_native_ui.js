import { app } from "/scripts/app.js";
import { GROUPS, NATIVE_VERSION, migrateGraph } from "./rh_native_migration.js";
import { configureNativeGroup, labelNativeControls } from "./rh_native_groups.js";

const NODES = new Set(["RH_Params2", "RH_UploadImage2", "RH_UploadImage", "RH_UploadVideo", "RH_UploadAudio",
    "RH_UploadFile", "RH_UploadLatent", "RH_BatchUploadImage", "RH_MultiInputImage"]);
const bound = new WeakSet();

function attach(node, restored = false) {
    if (!NODES.has(node.comfyClass || node.type)) return;
    labelNativeControls(node);
    const group = GROUPS[node.comfyClass || node.type]?.[0];
    if (group) configureNativeGroup(node, group, { restored });
    if (!bound.has(node)) {
        bound.add(node);
        // Instance lifecycle callback, not a replacement for prototype.configure.
        const configured = node.onConfigure;
        node.onConfigure = function () {
            const result = configured?.apply(this, arguments);
            attach(this, true);
            this.properties ??= {};
            this.properties.rh_native_ui_version = NATIVE_VERSION;
            return result;
        };
    }
}

app.registerExtension({
    name: "RunningHub.NativeInputs",
    nodeCreated(node) {
        attach(node);
    },
    loadedGraphNode(node) {
        attach(node, true);
    },
    beforeConfigureGraph(graphData) {
        try {
            const count = migrateGraph(graphData, (type) => globalThis.LiteGraph.createNode(type));
            if (count) console.info(`RH: migrated ${count} node(s) to native inputs; save a new workflow copy.`);
        } catch (error) {
            // ComfyUI logs extension-hook errors and continues loading. A throw
            // alone is NOT a safe stop. Keep the data in a missing-node
            // placeholder so a malformed migration cannot queue a cloud task.
            const subgraphIds = new Set((graphData.definitions?.subgraphs || []).map(item => String(item.id)));
            for (const node of graphData.nodes || []) {
                if (!GROUPS[node.type] && !subgraphIds.has(String(node.type))) continue;
                node.properties = { ...node.properties, rh_migration_original_type: node.type, rh_migration_error: String(error.message || error) };
                node.type = 'RH_MigrationRequired';
            }
            console.error('RH migration requires attention:', error);
            globalThis.alert('RH workflow migration could not finish. The original file is unchanged. Affected nodes are blocked placeholders. Do not overwrite your original workflow.\n\n' + String(error.message || error));
        }
    },
});
