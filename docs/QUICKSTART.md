# Quick Start Guide

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

The optional `query_api` setting defaults to `legacy`. Keep that default for normal use. `v2` is available for explicit migration/A-B validation.

## 3. Execute a workflow

Add `RH Execute`, connect `RH Config.config`, and queue the prompt.

`RH Execute` waits for the RH task, preserves the original returned files, converts supported files to ComfyUI values, and returns the `task_id`.

## 4. Override text parameters

Use `RH Param`:

- `node_id`: node ID in the RunningHub workflow.
- `field_name`: usually `text` for a text widget.
- `field_value`: replacement value.

Chain multiple `RH Param` nodes through `previous_params` when needed, then connect the final `params` to `RH Execute`.

## 5. Upload local media

Use the matching upload node:

- image -> `RH Upload Image`
- audio -> `RH Load Audio Path` + `RH Upload Audio`
- video -> `RH Upload Video`
- generic file -> `RH Upload File`
- latent -> `RH Upload Latent`

Each upload node can optionally append the returned RH filename to the parameter list for the remote node/field.

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
