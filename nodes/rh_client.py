"""RunningHub HTTP compatibility layer.

Legacy task creation remains the production path for existing ComfyUI workflows.
Query/upload adapters isolate the older /task/openapi APIs from the newer V2 APIs
so future RunningHub changes do not leak into node implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import io
import json
from typing import Any, Optional

import requests


class RHTaskSubmissionUncertainError(RuntimeError):
    """The create-task request may have reached RH, so automatic retry is unsafe."""


@dataclass
class RHQueryResult:
    status: str
    outputs: list[dict] = field(default_factory=list)
    error: str = ""
    raw: Any = None
    api_mode: str = "legacy"


class RHClient:
    SUPPORTED_QUERY_MODES = {"legacy", "v2"}

    def __init__(self, api_key: str, base_url: str, session=requests):
        self.api_key = api_key
        self.base_url = (base_url or "https://www.runninghub.cn").rstrip("/")
        self.session = session

    def query_task(self, task_id: str, mode: str = "legacy") -> RHQueryResult:
        mode = (mode or "legacy").strip().lower()
        if mode not in self.SUPPORTED_QUERY_MODES:
            raise ValueError(f"Unsupported RunningHub query mode: {mode}")
        if mode == "v2":
            return self.query_task_v2(task_id)
        return self.query_task_legacy(task_id)

    def create_task(
        self,
        workflow_or_app_id: str,
        params: Optional[list[dict]] = None,
        is_ai_app: bool = False,
        use_high_performance: bool = False,
        timeout: int = 30,
    ) -> str:
        """Create one RH task with a single safe POST attempt."""
        params = params or []
        if is_ai_app:
            url = f"{self.base_url}/task/openapi/ai-app/run"
            payload = {
                "webappId": int(workflow_or_app_id),
                "apiKey": self.api_key,
                "nodeInfoList": params,
            }
        else:
            url = f"{self.base_url}/task/openapi/create"
            payload = {
                "workflowId": workflow_or_app_id,
                "apiKey": self.api_key,
                "nodeInfoList": params,
            }

        if use_high_performance:
            payload["instanceType"] = "plus"

        try:
            response = self.session.post(
                url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=timeout,
            )
            response.raise_for_status()
        except self.session.exceptions.RequestException as exc:
            raise RHTaskSubmissionUncertainError(
                "RunningHub task submission status is uncertain because the HTTP request failed after submission may have started. "
                "Do not auto-retry. Check the RunningHub task list before retrying manually. "
                f"Transport error: {exc}"
            ) from exc

        try:
            result = response.json()
        except Exception as exc:
            raise RHTaskSubmissionUncertainError(
                "RunningHub returned an unreadable create-task response. The task may already exist. "
                "Check the RunningHub task list before retrying manually."
            ) from exc

        if result.get("code") == 0:
            task_id = (result.get("data") or {}).get("taskId")
            if task_id:
                return task_id
            raise RHTaskSubmissionUncertainError(
                "RunningHub reported create-task success but returned no taskId. "
                "The task may already exist; check the RunningHub task list before retrying."
            )

        error_msg = str(result.get("msg", "Unknown error"))
        if "WORKFLOW_NOT_SAVED_OR_NOT_RUNNING" in error_msg:
            raise RuntimeError(
                f"Workflow error: {error_msg}\n"
                f"Please check:\n"
                f"1. Workflow ID '{workflow_or_app_id}' exists on RunningHub\n"
                f"2. Workflow is saved\n"
                f"3. Workflow status is set to 'Running' (not Draft)\n"
                f"4. You have access to this workflow"
            )
        if "INVALID_API_KEY" in error_msg:
            raise RuntimeError("Invalid API key. Please check your RH_Config node.")
        if "INSUFFICIENT_BALANCE" in error_msg:
            raise RuntimeError("Insufficient balance. Please top up your RunningHub account.")
        raise RuntimeError(f"RunningHub task creation failed: {error_msg}")

    def cancel_task(self, task_id: str, timeout: int = 20) -> bool:
        """Request cancellation of a task through the legacy control endpoint."""
        response = self.session.post(
            f"{self.base_url}/task/openapi/cancel",
            json={"taskId": task_id, "apiKey": self.api_key},
            timeout=timeout,
        )
        response.raise_for_status()
        result = response.json()
        if result.get("code") == 0:
            return True
        raise RuntimeError(
            f"RunningHub task cancellation failed: {result.get('msg', 'Unknown error')}"
        )

    def query_task_legacy(self, task_id: str) -> RHQueryResult:
        url = f"{self.base_url}/task/openapi/outputs"
        payload = {"taskId": task_id, "apiKey": self.api_key}

        try:
            response = self.session.post(url, json=payload, timeout=20)
            response.raise_for_status()
            result = response.json()
        except self.session.exceptions.Timeout as exc:
            return RHQueryResult(
                status="NETWORK_ERROR",
                error=f"Request timed out: {exc}",
                api_mode="legacy",
            )
        except self.session.exceptions.RequestException as exc:
            return RHQueryResult(
                status="NETWORK_ERROR",
                error=str(exc),
                api_mode="legacy",
            )
        except (TypeError, ValueError) as exc:
            return RHQueryResult(
                status="API_ERROR",
                error=f"Invalid legacy query response: {exc}",
                api_mode="legacy",
            )

        code = result.get("code") if isinstance(result, dict) else None
        msg = str(result.get("msg", "")) if isinstance(result, dict) else ""
        data = result.get("data") if isinstance(result, dict) else None

        if msg == "APIKEY_TASK_IS_QUEUED":
            return RHQueryResult(status="QUEUED", raw=result, api_mode="legacy")
        if msg == "APIKEY_TASK_IS_RUNNING":
            return RHQueryResult(status="RUNNING", raw=result, api_mode="legacy")
        if code == 0 and isinstance(data, list):
            if data:
                return RHQueryResult(status="SUCCESS", outputs=data, raw=result, api_mode="legacy")
            return RHQueryResult(status="NO_OUTPUT", raw=result, api_mode="legacy")
        if code == 0 and data is None:
            return RHQueryResult(status="RUNNING", raw=result, api_mode="legacy")
        if code != 0:
            error = msg or "RunningHub legacy query failed"
            if isinstance(data, dict) and data:
                error = f"{error}: {data.get('error', data)}"
            return RHQueryResult(status="ERROR", error=error, raw=result, api_mode="legacy")

        return RHQueryResult(
            status="API_ERROR",
            error=f"Unexpected legacy query response: {result!r}",
            raw=result,
            api_mode="legacy",
        )

    def query_task_v2(self, task_id: str) -> RHQueryResult:
        url = f"{self.base_url}/openapi/v2/query"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"taskId": task_id}

        try:
            response = self.session.post(url, json=payload, headers=headers, timeout=20)
            response.raise_for_status()
            result = response.json()
        except self.session.exceptions.Timeout as exc:
            return RHQueryResult(
                status="NETWORK_ERROR",
                error=f"Request timed out: {exc}",
                api_mode="v2",
            )
        except self.session.exceptions.RequestException as exc:
            return RHQueryResult(status="NETWORK_ERROR", error=str(exc), api_mode="v2")
        except (TypeError, ValueError) as exc:
            return RHQueryResult(
                status="API_ERROR",
                error=f"Invalid V2 query response: {exc}",
                api_mode="v2",
            )

        if not isinstance(result, dict):
            return RHQueryResult(
                status="API_ERROR",
                error=f"Unexpected V2 query response: {result!r}",
                raw=result,
                api_mode="v2",
            )

        status = str(result.get("status", "")).strip().upper()
        outputs = result.get("results") or []
        error_code = str(result.get("errorCode", "") or "").strip()
        error_message = str(result.get("errorMessage", "") or "").strip()

        if status == "SUCCESS":
            if isinstance(outputs, list) and outputs:
                return RHQueryResult(status="SUCCESS", outputs=outputs, raw=result, api_mode="v2")
            return RHQueryResult(status="NO_OUTPUT", raw=result, api_mode="v2")
        if status in {"RUNNING", "PROCESSING"}:
            return RHQueryResult(status="RUNNING", raw=result, api_mode="v2")
        if status in {"QUEUED", "PENDING", "WAITING"}:
            return RHQueryResult(status="QUEUED", raw=result, api_mode="v2")
        if status in {"FAILED", "FAILURE", "ERROR", "CANCELLED", "CANCELED"}:
            error = error_message or error_code or f"RunningHub task ended with status {status}"
            if error_code and error_message:
                error = f"{error_code}: {error_message}"
            return RHQueryResult(status="ERROR", error=error, raw=result, api_mode="v2")

        if error_code or error_message:
            error = error_message or error_code
            if error_code and error_message:
                error = f"{error_code}: {error_message}"
            return RHQueryResult(status="ERROR", error=error, raw=result, api_mode="v2")

        return RHQueryResult(
            status="API_ERROR",
            error=f"Unknown V2 task status: {status or '<empty>'}",
            raw=result,
            api_mode="v2",
        )

    def upload_file_legacy(
        self,
        file_buffer,
        file_name: str,
        content_type: str,
        file_type: str,
        timeout: int = 60,
    ) -> str:
        stream = self._ensure_seekable_stream(file_buffer)
        stream.seek(0)
        response = self.session.post(
            f"{self.base_url}/task/openapi/upload",
            data={"apiKey": self.api_key, "fileType": file_type},
            files={"file": (file_name, stream, content_type)},
            timeout=timeout,
        )
        response.raise_for_status()
        result = response.json()
        if result.get("code") == 0:
            filename = (result.get("data") or {}).get("fileName")
            if filename:
                return filename
        raise RuntimeError(f"RunningHub legacy upload failed: {result.get('msg', result)!r}")

    def upload_file_v2(
        self,
        file_buffer,
        file_name: str,
        content_type: str,
        timeout: int = 60,
    ) -> str:
        stream = self._ensure_seekable_stream(file_buffer)
        stream.seek(0)
        response = self.session.post(
            f"{self.base_url}/openapi/v2/media/upload/binary",
            headers={"Authorization": f"Bearer {self.api_key}"},
            files={"file": (file_name, stream, content_type)},
            timeout=timeout,
        )
        response.raise_for_status()
        result = response.json()
        data = result.get("data") or {}
        code = result.get("code")
        if code in {0, 200}:
            filename = data.get("fileName") or data.get("filename")
            if filename:
                return filename
        raise RuntimeError(f"RunningHub V2 upload failed: {result.get('message', result)!r}")

    @staticmethod
    def _ensure_seekable_stream(file_buffer):
        if isinstance(file_buffer, (bytes, bytearray)):
            return io.BytesIO(file_buffer)
        if hasattr(file_buffer, "read") and hasattr(file_buffer, "seek"):
            return file_buffer
        if hasattr(file_buffer, "read"):
            return io.BytesIO(file_buffer.read())
        raise TypeError("file_buffer must be bytes or a readable file-like object")
