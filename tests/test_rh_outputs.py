import importlib.util
import pathlib
import tempfile
import types
import unittest
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_rh_outputs():
    path = ROOT / "nodes" / "rh_outputs.py"
    spec = importlib.util.spec_from_file_location("rh_outputs_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeDownloadResponse:
    def __init__(self, chunks, content_type=""):
        self._chunks = chunks
        self.headers = {"Content-Type": content_type} if content_type else {}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        yield from self._chunks


class RHOutputTests(unittest.TestCase):
    def setUp(self):
        self.module = load_rh_outputs()

    def test_normalize_preserves_remote_order(self):
        raw = [
            {"fileUrl": "https://example.invalid/a.mp3", "fileType": "mp3"},
            {"fileUrl": "https://example.invalid/b.txt", "fileType": "txt"},
            {"fileUrl": "https://example.invalid/c.mp4", "fileType": "mp4"},
        ]
        items = self.module.normalize_outputs(raw)
        self.assertEqual([item.index for item in items], [0, 1, 2])
        self.assertEqual([item.media_type for item in items], ["audio", "text", "video"])

    def test_normalize_accepts_v2_style_keys(self):
        items = self.module.normalize_outputs([
            {"url": "https://example.invalid/result.m4a", "outputType": "audio"}
        ])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].media_type, "audio")
        self.assertEqual(items[0].extension, ".m4a")

    def test_infer_media_type_uses_mime_or_url_fallbacks(self):
        self.assertEqual(
            self.module.infer_media_type("", "https://example.invalid/result.aac"),
            "audio",
        )
        self.assertEqual(
            self.module.infer_media_type("audio/mpeg", "https://example.invalid/no-extension"),
            "audio",
        )

    def test_download_is_atomic_and_updates_type_from_content_type(self):
        item = self.module.RHOutputItem(index=0, url="https://example.invalid/download")
        response = FakeDownloadResponse([b"abc", b"def"], content_type="audio/mpeg")
        session = types.SimpleNamespace(get=lambda *args, **kwargs: response)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.module.download_output_item(
                item,
                temp_dir,
                output_prefix="RH",
                task_id="task-123",
                session=session,
            )
            path = pathlib.Path(result.local_path)
            self.assertTrue(path.exists())
            self.assertEqual(path.read_bytes(), b"abcdef")
            self.assertEqual(path.suffix, ".mp3")
            self.assertEqual(result.media_type, "audio")
            self.assertFalse(path.with_name(path.name + ".part").exists())


if __name__ == "__main__":
    unittest.main()
