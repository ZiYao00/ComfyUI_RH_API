import importlib.util
import pathlib
import sys
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_batch_module(client_class, uncertain_error):
    package_name = "rh_batch_test_pkg"
    sys.modules.pop(f"{package_name}.rh_batch_execute", None)
    package = types.ModuleType(package_name)
    package.__path__ = [str(ROOT / "nodes")]
    sys.modules[package_name] = package

    rh_utils = types.ModuleType(f"{package_name}.rh_utils")
    rh_utils._validate_config = lambda config: None
    sys.modules[f"{package_name}.rh_utils"] = rh_utils

    rh_client = types.ModuleType(f"{package_name}.rh_client")
    rh_client.RHClient = client_class
    rh_client.RHTaskSubmissionUncertainError = uncertain_error
    sys.modules[f"{package_name}.rh_client"] = rh_client

    path = ROOT / "nodes" / "rh_batch_execute.py"
    module_name = f"{package_name}.rh_batch_execute"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class BatchExecuteTests(unittest.TestCase):
    def test_batch_uses_shared_client_for_each_submission(self):
        class Uncertain(RuntimeError):
            pass

        calls = []

        class FakeClient:
            def __init__(self, api_key, base_url):
                self.api_key = api_key
                self.base_url = base_url

            def create_task(self, **kwargs):
                calls.append(kwargs)
                return f"task-{len(calls)}"

        module = load_batch_module(FakeClient, Uncertain)
        (task_ids,) = module.RH_BatchExecute().batch_execute(
            {"api_key": "key", "base_url": "https://rh.example"},
            "workflow-1",
            [[{"nodeId": "1"}], [{"nodeId": "2"}]],
        )

        self.assertEqual(task_ids, "task-1,task-2")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["workflow_or_app_id"], "workflow-1")

    def test_uncertain_submission_stops_remaining_batch(self):
        class Uncertain(RuntimeError):
            pass

        calls = []

        class FakeClient:
            def __init__(self, api_key, base_url):
                pass

            def create_task(self, **kwargs):
                calls.append(kwargs)
                raise Uncertain("submission uncertain")

        module = load_batch_module(FakeClient, Uncertain)
        with self.assertRaises(Uncertain):
            module.RH_BatchExecute().batch_execute(
                {"api_key": "key", "base_url": "https://rh.example"},
                "workflow-1",
                [[], [], []],
            )

        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
