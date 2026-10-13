"""Pre-upload validation and fail-closed semantics for RH image upload families.

All tensors, media codecs and upload HTTP calls are mocked. No RH requests.
"""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from test_rh_utils_baseline import _install_minimal_import_stubs

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "rh_c3_safe_upload_test_pkg"


def load_upload(name):
    _install_minimal_import_stubs()
    package = types.ModuleType(PREFIX)
    package.__path__ = [str(ROOT / "nodes")]
    sys.modules[PREFIX] = package
    utils = types.ModuleType(PREFIX + ".rh_utils")
    utils.upload_file_to_rh = lambda **kwargs: "mock-file.png"
    sys.modules[PREFIX + ".rh_utils"] = utils
    target = PREFIX + "." + name
    sys.modules.pop(target, None)
    spec = importlib.util.spec_from_file_location(target, ROOT / "nodes" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[target] = module
    spec.loader.exec_module(module)
    return module


class FakeArray:
    def squeeze(self, _axis):
        return self
    def __mul__(self, _factor):
        return self
    def astype(self, _dtype):
        return self


class FakeTensor:
    def cpu(self):
        return self
    def numpy(self):
        return FakeArray()


class FakePIL:
    def save(self, stream, format=None):
        stream.write(b"mock-png")


class SafeUploadTests(unittest.TestCase):
    def test_multi_image_invalid_later_route_stops_before_any_upload(self):
        module = load_upload("rh_multi_input_image")
        with patch.object(module, "upload_file_to_rh") as send:
            with self.assertRaisesRegex(ValueError, "node_id_2"):
                module.RH_MultiInputImage().upload_single_run(
                    {"api_key": "fixture", "base_url": "https://www.runninghub.ai"},
                    image_1=FakeTensor(), node_id_1="111", field_name_1="image",
                    image_2=FakeTensor(), node_id_2="", field_name_2="mask",
                )
            send.assert_not_called()

    def test_multi_image_upload_failure_aborts_instead_of_skipping(self):
        module = load_upload("rh_multi_input_image")
        with patch.object(module.Image, "fromarray", return_value=FakePIL(), create=True), \
             patch.object(module, "upload_file_to_rh", side_effect=["first.png", None]) as send:
            with self.assertRaisesRegex(RuntimeError, "image_2"):
                module.RH_MultiInputImage().upload_single_run(
                    {"api_key": "fixture", "base_url": "https://www.runninghub.ai"},
                    image_1=FakeTensor(), node_id_1="111", field_name_1="image",
                    image_2=FakeTensor(), node_id_2="112", field_name_2="mask",
                    image_3=FakeTensor(), node_id_3="113", field_name_3="image",
                )
            self.assertEqual(send.call_count, 2)

    def test_multi_image_success_and_previous_params_are_preserved(self):
        module = load_upload("rh_multi_input_image")
        before = [{"nodeId": "28", "fieldName": "prompt", "fieldValue": "initial"}]
        with patch.object(module.Image, "fromarray", return_value=FakePIL(), create=True), \
             patch.object(module, "upload_file_to_rh", side_effect=["one.png", "three.png"]) as send:
            (params,) = module.RH_MultiInputImage().upload_single_run(
                {"api_key": "fixture", "base_url": "https://www.runninghub.ai"},
                previous_params=before,
                image_1=FakeTensor(), node_id_1="111",
                image_3=FakeTensor(), node_id_3="113", field_name_3="mask",
            )
        self.assertEqual(params[1], {"nodeId": "111", "fieldName": "image", "fieldValue": "one.png"})
        self.assertEqual(params[2], {"nodeId": "113", "fieldName": "mask", "fieldValue": "three.png"})
        self.assertEqual(len(before), 1)
        self.assertEqual(send.call_count, 2)

    def test_batch_upload_rejects_incomplete_config_before_upload(self):
        module = load_upload("rh_batch_upload_image")
        cfg = {"api_key": "fixture", "base_url": "https://www.runninghub.ai"}
        with patch.object(module, "upload_file_to_rh") as send:
            with self.assertRaises(ValueError):
                module.RH_BatchUploadImage().upload_batch(cfg, "", "image", image_1=FakeTensor())
            with self.assertRaises(ValueError):
                module.RH_BatchUploadImage().upload_batch(cfg, "111", "", image_1=FakeTensor())
            with self.assertRaises(ValueError):
                module.RH_BatchUploadImage().upload_batch(cfg, "111", "image")
            send.assert_not_called()

    def test_batch_upload_failure_aborts_no_partial_bundle(self):
        module = load_upload("rh_batch_upload_image")
        with patch.object(module.Image, "fromarray", return_value=FakePIL(), create=True), \
             patch.object(module, "upload_file_to_rh", side_effect=["one.png", None]) as send:
            with self.assertRaisesRegex(RuntimeError, "image_2"):
                module.RH_BatchUploadImage().upload_batch(
                    {"api_key": "fixture", "base_url": "https://www.runninghub.ai"},
                    "111", "image", image_1=FakeTensor(), image_2=FakeTensor(), image_3=FakeTensor()
                )
            self.assertEqual(send.call_count, 2)

    def test_batch_upload_success_preserves_one_param_set_per_image(self):
        module = load_upload("rh_batch_upload_image")
        with patch.object(module.Image, "fromarray", return_value=FakePIL(), create=True), \
             patch.object(module, "upload_file_to_rh", side_effect=["one.png", "two.png"]):
            (bundle,) = module.RH_BatchUploadImage().upload_batch(
                {"api_key": "fixture", "base_url": "https://www.runninghub.ai"},
                "111", "image", image_1=FakeTensor(), image_3=FakeTensor()
            )
        self.assertEqual(bundle, [
            [{"nodeId": "111", "fieldName": "image", "fieldValue": "one.png"}],
            [{"nodeId": "111", "fieldName": "image", "fieldValue": "two.png"}],
        ])


if __name__ == "__main__":
    unittest.main()
