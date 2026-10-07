# Quick Start Guide

> Native UI update (2026-10-07): Params 2 and all eight registered upload nodes now use native V3 schemas. Tested with ComfyUI 0.39.0 / frontend 1.53.10. Save an original workflow copy, restart the backend, then refresh with Ctrl+F5. See [原生输入使用说明、迁移边界与验证记录](NATIVE_UI.md). This update does not install or upgrade runtime dependencies.

## 1. Install

Place `ComfyUI_RH_API` under `ComfyUI/custom_nodes/`, install `requirements.txt`, and restart ComfyUI.

The requirements intentionally do not install or upgrade Torch/Torchaudio/CUDA packages.

## 2. Configure RunningHub

Add `RH Config`.

Required workflow setting:

- `workflow_or_app_id`: RunningHub workflow ID or AI app ID.

Recommended credential setup:

1. Copy `config.json.example` to `config.local.json`.
2. Put the local credential in `config.local.json`.
3. Leave the credential widget in `RH Config` blank.

`config.local.json` is ignored by Git.

The optional `query_api` selector on `RH Config` defaults to `legacy`. Keep that default for normal use. `v2` is available for explicit migration/A-B validation.

## 3. Execute a workflow

Add `RH Execute`, connect `RH Config.config`, and queue the prompt.

`RH Execute` waits for the RH task, preserves the original returned files, converts supported files to ComfyUI values, and returns the `task_id`.

## 4. Override text parameters

Use `RH Param`:

- `node_id`: node ID in the RunningHub workflow.
- `field_name`: usually `text` for a text widget.
- `field_value`: replacement value.

Chain multiple `RH Param` nodes through `previous_params` when needed, then connect the final `params` to `RH Execute`.

For multiple parameters in one node, use `RH Params 2`: select Param Count, then fill each Node / Field / Value. Each Value is one native connectable input, not a local fallback plus a separate override socket. Select custom to expose that row's custom field. A destructive count reduction asks for confirmation; cancel retains values and links. Connect its `params` output to an RH_PARAMS input on the execution node. Open legacy experimental graph workflows from a copy and re-export API prompts after migration.

## 5. Upload local media

Use the matching upload node:

- image -> `RH Upload Image`
- audio -> `RH Load Audio Path` + `RH Upload Audio`
- video -> `RH Upload Video`
- generic file -> `RH Upload File`
- latent -> `RH Upload Latent`

Image / Video / Audio can optionally append the returned RH filename to `RH_PARAMS`. File / Latent keep their existing single `RH_PARAM` output, and batch image nodes retain their separate batch semantics. Audio still accepts a file path, not an AUDIO waveform.

`RH Upload Image 2` provides 1 to 12 native groups with independent target node/field settings and IMAGE inputs. Its old HTML row form is retired. The unregistered `RH_UploadMask` module is not enabled by this update.

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
