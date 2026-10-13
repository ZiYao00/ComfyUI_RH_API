"""Read-only RH workflow schema connectivity probe. NEVER uploads or creates a task.

Example:
  python -B tests/probe_rh_workflow_schema.py --workflow-id YOUR_ID --base-url https://www.runninghub.ai

Reads ignored config.local.json, falling back to the existing config.json.
Prints only field names, primitive types and status, never API key or prompts.
"""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[1]


def load_config():
    result = {}
    for path in (ROOT / "config.json", ROOT / "config.local.json"):
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(raw, dict):
                result.update({k: value for k, value in raw.items() if value not in (None, "")})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--base-url", default="https://www.runninghub.ai")
    args = parser.parse_args()

    cfg = load_config()
    if not cfg.get("api_key"):
        print("STATUS: SKIPPED: no local RH API key configured")
        return 2

    package = types.ModuleType("rh_schema_probe")
    package.__path__ = [str(ROOT / "nodes")]
    sys.modules[package.__name__] = package
    client_module = importlib.import_module(package.__name__ + ".rh_client")
    schema_module = importlib.import_module(package.__name__ + ".rh_workflow_schema")
    try:
        payload = client_module.RHClient(cfg["api_key"], args.base_url).get_workflow_api_json(args.workflow_id)
        schema = schema_module.parse_workflow_api_json(payload, source="remote")
    except Exception as exc:
        # The RH body, response and credentials may contain user data.
        print("STATUS: FAILED: " + type(exc).__name__)
        return 1

    print("STATUS: PASS: read-only RH metadata")
    print("Nodes:", schema.node_count, "Fields:", len(schema.fields))
    print("Field signature:", schema.fingerprint[:16])
    for node_id in ("7", "27", "28", "111"):
        print("Node", node_id, ":", ", ".join(schema.fields_for_node(node_id)) or "not present")

    wrong = schema_module.validate_node_info_list(
        schema, [{"nodeId": "28", "fieldName": "text", "fieldValue": "example"}]
    )
    correct = schema_module.validate_node_info_list(schema, [
        {"nodeId": "28", "fieldName": "prompt", "fieldValue": "example"},
        {"nodeId": "27", "fieldName": "value", "fieldValue": "15"},
        {"nodeId": "7", "fieldName": "width", "fieldValue": "480"},
        {"nodeId": "7", "fieldName": "height", "fieldValue": "864"},
        {"nodeId": "111", "fieldName": "image", "fieldValue": "example.png"},
    ])
    print("Regression wrong 28.text rejected:", not wrong.ok)
    print("Regression correct 28.prompt and other fields accepted:", correct.ok)
    return 0 if not wrong.ok and correct.ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
