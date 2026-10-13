"""Offline RH Workflow API JSON regression cases. No network or paid tasks."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rh_workflow_schema_under_test", ROOT / "nodes" / "rh_workflow_schema.py")
schema_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = schema_module
spec.loader.exec_module(schema_module)


def sample():
    return {
        "7": {"class_type": "EmptyLatentImage", "inputs": {"width": 480, "height": 864}},
        "27": {"class_type": "Int", "inputs": {"value": 15}},
        "28": {"class_type": "CR Prompt Text", "inputs": {"prompt": "private text"}},
        "111": {"class_type": "LoadImage", "inputs": {"image": "private image.jpg"}},
        "50": {"class_type": "CLIPTextEncode", "inputs": {"text": ["28", 0]}},
    }


class WorkflowSchemaTests(unittest.TestCase):
    def test_regression_wrong_text_rejected_and_prompt_accepted(self):
        parsed = schema_module.parse_workflow_api_json(sample())
        bad = schema_module.validate_node_info_list(parsed, [
            {"nodeId": "28", "fieldName": "text", "fieldValue": "hello"},
        ])
        self.assertFalse(bad.ok)
        self.assertIn("28.prompt", bad.explain())
        good = schema_module.validate_node_info_list(parsed, [
            {"nodeId": "7", "fieldName": "width", "fieldValue": "480"},
            {"nodeId": "7", "fieldName": "height", "fieldValue": 864},
            {"nodeId": "27", "fieldName": "value", "fieldValue": "15"},
            {"nodeId": "28", "fieldName": "prompt", "fieldValue": "hello"},
            {"nodeId": "111", "fieldName": "image", "fieldValue": "RH-file.png"},
        ])
        self.assertTrue(good.ok, good.explain())

    def test_response_wrapper_string_graph_and_privacy(self):
        raw = sample()
        schema = schema_module.parse_workflow_api_json(
            {"code": 0, "data": {"prompt": json.dumps(raw)}}, source="remote"
        )
        summary = json.dumps(schema.summarize(), ensure_ascii=False)
        self.assertEqual(schema.node_count, 5)
        self.assertNotIn("private text", summary)
        self.assertNotIn("private image.jpg", summary)
        self.assertNotIn("private text", repr(schema))

    def test_signature_ignores_private_values_but_tracks_fields(self):
        graph = sample()
        original = schema_module.parse_workflow_api_json(graph).fingerprint
        graph["28"]["inputs"]["prompt"] = "a different secret"
        self.assertEqual(original, schema_module.parse_workflow_api_json(graph).fingerprint)
        graph["28"]["inputs"]["text"] = graph["28"]["inputs"].pop("prompt")
        self.assertNotEqual(original, schema_module.parse_workflow_api_json(graph).fingerprint)

    def test_connected_field_is_recognized_and_flagged(self):
        parsed = schema_module.parse_workflow_api_json(sample())
        report = schema_module.validate_node_info_list(
            parsed, [{"nodeId": "50", "fieldName": "text", "fieldValue": "override"}]
        )
        self.assertTrue(report.warnings)
        self.assertIn("connection", report.explain())

    def test_invalid_format_and_malformed_nodes_rejected(self):
        bad_cases = [
            {}, [], {"nodes": [{"id": 1, "type": "Text"}]},
            {"28": {"inputs": {"prompt": "hello"}}},
            {"code": 403, "data": {"prompt": "{}"}},
            {"code": 0, "data": {}},
        ]
        for case in bad_cases:
            with self.subTest(case=case):
                with self.assertRaises(schema_module.RHWorkflowSchemaError):
                    schema_module.parse_workflow_api_json(case)

    def test_invalid_values_and_missing_keys_fail(self):
        parsed = schema_module.parse_workflow_api_json(sample())
        report = schema_module.validate_node_info_list(parsed, [
            {"nodeId": "7", "fieldName": "width", "fieldValue": "n/a"},
            {"nodeId": "27", "fieldName": "value", "fieldValue": "10.5"},
            {"nodeId": "999", "fieldName": "foo", "fieldValue": "a"},
            {"nodeId": "28", "fieldName": "prompt"},
        ])
        self.assertEqual(len(report.errors), 4)

    def test_do_not_change_input_and_bool_zero_cases(self):
        graph = sample()
        graph["60"] = {"class_type": "Switch", "inputs": {"enabled": False}}
        parsed = schema_module.parse_workflow_api_json(graph)
        overrides = [
            {"nodeId": "60", "fieldName": "enabled", "fieldValue": False},
            {"nodeId": "7", "fieldName": "width", "fieldValue": 0},
            {"nodeId": "28", "fieldName": "prompt", "fieldValue": ""},
        ]
        original = json.dumps(overrides)
        self.assertTrue(schema_module.validate_node_info_list(parsed, overrides).ok)
        self.assertEqual(json.dumps(overrides), original)


if __name__ == "__main__":
    unittest.main()
