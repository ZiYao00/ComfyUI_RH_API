import importlib.util
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_rh_media():
    path = ROOT / "nodes" / "rh_media.py"
    spec = importlib.util.spec_from_file_location("rh_media_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeWaveform:
    def __init__(self):
        self.unsqueeze_calls = []

    def unsqueeze(self, dimension):
        self.unsqueeze_calls.append(dimension)
        return ("batched", dimension)


class RHMediaTests(unittest.TestCase):
    def setUp(self):
        self.module = load_rh_media()

    def test_audio_adapter_returns_standard_comfy_mapping(self):
        waveform = FakeWaveform()
        self.module.comfy_load_audio = lambda path: (waveform, 48000)
        self.module.torchaudio = None

        result = self.module.load_audio("sample.mp3")

        self.assertEqual(result["sample_rate"], 48000)
        self.assertEqual(result["waveform"], ("batched", 0))
        self.assertEqual(waveform.unsqueeze_calls, [0])

    def test_video_adapter_uses_lazy_video_from_file(self):
        class FakeInputImpl:
            @staticmethod
            def VideoFromFile(path):
                return ("video-from-file", path)

        self.module.InputImpl = FakeInputImpl
        result = self.module.load_video("sample.mp4")
        self.assertEqual(result, ("video-from-file", "sample.mp4"))

    def test_text_adapter_decodes_utf8_bom(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = pathlib.Path(temp_dir) / "result.txt"
            path.write_bytes(b"\xef\xbb\xbf" + "中文".encode("utf-8"))
            self.assertEqual(self.module.load_text(str(path)), "中文")


if __name__ == "__main__":
    unittest.main()
