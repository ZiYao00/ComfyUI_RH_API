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

    def test_default_query_mode_remains_legacy(self):
        session = RecordingSession({"code": 0, "msg": "success", "data": []})
        client = self.module.RHClient("key", "https://rh.example", session=session)
        result = client.query_task("task-1")
        self.assertEqual(result.api_mode, "legacy")
        self.assertEqual(result.status, "NO_OUTPUT")


if __name__ == "__main__":
    unittest.main()
