"""RH Upload Image 2 - multi-image uploader for a single RunningHub execution."""

from __future__ import annotations

from io import BytesIO

from .rh_params2 import ANY_TYPE, FlexibleOptionalInputType
from .rh_upload_image import RH_UploadImage
from .rh_utils import upload_file_to_rh


IMAGE_FIELD_NAMES = [
    "image",
    "init_image",
    "control_image",
    "mask",
    "reference",
    "custom",
]


class RH_UploadImage2:
    """Upload multiple images with independent RH node/field routing."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "config": (
                    "RH_CONFIG",
                    {"tooltip": "RunningHub configuration from RH Config node"},
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
    FUNCTION = "upload"
    CATEGORY = "Ken-Chen/RH-API"

    @staticmethod
    def _slot_number(name, prefix):
        try:
            return int(str(name).split(prefix, 1)[1])
        except (IndexError, ValueError):
            return 10**9

    @classmethod
    def _iter_rows(cls, kwargs):
        rows = [
            (name, value)
            for name, value in kwargs.items()
            if str(name).startswith("image_meta_")
        ]
        rows.sort(key=lambda item: cls._slot_number(item[0], "image_meta_"))
        return rows

    @staticmethod
    def _resolve_field_name(row, slot):
        field_name = str(row.get("field_name", "image") or "image").strip()
        custom_field_name = str(row.get("custom_field_name", "")).strip()

        if field_name == "custom":
            if not custom_field_name:
                raise ValueError(
                    f"RH Upload Image 2 row {slot} uses custom but custom_field_name is empty."
                )
            return custom_field_name
        return field_name

    def upload(self, config, previous_params=None, **kwargs):
        if not isinstance(config, dict) or "api_key" not in config or "base_url" not in config:
            raise ValueError("Invalid config: must be from RH_Config node")

        api_key = config["api_key"]
        base_url = config["base_url"]
        params = [dict(item) for item in (previous_params or [])]
        converter = RH_UploadImage()

        for row_name, row in self._iter_rows(kwargs):
            if not isinstance(row, dict):
                raise ValueError(f"RH Upload Image 2 input {row_name} must be an object.")

            if row.get("enabled", True) is False:
                continue

            slot = self._slot_number(row_name, "image_meta_")
            image_key = f"image_{slot}"
            image = kwargs.get(image_key)

            if image is None:
                continue

            node_id = str(row.get("node_id", "")).strip()
            if not node_id:
                raise ValueError(f"RH Upload Image 2 row {slot} is missing node_id.")

            actual_field_name = self._resolve_field_name(row, slot)
            if not actual_field_name:
                raise ValueError(f"RH Upload Image 2 row {slot} is missing field_name.")

            pil_image = converter._tensor_to_pil(image)
            buffer = BytesIO()
            pil_image.save(buffer, format="PNG")
            buffer_size = buffer.tell()
            buffer.seek(0)

            max_size = 10 * 1024 * 1024
            if buffer_size > max_size:
                raise ValueError(
                    f"RH Upload Image 2 row {slot} image size "
                    f"{buffer_size / 1024 / 1024:.2f}MB exceeds 10MB limit"
                )

            filename = upload_file_to_rh(
                api_key=api_key,
                base_url=base_url,
                file_buffer=buffer,
                file_name=f"image_{slot}.png",
                content_type="image/png",
                file_type="image",
            )

            params.append(
                {
                    "nodeId": node_id,
                    "fieldName": actual_field_name,
                    "fieldValue": filename,
                }
            )

        return (params,)
