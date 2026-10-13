"""
RH_MultiUploadImage Node - Upload multiple images for batch execution.
"""

import torch
import numpy as np
from PIL import Image
import io

from .rh_utils import upload_file_to_rh

class RH_BatchUploadImage:
    """
    A node to upload up to 8 images to RunningHub for batch execution.
    Each image will be treated as a separate run.
    """

    MAX_UPLOADS = 8

    @classmethod
    def INPUT_TYPES(cls):
        inputs = {
            "required": {
                "config": ("RH_CONFIG",),
                "node_id": ("STRING", {"multiline": False, "default": ""}),
                "field_name": (["image", "control_image", "mask"],),
            },
            "optional": {}
        }
        for i in range(1, cls.MAX_UPLOADS + 1):
            inputs["optional"][f"image_{i}"] = ("IMAGE",)

        return inputs

    RETURN_TYPES = ("RH_PARAM_BUNDLE",)
    FUNCTION = "upload_batch"
    CATEGORY = "Ken-Chen/RH-API"

    def upload_batch(self, config, node_id, field_name, **kwargs):
        api_key = config.get("api_key")
        base_url = config.get("base_url")
        batch_bundle = []

        node_id = str(node_id or "").strip()
        field_name = str(field_name or "").strip()
        if not node_id:
            raise ValueError("RH BatchUploadImage requires Node ID before uploading images.")
        if not field_name:
            raise ValueError("RH BatchUploadImage requires Field before uploading images.")

        connected = [
            (i, kwargs.get(f"image_{i}"))
            for i in range(1, self.MAX_UPLOADS + 1)
            if kwargs.get(f"image_{i}") is not None
        ]
        if not connected:
            raise ValueError("RH BatchUploadImage has no connected images.")

        for i, image_tensor in connected:
            img_np = image_tensor.cpu().numpy()
            img_pil = Image.fromarray((img_np.squeeze(0) * 255).astype(np.uint8))
            buffer = io.BytesIO()
            img_pil.save(buffer, format="PNG")
            rh_file_path = upload_file_to_rh(
                api_key=api_key, base_url=base_url, file_buffer=buffer,
                file_name=f"batch_upload_{i}.png", content_type="image/png", file_type="image"
            )
            if not rh_file_path:
                raise RuntimeError(
                    f"RH BatchUploadImage image_{i} upload failed; incomplete batch aborted."
                )
            batch_bundle.append([{
                "nodeId": node_id, "fieldName": field_name, "fieldValue": rh_file_path
            }])

        print(f"[Info] Bundled {len(batch_bundle)} runs for batch execution.")
        return (batch_bundle,)
