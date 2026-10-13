"""Live 8190 local smoke test: reads node schemas and executes only offline RH Inspect.

No RH paid task, uploads, GPUs or user workflows are used. Never target 8188.
"""
from __future__ import annotations
import json
from pathlib import Path
import tempfile
import time
import urllib.request
import uuid

BASE = "http://127.0.0.1:8190"


def fetch(route, payload=None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        BASE + route, data=body,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urllib.request.urlopen(req, timeout=12) as response:
        return json.load(response)


def inspect_node(name):
    return fetch("/object_info/" + name).get(name)


def check(value, description):
    if not value:
        raise AssertionError(description)
    print("PASS:", description, flush=True)


def main():
    sysinfo = fetch("/system_stats")["system"]
    check(sysinfo.get("comfyui_version") == "0.39.0", "8190 ComfyUI 0.39.0 detected")
    command = str(sysinfo.get("argv", [])).lower().replace("\\", "/")
    check("comfyui_test" in command, "The test package, not 8188, owns port 8190")
    for name in (
        "RH_Config", "RH_Execute", "RH_WorkflowInspect", "RH_Params2",
        "RH_UploadImage2", "RH_Download", "RH_BatchExecute",
        "RH_Param", "RH_MultiInputImage", "RH_BatchUploadImage",
    ):
        check(bool(inspect_node(name)), "Real test backend registered " + name)
    check(inspect_node("RH_MultiParams") is None,
          "Dormant RH_MultiParams source is intentionally not registered")
    execute = inspect_node("RH_Execute")
    check("instance_type" in execute["input"]["required"], "Execute supports instance combo")
    check("video_frame_mode" in execute["input"]["required"], "Execute supports video frame modes")
    check("workflow_schema" in execute["input"]["optional"], "Execute supports optional inspector")
    check(execute["output"] == ["IMAGE", "IMAGE", "STRING", "AUDIO", "VIDEO", "LATENT", "STRING"],
          "Execute retains seven output contracts")
    download = inspect_node("RH_Download")
    check(list(download["input"]["optional"])[-1] == "video_frame_mode",
          "Download appends the frame selector after legacy widgets")
    check(len(download["output"]) == 6, "Download retains six output contracts")
    check("instance_type" in inspect_node("RH_BatchExecute")["input"]["optional"],
          "Batch instance combo registered")
    check(inspect_node("RH_Params3_Lab") is None, "Obsolete V3 Lab is not loaded")
    q = fetch("/queue")
    check(not q.get("queue_running") and not q.get("queue_pending"),
          "8190 execution queue was empty before smoke test")

    with tempfile.TemporaryDirectory(prefix="rh-test-8190-") as folder:
        file = Path(folder) / "graph-api.json"
        file.write_text(json.dumps({
            "28": {"class_type": "CR Prompt Text", "inputs": {"prompt": "fixture"}},
            "7": {"class_type": "EmptyLatentImage", "inputs": {"width": 480}},
        }), encoding="utf-8")
        graph = {
            "10": {"class_type": "RH_Config", "inputs": {
                "api_key": "fixture", "workflow_or_app_id": "local_only_fixture",
                "base_url": "https://www.runninghub.ai", "is_ai_app": False,
            }},
            "20": {"class_type": "RH_WorkflowInspect", "inputs": {
                "config": ["10", 0], "source_mode": "local_file",
                "api_json_path": str(file), "node_filter": "28,7",
                "overrides_json": json.dumps([
                    {"nodeId": "28", "fieldName": "prompt", "fieldValue": "fixture"}
                ]),
            }},
        }
        check({n["class_type"] for n in graph.values()} == {"RH_Config", "RH_WorkflowInspect"},
              "Prompt cannot run a paid Execute or upload node")
        response = fetch("/prompt", {
            "prompt": graph, "client_id": "rh-local-smoke-" + uuid.uuid4().hex
        })
        check(not response.get("node_errors"), "Local-only graph accepted without schema errors")
        prompt_id = response.get("prompt_id")
        check(bool(prompt_id), "8190 queued one local-only inspector")
        for _ in range(80):
            history = fetch("/history/" + prompt_id)
            entry = history.get(prompt_id)
            if entry:
                status = entry.get("status", {})
                if status.get("status_str") == "success":
                    check(True, "Offline RH Workflow Inspect executed in real backend")
                    break
                if status.get("status_str") == "error":
                    raise AssertionError("8190 local-only node execution failed")
            time.sleep(0.5)
        else:
            raise TimeoutError("8190 local-only graph did not complete")

    print("LIVE_8190_PASS: no RunningHub task, upload or media used")


if __name__ == "__main__":
    main()
