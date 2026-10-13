"""Validation regressions for legacy RH parameter-building nodes."""
from pathlib import Path
import importlib.util
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "nodes" / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class RHParamFamilyTests(unittest.TestCase):
    def setUp(self):
        self.one = load("rh_param.py", "rh_c3_single_param_tests").RH_Param()
        self.multi = load("rh_multi_param.py", "rh_c3_multi_param_tests").RH_MultiParams()

    def test_single_requires_node_and_real_custom_field(self):
        for case in [
            {"node_id": "", "field_name": "text", "field_value": "hello"},
            {"node_id": "28", "field_name": "custom", "field_value": "hello"},
            {"node_id": "28", "field_name": "", "field_value": "hello"},
        ]:
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.one.add_param(**case)

    def test_single_accepts_prompt_and_empty_clear_value_without_logging_it(self):
        before = [{"nodeId": "7", "fieldName": "width", "fieldValue": "480"}]
        with patch("builtins.print") as logged:
            (result,) = self.one.add_param(
                "28", "custom", "private-value", previous_params=before,
                custom_field_name=" prompt ",
            )
        self.assertEqual(result[-1], {
            "nodeId": "28", "fieldName": "prompt", "fieldValue": "private-value"
        })
        self.assertEqual(len(before), 1)
        self.assertNotIn("private-value", str(logged.call_args_list))
        (clear,) = self.one.add_param("28", "text", "")
        self.assertEqual(clear[0]["fieldValue"], "")

    def test_multi_ignores_unconfigured_rows_including_default_text_selectors(self):
        (params,) = self.multi.bundle_params(field_name_1="text", field_name_2="text")
        self.assertEqual(params, [])
        (params,) = self.multi.bundle_params(
            node_id_1="28", field_name_1="custom", custom_field_name_1="prompt",
            field_value_1="hello", field_name_2="text"
        )
        self.assertEqual(params, [{"nodeId": "28", "fieldName": "prompt", "fieldValue": "hello"}])

    def test_multi_rejects_incomplete_configured_rows(self):
        for values in [
            {"field_value_2": "not discarded"},
            {"field_name_3": "width"},
            {"node_id_1": "28", "field_name_1": "custom"},
            {"node_id_1": "28", "field_name_1": ""},
        ]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.multi.bundle_params(**values)

    def test_multi_retains_valid_previous_params_and_blank_values(self):
        before = [{"nodeId": "7", "fieldName": "width", "fieldValue": "480"}]
        (params,) = self.multi.bundle_params(
            previous_params=before,
            node_id_2="28", field_name_2="text", field_value_2="",
        )
        self.assertEqual(len(params), 2)
        self.assertEqual(params[-1]["fieldValue"], "")
        self.assertEqual(len(before), 1)


if __name__ == "__main__":
    unittest.main()
