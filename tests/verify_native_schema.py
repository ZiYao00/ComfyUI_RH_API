"""Real installed-ComfyUI schema tests. Uses mocked uploads; never submits RH tasks.

Run with ComfyUI's Python and --comfy-root. The ordinary unittest suite remains
independent of Torch/ComfyUI. --export writes only .ui-test/native-object-info.json.
"""
from __future__ import annotations
import argparse
import importlib
import inspect
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfy-root", required=True)
    parser.add_argument("--export", action="store_true")
    args = parser.parse_args()
    sys.path.insert(0, args.comfy_root)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    package = types.ModuleType("rh_native_check")
    package.__path__ = [str(ROOT)]
    sys.modules[package.__name__] = package
    native = importlib.import_module("rh_native_check.nodes.rh_native")
    io = native.io
    definitions = {key: cls.GET_NODE_INFO_V1() for key, cls in native.NATIVE_NODE_CLASS_MAPPINGS.items()}

    class NativeSchemaTests(unittest.TestCase):
        def test_all_nine_nodes_are_real_v3_and_keep_output_contracts(self):
            expected = {
                "RH_Params2": ["RH_PARAMS"], "RH_UploadImage2": ["RH_PARAMS"],
                "RH_UploadImage": ["STRING", "RH_PARAMS"], "RH_UploadVideo": ["STRING", "RH_PARAMS"],
                "RH_UploadAudio": ["STRING", "RH_PARAMS"], "RH_UploadFile": ["RH_PARAM"],
                "RH_UploadLatent": ["RH_PARAM"], "RH_BatchUploadImage": ["RH_PARAM_BUNDLE"],
                "RH_MultiInputImage": ["RH_PARAMS"],
            }
            self.assertEqual(set(definitions), set(expected))
            for key, definition in definitions.items():
                with self.subTest(node=key):
                    self.assertTrue(issubclass(native.NATIVE_NODE_CLASS_MAPPINGS[key], io.ComfyNode))
                    self.assertEqual(list(definition["output"]), expected[key])

        def test_value_is_one_typed_input_with_a_native_string_widget(self):
            group = definitions["RH_Params2"]["input"]["required"]["param_count"]
            self.assertEqual(group[0], "COMFY_DYNAMICCOMBO_V3")
            for option in group[1]["options"]:
                count = int(option["key"])
                required = option["inputs"]["required"]
                for slot in range(1, count + 1):
                    kind, config = required[f"value_{slot}"]
                    self.assertEqual(set(kind.split(",")), {"STRING", "INT", "FLOAT", "BOOLEAN"})
                    self.assertEqual(config["widgetType"], "STRING")
                    self.assertNotIn(f"local_value_{slot}", required)
                    self.assertNotIn(f"enabled_{slot}", required)

        def test_audio_still_accepts_a_path_video_still_accepts_video(self):
            self.assertEqual(definitions["RH_UploadAudio"]["input"]["required"]["audio_path"][0], "STRING")
            self.assertEqual(definitions["RH_UploadVideo"]["input"]["required"]["video"][0], "VIDEO")

        def test_scalar_values_and_previous_params(self):
            previous = [{"nodeId": "0", "fieldName": "text", "fieldValue": "keep"}]
            group = {"param_count": "4"}
            for slot, value in enumerate((0, False, 0.25, ""), 1):
                group.update({f"node_id_{slot}": str(slot), f"field_name_{slot}": {f"field_name_{slot}": "text"}, f"value_{slot}": value})
            result = native.RH_Params2Native.execute(group, previous).result[0]
            self.assertEqual([item["fieldValue"] for item in result], ["keep", "0", "false", "0.25", ""])
            self.assertEqual(len(previous), 1)

        def test_empty_rows_are_ignored_without_an_enable_control(self):
            result = native.RH_Params2Native.execute({"param_count": "2", "node_id_1": "", "value_1": "",
                                                      "node_id_2": "2", "value_2": "keep"}).result[0]
            self.assertEqual(result, [{"nodeId": "2", "fieldName": "text", "fieldValue": "keep"}])

        def test_custom_field_and_invalid_scalar(self):
            group = {"param_count": "1", "node_id_1": "3", "field_name_1": {"field_name_1": "custom", "custom_field_name_1": "prompt"}, "value_1": "hello"}
            self.assertEqual(native.RH_Params2Native.execute(group).result[0][0]["fieldName"], "prompt")
            group["value_1"] = object()
            with self.assertRaises(TypeError):
                native.RH_Params2Native.execute(group)

        def test_bad_later_image_mapping_stops_before_any_upload(self):
            with patch.object(native.MultiImageUploader, "upload") as upload:
                with self.assertRaises(ValueError):
                    native.RH_UploadImage2Native.execute({}, {"image_count": "2", "node_id_1": "1", "image_1": object(), "image_2": object()})
                upload.assert_not_called()

        def test_image_group_routing_and_disabled_state(self):
            images = (object(), object())
            with patch.object(native.MultiImageUploader, "upload", return_value=([],)) as upload:
                native.RH_UploadImage2Native.execute({}, {
                    "image_count": "2", "node_id_1": "1", "image_1": images[0],
                    "field_name_1": {"field_name_1": "custom", "custom_field_name_1": "reference_image"},
                    "node_id_2": "2", "image_2": images[1], "enabled_2": False,
                })
                values = upload.call_args.kwargs
                self.assertEqual(values["image_meta_1"]["custom_field_name"], "reference_image")
                self.assertFalse(values["image_meta_2"]["enabled"])
                self.assertIs(values["image_1"], images[0])

        def test_single_uploads_delegate_without_changing_protocol(self):
            config = {"api_key": "test-only", "base_url": "https://invalid.example"}
            cases = [
                (native.RH_UploadImageNative, native.ImageUploader, "image", object()),
                (native.RH_UploadVideoNative, native.VideoUploader, "video", object()),
                (native.RH_UploadAudioNative, native.AudioUploader, "audio", "test.wav"),
            ]
            for cls, service, field, media in cases:
                with self.subTest(node=cls.__name__), patch.object(service, "upload", return_value=("remote.file", [])) as upload:
                    result = cls.execute(config, media, node_id="1", field_name=field)
                    self.assertEqual(result.result[0], "remote.file")
                    self.assertIs(upload.call_args.args[0], config)
                    self.assertIs(upload.call_args.args[1], media)

        def test_real_backend_expands_browser_prompt_without_a_custom_parser(self):
            from comfy_api.latest import _io
            flat = {
                "param_count": "2", "param_count.node_id_1": "12", "param_count.field_name_1": "custom",
                "param_count.field_name_1.custom_field_name_1": "prompt", "param_count.value_1": "hello",
                "param_count.node_id_2": "13", "param_count.field_name_2": "steps", "param_count.value_2": 0,
            }
            finalized, _, v3_data = _io.get_finalized_class_inputs(native.RH_Params2Native.INPUT_TYPES(), flat)
            self.assertIn("param_count.value_2", finalized["required"])
            nested = _io.build_nested_inputs(flat, v3_data)
            result = native.RH_Params2Native.EXECUTE_NORMALIZED(**nested).result[0]
            self.assertEqual(result, [{"nodeId": "12", "fieldName": "prompt", "fieldValue": "hello"},
                                      {"nodeId": "13", "fieldName": "steps", "fieldValue": "0"}])

        def test_real_backend_expands_image_group_and_omitted_optional_image(self):
            from comfy_api.latest import _io
            flat = {"config": {"api_key": "test-only", "base_url": "https://invalid.example"}, "image_count": "1", "image_count.node_id_1": "12", "image_count.field_name_1": "image"}
            _, _, v3_data = _io.get_finalized_class_inputs(native.RH_UploadImage2Native.INPUT_TYPES(), flat)
            nested = _io.build_nested_inputs(flat, v3_data)
            self.assertEqual(native.RH_UploadImage2Native.EXECUTE_NORMALIZED(**nested).result[0], [])

        def test_package_registry_uses_native_classes(self):
            spec = importlib.util.spec_from_file_location("rh_native_check", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for name, cls in native.NATIVE_NODE_CLASS_MAPPINGS.items():
                self.assertIs(module.NODE_CLASS_MAPPINGS[name], cls)
                cls.VALIDATE_CLASS()
            self.assertNotIn("RH_UploadMask", module.NODE_CLASS_MAPPINGS)
            self.assertEqual(module.WEB_DIRECTORY, "js")

        def test_flat_widget_order_is_preserved_for_stable_single_uploads(self):
            for key in ("RH_UploadImage", "RH_UploadVideo", "RH_UploadAudio"):
                names = list(definitions[key]["input"]["optional"])
                self.assertEqual(names, ["node_id", "field_name", "custom_field_name", "previous_params"])

    with patch("requests.sessions.Session.request", side_effect=AssertionError("Network is forbidden in schema tests")):
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NativeSchemaTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    print("EXECUTE_NORMALIZED signature:", inspect.signature(native.RH_Params2Native.EXECUTE_NORMALIZED))
    print("DynamicGroup available:", hasattr(io, "DynamicGroup"))
    if args.export:
        # Test-only source/sink definitions are used in an isolated frontend, not registered in the user's server.
        for type_name in ("STRING", "INT", "FLOAT", "BOOLEAN", "IMAGE", "VIDEO", "AUDIO"):
            name = "RH_Test_" + type_name
            definitions[name] = {"name": name, "display_name": name, "category": "RH UI Tests", "input": {"required": {}},
                                 "output": [type_name], "output_name": [type_name], "output_is_list": [False], "output_node": False}
        for definition in definitions.values():
            # ComfyUI's loader supplies this when registering classes.
            definition["python_module"] = "custom_nodes.ComfyUI_RH_API"
        output = ROOT / ".ui-test" / "native-object-info.json"
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(definitions, ensure_ascii=False), encoding="utf-8")
        print("Exported:", output)
    raise SystemExit(0)


if __name__ == "__main__":
    main()
