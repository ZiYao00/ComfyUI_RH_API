"""RH Params V2 compatibility parser and multi-parameter builder."""

from __future__ import annotations


FIELD_NAMES = [
    "text",
    "image",
    "video",
    "mask",
    "seed",
    "steps",
    "cfg",
    "sampler_name",
    "scheduler",
    "denoise",
    "width",
    "height",
    "batch_size",
    "model",
    "vae",
    "lora",
    "control_net",
    "strength",
    "scale",
    "custom",
]


class AnyType(str):
    """Wildcard ComfyUI type compatible with the established rgthree pattern."""

    def __ne__(self, other):
        return False


ANY_TYPE = AnyType("*")


class FlexibleOptionalInputType(dict):
    """Accept frontend-created widgets and value sockets."""

    def __init__(self, input_type, data=None):
        super().__init__()
        self.input_type = input_type
        self.data = data or {}
        self.update(self.data)

    def __contains__(self, key):
        return True

    def __getitem__(self, key):
        if key in self.data:
            return self.data[key]
        return (self.input_type,)


class RH_Params2:
    """Build multiple RunningHub parameters inside one node."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "param_count": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 16,
                        "step": 1,
                        "tooltip": "Number of RH parameter slots and value sockets.",
                    },
                ),
            },
            "optional": FlexibleOptionalInputType(
                ANY_TYPE,
                data={
                    "previous_params": (
                        "RH_PARAMS",
                        {
                            "default": None,
                            "tooltip": "Optional upstream RH_PARAMS for chaining.",
                        },
                    ),
                },
            ),
        }

    RETURN_TYPES = ("RH_PARAMS",)
    RETURN_NAMES = ("params",)
    FUNCTION = "build_params"
    CATEGORY = "Ken-Chen/RH-API"

    @staticmethod
    def _slot_number(name, prefix):
        try:
            return int(str(name).split(prefix, 1)[1])
        except (IndexError, ValueError):
            return 10**9

    @staticmethod
    def _stringify_value(value):
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    @staticmethod
    def _clamp_count(value):
        try:
            return max(1, min(16, int(value)))
        except (TypeError, ValueError):
            return 1

    @classmethod
    def _legacy_slot_numbers(cls, kwargs):
        slots = []
        for name in kwargs:
            text = str(name)
            if text.startswith("param_") and text[len("param_"):].isdigit():
                slots.append(cls._slot_number(text, "param_"))
        return sorted(set(slots))

    @classmethod
    def _dynamic_slot_numbers(cls, kwargs):
        prefixes = (
            "node_id_",
            "field_name_",
            "custom_field_name_",
            "local_value_",
            "value_",
        )
        slots = set()
        for name in kwargs:
            text = str(name)
            for prefix in prefixes:
                if text.startswith(prefix) and text[len(prefix):].isdigit():
                    slots.add(cls._slot_number(text, prefix))
                    break
        return sorted(slots)

    @classmethod
    def _resolve_count(cls, param_count, kwargs):
        if param_count is not None:
            return cls._clamp_count(param_count)

        discovered = cls._legacy_slot_numbers(kwargs) + cls._dynamic_slot_numbers(kwargs)
        return cls._clamp_count(max(discovered) if discovered else 1)

    @staticmethod
    def _legacy_row(kwargs, slot):
        row = kwargs.get(f"param_{slot}")
        return row if isinstance(row, dict) else {}

    def build_params(self, param_count=None, previous_params=None, **kwargs):
        params = [dict(item) for item in (previous_params or [])]
        count = self._resolve_count(param_count, kwargs)

        for slot in range(1, count + 1):
            legacy = self._legacy_row(kwargs, slot)
            if legacy.get("enabled", True) is False:
                continue

            node_id = str(
                kwargs.get(f"node_id_{slot}", legacy.get("node_id", "")) or ""
            ).strip()
            field_name = str(
                kwargs.get(
                    f"field_name_{slot}",
                    legacy.get("field_name", "text"),
                )
                or "text"
            ).strip()
            custom_field_name = str(
                kwargs.get(
                    f"custom_field_name_{slot}",
                    legacy.get("custom_field_name", ""),
                )
                or ""
            ).strip()
            local_value = kwargs.get(
                f"local_value_{slot}",
                legacy.get("local_value", legacy.get("field_value", "")),
            )

            external_key = f"value_{slot}"
            has_external_value = external_key in kwargs
            field_value = kwargs.get(external_key) if has_external_value else local_value

            if not node_id and not has_external_value and field_value in ("", None):
                continue
            if not node_id:
                raise ValueError(f"RH Params V2 row {slot} is missing node_id.")

            if field_name == "custom":
                if not custom_field_name:
                    raise ValueError(
                        f"RH Params V2 row {slot} uses custom but custom_field_name is empty."
                    )
                actual_field_name = custom_field_name
            else:
                actual_field_name = field_name

            if not actual_field_name:
                raise ValueError(f"RH Params V2 row {slot} is missing field_name.")

            params.append(
                {
                    "nodeId": node_id,
                    "fieldName": actual_field_name,
                    "fieldValue": self._stringify_value(field_value),
                }
            )

        return (params,)
