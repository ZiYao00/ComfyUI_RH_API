import importlib.util
import pathlib
import sys
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_standalone_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_rh_execute_module():
    package_name = "rh_test_pkg"
    package = types.ModuleType(package_name)
    package.__path__ = [str(ROOT / "nodes")]
    sys.modules[package_name] = package

    rh_utils = types.ModuleType(f"{package_name}.rh_utils")
    rh_utils._monitor_task = lambda *args, **kwargs: None
    rh_utils._get_outputs = lambda *args, **kwargs: None
    rh_utils._create_placeholder_image = lambda text: f"image:{text}"
    rh_utils._create_placeholder_latent = lambda: {"samples": "empty"}
    sys.modules[f"{package_name}.rh_utils"] = rh_utils

    requests = types.ModuleType("requests")
    sys.modules.setdefault("requests", requests)

    path = ROOT / "nodes" / "rh_execute.py"
    module_name = f"{package_name}.rh_execute"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class NodeContractTests(unittest.TestCase):
    def test_rh_param_does_not_mutate_previous_params(self):
        module = load_standalone_module("rh_param_under_test", ROOT / "nodes" / "rh_param.py")
        previous = [{"nodeId": "1", "fieldName": "text", "fieldValue": "old"}]
        original = [dict(previous[0])]

        (result,) = module.RH_Param().add_param(
            node_id="2",
            field_name="text",
            field_value="new",
            previous_params=previous,
        )

        self.assertEqual(previous, original)
        self.assertEqual(len(result), 2)
        self.assertIsNot(result, previous)

    def test_rh_execute_no_output_preserves_declared_arity(self):
        module = load_rh_execute_module()
        node = module.RH_Execute()
        node._create_task = lambda *args, **kwargs: "task-1"

        result = node.execute(
            {
                "api_key": "key",
                "workflow_or_app_id": "workflow-1",
                "base_url": "https://example.invalid",
            }
        )

        self.assertEqual(len(result), 7)
        self.assertEqual(result[6], "task-1")
        self.assertEqual(result[5], {"samples": "empty"})


if __name__ == "__main__":
    unittest.main()
