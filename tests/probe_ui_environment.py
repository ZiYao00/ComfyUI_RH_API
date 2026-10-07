"""Read-only ComfyUI UI capability probe. Never queues a prompt or installs packages."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def get(url: str):
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8188")
    args = parser.parse_args()
    parsed = urllib.parse.urlparse(args.url)
    if parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        parser.error("Only a loopback ComfyUI URL is accepted.")
    base = args.url.rstrip("/")
    result = {
        "project": str(ROOT),
        "probe_python": sys.executable,
        "probe_python_version": sys.version.split()[0],
        "node": shutil.which("node"),
        "packages": {},
        "url": base,
    }
    for name in ("comfyui-frontend-package", "playwright", "torch", "pytest"):
        try:
            result["packages"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result["packages"][name] = None
    try:
        result["comfy_api_importable"] = importlib.util.find_spec("comfy_api") is not None
        stats = json.loads(get(base + "/system_stats"))
        system = stats.get("system", {})
        # Do not print argv, usernames, credential/config data or device details.
        result["running_comfyui"] = {
            key: system[key] for key in (
                "comfyui_version", "required_frontend_version", "installed_templates_version",
                "python_version", "embedded_python", "pytorch_version", "os"
            ) if key in system
        }
        extensions = json.loads(get(base + "/extensions"))
        result["rh_extensions"] = [item for item in extensions if "rh_" in item.lower() or "runninghub" in item.lower()]
        matches = {}
        for url in result["rh_extensions"]:
            filename = urllib.parse.unquote(urllib.parse.urlparse(url).path).rsplit("/", 1)[-1]
            local = ROOT / "js" / filename
            if local.is_file():
                served = get(base + url)
                matches[filename] = {
                    "same_bytes_as_project": served == local.read_bytes(),
                    "served_sha256": hashlib.sha256(served).hexdigest(),
                    "extension_url": url,
                }
        result["script_matches"] = matches
        info = json.loads(get(base + "/object_info/RH_Params2"))
        result["params2_registered"] = "RH_Params2" in info
        result["object_info_response_keys"] = list(info)[:8]
        result["registered_rh_nodes"] = []
        for node_id in ("RH_Param", "RH_Params2", "RH_UploadImage", "RH_UploadImage2", "RH_UploadVideo", "RH_UploadAudio"):
            node_info = json.loads(get(base + "/object_info/" + node_id))
            if node_id in node_info:
                result["registered_rh_nodes"].append(node_id)
        argv = system.get("argv", [])
        if argv and str(argv[0]).lower().endswith(".py"):
            result["running_entry_script"] = argv[0]
        if sys.platform == "win32":
            import subprocess
            port = parsed.port or 80
            ps = (
                "$ErrorActionPreference='Stop'; "
                "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); "
                f"$connections=Get-NetTCPConnection -LocalPort {port} -State Listen; "
                "$procId=$connections[0].OwningProcess; "
                "$p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$procId); "
                "@{executable=$p.ExecutablePath;command=$p.CommandLine}|ConvertTo-Json -Compress"
            )
            proc = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps], capture_output=True, timeout=15)
            if proc.returncode == 0:
                process = json.loads(proc.stdout.decode("utf-8-sig"))
                result["server_python"] = process.get("executable")
                # Command line is deliberately not emitted: it may contain secrets.
                import re
                candidates = re.findall(r'(?:"([^"\r\n]+main\.py)"|([^\s"]+main\.py))', process.get("command") or "")
                result["server_entry_candidates"] = [a or b for a, b in candidates]
        result["params2_input_names"] = {
            section: list(values) for section, values in info.get("RH_Params2", {}).get("input", {}).items()
            if isinstance(values, dict)
        }
    except (OSError, ValueError, urllib.error.URLError) as exc:
        result["probe_error"] = f"{type(exc).__name__}: {exc}"
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
