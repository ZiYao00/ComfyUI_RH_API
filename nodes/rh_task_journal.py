"""Local, append-by-task journal for confirmed RunningHub task IDs.

Only task identifiers, workflow identity, the selected instance and UTC time
are recorded. Do not store authorization data, nodeInfoList or remote results.
Writing is atomic, and journal failure must never cause a paid task retry.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit


JOURNAL_DIR = Path(__file__).resolve().parents[1] / ".rh-task-history"


def record_created_task(
    task_id: str,
    config: dict,
    *,
    instance_type: str = "auto",
    origin: str = "execute",
    directory: Path | None = None,
) -> Path:
    """Persist one *confirmed* RH task ID, using a safe local filename."""
    if not isinstance(config, dict):
        raise ValueError("Task journal requires an RH Config mapping.")
    task = str(task_id or "").strip()
    if not task or len(task) > 256 or any(ord(char) < 32 for char in task):
        raise ValueError("Task journal requires a valid returned task ID.")
    workflow_id = str(config.get("workflow_or_app_id") or "").strip()
    if len(workflow_id) > 256:
        raise ValueError("Workflow ID is too long for task journal.")
    parsed = urlsplit(str(config.get("base_url") or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Task journal requires an HTTP(S) RH endpoint.")
    # Strip URL credentials, path and query tokens before persisting.
    endpoint = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        endpoint += f":{parsed.port}"
    if not isinstance(instance_type, str) or instance_type not in {"auto", "default", "plus", "ultra"}:
        raise ValueError("Task journal requires a recognized instance type.")
    if origin not in {"execute", "batch"}:
        raise ValueError("Task journal has an unknown operation.")

    data = {
        "taskId": task,
        "workflowOrAppId": workflow_id,
        "isAiApp": bool(config.get("is_ai_app", False)),
        "baseUrl": endpoint,
        "instanceType": instance_type,
        "operation": origin,
        "submittedAtUTC": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "submitted",
    }
    root = Path(directory) if directory is not None else JOURNAL_DIR
    root.mkdir(parents=True, exist_ok=True)
    identity = hashlib.sha256((endpoint + "\n" + task).encode("utf-8")).hexdigest()
    final = root / (identity[:32] + ".json")
    part = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=root,
            prefix=".pending-", suffix=".part", delete=False
        ) as file:
            part = Path(file.name)
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(part, final)
    finally:
        if part is not None:
            part.unlink(missing_ok=True)
    return final
