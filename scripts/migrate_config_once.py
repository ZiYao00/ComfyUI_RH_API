"""One-time local credential transfer without printing or returning secrets.

The runtime never imports this maintenance utility. Run only against a known
legacy config.local.json and after 'git rm --cached config.json'.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--destination", default=str(ROOT / "config.json"))
    parser.add_argument("--keep-legacy-keys", action="store_true")
    args = parser.parse_args()
    source = Path(args.source).resolve()
    destination = Path(args.destination).resolve()
    if destination.name != "config.json":
        raise SystemExit("Destination filename must be config.json.")
    target_root = destination.parent
    # Only the explicitly named file is read; never overwrite the source.
    if source.name != "config.local.json" or not source.is_file():
        raise SystemExit("Source must be an existing config.local.json.")
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "config.json"],
            cwd=target_root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "config.json"],
            cwd=target_root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
    except OSError:
        raise SystemExit("Git preflight unavailable; no credential written.")
    if tracked or not ignored:
        raise SystemExit("config.json is still Git-tracked or not ignored; no credential written.")
    if source.stat().st_size > 65536:
        raise SystemExit("Legacy credential file is unexpectedly large.")
    try:
        previous = json.loads(source.read_text(encoding="utf-8-sig"))
        current = json.loads(destination.read_text(encoding="utf-8-sig")) if destination.is_file() else {}
    except (OSError, ValueError, UnicodeError):
        raise SystemExit("Credential JSON cannot be safely parsed.")
    if not isinstance(previous, dict) or not isinstance(current, dict):
        raise SystemExit("Credential file format invalid.")
    secret = previous.get("api_key")
    if not isinstance(secret, str) or not secret.strip():
        raise SystemExit("No nonempty API Key in the legacy source.")
    existing = current.get("api_keys", {})
    if current.get("api_key") not in (None, "") or (isinstance(existing, dict) and any(existing.values())):
        raise SystemExit("Destination has an existing API Key; refusing to overwrite.")
    if existing and not isinstance(existing, dict):
        raise SystemExit("Destination API key structure invalid.")
    result = {
        "api_keys": {"international": secret},
        "trusted_custom_endpoints": {},
    }
    if args.keep_legacy_keys:
        # The still-running 8188 V1 code reads only these old field names.
        # They are temporary in-file aliases, NOT a second config file.
        result["api_key"] = secret
        result["base_url"] = current.get("base_url") or "https://www.runninghub.cn"
    tmp = destination.with_name("config.json.pending")
    if tmp.exists():
        raise SystemExit("A pending config migration file already exists.")
    try:
        with tmp.open("x", encoding="utf-8") as file:
            json.dump(result, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp, destination)
    except OSError:
        raise SystemExit("Could not atomically write the new ignored config.json.")
    reread = json.loads(destination.read_text(encoding="utf-8"))
    if reread.get("api_keys", {}).get("international") != secret or (args.keep_legacy_keys and reread.get("api_key") != secret):
        raise SystemExit("Credential transfer verification failed.")
    print("PASS: credential moved to Git-ignored config.json (value not shown).")
    print("SOURCE_UNCHANGED: yes")

if __name__ == "__main__":
    main()
