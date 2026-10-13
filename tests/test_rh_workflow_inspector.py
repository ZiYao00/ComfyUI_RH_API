"""Offline regression tests for RH workflow inspection."""
from __future__ import annotations
import importlib
import json
import sys
import types
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "rh_inspector_tests"


def module():
    package = types.ModuleType(PREFIX)
    package.__path__ = [str(ROOT / "nodes")]
    sys.modules[PREFIX] = package
    for item in ("rh_workflow_inspector", "rh_workflow_schema", "rh_client"):
        sys.modules.pop(PREFIX + "." + item, None)
    return importlib.import_module(PREFIX + ".rh_workflow_inspector")


def settings():
    return dict(api_key="[REDACTED]", base_url="https://www.runninghub.ai",
                workflow_or_app_id="example-workflow", is_ai_app=False)


def api_graph():
    return {"28": {"class_type": "CR Prompt Text", "inputs": {"prompt": "value"}},
            "7": {"class_type": "Image", "inputs": {"width": 480}}}


class InspectorTests(unittest.TestCase):
    def test_correct_field(self):
        api = module()
        payload = {"code": 0, "data": {"prompt": json.dumps(api_graph())}}
        with patch.object(api.RHClient, "get_workflow_api_json", return_value=payload) as fetched:
            result, report = api.inspect_workflow(settings(), node_filter="28",
                overrides_json='[{"nodeId":"28","fieldName":"prompt","fieldValue":"hi"}]')
        self.assertTrue(result.remote_verified)
        self.assertIn("prompt (string)", report)
        fetched.assert_called_once()

    def test_wrong_field(self):
        api = module()
        payload = {"code": 0, "data": {"prompt": json.dumps(api_graph())}}
        with patch.object(api.RHClient, "get_workflow_api_json", return_value=payload):
            with self.assertRaises(ValueError) as result:
                api.inspect_workflow(settings(), overrides_json='[{"nodeId":"28","fieldName":"text","fieldValue":"x"}]')
        self.assertIn("28.prompt", str(result.exception))

    def test_inspection_scope_and_age(self):
        from dataclasses import replace
        api = module()
        parsed = api.parse_workflow_api_json(api_graph())
        scoped = api.RHWorkflowInspection.bind(parsed, settings(), remote_verified=True)
        scoped.assert_matches(settings())
        for change in (
            {**settings(), "workflow_or_app_id": "different-workflow"},
            {**settings(), "base_url": "https://www.runninghub.cn"},
            {**settings(), "is_ai_app": True},
        ):
            with self.assertRaises(ValueError):
                scoped.assert_matches(change)
        old = replace(scoped, checked_at=scoped.checked_at - 1900)
        with self.assertRaisesRegex(ValueError, "stale"):
            old.assert_matches(settings())

    def test_local_file_inspection_no_cloud_call(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temp:
            target = Path(temp) / "api.json"
            target.write_text(json.dumps(api_graph()), encoding="utf-8")
            api = module()
            with patch.object(api.RHClient, "get_workflow_api_json") as fetch:
                inspected, report = api.inspect_workflow(
                    settings(), source_mode="local_file", api_json_path=str(target), node_filter="28"
                )
                fetch.assert_not_called()
        self.assertFalse(inspected.remote_verified)
        self.assertIn("local snapshot", report)

    def test_unknown_node_and_app_rejected(self):
        api = module()
        with self.assertRaisesRegex(ValueError, "AI App"):
            api.inspect_workflow({**settings(), "is_ai_app": True})
        payload = {"code": 0, "data": {"prompt": json.dumps(api_graph())}}
        with patch.object(api.RHClient, "get_workflow_api_json", return_value=payload):
            with self.assertRaisesRegex(ValueError, "not present"):
                api.inspect_workflow(settings(), node_filter="999")

    def test_remote_failure_does_not_expose_response(self):
        api = module()
        with patch.object(api.RHClient, "get_workflow_api_json", side_effect=RuntimeError("HIDDEN_PAYLOAD")):
            with self.assertRaises(RuntimeError) as raised:
                api.inspect_workflow(settings())
        self.assertIn("metadata fetch failed", str(raised.exception))
        self.assertNotIn("HIDDEN_PAYLOAD", str(raised.exception))

