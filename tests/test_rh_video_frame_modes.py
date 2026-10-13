"""RH video frame modes: preserve lazy VIDEO while bounding optional IMAGE frames.

Only local fakes are used; no RH API, GPU, codec install or paid task.
"""
import importlib
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from test_rh_utils_baseline import load_rh_utils


class FrameModesTests(unittest.TestCase):
    def setUp(self):
        self.utils = load_rh_utils()
        self.media = importlib.import_module(self.utils.__package__ + ".rh_media")
        self.outputs = importlib.import_module(self.utils.__package__ + ".rh_outputs")
        self.policy = importlib.import_module(self.utils.__package__ + ".rh_video_frame_policy")

    def test_mode_validator_accepts_only_known_explicit_values(self):
        for value in ("all_frames", "preview_only", "disabled"):
            self.assertEqual(self.policy.validate_video_frame_mode(value), value)
        for value in ("", "first", None, 1, False, "all_frames "):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.policy.validate_video_frame_mode(value)

    def test_all_frames_preview_and_disabled_have_bounded_decode_calls(self):
        sentinel_video = object()
        downloaded = SimpleNamespace(index=0, local_path="local-video.mp4", media_type="video")
        source = [{"fileUrl": "https://example.invalid/video.mp4", "fileType": "mp4"}]
        with patch.object(self.outputs, "download_output_item", return_value=downloaded) as fetch, \
             patch.object(self.media, "load_video", return_value=sentinel_video) as lazy, \
             patch.object(self.media, "extract_video_frames", return_value=["frame"]) as extract, \
             patch.object(self.utils, "_create_placeholder_image", return_value="placeholder"), \
             patch.object(self.utils, "_create_placeholder_latent", return_value={"samples": "empty"}):
            preview = self.utils._process_outputs(source, False, "RH", task_id="sample", video_frame_mode="preview_only")
            self.assertEqual(preview[1], ["frame"])
            self.assertIs(preview[4], sentinel_video)
            self.assertEqual(extract.call_args.kwargs, {"max_frames": 1})
            extract.reset_mock()
            disabled = self.utils._process_outputs(source, False, "RH", task_id="sample", video_frame_mode="disabled")
            self.assertEqual(disabled[1], ["placeholder"])
            self.assertIs(disabled[4], sentinel_video)
            extract.assert_not_called()
            extract.reset_mock()
            full = self.utils._process_outputs(source, False, "RH", task_id="sample")
            self.assertEqual(full[1], ["frame"])
            self.assertIs(full[4], sentinel_video)
            self.assertEqual(extract.call_args.args, ("local-video.mp4",))
            self.assertEqual(extract.call_args.kwargs, {})
            self.assertEqual(fetch.call_count, 3)
            self.assertEqual(lazy.call_count, 3)

    def test_rejects_bad_mode_before_any_download(self):
        source = [{"fileUrl": "https://example.invalid/video.mp4", "fileType": "mp4"}]
        with patch.object(self.outputs, "download_output_item") as fetch:
            with self.assertRaisesRegex(ValueError, "video_frame_mode"):
                self.utils._process_outputs(source, False, "RH", video_frame_mode="unknown")
            fetch.assert_not_called()

    def test_preview_decoder_stops_reading_after_one_frame(self):
        caps = []

        class FakeFrame:
            def astype(self, _type):
                return self
            def __truediv__(self, _num):
                return self

        class FakeCapture:
            def __init__(self):
                self.read_calls = 0
                self.released = False
                caps.append(self)
            def read(self):
                self.read_calls += 1
                return (True, FakeFrame()) if self.read_calls <= 5 else (False, None)
            def release(self):
                self.released = True

        codec = SimpleNamespace(
            VideoCapture=lambda _path: FakeCapture(),
            cvtColor=lambda frame, _code: frame,
            COLOR_BGR2RGB=1,
        )
        tensor = SimpleNamespace(unsqueeze=lambda _axis: "frame")
        fake_torch = SimpleNamespace(from_numpy=lambda _value: tensor)
        with patch.object(self.media, "cv2", codec), \
             patch.object(self.media, "np", SimpleNamespace(float32=object())), \
             patch.object(self.media, "torch", fake_torch):
            short = self.media.extract_video_frames("sample.mp4", max_frames=1)
            entire = self.media.extract_video_frames("sample.mp4")
            with self.assertRaisesRegex(ValueError, "max_frames"):
                self.media.extract_video_frames("sample.mp4", max_frames=0)
        self.assertEqual(short, ["frame"])
        self.assertEqual(entire, ["frame"] * 5)
        self.assertEqual([cap.read_calls for cap in caps], [1, 6])
        self.assertTrue(all(cap.released for cap in caps))


if __name__ == "__main__":
    unittest.main()
