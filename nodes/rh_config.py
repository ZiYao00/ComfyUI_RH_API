"""RH Config: one Git-ignored config.json, scoped keys and native site selection.

Keep existing V1 input positions and names for saved graphs/API prompts.
The optional site selector is appended after all legacy widgets.
"""
from __future__ import annotations

from .rh_security import (
    OFFICIAL_ORIGINS, load_private_config, canonical_origin,
    validate_api_origin, credential_for_origin,
)


class RH_Config:
    @staticmethod
    def load_config_file() -> dict:
        """Legacy method name; there is exactly one active file: config.json."""
        return load_private_config()

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {
                    "default": "", "multiline": False, "advanced": True,
                    "tooltip": "Prefer config.json (ignored by Git). Values entered here may be serialized in workflow JSON.",
                }),
                "workflow_or_app_id": ("STRING", {
                    "default": "", "multiline": False,
                    "tooltip": "Workflow or AI App ID: store large IDs as strings, never JavaScript numbers.",
                }),
                "base_url": ("STRING", {
                    "default": "https://www.runninghub.cn", "multiline": False,
                    "advanced": True, "display_name": "Custom URL / legacy base_url",
                    "tooltip": "Only used for Custom or old workflows. The original STRING input and links are preserved.",
                }),
            },
            "optional": {
                "is_ai_app": ("BOOLEAN", {
                    "default": False, "tooltip": "Run an AI App rather than a workflow.",
                }),
                "query_api": (["legacy", "v2"], {
                    "default": "legacy", "tooltip": "Existing query API; do not change production to v2 implicitly.",
                }),
                "site": (["international", "domestic", "custom"], {
                    "default": "international", "display_name": "Base URL",
                    "tooltip": "International (.ai), Domestic (.cn), or Custom (must be trusted in config.json).",
                }),
            },
        }

    RETURN_TYPES = ("RH_CONFIG",)
    RETURN_NAMES = ("config",)
    FUNCTION = "create_config"
    CATEGORY = "Ken-Chen/RH-API"

    @staticmethod
    def _selected_origin(site, base_url, settings) -> str:
        if site is None:
            # Old API prompts never contain the appended site selector. Do not
            # mistake the new UI default for the intent of an old prompt.
            previous = str(base_url or "").strip() or str(settings.get("base_url") or "").strip()
            return validate_api_origin(previous or OFFICIAL_ORIGINS["domestic"], private_config=settings)
        if site not in (*OFFICIAL_ORIGINS, "custom"):
            raise ValueError("RH Base URL selection must be international, domestic or custom.")
        if site in OFFICIAL_ORIGINS:
            return OFFICIAL_ORIGINS[site]
        custom = str(base_url or "").strip()
        if not custom:
            raise ValueError("Custom Base URL requires an explicit HTTPS origin in the legacy/custom URL field.")
        # A legacy workflow can keep a connected STRING base_url through
        # migration (site='custom'), even when that link supplies a known RH
        # official host. Both official hosts are already allowed by the
        # central origin validator. Unknown custom destinations still require
        # explicit private authorization before any credential is sent.
        return validate_api_origin(custom, private_config=settings)

    def create_config(self, api_key, workflow_or_app_id, base_url,
                      is_ai_app=False, query_api="legacy", site=None):
        settings = self.load_config_file()
        if not isinstance(settings, dict):
            raise ValueError("Invalid RH private configuration.")
        if not isinstance(workflow_or_app_id, str) or not workflow_or_app_id.strip():
            raise ValueError("Workflow / App ID must be a nonempty STRING to preserve large identifiers.")
        origin = self._selected_origin(site, base_url, settings)
        # No accidental cross-region fallback. Local keys are explicitly
        # mapped to one origin, even when imported workflows choose another.
        widget_key = str(api_key or "").strip()
        local_key = credential_for_origin(settings, origin)
        resolved_key = widget_key or local_key
        if not resolved_key:
            raise ValueError("Missing API Key for this RH site. Add it to config.json for the selected region.")
        if not isinstance(is_ai_app, bool):
            raise ValueError("is_ai_app must be BOOLEAN.")
        if query_api not in ("legacy", "v2"):
            raise ValueError("query_api must be legacy or v2.")

        # Never log API keys, private custom endpoints, prompts or media data.
        return ({
            "api_key": resolved_key,
            "workflow_or_app_id": workflow_or_app_id.strip(),
            "base_url": origin,
            "is_ai_app": is_ai_app,
            "query_api": query_api,
        },)
