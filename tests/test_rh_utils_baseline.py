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
    module_path = ROOT / "nodes" / "rh_utils.py"
    spec = importlib.util.spec_from_file_location("rh_utils_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
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

    def test_download_text_decodes_utf8_bom(self):
        content = b"\xef\xbb\xbf" + "中文文本".encode("utf-8")
        response = FakeResponse(content=content)
        with mock.patch.object(self.rh_utils.requests, "get", return_value=response):
            result = self.rh_utils._download_text("https://example.invalid/result.txt")
        self.assertEqual(result, "中文文本")


if __name__ == "__main__":
    unittest.main()
