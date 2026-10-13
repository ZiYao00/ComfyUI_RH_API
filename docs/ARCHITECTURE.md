# ComfyUI_RH_API Architecture

This document defines the compatibility and reliability rules for maintaining the connector. It is intentionally small and describes durable behavior rather than individual bug-fix history.

## 1. Compatibility boundary

Existing ComfyUI node IDs are public workflow contracts. Keep names such as `RH_Config`, `RH_Execute`, `RH_Param`, `RH_Download`, and the existing upload node IDs stable unless a deliberate breaking release is made.

Repository name, display name, documentation branding, and hosting location may change independently from node IDs.

New inputs should be optional and preserve old defaults whenever possible. Stable released node IDs are public contracts. When a V3 dynamic-input structure necessarily changes serialized input names, provide an explicit graph migration rather than silently reinterpreting saved slots or links.

### Native input/UI policy (2026-10-12)

`nodes/rh_native.py` is the active V3 schema boundary for `RH_Execute`, `RH_Params2`, and all eight registered upload nodes. It uses official V3 `ComfyNode`, `MultiType`, `DynamicCombo`, and `Autogrow` APIs while preserving public node IDs. Existing upload classes remain implementation services for unchanged media encoding/RH HTTP behavior. `RH_Execute` now owns the former Execute 2 multi-`RH_PARAMS` behavior. Its entire fan-in is one native Autogrow chain: only `params` is visible initially; connecting it reveals `params_1`, then `params_2`, through `params_15` for a maximum of 16 sources. The legacy `RH_Execute2` class remains deprecated for non-graph compatibility, while saved graph nodes migrate to `RH_Execute` before construction.

Each Params row has exactly ONE declared Value input. A native STRING widget can accept linked STRING, INT, FLOAT or BOOLEAN values through `MultiType`. Do not reintroduce separate `local_value_N` widgets plus wildcard `value_N` sockets. The legacy parser still accepts older tuples for migration/tests; that is not permission to expose the old design again.

`RH_Params2` and `RH_UploadImage2` use native repeated DynamicCombo configuration groups; neither exposes an Enable switch. Params V2 retains a user-editable Param Count with the established same-session value/link cache. Upload Image V2 instead hides its *serialized* native `image_count` selector through the supported widget visibility property and derives the selected count from connected IMAGE slots and populated Node/Field metadata. Connecting the last IMAGE reveals the next row (up to 12); disconnecting a completely empty trailing row can shrink it. Sparse or configured rows never renumber or silently lose their route. Count remains a single native source of truth for group expansion, workflow serialization, and backend validation; there is no shadow UI count or handwritten business input. Only the UI changes: public node ID, `RH_PARAMS` output, route fields, media encoding, and RH HTTP calls stay the same. Both grouped nodes use non-interactive, non-serializing 4 px visual spacers.

Fixed-input upload nodes preserve their flat API names, widget order and output contracts. Audio remains an audio file path input, Video remains VIDEO, File/Latent remain RH_PARAM, and batch image uploads retain their distinct batch semantics. `RH_UploadMask` was not registered before this work and is not silently enabled by this change.

Legacy Params/Image and Execute GRAPH workflows have an explicit, transactional migration adapter. Preserve stable slot order, values, custom fields and external links. Previous Execute names map `params` -> `params.params` and `params_2`/`extra_params.params_2` -> `params.params_1`, continuing by one-based display order without moving target slots. Because both active V2 grouped nodes removed Enable, any legacy disabled row that still contains data or a connection must block migration rather than become active silently. Duplicate/unsupported mappings or legacy RH nodes inside subgraph definitions must produce blocked placeholders and an explicit warning, not a runnable node with default values. API-format prompts do not contain graph migration context and must be re-exported after these schema migrations. See [Native UI guide and verification record](NATIVE_UI.md).

Verified runtime: ComfyUI 0.39.0 and frontend 1.55.14 for the 2026-10-12 isolated Image V2 UI test; frontend 1.53.10 was the earlier native-input baseline. These are tested versions, not a minimum-version compatibility claim. Current Core's Autogrow template only expands one input specification, so Image V2's composite route+image rows still use native DynamicCombo; do not replace it with custom addInput or parallel count state. Do not silently fall back to a double-input UI, auto-upgrade the runtime, or confuse display-name V2 / ComfyUI V3 schema with RunningHub's V2 HTTP API.

## 2. RunningHub API boundary

RunningHub HTTP behavior belongs in `nodes/rh_client.py`.

Current policy:

- Legacy task creation remains the production path for existing workflow/API-app calls.
- Legacy result query remains the default (`query_api=legacy`).
- V2 result query is supported explicitly for compatibility testing.
- Legacy and V2 media upload implementations are isolated in the client.
- Do not automatically switch production behavior to a newer RH API until the same real task has been compared through both query paths.

Node code should consume normalized statuses/results instead of parsing RH response shapes directly.

### Normalized task states

The connector distinguishes at least:

- `QUEUED`
- `RUNNING`
- `SUCCESS`
- `NO_OUTPUT`
- `ERROR`
- `API_ERROR`
- `NETWORK_ERROR`

Network failure is not equivalent to a running cloud task.

## 3. Paid task submission and retry safety

Creating a cloud task can consume credits. Task creation therefore uses a single safe POST attempt.

If a transport failure, unreadable response, or success-without-taskId occurs after the request may have reached RunningHub, the connector reports an uncertain submission state and does **not** automatically submit another task. The operator should check the RH task list before retrying manually.

Read-only queries and raw-file downloads may use bounded retries in the future because they are idempotent. Task creation must not inherit that retry policy without a documented RH idempotency mechanism.

## 4. Raw-first output invariant

Remote assets are the source of truth.

The output pipeline is:

```text
RH API response
    -> normalize output records
    -> download original remote files
    -> atomically preserve/stage files
    -> convert local files to ComfyUI media types
```

Media conversion must never be a prerequisite for preserving the RH result.

If an MP3, MP4, image, text file, or latent file is downloaded successfully but ComfyUI conversion fails, the original file must remain available and the conversion failure must be explicit.

## 5. Output normalization

`nodes/rh_outputs.py` owns result normalization and raw downloads.

An output item records a stable original index and infers media type from multiple signals:

1. RH-declared type (`fileType`, `outputType`, etc.)
2. URL extension
3. HTTP `Content-Type`

Supported internal media families are:

- image
- video
- audio
- text
- latent
- unknown

Unknown files must not be discarded solely because the connector does not recognize their media type.

Parallel downloads are allowed, but results must be restored to the original RH result order by index before selection or aggregation.

## 6. Atomic local persistence

Raw files are written to a temporary `.part` path and renamed to the final name only after the download succeeds.

A failed or interrupted transfer must not leave a partial file that looks like a completed output.

Saved names should be collision-resistant and include at least a stable output prefix, task identifier when available, and original output index.

## 7. ComfyUI media adapters

`nodes/rh_media.py` is the only layer that should know how preserved files become ComfyUI media values.

### IMAGE

Decode the preserved local image into the standard ComfyUI image tensor. Preserve the original RH file separately; do not use a re-encoded image as the only saved artifact.

### AUDIO

Return the standard ComfyUI AUDIO mapping:

```python
{
    "waveform": waveform_with_batch_dimension,
    "sample_rate": sample_rate,
}
```

Prefer ComfyUI's current PyAV-based audio loader. Torchaudio is only a compatibility fallback and must not be auto-upgraded by this plugin.

Never rename arbitrary compressed audio bytes to `.wav` as a decoding strategy.

### VIDEO

Use ComfyUI's lazy `InputImpl.VideoFromFile` path for the `VIDEO` output when available. Do not decode an entire video into float32 image tensors just to construct the standard VIDEO output.

`video_frames` is retained as a legacy compatibility output. New workflows should prefer `video`. Full-frame extraction can be memory intensive and may be reduced/deprecated in a future breaking release only after compatibility planning.

### TEXT

Decode UTF-8/UTF-8-BOM explicitly so Chinese text does not depend on HTTP charset guessing.

### LATENT

Use the safetensors file API (`load_file`) for local `.safetensors` files.

## 8. Failure semantics: no fake success

Absence and failure are different states.

Examples:

- No audio was produced -> audio output may be `None`.
- RH produced audio but the download failed -> error.
- Audio was preserved but ComfyUI decoding failed -> error with the preserved file path/log available.

Do not replace processing failures with synthetic one-second silence, synthetic videos, or other data that can be mistaken for a successful result.

Image/video-frame placeholders may remain only where required by legacy ComfyUI output contracts, and must not hide a real remote media conversion failure.

## 9. Secrets

`config.local.json` is the preferred local secret store and is ignored by Git.

Node-entered values override file values for compatibility, but API keys should normally be left blank in workflow nodes so workflow JSON does not contain secrets.

UI masking is a display protection only; it does not replace secret-at-rest handling.

Never print API key contents in logs.

## 10. Dependency policy

The connector owns as few Python dependencies as possible.

- `requests` is a connector dependency.
- Torch, NumPy, Pillow, and safetensors are supplied by ComfyUI and must not be pinned/upgraded by this plugin.
- OpenCV is optional for legacy `video_frames` extraction.
- Torchaudio is optional as an old-runtime audio fallback.

Do not add an automatic dependency that can replace the user's ComfyUI/CUDA Torch stack without explicit justification and validation.

## 11. Test policy

Unit tests use the Python standard library (`unittest`, mocks/stubs) so connector logic can be validated without installing a second ComfyUI/Torch environment.

Before a local maintenance commit, run:

```bash
python -B tests/run_tests.py
python -B -m compileall -q nodes tests
git diff --check
```

Real RH regression is still required for release confidence because unit tests do not reproduce the user's ComfyUI build, RH account, signed output URLs, or current cloud workflow nodes.

Minimum real regression matrix:

| Output | RH task succeeds | Original file preserved | ComfyUI output valid |
| --- | --- | --- | --- |
| Text | yes | yes | STRING |
| Image | yes | yes | IMAGE |
| Audio | yes | yes | AUDIO |
| Video | yes | yes | VIDEO |

Current real-world validation status (2026-09-16):

- **Audio: PASS.** A real RunningHub audio-generation workflow completed successfully, the returned audio file was preserved in the local ComfyUI output path, and the previous one-second fallback symptom is no longer present.
- **Video: PENDING.** The refactored VIDEO path has unit-test coverage but has not yet been revalidated with a real RunningHub video task after the output-layer changes.

Also verify Chinese UTF-8 text, multiple outputs, no-output tasks, and a deliberate conversion/download failure path when practical.

## 12. Deferred follow-up backlog

The current maintenance cycle is intentionally closed without forcing tests that the present environment cannot run. The following items are deferred rather than treated as release blockers:

- **Real VIDEO regression:** pending until an environment capable of running the RH video workflow is available. After that test, decide whether legacy `video_frames` should support `all_frames`, `preview_only`, or `disabled` modes to reduce memory pressure.
- **V2 upload A/B:** the V2 media-upload adapter exists, but Legacy remains the default until image/audio/video uploads are compared against the same real RH workflows.
- **Result Manifest / `RH_RESULT_BUNDLE`:** add a structured result bundle when multi-file/multi-type workflows justify a new public node contract.
- **Workflow Inspector:** use RH workflow metadata to reduce manual `node_id` / `field_name` entry only after the core connector remains stable in normal use.
- **Diagnostics surface:** add a compact task/output diagnostic report if future failures show that console logs are insufficient.

Task creation (including batch submission), result queries/uploads, and task cancellation should continue to converge on `RHClient` rather than introducing new direct HTTP calls in node implementations.

## 13. Version-control policy for this maintenance branch

During local stabilization of the upstream plugin:

- commits are local rollback points;
- do not push to the current upstream remote;
- do not rename the plugin or node IDs during bug-fix/refactor work;
- do not commit `__pycache__`, `.pyc`, or `config.local.json`;
- keep unrelated local files out of maintenance commits.

A separately named repository can be created later after real-world regression is complete and the connector has a stable maintenance baseline.
