"""Multi-source RH_PARAMS merge service plus deprecated RH Execute 2 compatibility node."""

from __future__ import annotations

from .rh_execute import RH_Execute


class FlexibleRHParamsInput(dict):
    """Allow frontend-created params_N sockets to pass ComfyUI validation."""

    def __init__(self, data=None):
        super().__init__()
        self.data = data or {}
        self.update(self.data)

    def __contains__(self, key):
        return key in self.data or str(key).startswith("params_")

    def __getitem__(self, key):
        if key in self.data:
            return self.data[key]
        if str(key).startswith("params_"):
            return (
                "RH_PARAMS",
                {
                    "default": None,
                    "tooltip": "Additional RH_PARAMS source.",
                },
            )
        raise KeyError(key)


class RH_Execute2(RH_Execute):
    """Deprecated compatibility node; RH_Execute now owns the V2 multi-source behavior."""

    DEPRECATED = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "config": (
                    "RH_CONFIG",
                    {"tooltip": "RunningHub configuration from RH Config node"},
                ),
                "timeout": (
                    "INT",
                    {
                        "default": 600,
                        "min": 60,
                        "max": 3600,
                        "tooltip": "Maximum time to wait for task completion (seconds)",
                    },
                ),
            },
            "optional": FlexibleRHParamsInput(
                {
                    "params": (
                        "RH_PARAMS",
                        {
                            "default": None,
                            "tooltip": "Primary RH_PARAMS source. More params inputs appear as needed.",
                        },
                    ),
                    "use_high_performance": (
                        "BOOLEAN",
                        {
                            "default": False,
                            "tooltip": "Use RTX 4090 48GB instance (costs more credits)",
                        },
                    ),
                    "save_to_local": (
                        "BOOLEAN",
                        {
                            "default": False,
                            "tooltip": (
                                "Off: do not preserve RH originals in ComfyUI output. "
                                "On: also save RH originals to ComfyUI output."
                            ),
                        },
                    ),
                    "output_prefix": (
                        "STRING",
                        {
                            "default": "RH",
                            "multiline": False,
                            "tooltip": "Prefix used only when RH original files are preserved.",
                        },
                    ),
                }
            ),
        }

    @staticmethod
    def _params_sort_key(name):
        if name == "params":
            return (0, 1)
        try:
            return (0, int(str(name).split("_", 1)[1]))
        except (IndexError, ValueError):
            return (1, str(name))

    @classmethod
    def merge_param_sources(cls, params=None, dynamic_params=None):
        """Merge param groups without mutating any upstream list/dict."""
        sources = [("params", params)]
        for name, value in sorted(
            (dynamic_params or {}).items(),
            key=lambda item: cls._params_sort_key(item[0]),
        ):
            if str(name).startswith("params_"):
                sources.append((str(name), value))

        merged = []
        key_to_index = {}
        key_to_source = {}

        for source_name, group in sources:
            if group is None:
                continue
            if not isinstance(group, (list, tuple)):
                raise ValueError(f"RH Execute input {source_name} must be an RH_PARAMS list.")

            for item_index, item in enumerate(group, 1):
                if not isinstance(item, dict):
                    raise ValueError(
                        f"RH Execute input {source_name} item {item_index} must be an object."
                    )

                node_id = str(item.get("nodeId", "")).strip()
                field_name = str(item.get("fieldName", "")).strip()
                if not node_id or not field_name:
                    raise ValueError(
                        f"RH Execute input {source_name} item {item_index} "
                        "must contain nodeId and fieldName."
                    )

                copied = dict(item)
                copied["nodeId"] = node_id
                copied["fieldName"] = field_name
                key = (node_id, field_name)

                if key in key_to_index:
                    previous_source = key_to_source[key]
                    print(
                        "Warning: RH Execute parameter override: "
                        f"Node {node_id}.{field_name} from {previous_source} "
                        f"is replaced by {source_name}."
                    )
                    merged[key_to_index[key]] = copied
                    key_to_source[key] = source_name
                else:
                    key_to_index[key] = len(merged)
                    key_to_source[key] = source_name
                    merged.append(copied)

        return merged

    def execute(
        self,
        config,
        params=None,
        timeout=600,
        use_high_performance=False,
        save_to_local=False,
        output_prefix="RH",
        **kwargs,
    ):
        merged_params = self.merge_param_sources(params=params, dynamic_params=kwargs)
        return super().execute(
            config=config,
            params=merged_params,
            timeout=timeout,
            use_high_performance=use_high_performance,
            save_to_local=save_to_local,
            output_prefix=output_prefix,
        )
