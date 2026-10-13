"""Atomic local RH task journal tests. No network and no workspace files."""
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("rh_task_journal_test_module", ROOT / "nodes" / "rh_task_journal.py")
journal = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = journal
SPEC.loader.exec_module(journal)


def fixture_config():
    return {
        "api_key": "[REDACTED]",
        "base_url": "https://name:pass@www.runninghub.ai/secret?token=example",
        "workflow_or_app_id": "workflow-1",
        "nodeInfoList": ["private prompt"],
    }


class TaskJournalTests(unittest.TestCase):
    def test_confirmed_task_saved_atomically_without_credentials_or_prompts(self):
        with TemporaryDirectory() as temp:
            target = journal.record_created_task(
                "rh-task-1", fixture_config(), instance_type="plus", directory=Path(temp)
            )
            self.assertEqual(target.parent, Path(temp))
            self.assertEqual(len(list(Path(temp).glob("*.json"))), 1)
            self.assertEqual(list(Path(temp).glob("*.part")), [])
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(data["taskId"], "rh-task-1")
            self.assertEqual(data["instanceType"], "plus")
            self.assertEqual(data["baseUrl"], "https://www.runninghub.ai")
            self.assertEqual(data["status"], "submitted")
            raw = target.read_text(encoding="utf-8")
            for private in ("[REDACTED]", "private prompt", "pass@", "token=example"):
                self.assertNotIn(private, raw)
            self.assertFalse(target.name.startswith("rh-task"))
            self.assertEqual(target, journal.record_created_task(
                "rh-task-1", fixture_config(), instance_type="plus", directory=Path(temp)
            ))

    def test_invalid_record_is_rejected_without_files(self):
        with TemporaryDirectory() as temp:
            base = fixture_config()
            for task, config, instance in [
                ("", base, "auto"), ("bad\nline", base, "auto"),
                ("task", base, "premium"), ("task", {**base, "base_url": "invalid"}, "plus"),
            ]:
                with self.subTest(task=task, instance=instance):
                    with self.assertRaises(ValueError):
                        journal.record_created_task(task, config, instance_type=instance, directory=Path(temp))
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_failed_atomic_replace_cleans_partial_file(self):
        with TemporaryDirectory() as temp:
            with patch.object(journal.os, "replace", side_effect=OSError("disk unavailable")):
                with self.assertRaises(OSError):
                    journal.record_created_task("task", fixture_config(), directory=Path(temp))
            self.assertEqual(list(Path(temp).glob("*.json")), [])
            self.assertEqual(list(Path(temp).glob("*.part")), [])


if __name__ == "__main__":
    unittest.main()
