# Quick Start Guide

> Native UI baseline (2026-10-07): `RH Execute`, `RH Params V2`, and eight registered upload nodes use V3 schemas, with `RH Execute` incorporating the former Execute 2 multi-params Autogrow chain. Image V2 update (2026-10-12): its IMAGE inputs grow automatically as they are connected, with no user-facing Image Count. Checked with ComfyUI 0.39.0 / frontend 1.55.14 in an isolated browser; the earlier baseline used frontend 1.53.10. For a backend code update restart ComfyUI; for this JS-only update refresh the browser with Ctrl+F5. See [原生输入使用说明、迁移边界与验证记录](NATIVE_UI.md). No runtime dependencies are installed or upgraded.

## 1. Install

Place `ComfyUI_RH_API` under `ComfyUI/custom_nodes/`, install `requirements.txt`, and restart ComfyUI.

The requirements intentionally do not install or upgrade Torch/Torchaudio/CUDA packages.

## 2. Configure RunningHub

Add `RH Config`.

Required workflow setting:

- `workflow_or_app_id`: RunningHub workflow ID or AI app ID.

Recommended credential setup on the currently running 8188 plugin:

1. Use the **one private, Git-ignored and untracked** `config.json` in the plugin root; never commit it.
2. Keep the existing root `api_key` and `base_url` compatibility fields until the running plugin has been upgraded. Newer code will use the same file's `api_keys.international` and `api_keys.domestic` keys.
3. Leave the RH Config credential widget blank and explicitly set the current V1 STRING `base_url` to the correct RunningHub site.
4. The International / Domestic / Custom dropdown has passed isolated testing but is **not yet installed on 8188 or 8190**; do not expect the live node to show it before a separately validated deployment.

For new installs, copy the public `config.json.example` to private `config.json`. A legacy `config.local.json` may still override nonempty values for compatibility; avoid keeping both files. New RH Config nodes leave `base_url` blank to read the private config, while saved explicit URLs retain precedence. Only official HTTPS sites or explicitly trusted private-config custom endpoints are accepted.

The optional `query_api` selector on `RH Config` defaults to `legacy`. Keep that default for normal use. `v2` is available for explicit migration/A-B validation.

## 3. Execute a workflow

Add `RH Execute`, connect `RH Config.config`, and queue the prompt.

`RH Execute` waits for the RH task, preserves/stages the returned files, converts supported files to ComfyUI values, and returns the `task_id`. Its RH_PARAMS fan-in is one native Autogrow chain: by default only `params` is visible; connecting it reveals `params_1`, then `params_2`, and so on through `params_15` (16 sources total). Later sources override duplicate node/field pairs, matching the former Execute 2 behavior. Saved graph workflows from the old Execute layouts are migrated automatically; old API-format prompts should be re-exported from the migrated graph.

### 3A. Inspect cloud fields before generating (optional, recommended)

Use the new **RH Workflow Inspect** node to check a RunningHub workflow's
actual API-format fields instead of guessing that every text node uses
`fieldName=text`.

For **no-upload/no-paid preflight**, make a separate, inspection-only ComfyUI
workflow with `RH Config` connected to `RH Workflow Inspect`. Choose
`remote` to query the official RH workflow metadata; select the matching
regional `base_url` on `RH Config` (`.ai` or `.cn`). The `local_file`
source can read an exported `api_format` JSON by its file path when the
remote endpoint is unavailable. Enter comma-separated `Node IDs` such as
`28,7,27,111` to list relevant fields. Optionally paste a JSON
`nodeInfoList` into the advanced manual check field. The `field_report`
STRING output can be connected to `RH Text Display`.

**Caution:** global **Queue** executes other output nodes in the same
graph. Do not queue a graph containing RH Execute while expecting an
inspection-only/no-paid run. The inspector itself never uploads media or
submits a paid task.

After checking the fields, in the generation graph connect
`RH Workflow Inspect.schema` to `RH Execute.workflow_schema`.
This enables strict validation of the **final merged** RH_PARAMS before
the paid create-task POST. An invalid `28.text` route fails with a
`28.prompt` suggestion. Existing workflows with no schema connection
execute as before. If an upstream upload is present, that upload can
still run **before** Execute checks the final values.

The inspector only supports RH **workflows**, not AI Apps. Local JSON is
an offline snapshot, not proof that RH's online workflow is unchanged.
The updated Python nodes require a ComfyUI backend restart before appearing
in the live UI; preserve a copy of the existing workflow before updating.

### 3B. Choose the RunningHub execution instance

`RH Execute` now uses `Instance Type` with four choices:
`auto`, `default`, `plus`, `ultra`. `auto` omits the RH
`instanceType` field and preserves the previous unchecked
High Performance behavior. `default` is explicit 24 GB,
`plus` is 48 GB, `ultra` is 84 GB. The same setting is optional
on `RH Batch Execute`.

Saved old Execute graphs automatically convert High Performance
`false → auto`, `true → plus`. If the old Boolean widget had an
external link, migration stops and warns instead of losing the
connection: keep the original workflow and migrate that link manually.
API-format prompts must be exported again after graph migration.
Your RH membership does not by itself prove which API instances your
account can run or how usage is charged; verify before a paid task.

### 3C. Recover a created task without submitting another paid run

After RunningHub confirms task creation, RH Execute and RH Batch Execute
record the Task ID in the plugin-local `.rh-task-history` folder. Files
are named by a digest and contain a readable `taskId`. They are ignored
by Git; they do not include your API key, prompt or media files.

If generation monitoring times out or ComfyUI closes after submission,
open the latest local JSON record and copy its `taskId`. Use your existing
**RH Task Manager** node with **Get Status**, or **RH Download Results**
with the same RH Config and the saved Task ID. This checks/downloads
the existing task instead of creating a new paid task. Never restart the
RH Execute node solely to retrieve an already-created result.

A transport failure before RH returns a Task ID remains uncertain and
cannot be automatically reconciled; inspect the RH website's task
history before considering a manual retry. A batch now stops on its first
failed submission and reports all earlier confirmed IDs rather than
continuing blindly. This is a deliberate safety change.

### 3D. Download failures are not media results

`RH Download Results` now stops with a visible error when a remote
task or output fails to download or convert. It no longer substitutes
artificial images and prints a misleading successful batch message.
Already preserved original files remain intact. Use the existing Task
ID (or the local task journal) to retry the **download** after fixing
the issue; this does not create another paid RH generation.

### 3E. Limit video frame memory (recommended for long videos)

In `RH Execute` or `RH Download Results`, set `Video Frames`:

- `all_frames`: legacy default, extracts every frame; may use several GB
  for a 30-second video. Use only if a downstream node requires all IMAGE
  frames.
- `preview_only`: extracts **one preview frame** from the first video;
  the full original video remains in `VIDEO`.
- `disabled`: skips video-to-IMAGE extraction entirely. The
  `video_frames` IMAGE port retains a compatibility placeholder;
  use `VIDEO` for the real MP4/video.

For the user's H3 30-second generation workflow, prefer
`disabled` if you only need the resulting video file, or
`preview_only` if you also want one frame for inspection. The default
remains `all_frames` so existing workflows retain their frame output.
Settings are independent of the RH cloud instance selector and do not
change credit costs or the remote result. No paid video task was
submitted during development of this feature.

## 4. Override text parameters

Use `RH Param`:

- `node_id`: node ID in the RunningHub workflow.
- `field_name`: usually `text` for a text widget.
- `field_value`: replacement value.

Chain multiple `RH Param` nodes through `previous_params` when needed, then connect the final `params` to `RH Execute`.

For multiple parameters in one node, use `RH Params V2`: select Param Count, then fill each Node / Field / Value. Each Value is one native connectable input, not a local fallback plus a separate override socket. There is no Enable switch; an unused empty row is ignored. Select custom to expose that row's custom field. Visible groups use a 4 px display-only gap that is not serialized. Reducing Param Count hides higher rows immediately with no confirmation and excludes them from execution; increasing Count again in the same editor session restores their cached values and links. This hidden-row cache is not a cross-restart persistence guarantee, so restore the Count before saving if those hidden rows must survive a close/reload. Connect the node's `params` output to `RH Execute`.

## 5. Upload local media

Use the matching upload node:

- image -> `RH Upload Image`
- audio -> `RH Load Audio Path` + `RH Upload Audio`
- video -> `RH Upload Video`
- generic file -> `RH Upload File`
- latent -> `RH Upload Latent`

Image / Video / Audio can optionally append the returned RH filename to `RH_PARAMS`. File / Latent keep their existing single `RH_PARAM` output, and batch image nodes retain their separate batch semantics. Audio still accepts a file path, not an AUDIO waveform.

`RH Upload Image V2` starts with Image 1. Connecting it reveals Image 2; each connected last slot reveals another native IMAGE input together with its independent Node / Field / Custom Field controls, up to 12 slots. A trailing unconfigured row can disappear after disconnection; disconnected rows containing a target mapping stay visible, and sparse numbers never shift. `Image Count` is hidden, not deleted from the saved V3 group/prompt contract, so older saved workflows still load. No Enable switch or handwritten HTML form is used. The single-image `RH Upload Image` and the unregistered `RH_UploadMask` are unchanged.

### 5A. Invalid mappings stop instead of being silently omitted

For `RH Param` and `RH MultiParams`, provide a real **Node ID**
and **Field** for each configured row. If Field is `custom`, enter
the actual API field name (for H3 Node 28, use `prompt`, not `text`).
Completely blank MultiParams rows are still ignored. A configured
row missing its Node ID or Custom Field now fails visibly.

For `RH Multi-Input Image`, every connected IMAGE must have its own
Node ID and Field. All connected routes are checked **before the first
upload**; one incomplete slot blocks the whole group.
`RH Batch Upload Image` likewise stops if the shared routing is
missing, no images are connected or one upload fails. It no longer
silently submits fewer runs than requested. Fix the mapping and
rerun only after checking which uploaded remote files may already
exist. These checks happen before any paid RH Execute task is created.

## 6. Understand output saving

The connector is raw-first:

```text
RunningHub result
  -> original file download
  -> atomic local save/stage
  -> ComfyUI media conversion
```

With `save_to_local=true`, the original RH file is saved in the ComfyUI output directory.

A local conversion error does not delete the preserved RH file and does not silently return fake one-second audio.

## 7. Video note

Use `RH Execute.video` for current ComfyUI video pipelines. It is built from the preserved MP4 through ComfyUI's lazy file-backed video API when available.

`video_frames` remains for older workflows and may consume significant memory because it materializes frames.

## 8. If task submission is uncertain

Cloud task creation is intentionally not auto-retried after an ambiguous HTTP failure. The remote task may already have been created and charged.

Check the RunningHub task list before manually retrying.

## 9. Basic validation after updating the connector

Run:

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
python3 -m compileall -q nodes tests
git diff --check
```

Then run one existing RH workflow in ComfyUI and confirm:

- RH backend shows a successful task.
- Console prints `Preserved RH output` for each returned file.
- The original file appears in ComfyUI `output` when `save_to_local=true`.
- The expected ComfyUI output (`STRING`, `IMAGE`, `AUDIO`, or `VIDEO`) is usable downstream.

See [ARCHITECTURE.md](./ARCHITECTURE.md) for maintenance rules and the full real-regression matrix.
