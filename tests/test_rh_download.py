"""RH Download must not represent failed remote media as successful placeholders."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def load_download():
    torch = types.ModuleType("torch")
    torch.cat = Mock(side_effect=lambda values, dim=0: list(values))
    sys.modules["torch"] = torch

    prefix = "rh_download_contract_tests"
    package = types.ModuleType(prefix)
    package.__path__ = [str(ROOT / "nodes")]
    sys.modules[prefix] = package

    utils = types.ModuleType(prefix + ".rh_utils")
    utils._monitor_task = Mock(return_value=None)
    utils._get_outputs = Mock(return_value=("image", "frames", "text", None, None, {"samples": "latent"}))
    sys.modules[prefix + ".rh_utils"] = utils
    sys.modules.pop(prefix + ".rh_download", None)
    spec = importlib.util.spec_from_file_location(prefix + ".rh_download", ROOT / "nodes" / "rh_download.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, utils, torch


def config():
    return {"api_key": "[REDACTED]", "base_url": "https://www.runninghub.ai"}


class DownloadContractTests(unittest.TestCase):
    def test_success_keeps_all_six_output_types(self):
        module, utils, torch = load_download()
        result = module.RH_Download().download(config(), "successful-task")
        self.assertEqual(len(result), 6)
        self.assertEqual(result[0], ["image"])
        self.assertEqual(result[1], ["frames"])
        self.assertEqual(result[2], "text")
        self.assertEqual(result[5]["samples"], ["latent"])
        self.assertEqual(torch.cat.call_count, 3)

    def test_monitor_error_is_not_a_fake_success(self):
        module, utils, torch = load_download()
        utils._monitor_task.side_effect = ConnectionError("offline")
        with self.assertRaisesRegex(RuntimeError, "task-1"):
            module.RH_Download().download(config(), "task-1")
        torch.cat.assert_not_called()

    def test_no_output_is_visible_failure_not_placeholder(self):
        module, utils, torch = load_download()
        utils._get_outputs.return_value = None
        with self.assertRaisesRegex(RuntimeError, "task-2"):
            module.RH_Download().download(config(), "task-2")
        torch.cat.assert_not_called()

    def test_partial_batch_failures_raise_before_tensor_aggregation(self):
        module, utils, torch = load_download()
        def process(task_id, *args):
            if task_id == "bad-task":
                raise OSError("partial download")
            return ("image", "frames", task_id, None, None, {"samples": "latent"})

        with patch.object(module.RH_Download, "_process_single_task", side_effect=process):
            with self.assertRaises(RuntimeError) as raised:
                module.RH_Download().download(config(), "good-task,bad-task,another-task")
        self.assertIn("bad-task", str(raised.exception))
        self.assertIn("1/3", str(raised.exception))
        torch.cat.assert_not_called()


if __name__ == "__main__":
    unittest.main()
