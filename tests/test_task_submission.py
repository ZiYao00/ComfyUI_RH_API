import importlib.util
import pathlib
import sys
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def make_requests_stub():
    requests = types.ModuleType("requests")

    class RequestException(Exception):
        pass

    class Timeout(RequestException):
        pass

    requests.exceptions = types.SimpleNamespace(
        RequestException=RequestException,
        Timeout=Timeout,
    )
    requests.post = None
    return requests


def load_rh_execute(requests_module):
    sys.modules["requests"] = requests_module
    package_name = "rh_execute_submission_test_pkg"
    sys.modules.pop(f"{package_name}.rh_client", None)
    sys.modules.pop(f"{package_name}.rh_execute", None)
    package = types.ModuleType(package_name)
    package.__path__ = [str(ROOT / "nodes")]
    sys.modules[package_name] = package

    rh_utils = types.ModuleType(f"{package_name}.rh_utils")
    rh_utils._monitor_task = lambda *args, **kwargs: None
    rh_utils._get_outputs = lambda *args, **kwargs: None
    rh_utils._create_placeholder_image = lambda text: text
    rh_utils._create_placeholder_latent = lambda: {"samples": "empty"}
    sys.modules[f"{package_name}.rh_utils"] = rh_utils

    path = ROOT / "nodes" / "rh_execute.py"
    module_name = f"{package_name}.rh_execute"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class TaskSubmissionTests(unittest.TestCase):
    def test_successful_creation_posts_once(self):
        requests = make_requests_stub()
        calls = []

        def post(*args, **kwargs):
            calls.append((args, kwargs))
            return FakeResponse({"code": 0, "data": {"taskId": "task-123"}})

        requests.post = post
        module = load_rh_execute(requests)
        task_id = module.RH_Execute()._create_task(
            {
                "api_key": "key",
                "base_url": "https://rh.example",
                "workflow_or_app_id": "workflow-1",
                "is_ai_app": False,
            },
            params=[],
            use_high_performance=False,
        )

        self.assertEqual(task_id, "task-123")
        self.assertEqual(len(calls), 1)

    def test_transport_failure_is_not_retried(self):
        requests = make_requests_stub()
        calls = []

        def post(*args, **kwargs):
            calls.append((args, kwargs))
            raise requests.exceptions.Timeout("response lost")

        requests.post = post
        module = load_rh_execute(requests)

        with self.assertRaises(module.RHTaskSubmissionUncertainError) as context:
            module.RH_Execute()._create_task(
                {
                    "api_key": "key",
                    "base_url": "https://rh.example",
                    "workflow_or_app_id": "workflow-1",
                    "is_ai_app": False,
                },
                params=[],
                use_high_performance=False,
            )

        self.assertEqual(len(calls), 1)
        self.assertIn("Do not auto-retry", str(context.exception))

    def test_preflight_bad_route_blocks_paid_task_creation(self):
        requests = make_requests_stub()
        calls = []
        requests.post = lambda *args, **kwargs: calls.append((args, kwargs))
        module = load_rh_execute(requests)
        schema_module = sys.modules[module.__package__ + ".rh_workflow_schema"]
        parsed = schema_module.parse_workflow_api_json({
            "28": {"class_type": "CR Prompt Text", "inputs": {"prompt": "default"}}
        })
        settings = {
            "api_key": "[REDACTED]",
            "base_url": "https://www.runninghub.ai",
            "workflow_or_app_id": "example-workflow",
            "is_ai_app": False,
        }
        inspection = schema_module.RHWorkflowInspection.bind(parsed, settings, remote_verified=True)
        with self.assertRaises(ValueError) as result:
            module.RH_Execute().execute(
                settings,
                params=[{"nodeId": "28", "fieldName": "text", "fieldValue": "hello"}],
                workflow_schema=inspection,
            )
        self.assertIn("28.prompt", str(result.exception))
        self.assertEqual(calls, [])

    def test_preflight_correct_route_keeps_payload_and_legacy_behavior(self):
        from unittest.mock import patch
        requests = make_requests_stub()
        module = load_rh_execute(requests)
        schema_module = sys.modules[module.__package__ + ".rh_workflow_schema"]
        parsed = schema_module.parse_workflow_api_json({
            "28": {"class_type": "CR Prompt Text", "inputs": {"prompt": "default"}}
        })
        settings = {
            "api_key": "[REDACTED]",
            "base_url": "https://www.runninghub.ai",
            "workflow_or_app_id": "example-workflow",
            "is_ai_app": False,
        }
        inspection = schema_module.RHWorkflowInspection.bind(parsed, settings, remote_verified=True)
        params = [{"nodeId": "28", "fieldName": "prompt", "fieldValue": "hello"}]
        with patch.object(module.RH_Execute, "_create_task", return_value="task-stub") as create:
            result = module.RH_Execute().execute(settings, params=params, workflow_schema=inspection)
            create.assert_called_once_with(settings, params, False)
        self.assertEqual(result[-1], "task-stub")
        self.assertEqual(params[0]["fieldValue"], "hello")

    def test_preflight_cross_workflow_never_submits_task(self):
        from unittest.mock import patch
        requests = make_requests_stub()
        module = load_rh_execute(requests)
        schema_module = sys.modules[module.__package__ + ".rh_workflow_schema"]
        parsed = schema_module.parse_workflow_api_json({
            "28": {"class_type": "CR Prompt Text", "inputs": {"prompt": "default"}}
        })
        settings = {
            "api_key": "[REDACTED]",
            "base_url": "https://www.runninghub.ai",
            "workflow_or_app_id": "example-workflow",
        }
        inspection = schema_module.RHWorkflowInspection.bind(parsed, settings, remote_verified=True)
        with patch.object(module.RH_Execute, "_create_task") as create:
            with self.assertRaisesRegex(ValueError, "different workflow"):
                module.RH_Execute().execute(
                    {**settings, "workflow_or_app_id": "unrelated-workflow"},
                    params=[{"nodeId": "28", "fieldName": "prompt", "fieldValue": "hello"}],
                    workflow_schema=inspection,
                )
            create.assert_not_called()

    def test_explicit_business_error_is_not_reported_as_uncertain(self):
        requests = make_requests_stub()
        requests.post = lambda *args, **kwargs: FakeResponse({
            "code": 1,
            "msg": "INVALID_API_KEY",
            "data": None,
        })
        module = load_rh_execute(requests)

        with self.assertRaises(Exception) as context:
            module.RH_Execute()._create_task(
                {
                    "api_key": "bad",
                    "base_url": "https://rh.example",
                    "workflow_or_app_id": "workflow-1",
                    "is_ai_app": False,
                },
                params=[],
                use_high_performance=False,
            )

        self.assertNotIsInstance(context.exception, module.RHTaskSubmissionUncertainError)
        self.assertIn("Invalid API key", str(context.exception))


if __name__ == "__main__":
    unittest.main()
