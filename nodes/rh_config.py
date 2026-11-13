"""
RH_Config Node - Configuration node for RunningHub API
Simplified configuration with clear parameter names
"""

import json
import os
from urllib.parse import urlsplit


_OFFICIAL_ENDPOINTS = {"www.runninghub.ai", "www.runninghub.cn"}


def _validated_endpoint(url, trusted_custom_endpoints=None):
    """Never send a locally stored API key to an untrusted workflow URL."""
    raw = str(url or "").strip()
    try:
        parsed = urlsplit(raw)
        valid_https_root = (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and parsed.port is None
            and parsed.path in ("", "/")
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        valid_https_root = False

    if not valid_https_root:
        raise ValueError("RunningHub base_url must be an HTTPS origin without credentials, port, path or query.")

    origin = raw.rstrip("/")
    if parsed.hostname in _OFFICIAL_ENDPOINTS:
        return origin

    # An imported workflow cannot add a trusted endpoint; only private config can.
    custom = trusted_custom_endpoints if isinstance(trusted_custom_endpoints, dict) else {}
    trusted_origins = {
        value.strip().rstrip("/")
        for value in custom.values()
        if isinstance(value, str)
    }
    if origin not in trusted_origins:
        raise ValueError(
            "Untrusted RunningHub API base_url. Use www.runninghub.ai or www.runninghub.cn; "
            "for an intentional custom HTTPS proxy, add its exact origin to "
            "trusted_custom_endpoints in private config.json."
        )
    return origin


class RH_Config:
    """
    Configuration node for RunningHub API credentials and settings.
    This node stores your API key and workflow/app ID for use by other nodes.
    Blank fields load from private config.json; legacy config.local.json may override
    nonempty fields when both files exist (backward compatibility).
    """

    @staticmethod
    def load_config_file():
        """
        Load config.json first, then apply nonempty values from optional legacy
        config.local.json for compatibility. New installs use only config.json.

        Returns:
            dict: Configuration dictionary or empty dict if no valid file exists
        """
        plugin_root = os.path.dirname(os.path.dirname(__file__))
        # Load the private config first, then let nonempty values from the
        # legacy local file override it. This keeps older installations working
        # without forcing an unsafe migration of existing private settings.
        config_paths = [
            os.path.join(plugin_root, "config.json"),
            os.path.join(plugin_root, "config.local.json"),
        ]
        merged_config = {}
        loaded_files = []

        for config_path in config_paths:
            if not os.path.exists(config_path):
                continue

            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                if not isinstance(config, dict):
                    raise ValueError("configuration root must be a JSON object")

                for key, value in config.items():
                    if value is not None and value != "":
                        merged_config[key] = value
                loaded_files.append(os.path.basename(config_path))
            except Exception as e:
                print(f"⚠️ Error loading {os.path.basename(config_path)}: {e}")

        if loaded_files:
            print(f"✓ Loaded RH configuration from: {', '.join(loaded_files)}")
        else:
            print("ℹ️ No valid RH configuration file found")

        return merged_config
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "RunningHub API key. Leave blank to use private config.json; do not save credentials in shared workflows."
                }),
                "workflow_or_app_id": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Workflow ID or AI App ID from RunningHub"
                }),
                "base_url": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Leave blank to use config.json or the domestic default. Only official HTTPS sites or private-config trusted custom proxies are accepted."
                }),
            },
            "optional": {
                "is_ai_app": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Enable this if calling an AI App instead of a workflow"
                }),
                "query_api": (["legacy", "v2"], {
                    "default": "legacy",
                    "tooltip": "Task result query API. Keep 'legacy' for existing workflows; use 'v2' only for compatibility testing until validated."
                }),
            }
        }
    
    RETURN_TYPES = ("RH_CONFIG",)
    RETURN_NAMES = ("config",)
    FUNCTION = "create_config"
    CATEGORY = "Ken-Chen/RH-API"
    
    def create_config(self, api_key, workflow_or_app_id, base_url, is_ai_app=False, query_api="legacy"):
        """
        Create configuration dictionary for RunningHub API

        Args:
            api_key: Your RunningHub API key (if empty, loads from the local config file)
            workflow_or_app_id: Workflow ID or AI App ID
            base_url: API base URL (if empty, loads from the local config file)
            is_ai_app: Whether this is an AI App (True) or workflow (False)

        Returns:
            Configuration dictionary
        """
        # Load configuration from file if needed
        file_config = self.load_config_file()

        # Node inputs have the highest priority. Use file config as a fallback.
        final_api_key = api_key.strip() if api_key and api_key.strip() else file_config.get("api_key", "")
        final_base_url = base_url.strip() if base_url and base_url.strip() else (file_config.get("base_url") or "https://www.runninghub.cn")
        final_base_url = _validated_endpoint(final_base_url, file_config.get("trusted_custom_endpoints"))
        final_workflow_id = workflow_or_app_id.strip() if workflow_or_app_id and workflow_or_app_id.strip() else file_config.get("workflow_or_app_id", "")

        # Validate required fields
        if not final_api_key:
            raise ValueError("API key is required. Put it in private config.json or the RH Config node.")

        if not final_workflow_id:
            raise ValueError("Workflow ID or AI App ID is required. Provide it in the node or in a config file.")

        final_query_api = str(query_api or file_config.get("query_api", "legacy")).strip().lower()
        if final_query_api not in {"legacy", "v2"}:
            raise ValueError("query_api must be 'legacy' or 'v2'.")

        config = {
            "api_key": final_api_key,
            "workflow_or_app_id": final_workflow_id,
            "base_url": final_base_url,
            "is_ai_app": is_ai_app,
            "query_api": final_query_api,
        }

        # Show where values came from
        api_source = "node input" if (api_key and api_key.strip()) else "config file"
        base_url_source = "node input" if (base_url and base_url.strip()) else ("config file" if file_config.get("base_url") else "default")
        workflow_id_source = "node input" if (workflow_or_app_id and workflow_or_app_id.strip()) else "config file"

        print(f"✓ RH Config created: {'AI App' if is_ai_app else 'Workflow'} ID={final_workflow_id}")
        print(f"  API Key: loaded from {api_source}")
        print(f"  Workflow ID: loaded from {workflow_id_source}")
        print(f"  Base URL: {final_base_url} (from {base_url_source})")

        return (config,)

