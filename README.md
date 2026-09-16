# ComfyUI RunningHub API Connector

[English](./README.md) | [中文](./README_CN.md)

ComfyUI custom nodes for calling RunningHub workflows and AI apps from a local ComfyUI instance.

## Key features

- Run RunningHub workflows and AI apps from ComfyUI.
- Chain text parameters and uploaded image/audio/video/file inputs.
- Preserve original RH output files before converting them to ComfyUI values.
- Return ComfyUI `IMAGE`, `AUDIO`, `VIDEO`, `STRING`, and `LATENT` outputs where supported.
- Surface download/conversion failures instead of replacing them with fake successful media.
- Keep legacy RH result queries as the default while exposing an explicit V2 query mode for validation.
- Store local credentials in ignored `config.local.json` instead of workflow JSON whenever possible.

See [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) for compatibility and maintenance rules.

## Installation

### ComfyUI Manager

Search for `ComfyUI_RH_API`, install it, then restart ComfyUI.

### Manual

Clone the repository into `ComfyUI/custom_nodes/ComfyUI_RH_API`, then install only the connector-owned requirements:

```bash
pip install -r requirements.txt
```

The plugin deliberately does not pin or upgrade the Torch/CUDA stack supplied by ComfyUI.

## Quick start

1. Add `RH Config` and provide a RunningHub workflow/app ID.
2. Prefer leaving the credential field blank and supplying it through `config.local.json`.
3. Add `RH Execute` and connect the `config` output.
4. Add `RH Param` and/or upload nodes when remote workflow inputs need to be overridden.
5. Queue the ComfyUI workflow.

`RH Execute` returns:

- `images`
- `video_frames` (legacy compatibility output)
- `text`
- `audio`
- `video`
- `latent`
- `task_id`

New video workflows should prefer the `video` output. `video_frames` can require substantial memory for long videos.

## Configuration

Create an ignored `config.local.json` beside the plugin files:

```json
{
  "api_key": "[REDACTED_SECRET]",
  "base_url": "https://www.runninghub.cn",
  "query_api": "legacy"
}
```

`config.local.json` overrides non-empty values from the tracked legacy `config.json`. Values entered directly in `RH Config` have the highest priority.

### Query API mode

`RH Config` includes optional `query_api`:

- `legacy` — default for compatibility with existing workflows.
- `v2` — explicit RunningHub V2 result-query path for migration testing.

Do not treat V2 as an automatic production switch until the same real task has been compared through both query paths.

## Output behavior

The connector uses a raw-first pipeline:

```text
RH result metadata
  -> normalize result type/order
  -> download original file atomically
  -> preserve/stage the original file
  -> convert the local file to a ComfyUI media value
```

If a remote file was downloaded but conversion fails, the original file is kept and the node reports the conversion error. In particular, audio failures are no longer replaced by synthetic one-second silence.

When `save_to_local=true`, original RH outputs are preserved in the ComfyUI output directory. When it is false, files needed by ComfyUI media objects are staged in ComfyUI/system temporary storage.

## Upload nodes

Available upload paths include:

- `RH Upload Image`
- `RH Load Audio Path` + `RH Upload Audio`
- `RH Upload Video`
- `RH Upload File`
- `RH Upload Latent`
- batch/multi-image upload nodes

Legacy upload remains the default. The internal client also contains a V2 media-upload adapter so migration can be validated without rewriting every upload node.

## Task safety

Cloud task creation uses a single safe POST attempt. If the request may have reached RunningHub but the response is lost or unreadable, the connector reports that submission status is uncertain and does not automatically create another paid task.

Check the RunningHub task list before manually retrying an uncertain submission.

## Troubleshooting

### RunningHub has a file but ComfyUI reports conversion failure

This means the raw download succeeded but the local ComfyUI media adapter could not convert it. Check the console message and the preserved output file. Do not regenerate the RH task until you know a new cloud run is necessary.

### Network error while polling

Network failures are reported separately from `RUNNING`. After repeated query failures, polling stops with an explicit connection error instead of pretending the cloud task is still running.

### Task submission status is uncertain

Check the RunningHub backend task list before retrying. Automatic task-creation retry is intentionally disabled to avoid duplicate paid tasks.

### Video output

Current ComfyUI builds use the lazy `VideoFromFile` API for the `video` output. If an older ComfyUI build lacks that API, the original MP4 is still preserved and an explicit conversion error is reported.

### Optional legacy media support

- OpenCV is only needed for legacy `video_frames` extraction.
- Torchaudio is only an audio-decoding fallback for older ComfyUI environments.

Do not install/upgrade Torchaudio independently if that would disturb the Torch/CUDA versions used by ComfyUI.

## Tests

The connector tests use Python standard-library mocks/stubs and do not install a second Torch environment:

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
python3 -m compileall -q nodes tests
git diff --check
```

Unit tests do not replace a real ComfyUI + RunningHub regression. Before a release or repository fork, verify at least Text, Image, Audio, and Video with real RH tasks.

## License

MIT. See [LICENSE](./LICENSE).
