"""Post-migration integrity gate; verifies secrets locally without printing them."""
from __future__ import annotations
from contextlib import redirect_stdout
from io import StringIO
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: check_config_final_state.py PATH_TO_PLUGIN_ROOT")
    root = Path(sys.argv[1]).resolve()
    config = root / "config.json"
    legacy = root / "config.local.json"
    if not config.is_file() or legacy.exists():
        raise SystemExit("FAIL: expected one config.json and no config.local.json")
    if subprocess.run(["git", "ls-files", "--error-unmatch", "config.json"], cwd=root,
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        raise SystemExit("FAIL: config.json remains tracked in Git")
    if subprocess.run(["git", "check-ignore", "-q", "config.json"], cwd=root,
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        raise SystemExit("FAIL: config.json is not ignored")
    try:
        new = json.loads(config.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError):
        raise SystemExit("FAIL: config.json invalid")
    if not isinstance(new, dict) or not isinstance(new.get("api_keys"), dict):
        raise SystemExit("FAIL: modern config schema missing")
    intl = new["api_keys"].get("international", "")
    if not isinstance(intl, str) or not intl:
        raise SystemExit("FAIL: international key is not configured")
    # Legacy compatibility aliases may remain until 8188 is migrated.
    if (root / "nodes/rh_config.py").is_file() and "api_key" in new:
        if new.get("api_key") != intl:
            raise SystemExit("FAIL: legacy Key mismatch")
        spec = importlib.util.spec_from_file_location("old_rh_config_safe_gate", root / "nodes/rh_config.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with redirect_stdout(StringIO()):
            legacy_settings = module.RH_Config.load_config_file()
        if legacy_settings.get("api_key") != intl or legacy_settings.get("base_url") != new.get("base_url"):
            raise SystemExit("FAIL: older RH Config reads different credentials or base_url")
    print("PASS: exactly one private runtime config.json, Git ignored/untracked.")
    print("PASS: international credential present and backward-compatible; no secret values displayed.")

if __name__ == "__main__":
    main()
