import importlib.util
import pathlib
import sys
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module():
    package_name = "rh_execute2_test_pkg"
    package = types.ModuleType(package_name)
    package.__path__ = [str(ROOT / "nodes")]
    sys.modules[package_name] = package

    base_module = types.ModuleType(f"{package_name}.rh_execute")

    class FakeRHExecute:
        @classmethod
        def INPUT_TYPES(cls):
            return {}

        def execute(self, **kwargs):
            return kwargs

    base_module.RH_Execute = FakeRHExecute
    sys.modules[f"{package_name}.rh_execute"] = base_module

    path = ROOT / "nodes" / "rh_execute2.py"
    module_name = f"{package_name}.rh_execute2"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class RHExecute2Tests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_flexible_optional_inputs_accept_dynamic_params(self):
        optional = self.module.RH_Execute2.INPUT_TYPES()["optional"]
        self.assertIn("params_2", optional)
        self.assertEqual(optional["params_27"][0], "RH_PARAMS")

    def test_later_param_input_overrides_earlier_source(self):
        base = [
            {"nodeId": "12", "fieldName": "text", "fieldValue": "base"},
            {"nodeId": "13", "fieldName": "seed", "fieldValue": "1"},
        ]
        override = [{"nodeId": "12", "fieldName": "text", "fieldValue": "override"}]

        result = self.module.RH_Execute2.merge_param_sources(
            params=base,
            dynamic_params={"params_2": override},
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["fieldValue"], "override")
        self.assertEqual(base[0]["fieldValue"], "base")

    def test_numeric_input_order_controls_priority(self):
        result = self.module.RH_Execute2.merge_param_sources(
            params=[{"nodeId": "1", "fieldName": "text", "fieldValue": "base"}],
            dynamic_params={
                "params_10": [{"nodeId": "1", "fieldName": "text", "fieldValue": "ten"}],
                "params_2": [{"nodeId": "1", "fieldName": "text", "fieldValue": "two"}],
            },
        )
        self.assertEqual(result[0]["fieldValue"], "ten")

    def test_execute_defaults_to_downstream_save_only(self):
        node = self.module.RH_Execute2()
        result = node.execute(
            config={"api_key": "k", "workflow_or_app_id": "w", "base_url": "u"},
            params=[{"nodeId": "1", "fieldName": "text", "fieldValue": "x"}],
        )
        self.assertFalse(result["save_to_local"])
        self.assertEqual(result["params"][0]["fieldValue"], "x")

    def test_invalid_param_fails_before_submission(self):
        with self.assertRaises(ValueError):
            self.module.RH_Execute2.merge_param_sources(
                params=[{"nodeId": "", "fieldName": "text", "fieldValue": "x"}],
            )


if __name__ == "__main__":
    unittest.main()
