"""RunningHub workflow inspection service: read only; never uploads or queues tasks.

The standalone ComfyUI inspection node deliberately has no RH_PARAMS input.
Connecting upload results to a preflight node would upload media before validation.
"""
from __future__ import annotations

import json
from pathlib import Path

from .rh_client import RHClient
from .rh_workflow_schema import (
    RHWorkflowInspection,
    RHWorkflowSchemaError,
    parse_workflow_api_json,
    validate_node_info_list,
)


def inspect_workflow(
    config: dict,
    *,
    source_mode: str = "remote",
    api_json_path: str = "",
    node_filter: str = "",
    overrides_json: str = "",
) -> tuple[RHWorkflowInspection, str]:
    """Return scoped metadata and a human-readable, value-free field report.

    source_mode=remote explicitly fetches the cloud API definition.
    source_mode=local_file reads a user-supplied exported *API* JSON on disk.
    """
    if not isinstance(config, dict) or config.get("is_ai_app"):
        raise ValueError("RH Workflow Inspect supports workflow IDs, not AI App IDs.")
    if any(not config.get(k) for k in ("api_key", "workflow_or_app_id", "base_url")):
        raise ValueError("RH Workflow Inspect requires a complete RH Config.")
    if source_mode == "remote":
        # This request does not upload media or submit/charge a task. Do not log
        # the body, including default values or token-bearing error messages.
        try:
            raw = RHClient(config["api_key"], config["base_url"]).get_workflow_api_json(
                config["workflow_or_app_id"]
            )
        except Exception as exc:
            raise RuntimeError(
                f"RH workflow metadata fetch failed ({type(exc).__name__}). "
                "Check the account, region, workflow ID and RH API access. "
                "Use local_file mode with an exported API JSON if unavailable."
            ) from None
        schema = parse_workflow_api_json(raw, source="remote")
        remote_verified = True
    elif source_mode == "local_file":
        if not str(api_json_path or "").strip():
            raise ValueError("Select an exported ComfyUI API-format .json file.")
        path = Path(str(api_json_path)).expanduser()
        if path.suffix.lower() != ".json" or not path.is_file():
            raise ValueError("Local inspection requires an existing .json file.")
        if path.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("Local API JSON exceeds the 32 MiB inspection limit.")
        schema = parse_workflow_api_json(path.read_bytes(), source="local_file")
        remote_verified = False
    else:
        raise ValueError("Inspection source must be remote or local_file.")

    inspected = RHWorkflowInspection.bind(schema, config, remote_verified=remote_verified)
    requested_nodes = [s.strip() for s in str(node_filter or "").replace(";", ",").split(",") if s.strip()]
    if len(requested_nodes) > 100:
        raise ValueError("Inspect at most 100 node IDs at a time.")
    missing = [name for name in requested_nodes if name not in schema.nodes]
    if missing:
        raise RHWorkflowSchemaError("Node IDs not present in API JSON: " + ", ".join(missing[:20]))

    if not isinstance(overrides_json, str) or len(overrides_json) > 65536:
        raise ValueError("Manual override JSON must be text up to 64 KiB.")
    if overrides_json.strip():
        try:
            overrides = json.loads(overrides_json)
        except (TypeError, ValueError) as exc:
            raise ValueError("Manual nodeInfoList is not valid JSON.") from None
    else:
        overrides = []
    report = validate_node_info_list(schema, overrides)
    if report.errors:
        raise ValueError(report.explain())

    lines = [
        "RunningHub Workflow Field Inspector",
        f"Workflow ID: {inspected.workflow_id}",
        f"Source: {schema.source}" + (
            " (fetched from RH)" if remote_verified
            else " (local snapshot; remote changes are not checked)"
        ),
        f"Nodes: {schema.node_count}, fields: {len(schema.fields)}",
        f"Field signature: {schema.fingerprint[:16]}",
    ]
    limit = 250
    emitted = 0
    selected = requested_nodes or sorted(
        schema.nodes, key=lambda node_id: (0, int(node_id)) if node_id.isdigit() else (1, node_id)
    )
    for node_id in selected:
        fields = sorted(
            (name, spec) for (id_, name), spec in schema.fields.items() if id_ == node_id
        )
        if emitted >= limit:
            break
        lines.append(f"Node {node_id}: {schema.nodes[node_id]}")
        for field_name, spec in fields:
            if emitted >= limit:
                break
            note = " [connected - caution]" if spec.connected else ""
            lines.append(f"  {field_name} ({spec.kind}){note}")
            emitted += 1
    if emitted < sum(
        len(schema.fields_for_node(node_id)) for node_id in selected
    ):
        lines.append("Output limited to 250 fields; use Node IDs filter to narrow the result.")
    lines.append(report.explain())
    return inspected, "\n".join(lines)
