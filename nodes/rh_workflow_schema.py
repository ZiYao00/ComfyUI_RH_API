"""Parse RunningHub ComfyUI API-format workflows without retaining prompt contents.

The exact node ID and input key pairs in the API graph are authoritative.
Media/control inference from field names is intentionally out of scope.
This module has no ComfyUI or network dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import difflib
import hashlib
import json
import math
import re
from typing import Any, Mapping


class RHWorkflowSchemaError(ValueError):
    """A supplied workflow cannot be trusted as a ComfyUI API-format graph."""


@dataclass(frozen=True)
class RHFieldSpec:
    node_id: str
    name: str
    kind: str
    node_class: str
    node_title: str
    connected: bool = False


@dataclass
class RHWorkflowSchema:
    nodes: dict[str, str]
    fields: dict[tuple[str, str], RHFieldSpec]
    fingerprint: str
    source: str = "unknown"

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    def fields_for_node(self, node_id: str) -> list[str]:
        return sorted(field for (node, field) in self.fields if node == str(node_id))

    def summarize(self, *, selected_nodes: tuple[str, ...] = ()) -> dict:
        # Do not expose API keys, prompt values or original uploaded filenames.
        ids = selected_nodes or tuple(sorted(self.nodes))
        return {
            "source": self.source,
            "fingerprint": self.fingerprint,
            "node_count": self.node_count,
            "field_count": len(self.fields),
            "nodes": [
                {"nodeId": node_id, "classType": self.nodes[node_id],
                 "fields": self.fields_for_node(node_id)}
                for node_id in ids if node_id in self.nodes
            ],
        }


@dataclass
class RHValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def explain(self) -> str:
        if self.ok and not self.warnings:
            return "RH workflow field validation passed."
        parts = ["RH workflow field validation " + ("failed:" if self.errors else "passed with warnings:")]
        parts.extend("ERROR: " + item for item in self.errors)
        parts.extend("WARNING: " + item for item in self.warnings)
        return "\n".join(parts)


def _decode_api_payload(value: Any) -> Mapping:
    if isinstance(value, bytes):
        if len(value) > 32 * 1024 * 1024:
            raise RHWorkflowSchemaError("Workflow JSON exceeds 32 MiB.")
        value = value.decode("utf-8-sig")
    if isinstance(value, str):
        if len(value) > 32 * 1024 * 1024:
            raise RHWorkflowSchemaError("Workflow JSON exceeds 32 MiB.")
        try:
            value = json.loads(value)
        except (ValueError, TypeError) as exc:
            raise RHWorkflowSchemaError("Workflow is not valid JSON.") from exc
    if not isinstance(value, dict):
        raise RHWorkflowSchemaError("Workflow API JSON must be an object.")

    if "code" in value and "data" in value:
        if value["code"] != 0:
            raise RHWorkflowSchemaError("RH did not return a successful workflow definition.")
        data = value["data"]
        if not isinstance(data, dict) or "prompt" not in data:
            raise RHWorkflowSchemaError("RH response is missing data.prompt.")
        return _decode_api_payload(data["prompt"])
    if "prompt" in value and len(value) <= 3 and isinstance(value["prompt"], (str, dict)):
        return _decode_api_payload(value["prompt"])
    return value


def _is_link(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], (str, int))
        and not isinstance(value[0], bool)
        and isinstance(value[1], int)
        and not isinstance(value[1], bool)
        and value[1] >= 0
    )


def _kind(value: Any) -> str:
    if _is_link(value):
        return "connection"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if value is None:
        return "unknown"
    return "structured"


def parse_workflow_api_json(value: Any, *, source: str = "export") -> RHWorkflowSchema:
    """Accept an exported API object or RH's code/data.prompt response."""
    graph = _decode_api_payload(value)
    if not graph or len(graph) > 4096:
        raise RHWorkflowSchemaError("Workflow has no nodes or exceeds the supported node limit.")
    # The browser workflow graph has a different format and is not a valid source
    # for RH nodeInfoList validation.
    if "nodes" in graph and isinstance(graph["nodes"], list):
        raise RHWorkflowSchemaError("Please export the workflow in API format, not UI graph format.")

    nodes: dict[str, str] = {}
    fields: dict[tuple[str, str], RHFieldSpec] = {}
    for raw_node_id, node in graph.items():
        node_id = str(raw_node_id).strip()
        if not node_id or not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
            raise RHWorkflowSchemaError("Invalid API-format node structure.")
        node_class = node.get("class_type")
        if not isinstance(node_class, str) or not node_class.strip():
            raise RHWorkflowSchemaError("Workflow node is missing class_type.")
        # Cloud-provided node titles can contain private prompt fragments.
        # Retain only the non-sensitive class name at this layer.
        title = node_class[:120]
        nodes[node_id] = node_class
        if len(node["inputs"]) > 512:
            raise RHWorkflowSchemaError("Workflow node has too many inputs.")
        for name, original in node["inputs"].items():
            if not isinstance(name, str) or not name:
                raise RHWorkflowSchemaError("Workflow input name is invalid.")
            kind = _kind(original)
            fields[(node_id, name)] = RHFieldSpec(
                node_id=node_id, name=name, kind=kind,
                node_class=node_class, node_title=title, connected=kind == "connection"
            )

    # A field signature is sufficient for invalidating a stale schema without
    # retaining full prompt text, image filenames, or other workflow data.
    signature = [
        (node_id, name, spec.node_class, spec.kind)
        for (node_id, name), spec in sorted(fields.items())
    ]
    fingerprint = hashlib.sha256(
        json.dumps(signature, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return RHWorkflowSchema(nodes=nodes, fields=fields, fingerprint=fingerprint, source=source)


def _matches_kind(value: Any, kind: str) -> bool:
    if kind in {"string", "unknown", "structured"}:
        return True  # RH accepts stringified overrides and some special widget encodings.
    if kind == "boolean":
        return isinstance(value, bool) or (
            isinstance(value, str) and value.lower().strip() in {"true", "false", "0", "1"}
        ) or value in (0, 1)
    if kind == "integer":
        return (isinstance(value, int) and not isinstance(value, bool)) or (
            isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value.strip()) is not None
        )
    if kind == "float":
        try:
            return not isinstance(value, bool) and math.isfinite(float(value))
        except (ValueError, TypeError, OverflowError):
            return False
    return True


def validate_node_info_list(schema: RHWorkflowSchema, overrides: Any) -> RHValidationReport:
    """Validate final merged overrides; never modify values or silently fix names."""
    report = RHValidationReport()
    if not isinstance(overrides, (list, tuple)):
        report.errors.append("nodeInfoList must be an array.")
        return report
    for index, entry in enumerate(overrides, 1):
        if not isinstance(entry, dict):
            report.errors.append(f"Override #{index} must be an object.")
            continue
        node_id = str(entry.get("nodeId") or "").strip()
        field_name = entry.get("fieldName")
        field_name = field_name.strip() if isinstance(field_name, str) else ""
        label = f"Override #{index} ({node_id or '?'}.{field_name or '?'})"
        if not node_id or not field_name or "fieldValue" not in entry:
            report.errors.append(f"{label}: nodeId, fieldName and fieldValue are required.")
            continue
        if node_id not in schema.nodes:
            report.errors.append(f"{label}: node does not exist in the workflow API JSON.")
            continue
        spec = schema.fields.get((node_id, field_name))
        if spec is None:
            available = schema.fields_for_node(node_id)
            options = difflib.get_close_matches(field_name, available, n=3, cutoff=0.45)
            if not options and len(available) == 1:
                options = available
            suggestion = " Available fields: " + ", ".join(schema.fields_for_node(node_id)[:20]) + "."
            if options:
                suggestion = " Did you mean " + ", ".join(node_id + "." + name for name in options) + "?" + suggestion
            report.errors.append(f"{label}: field does not exist." + suggestion)
            continue
        if spec.connected:
            report.warnings.append(
                f"{label}: the original field is a node connection; RH does not recommend overriding connected inputs."
            )
        elif spec.kind == "structured":
            report.warnings.append(f"{label}: complex field type was not validated.")
        elif not _matches_kind(entry["fieldValue"], spec.kind):
            report.errors.append(f"{label}: value is incompatible with expected {spec.kind} input.")
    return report
