import importlib.util
import io
import pathlib
import sys
import types
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _install_minimal_import_stubs():
    """Install only the modules needed to import rh_utils in a plain Python runtime."""
    torch = types.ModuleType("torch")
    torch.float32 = object()
    torch.zeros = lambda *args, **kwargs: None
    torch.cat = lambda items, dim=0: items
    sys.modules["torch"] = torch

    numpy = types.ModuleType("numpy")
    numpy.float32 = float
    numpy.uint8 = int
    numpy.array = lambda value: value
    sys.modules["numpy"] = numpy

    pil = types.ModuleType("PIL")
    image = types.ModuleType("PIL.Image")
    image_draw = types.ModuleType("PIL.ImageDraw")
    image_font = types.ModuleType("PIL.ImageFont")
    pil.Image = image
    pil.ImageDraw = image_draw
    pil.ImageFont = image_font
    sys.modules["PIL"] = pil
    sys.modules["PIL.Image"] = image
    sys.modules["PIL.ImageDraw"] = image_draw
    sys.modules["PIL.ImageFont"] = image_font

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
    requests.get = None
    sys.modules["requests"] = requests


def load_rh_utils():
    _install_minimal_import_stubs()
    package_name = "rh_utils_test_pkg"
    sys.modules.pop(f"{package_name}.rh_client", None)
    sys.modules.pop(f"{package_name}.rh_utils", None)
    package = types.ModuleType(package_name)
    package.__path__ = [str(ROOT / "nodes")]
    sys.modules[package_name] = package

    module_path = ROOT / "nodes" / "rh_utils.py"
    module_name = f"{package_name}.rh_utils"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload=None, content=b""):
        self._payload = payload
        self.content = content
        self.encoding = None
        self.apparent_encoding = "utf-8"

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload

    @property
    def text(self):
        encoding = self.encoding or "utf-8"
        return self.content.decode(encoding)


class RHUtilsBaselineTests(unittest.TestCase):
    def setUp(self):
        self.rh_utils = load_rh_utils()

    def test_check_task_status_maps_queued(self):
        response = FakeResponse({"code": 0, "msg": "APIKEY_TASK_IS_QUEUED", "data": None})
        with mock.patch.object(self.rh_utils.requests, "post", return_value=response):
            result = self.rh_utils._check_task_status("task-1", "key", "https://example.invalid")
        self.assertEqual(result, {"taskStatus": "QUEUED"})

    def test_check_task_status_returns_output_list(self):
        outputs = [{"fileUrl": "https://example.invalid/a.png", "fileType": "png"}]
        response = FakeResponse({"code": 0, "msg": "", "data": outputs})
        with mock.patch.object(self.rh_utils.requests, "post", return_value=response):
            result = self.rh_utils._check_task_status("task-1", "key", "https://example.invalid")
        self.assertEqual(result, outputs)

    def test_check_task_status_supports_v2_query_mode(self):
        outputs = [{"url": "https://example.invalid/a.jpg", "outputType": "jpg"}]
        response = FakeResponse({
            "taskId": "task-1",
            "status": "SUCCESS",
            "errorCode": "",
            "errorMessage": "",
            "results": outputs,
        })
        with mock.patch.object(self.rh_utils.requests, "post", return_value=response) as post:
            result = self.rh_utils._check_task_status(
                "task-1",
                "key",
                "https://example.invalid",
                query_api="v2",
            )
        self.assertEqual(result, outputs)
        self.assertTrue(post.call_args.args[0].endswith("/openapi/v2/query"))
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer key")

    def test_upload_file_rewinds_seekable_stream_before_post(self):
        buffer = io.BytesIO(b"abc")
        buffer.seek(3)

        def fake_post(url, data, files, timeout):
            uploaded = files["file"][1]
            self.assertEqual(uploaded.tell(), 0)
            return FakeResponse({"code": 0, "data": {"fileName": "server-name.bin"}})

        with mock.patch.object(self.rh_utils.requests, "post", side_effect=fake_post):
            result = self.rh_utils.upload_file_to_rh(
                api_key="key",
                base_url="https://example.invalid",
                file_buffer=buffer,
                file_name="sample.bin",
                content_type="application/octet-stream",
                file_type="file",
            )
        self.assertEqual(result, "server-name.bin")

    def test_upload_file_accepts_raw_bytes(self):
        def fake_post(url, data, files, timeout):
            uploaded = files["file"][1]
            self.assertTrue(hasattr(uploaded, "read"))
            self.assertEqual(uploaded.read(), b"abc")
            return FakeResponse({"code": 0, "data": {"fileName": "server-name.bin"}})

        with mock.patch.object(self.rh_utils.requests, "post", side_effect=fake_post), \
             mock.patch.object(self.rh_utils.time, "sleep", return_value=None):
            result = self.rh_utils.upload_file_to_rh(
                api_key="key",
                base_url="https://example.invalid",
                file_buffer=b"abc",
                file_name="sample.bin",
                content_type="application/octet-stream",
                file_type="file",
            )
        self.assertEqual(result, "server-name.bin")

    def test_check_task_status_reports_network_error_explicitly(self):
        error = self.rh_utils.requests.exceptions.RequestException("offline")
        with mock.patch.object(self.rh_utils.requests, "post", side_effect=error):
            result = self.rh_utils._check_task_status("task-1", "key", "https://example.invalid")
        self.assertEqual(result["taskStatus"], "NETWORK_ERROR")
        self.assertIn("offline", result["error"])

    def test_monitor_stops_immediately_for_completed_no_output(self):
        statuses = [
            {"taskStatus": "completed_no_output"},
            [{"fileUrl": "https://example.invalid/late.png", "fileType": "png"}],
        ]
        ticks = iter(range(100, 1000, 10))
        with mock.patch.object(self.rh_utils, "_check_task_status", side_effect=statuses) as check_status, \
             mock.patch.object(self.rh_utils.time, "time", side_effect=lambda: next(ticks)), \
             mock.patch.object(self.rh_utils.time, "sleep", return_value=None):
            self.rh_utils._monitor_task(
                "task-1",
                {"api_key": "key", "base_url": "https://example.invalid"},
                timeout=60,
            )
        self.assertEqual(check_status.call_count, 1)

    def test_download_text_decodes_utf8_bom(self):
        content = b"\xef\xbb\xbf" + "中文文本".encode("utf-8")
        response = FakeResponse(content=content)
        with mock.patch.object(self.rh_utils.requests, "get", return_value=response):
            result = self.rh_utils._download_text("https://example.invalid/result.txt")
        self.assertEqual(result, "中文文本")

    def test_download_latent_uses_load_file_and_cleans_temp_file(self):
        response = FakeResponse(content=b"fake-safetensors")
        self.rh_utils.SAFETENSORS_AVAILABLE = True
        self.rh_utils.load_file = mock.Mock(return_value={"samples": "ok"})

        with mock.patch.object(self.rh_utils.requests, "get", return_value=response):
            result = self.rh_utils._download_latent("https://example.invalid/result.safetensors")

        self.assertEqual(result, {"samples": "ok"})
        temp_path = self.rh_utils.load_file.call_args.args[0]
        self.assertFalse(pathlib.Path(temp_path).exists())


if __name__ == "__main__":
    unittest.main()
