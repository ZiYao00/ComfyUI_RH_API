"""Regression tests for the public RH Config setup (no ComfyUI/cloud required)."""

import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("rh_public_config_under_test", ROOT / "nodes" / "rh_config.py")
CONFIG_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONFIG_MODULE)


class RHConfigPublicInstallTests(unittest.TestCase):
    def test_new_node_has_blank_base_url_so_config_file_is_effective(self):
        self.assertEqual(CONFIG_MODULE.RH_Config.INPUT_TYPES()["required"]["base_url"][1]["default"], "")

    def test_blank_node_url_uses_international_config(self):
        with patch.object(
            CONFIG_MODULE.RH_Config,
            "load_config_file",
            return_value={"api_key": "test-key", "base_url": "https://www.runninghub.ai"},
        ):
            (value,) = CONFIG_MODULE.RH_Config().create_config("", "workflow-1", "")
        self.assertEqual(value["base_url"], "https://www.runninghub.ai")
        self.assertEqual(value["api_key"], "test-key")

    def test_existing_explicit_url_and_key_are_preserved(self):
        with patch.object(
            CONFIG_MODULE.RH_Config,
            "load_config_file",
            return_value={"api_key": "file-key", "base_url": "https://www.runninghub.ai"},
        ):
            (value,) = CONFIG_MODULE.RH_Config().create_config(
                "node-key", "workflow-1", "https://www.runninghub.cn"
            )
        self.assertEqual(value["base_url"], "https://www.runninghub.cn")
        self.assertEqual(value["api_key"], "node-key")

    def test_default_site_stays_domestic_without_config_file(self):
        with patch.object(CONFIG_MODULE.RH_Config, "load_config_file", return_value={"api_key": "test-key"}):
            (value,) = CONFIG_MODULE.RH_Config().create_config("", "workflow-1", "")
        self.assertEqual(value["base_url"], "https://www.runninghub.cn")

    def test_missing_key_reports_private_config_file(self):
        with patch.object(CONFIG_MODULE.RH_Config, "load_config_file", return_value={}):
            with self.assertRaisesRegex(ValueError, "config.json"):
                CONFIG_MODULE.RH_Config().create_config("", "workflow-1", "")

    def test_legacy_config_local_override_is_not_silently_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "config.json").write_text(
                json.dumps({"api_key": "primary", "base_url": "https://www.runninghub.ai"}),
                encoding="utf-8",
            )
            (root / "config.local.json").write_text(
                json.dumps({"api_key": "legacy"}),
                encoding="utf-8",
            )
            with patch.object(CONFIG_MODULE, "__file__", str(root / "nodes" / "rh_config.py")):
                settings = CONFIG_MODULE.RH_Config.load_config_file()
        self.assertEqual(settings["api_key"], "legacy")
        self.assertEqual(settings["base_url"], "https://www.runninghub.ai")


if __name__ == "__main__":
    unittest.main()
