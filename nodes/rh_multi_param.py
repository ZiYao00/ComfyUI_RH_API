"""
RH_MultiParams Node - Set multiple parameters for a single run.
"""

class RH_MultiParams:
    """
    A node to set up to 4 different parameters for a single RunningHub execution.
    This helps to reduce the number of RH_Param nodes in complex workflows.
    """

    MAX_PARAMS = 4

    @classmethod
    def INPUT_TYPES(cls):
        # Common field names for RunningHub workflows (same as RH_Param)
        field_names = [
            "text",           # Text prompts
            "image",          # Image inputs
            "video",          # Video inputs
            "mask",           # Mask inputs
            "seed",           # Random seed
            "steps",          # Sampling steps
            "cfg",            # CFG scale
            "sampler_name",   # Sampler name
            "scheduler",      # Scheduler
            "denoise",        # Denoise strength
            "width",          # Image width
            "height",         # Image height
            "batch_size",     # Batch size
            "model",          # Model name
            "vae",            # VAE name
            "lora",           # LoRA name
            "control_net",    # ControlNet
            "strength",       # Strength parameter
            "scale",          # Scale parameter
            "custom",         # Custom field (user input)
        ]

        inputs = {
            "required": {},
            "optional": {
                "previous_params": ("RH_PARAMS", {
                    "tooltip": "Connect previous RH_Param or RH_MultiParams node to chain parameters"
                })
            }
        }

        # Dynamically create 4 sets of inputs with dropdown for field_name
        for i in range(1, cls.MAX_PARAMS + 1):
            inputs["optional"][f"node_id_{i}"] = ("STRING", {
                "multiline": False,
                "default": "",
                "tooltip": f"Node ID in the workflow for parameter {i}"
            })
            inputs["optional"][f"field_name_{i}"] = (field_names, {
                "default": "text",
                "tooltip": f"Field name to modify for parameter {i} - select from common types or use 'custom'"
            })
            inputs["optional"][f"field_value_{i}"] = ("STRING", {
                "multiline": True,
                "default": "",
                "tooltip": f"Value to set for parameter {i}"
            })
            inputs["optional"][f"custom_field_name_{i}"] = ("STRING", {
                "multiline": False,
                "default": "",
                "tooltip": f"Custom field name for parameter {i} (only used when field_name_{i} is 'custom')"
            })

        return inputs

    RETURN_TYPES = ("RH_PARAMS",)
    FUNCTION = "bundle_params"
    CATEGORY = "Ken-Chen/RH-API"

    def bundle_params(self, previous_params=None, **kwargs):
        """
        Bundle multiple parameters into a single list.

        Args:
            previous_params: Previous parameter list (for chaining)
            **kwargs: Dynamic keyword arguments containing node_id, field_name, field_value,
                     and custom_field_name for each parameter slot

        Returns:
            Updated parameter list
        """
        # Initialize with previous params if they exist
        params_list = []
        if previous_params:
            params_list.extend(previous_params)

        new_params_count = 0
        for i in range(1, self.MAX_PARAMS + 1):
            node_id = str(kwargs.get(f"node_id_{i}") or "").strip()
            field_name = str(kwargs.get(f"field_name_{i}") or "").strip()
            field_value = kwargs.get(f"field_value_{i}", "")
            custom_field_name = str(kwargs.get(f"custom_field_name_{i}") or "").strip()

            # An untouched field dropdown defaults to text even in unused rows.
            # A changed field, value, node ID or custom field means the row is
            # configured and must never disappear silently.
            active = (
                bool(node_id or custom_field_name)
                or field_name not in ("", "text")
                or field_value not in (None, "")
            )
            if not active:
                continue
            if not node_id:
                raise ValueError(f"RH MultiParams slot {i} requires Node ID.")
            if not field_name:
                raise ValueError(f"RH MultiParams slot {i} requires Field.")
            actual_field_name = custom_field_name if field_name == "custom" else field_name
            if not actual_field_name:
                raise ValueError(f"RH MultiParams slot {i} requires Custom Field.")

            params_list.append({
                "nodeId": node_id,
                "fieldName": actual_field_name,
                "fieldValue": field_value,
            })
            new_params_count += 1
            # Prompt values are deliberately not printed in normal logs.
            print(f"RH MultiParams: Added slot {i} for Node {node_id}.{actual_field_name}")

        if new_params_count == 0 and not previous_params:
            print("⚠ Warning: RH_MultiParams - No new parameters were set and no previous params were provided.")
            return ([],)

        print(f"✓ RH MultiParams: Bundled {len(params_list)} total parameters ({new_params_count} from this node).")
        return (params_list,)

