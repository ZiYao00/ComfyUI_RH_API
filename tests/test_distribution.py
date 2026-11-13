"""Public Git clone safety checks. Does not read or publish local credentials."""

import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None


class PublicDistributionTests(unittest.TestCase):
    def test_install_entrypoints_and_docs_exist(self):
        required = (
            "__init__.py", "requirements.txt", "LICENSE", "config.json.example",
            "README.md", "README_CN.md", "docs/INSTALL.md", "docs/INSTALL_CN.md",
            "docs/RELEASE_CHECKLIST.md", ".github/workflows/ci.yml",
            "nodes/rh_config.py", "js/rh_config_secret.js",
        )
        for name in required:
            with self.subTest(name=name):
                self.assertTrue((ROOT / name).is_file())

    def test_public_config_template_has_no_credential(self):
        template = json.loads((ROOT / "config.json.example").read_text(encoding="utf-8"))
        self.assertEqual(template["api_key"], "")
        self.assertIn(template["base_url"], {"https://www.runninghub.ai", "https://www.runninghub.cn"})

    def test_config_and_local_records_are_ignored(self):
        patterns = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for name in ("config.json", "config.local.json", ".rh-task-history/", ".ui-test/", ".codex-backups/"):
            self.assertIn(name, patterns)
        if not (ROOT / ".git").exists():
            return
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.PIPE,
        )
        paths = {p.decode("utf-8").replace("\\", "/") for p in result.stdout.split(b"\0") if p}
        self.assertFalse({"config.json", "config.local.json", "config.json.pending"} & paths)
        self.assertFalse(any(p.startswith((".rh-task-history/", ".ui-test/", ".codex-backups/")) for p in paths))

    @unittest.skipIf(tomllib is None, "tomllib requires Python 3.11+")
    def test_repository_metadata_is_ours_and_registry_publisher_is_not_upstream(self):
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(
            metadata["project"]["urls"]["Repository"],
            "https://github.com/ZiYao00/ComfyUI_RH_API",
        )
        self.assertNotEqual(metadata.get("tool", {}).get("comfy", {}).get("PublisherId"), "xuchenxu168")

    def test_registry_publication_is_not_automatic(self):
        action = (ROOT / ".github/workflows/publish_action.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", action)
        self.assertNotIn("  push:", action)
        self.assertIn("COMFY_REGISTRY_ENABLED", action)

    def test_public_readmes_link_the_fork_installation(self):
        for path in ("README.md", "README_CN.md"):
            body = (ROOT / path).read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("https://github.com/ZiYao00/ComfyUI_RH_API.git", body)
                self.assertIn("docs/INSTALL", body)


if __name__ == "__main__":
    unittest.main()
