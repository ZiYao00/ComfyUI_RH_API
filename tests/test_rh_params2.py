import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module():
    path = ROOT / "nodes" / "rh_params2.py"
    spec = importlib.util.spec_from_file_location("rh_params2_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RHParams2Tests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_builds_multiple_rows_and_preserves_previous(self):
        previous = [{"nodeId": "1", "fieldName": "seed", "fieldValue": "7"}]
        original = [dict(previous[0])]

        (result,) = self.module.RH_Params2().build_params(
            previous_params=previous,
            param_1={
                "enabled": True,
                "node_id": "12",
                "field_name": "text",
                "custom_field_name": "",
                "local_value": "hello",
            },
            param_2={
                "enabled": True,
                "node_id": "13",
                "field_name": "strength",
                "custom_field_name": "",
                "local_value": "0.8",
            },
        )

        self.assertEqual(previous, original)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[1], {"nodeId": "12", "fieldName": "text", "fieldValue": "hello"})
        self.assertEqual(result[2], {"nodeId": "13", "fieldName": "strength", "fieldValue": "0.8"})

    def test_external_value_overrides_local_value(self):
        (result,) = self.module.RH_Params2().build_params(
            param_1={
                "enabled": True,
                "node_id": "1584",
                "field_name": "width",
                "custom_field_name": "",
                "local_value": "1088",
            },
            value_1=1664,
        )

        self.assertEqual(result[0]["fieldValue"], "1664")

    def test_bool_external_value_uses_lowercase_string(self):
        (result,) = self.module.RH_Params2().build_params(
            param_1={
                "enabled": True,
                "node_id": "9",
                "field_name": "custom",
                "custom_field_name": "enabled",
                "local_value": "",
            },
            value_1=False,
        )

        self.assertEqual(result[0], {"nodeId": "9", "fieldName": "enabled", "fieldValue": "false"})

    def test_custom_field_is_emitted(self):
        (result,) = self.module.RH_Params2().build_params(
            param_3={
                "enabled": True,
                "node_id": "12",
                "field_name": "custom",
                "custom_field_name": "prompt_text",
                "local_value": "x",
            }
        )

        self.assertEqual(result[0]["fieldName"], "prompt_text")

    def test_custom_field_requires_name(self):
        with self.assertRaises(ValueError):
            self.module.RH_Params2().build_params(
                param_1={
                    "enabled": True,
                    "node_id": "12",
                    "field_name": "custom",
                    "custom_field_name": "",
                    "local_value": "x",
                }
            )

    def test_disabled_and_empty_rows_are_ignored(self):
        (result,) = self.module.RH_Params2().build_params(
            param_1={
                "enabled": False,
                "node_id": "12",
                "field_name": "text",
                "custom_field_name": "",
                "local_value": "skip",
            },
            param_2={
                "enabled": True,
                "node_id": "",
                "field_name": "text",
                "custom_field_name": "",
                "local_value": "",
            },
        )

        self.assertEqual(result, [])

    def test_external_value_without_node_id_fails(self):
        with self.assertRaises(ValueError):
            self.module.RH_Params2().build_params(
                param_4={
                    "enabled": True,
                    "node_id": "",
                    "field_name": "width",
                    "custom_field_name": "",
                    "local_value": "",
                },
                value_4=1024,
            )

    def test_param_count_widget_controls_one_to_sixteen_slots(self):
        required = self.module.RH_Params2.INPUT_TYPES()["required"]
        self.assertIn("param_count", required)
        input_type, options = required["param_count"]
        self.assertEqual(input_type, "INT")
        self.assertEqual(options["default"], 1)
        self.assertEqual(options["min"], 1)
        self.assertEqual(options["max"], 16)
        self.assertEqual(options["step"], 1)

    def test_param_count_does_not_change_emitted_params(self):
        (result,) = self.module.RH_Params2().build_params(
            param_count=3,
            param_1={
                "enabled": True,
                "node_id": "12",
                "field_name": "text",
                "custom_field_name": "",
                "local_value": "hello",
            },
        )
        self.assertEqual(
            result,
            [{"nodeId": "12", "fieldName": "text", "fieldValue": "hello"}],
        )

    def test_native_widgets_build_multiple_rows(self):
        (result,) = self.module.RH_Params2().build_params(
            param_count=2,
            node_id_1="12",
            field_name_1="text",
            custom_field_name_1="",
            local_value_1="hello",
            node_id_2="13",
            field_name_2="strength",
            custom_field_name_2="",
            local_value_2="0.8",
        )
        self.assertEqual(
            result,
            [
                {"nodeId": "12", "fieldName": "text", "fieldValue": "hello"},
                {"nodeId": "13", "fieldName": "strength", "fieldValue": "0.8"},
            ],
        )

    def test_native_widget_external_value_overrides_local_value(self):
        (result,) = self.module.RH_Params2().build_params(
            param_count=1,
            node_id_1="1584",
            field_name_1="width",
            custom_field_name_1="",
            local_value_1="1088",
            value_1=1664,
        )
        self.assertEqual(
            result,
            [{"nodeId": "1584", "fieldName": "width", "fieldValue": "1664"}],
        )

    def test_native_custom_field_is_used(self):
        (result,) = self.module.RH_Params2().build_params(
            param_count=1,
            node_id_1="9",
            field_name_1="custom",
            custom_field_name_1="prompt_text",
            local_value_1="hello",
        )
        self.assertEqual(
            result,
            [{"nodeId": "9", "fieldName": "prompt_text", "fieldValue": "hello"}],
        )

    def test_param_count_limits_native_output_slots(self):
        (result,) = self.module.RH_Params2().build_params(
            param_count=1,
            node_id_1="1",
            field_name_1="text",
            local_value_1="keep",
            node_id_2="2",
            field_name_2="text",
            local_value_2="ignore",
        )
        self.assertEqual(
            result,
            [{"nodeId": "1", "fieldName": "text", "fieldValue": "keep"}],
        )

    def test_dynamic_optional_type_accepts_unknown_inputs(self):
        optional = self.module.RH_Params2.INPUT_TYPES()["optional"]
        self.assertIn("param_99", optional)
        self.assertEqual(str(optional["value_99"][0]), "*")


if __name__ == "__main__":
    unittest.main()
