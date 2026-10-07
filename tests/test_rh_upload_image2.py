import importlib.util
import pathlib
import sys
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module():
    package_name = "rh_upload_image2_test_pkg"
    package = types.ModuleType(package_name)
    package.__path__ = [str(ROOT / "nodes")]
    sys.modules[package_name] = package

    params_module = types.ModuleType(f"{package_name}.rh_params2")

    class AnyType(str):
        def __ne__(self, other):
            return False

    class FlexibleOptionalInputType(dict):
        def __init__(self, input_type, data=None):
            super().__init__()
            self.input_type = input_type
            self.data = data or {}
            self.update(self.data)

        def __contains__(self, key):
            return True

        def __getitem__(self, key):
            if key in self.data:
                return self.data[key]
            return (self.input_type,)

    params_module.ANY_TYPE = AnyType("*")
    params_module.FlexibleOptionalInputType = FlexibleOptionalInputType
    sys.modules[f"{package_name}.rh_params2"] = params_module

    upload_image_module = types.ModuleType(f"{package_name}.rh_upload_image")

    class FakePilImage:
        def save(self, buffer, format="PNG"):
            buffer.write(b"fake-png-bytes")

    class FakeRHUploadImage:
        def _tensor_to_pil(self, image):
            return FakePilImage()

    upload_image_module.RH_UploadImage = FakeRHUploadImage
    sys.modules[f"{package_name}.rh_upload_image"] = upload_image_module

    utils_module = types.ModuleType(f"{package_name}.rh_utils")
    uploads = []

    def fake_upload_file_to_rh(**kwargs):
        uploads.append(kwargs)
        return "server/" + kwargs["file_name"]

    utils_module.upload_file_to_rh = fake_upload_file_to_rh
    utils_module._uploads = uploads
    sys.modules[f"{package_name}.rh_utils"] = utils_module

    path = ROOT / "nodes" / "rh_upload_image2.py"
    module_name = f"{package_name}.rh_upload_image2"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    module._test_uploads = uploads
    return module


class RHUploadImage2Tests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.config = {"api_key": "k", "base_url": "https://example.test"}

    def test_uploads_multiple_images_with_independent_routing(self):
        previous = [{"nodeId": "1", "fieldName": "seed", "fieldValue": "7"}]
        original = [dict(previous[0])]

        (result,) = self.module.RH_UploadImage2().upload(
            config=self.config,
            previous_params=previous,
            image_meta_1={
                "enabled": True,
                "node_id": "318",
                "field_name": "image",
                "custom_field_name": "",
            },
            image_1=object(),
            image_meta_3={
                "enabled": True,
                "node_id": "192",
                "field_name": "reference",
                "custom_field_name": "",
            },
            image_3=object(),
        )

        self.assertEqual(previous, original)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[1], {
            "nodeId": "318",
            "fieldName": "image",
            "fieldValue": "server/image_1.png",
        })
        self.assertEqual(result[2], {
            "nodeId": "192",
            "fieldName": "reference",
            "fieldValue": "server/image_3.png",
        })
        self.assertEqual(len(self.module._test_uploads), 2)

    def test_custom_field_name_is_used(self):
        (result,) = self.module.RH_UploadImage2().upload(
            config=self.config,
            image_meta_2={
                "enabled": True,
                "node_id": "315",
                "field_name": "custom",
                "custom_field_name": "ref_image",
            },
            image_2=object(),
        )

        self.assertEqual(result[0]["fieldName"], "ref_image")

    def test_connected_image_requires_node_id(self):
        with self.assertRaises(ValueError):
            self.module.RH_UploadImage2().upload(
                config=self.config,
                image_meta_1={
                    "enabled": True,
                    "node_id": "",
                    "field_name": "image",
                    "custom_field_name": "",
                },
                image_1=object(),
            )

    def test_disabled_or_unconnected_rows_are_skipped(self):
        (result,) = self.module.RH_UploadImage2().upload(
            config=self.config,
            image_meta_1={
                "enabled": False,
                "node_id": "318",
                "field_name": "image",
                "custom_field_name": "",
            },
            image_1=object(),
            image_meta_2={
                "enabled": True,
                "node_id": "192",
                "field_name": "reference",
                "custom_field_name": "",
            },
        )

        self.assertEqual(result, [])
        self.assertEqual(self.module._test_uploads, [])

    def test_custom_field_requires_name(self):
        with self.assertRaises(ValueError):
            self.module.RH_UploadImage2().upload(
                config=self.config,
                image_meta_1={
                    "enabled": True,
                    "node_id": "318",
                    "field_name": "custom",
                    "custom_field_name": "",
                },
                image_1=object(),
            )


if __name__ == "__main__":
    unittest.main()
