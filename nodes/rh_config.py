"""
RH_Config Node - Configuration node for RunningHub API
Simplified configuration with clear parameter names
"""

import json
import os

class RH_Config:
    """
    Configuration node for RunningHub API credentials and settings.
    This node stores your API key and workflow/app ID for use by other nodes.
    Empty values are loaded from config.local.json first, with config.json kept
    as a backward-compatible fallback.
    """

    @staticmethod
    def load_config_file():
        """
        Load configuration from a local private config first, then fall back to
        the legacy config.json for backward compatibility.

        Returns:
            dict: Configuration dictionary or empty dict if no valid file exists
        """
        plugin_root = os.path.dirname(os.path.dirname(__file__))
        # Load the tracked legacy file first, then let non-empty values from the
        # ignored local file override it. This keeps older installations working
        # while making config.local.json the preferred place for secrets.
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
                    "tooltip": "RunningHub API key. Leave empty to use config.local.json. Node input overrides the file value; prefer leaving this blank to avoid saving secrets in workflow JSON."
                }),
                "workflow_or_app_id": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Workflow ID or AI App ID from RunningHub"
                }),
                "base_url": ("STRING", {
                    "default": "https://www.runninghub.cn",
                    "multiline": False,
                    "tooltip": "RunningHub API base URL (leave empty to load from the config files)"
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
        final_base_url = base_url.strip() if base_url and base_url.strip() else file_config.get("base_url", "https://www.runninghub.cn")
        final_workflow_id = workflow_or_app_id.strip() if workflow_or_app_id and workflow_or_app_id.strip() else file_config.get("workflow_or_app_id", "")

        # Validate required fields
        if not final_api_key:
            raise ValueError("API key is required. Provide it in the node or in config.local.json.")

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
        base_url_source = "node input" if (base_url and base_url.strip()) else "config file"
        workflow_id_source = "node input" if (workflow_or_app_id and workflow_or_app_id.strip()) else "config file"

        print(f"✓ RH Config created: {'AI App' if is_ai_app else 'Workflow'} ID={final_workflow_id}")
        print(f"  API Key: loaded from {api_source}")
        print(f"  Workflow ID: loaded from {workflow_id_source}")
        print(f"  Base URL: {final_base_url} (from {base_url_source})")

        return (config,)

