import importlib.util
import io
import pathlib
import sys
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def make_requests_stub():
    requests = types.ModuleType("requests")

    class RequestException(Exception):
        pass

    class Timeout(RequestException):
        pass

    requests.exceptions = types.SimpleNamespace(
        RequestException=RequestException,
        Timeout=Timeout,
    )
    requests.post = None
    return requests


def load_rh_client():
    sys.modules["requests"] = make_requests_stub()
    path = ROOT / "nodes" / "rh_client.py"
    spec = importlib.util.spec_from_file_location("rh_client_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class RecordingSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []
        requests = make_requests_stub()
        self.exceptions = requests.exceptions

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload)


class RHClientTests(unittest.TestCase):
    def setUp(self):
        self.module = load_rh_client()

    def test_legacy_success_is_normalized(self):
        session = RecordingSession({
            "code": 0,
            "msg": "success",
            "data": [{"fileUrl": "https://example.invalid/a.png", "fileType": "png"}],
        })
        client = self.module.RHClient("key", "https://rh.example", session=session)
        result = client.query_task("task-1", mode="legacy")

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(len(result.outputs), 1)
        self.assertEqual(result.api_mode, "legacy")
        self.assertTrue(session.calls[0][0].endswith("/task/openapi/outputs"))

    def test_v2_success_is_normalized_and_uses_bearer_auth(self):
        session = RecordingSession({
            "taskId": "task-1",
            "status": "SUCCESS",
            "errorCode": "",
            "errorMessage": "",
            "results": [{"url": "https://example.invalid/a.jpg", "outputType": "jpg"}],
        })
        client = self.module.RHClient("secret-key", "https://rh.example", session=session)
        result = client.query_task("task-1", mode="v2")

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.outputs[0]["outputType"], "jpg")
        url, kwargs = session.calls[0]
        self.assertTrue(url.endswith("/openapi/v2/query"))
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret-key")
        self.assertEqual(kwargs["json"], {"taskId": "task-1"})

    def test_v2_running_and_failure_are_normalized(self):
        running_session = RecordingSession({"taskId": "task-1", "status": "RUNNING", "results": None})
        running = self.module.RHClient("key", "https://rh.example", session=running_session).query_task(
            "task-1", mode="v2"
        )
        self.assertEqual(running.status, "RUNNING")

        failed_session = RecordingSession({
            "taskId": "task-1",
            "status": "FAILED",
            "errorCode": "E1",
            "errorMessage": "bad task",
            "results": None,
        })
        failed = self.module.RHClient("key", "https://rh.example", session=failed_session).query_task(
            "task-1", mode="v2"
        )
        self.assertEqual(failed.status, "ERROR")
        self.assertEqual(failed.error, "E1: bad task")

    def test_v2_upload_returns_comfy_filename(self):
        session = RecordingSession({
            "code": 0,
            "message": "success",
            "data": {
                "type": "audio",
                "download_url": "https://example.invalid/a.mp3",
                "fileName": "openapi/a.mp3",
                "size": "3",
            },
        })
        client = self.module.RHClient("key", "https://rh.example", session=session)
        filename = client.upload_file_v2(io.BytesIO(b"abc"), "a.mp3", "audio/mpeg")

        self.assertEqual(filename, "openapi/a.mp3")
        url, kwargs = session.calls[0]
        self.assertTrue(url.endswith("/openapi/v2/media/upload/binary"))
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer key")
        self.assertIn("file", kwargs["files"])

    def test_create_task_preserves_legacy_json_body(self):
        session = RecordingSession({"code": 0, "data": {"taskId": "task-123"}})
        client = self.module.RHClient("key", "https://rh.example", session=session)

        task_id = client.create_task(
            workflow_or_app_id="workflow-1",
            params=[{"nodeId": "1", "fieldName": "text", "fieldValue": "hello"}],
            use_high_performance=True,
        )

        self.assertEqual(task_id, "task-123")
        url, kwargs = session.calls[0]
        self.assertTrue(url.endswith("/task/openapi/create"))
        self.assertIn('"workflowId": "workflow-1"', kwargs["data"])
        self.assertIn('"instanceType": "plus"', kwargs["data"])
        self.assertEqual(kwargs["headers"]["Content-Type"], "application/json")

    def test_workflow_schema_fetch_is_read_only_and_never_creates_a_task(self):
        session = RecordingSession({"code": 0, "data": {"prompt": '{"28":{"class_type":"CR Prompt Text","inputs":{"prompt":"private"}}}'}})
        client = self.module.RHClient("secret", "https://www.runninghub.ai", session=session)
        response = client.get_workflow_api_json("2109574959826993154")
        self.assertEqual(response["code"], 0)
        self.assertEqual(len(session.calls), 1)
        url, kwargs = session.calls[0]
        self.assertEqual(url, "https://www.runninghub.ai/api/openapi/getJsonApiFormat")
        self.assertEqual(kwargs["json"], {"apiKey": "secret", "workflowId": "2109574959826993154"})
        self.assertFalse(kwargs["allow_redirects"])
        self.assertNotIn("instanceType", kwargs["json"])
        self.assertNotIn("nodeInfoList", kwargs["json"])

    def test_schema_fetch_rejects_untrusted_api_key_destination(self):
        session = RecordingSession({"code": 0, "data": {"prompt": "{}"}})
        for address in ("http://www.runninghub.ai", "https://www.runninghub.ai.evil.example",
                        "https://evil.example", "https://www.runninghub.cn@evil.example"):
            with self.subTest(address=address):
                with self.assertRaises(ValueError):
                    self.module.RHClient("secret", address, session=session).get_workflow_api_json("11")
        self.assertEqual(session.calls, [])

    def test_schema_fetch_reports_upstream_error_without_leaking_response(self):
        session = RecordingSession({"code": 403, "msg": "secret data", "data": None})
        with self.assertRaisesRegex(RuntimeError, "could not return") as context:
            self.module.RHClient("secret", "https://www.runninghub.cn", session=session).get_workflow_api_json("11")
        self.assertNotIn("secret data", str(context.exception))

    def test_instance_types_are_explicit_and_auto_omits_field(self):
        import json
        for selection, expected in [
            ("auto", None), ("default", "default"), ("plus", "plus"), ("ultra", "ultra")
        ]:
            with self.subTest(selection=selection):
                session = RecordingSession({"code": 0, "data": {"taskId": "sample-task"}})
                client = self.module.RHClient("example", "https://www.runninghub.ai", session=session)
                result = client.create_task("sample-workflow", instance_type=selection)
                self.assertEqual(result, "sample-task")
                self.assertEqual(len(session.calls), 1)
                payload = json.loads(session.calls[0][1]["data"])
                self.assertEqual(payload.get("instanceType"), expected)

    def test_invalid_instance_selection_and_conflicting_legacy_flag_prevent_posts(self):
        session = RecordingSession({"code": 0, "data": {"taskId": "sample-task"}})
        client = self.module.RHClient("example", "https://www.runninghub.ai", session=session)
        for choice in ("unexpected", "", True, 42):
            with self.subTest(choice=choice), self.assertRaises(ValueError):
                client.create_task("sample-workflow", instance_type=choice)
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            client.create_task("sample-workflow", use_high_performance=True, instance_type="ultra")
        self.assertEqual(session.calls, [])

    def test_legacy_instances_and_positional_timeout_remain_compatible(self):
        import json
        for enabled, expected in ((False, None), (True, "plus")):
            session = RecordingSession({"code": 0, "data": {"taskId": "sample-task"}})
            client = self.module.RHClient("example", "https://www.runninghub.ai", session=session)
            client.create_task("sample-workflow", [], False, enabled, 21)
            url, kwargs = session.calls[0]
            self.assertEqual(kwargs["timeout"], 21)
            self.assertEqual(json.loads(kwargs["data"]).get("instanceType"), expected)

    def test_ai_app_explicit_instance_not_assumed_supported(self):
        session = RecordingSession({"code": 0, "data": {"taskId": "sample-task"}})
        client = self.module.RHClient("example", "https://www.runninghub.ai", session=session)
        with self.assertRaisesRegex(ValueError, "AI Apps"):
            client.create_task("12345", is_ai_app=True, instance_type="ultra")
        self.assertEqual(session.calls, [])

    def test_confirmed_creation_calls_journal_hook_once(self):
        session = RecordingSession({"code": 0, "data": {"taskId": "recorded-id"}})
        client = self.module.RHClient("example", "https://www.runninghub.ai", session=session)
        written = []
        result = client.create_task(
            "workflow-1", instance_type="plus", on_task_created=written.append
        )
        self.assertEqual(result, "recorded-id")
        self.assertEqual(written, ["recorded-id"])
        self.assertEqual(len(session.calls), 1)

    def test_failed_journal_hook_does_not_retry_or_lose_confirmed_id(self):
        session = RecordingSession({"code": 0, "data": {"taskId": "confirmed-id"}})
        client = self.module.RHClient("example", "https://www.runninghub.ai", session=session)
        def unavailable(_task):
            raise OSError("cannot write record")
        self.assertEqual(client.create_task("workflow-1", on_task_created=unavailable), "confirmed-id")
        self.assertEqual(len(session.calls), 1)

    def test_cancel_task_is_centralized_in_client(self):
        session = RecordingSession({"code": 0, "msg": "success", "data": None})
        client = self.module.RHClient("key", "https://rh.example", session=session)

        self.assertTrue(client.cancel_task("task-1"))
        url, kwargs = session.calls[0]
        self.assertTrue(url.endswith("/task/openapi/cancel"))
        self.assertEqual(kwargs["json"], {"taskId": "task-1", "apiKey": "key"})

    def test_default_query_mode_remains_legacy(self):
        session = RecordingSession({"code": 0, "msg": "success", "data": []})
        client = self.module.RHClient("key", "https://rh.example", session=session)
        result = client.query_task("task-1")
        self.assertEqual(result.api_mode, "legacy")
        self.assertEqual(result.status, "NO_OUTPUT")


if __name__ == "__main__":
    unittest.main()
