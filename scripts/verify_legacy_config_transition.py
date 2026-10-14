"""Check and optionally retire one explicit legacy config.local.json safely.

Only config.local.json in the same directory as the provided config.json can be
deleted. The old RH Config reader's effective configuration must be identical
with and without that legacy file. Does not print keys or private values.
"""
from __future__ import annotations
import argparse
from contextlib import redirect_stdout
from io import StringIO
import importlib.util
import json
from pathlib import Path
import subprocess
from unittest.mock import patch


def _exit(message):
    raise SystemExit(message)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    p.add_argument("--destination", required=True)
    p.add_argument("--retire-old", action="store_true")
    a = p.parse_args()
    source = Path(a.source).resolve()
    target = Path(a.destination).resolve()
    if source.parent != target.parent or source.name != "config.local.json" or target.name != "config.json":
        _exit("Only one explicit same-directory legacy config.local.json may be retired.")
    root = source.parent
    if not source.is_file() or not target.is_file() or not (root / "nodes/rh_config.py").is_file():
        _exit("Required legacy config or RH Config module is missing; no change.")
    if source.stat().st_size > 65536 or target.stat().st_size > 65536:
        _exit("Unexpected config file size; no change.")
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "config.json"],
        cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "config.json"],
        cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0
    if tracked or not ignored:
        _exit("Destination remains tracked or unprotected by Git ignore; no change.")
    try:
        old = json.loads(source.read_text(encoding="utf-8-sig"))
        new = json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, UnicodeError):
        _exit("Could not parse private configuration; no change.")
    if not isinstance(old, dict) or not isinstance(new, dict):
        _exit("Unexpected configuration shape; no change.")
    secret = old.get("api_key")
    if not isinstance(secret, str) or not secret.strip():
        _exit("Legacy source lacks the expected API key; no change.")
    if (new.get("api_key") != secret or
        not isinstance(new.get("api_keys"), dict) or
        new["api_keys"].get("international") != secret):
        _exit("New config lacks exact legacy and international credentials; no change.")
    # Load the real old V1 code and compare the exact merged result, including
    # base_url and optional historical keys, before/after exclusion.
    spec = importlib.util.spec_from_file_location("legacy_rh_config_preflight", root / "nodes/rh_config.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    with redirect_stdout(StringIO()):
        before = module.RH_Config.load_config_file()
        real_exists = module.os.path.exists
        def without_source(value):
            if Path(value).resolve() == source:
                return False
            return real_exists(value)
        with patch.object(module.os.path, "exists", side_effect=without_source):
            after = module.RH_Config.load_config_file()
    if before != after:
        _exit("Legacy reader effective configuration would change; no legacy file deletion.")
    if a.retire_old:
        source.unlink()
        if source.exists():
            _exit("Legacy config removal was not confirmed.")
        print("PASS: exact legacy config.local.json file retired; config.json remains ignored.")
    else:
        print("PASS: old RH_Config resolves the same settings with config.json alone.")
    print("SECRET_EXPOSURE: no values printed")


if __name__ == "__main__":
    main()
