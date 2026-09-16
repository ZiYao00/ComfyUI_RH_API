# ComfyUI_RH_API Architecture

This document defines the compatibility and reliability rules for maintaining the connector. It is intentionally small and describes durable behavior rather than individual bug-fix history.

## 1. Compatibility boundary

Existing ComfyUI node IDs are public workflow contracts. Keep names such as `RH_Config`, `RH_Execute`, `RH_Param`, `RH_Download`, and the existing upload node IDs stable unless a deliberate breaking release is made.

Repository name, display name, documentation branding, and hosting location may change independently from node IDs.

New inputs should be optional and preserve old defaults whenever possible. Existing saved workflows should continue to load without migration.

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
python3 -m unittest discover -s tests -p "test_*.py" -v
python3 -m compileall -q nodes tests
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
