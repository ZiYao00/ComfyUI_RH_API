"""
RH_Execute Node - Execute RunningHub workflows and AI apps
Simplified execution with automatic progress tracking and output handling
"""

# Import shared logic from rh_utils
from .rh_utils import _monitor_task, _get_outputs, _create_placeholder_image, _create_placeholder_latent
from .rh_client import RHClient, RHTaskSubmissionUncertainError

try:
    import comfy.utils
    COMFY_AVAILABLE = True
except ImportError:
    COMFY_AVAILABLE = False


class RH_Execute:
    """
    Execute RunningHub workflows or AI apps.
    Handles task creation, monitoring, and output processing automatically.
    """
    
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "config": ("RH_CONFIG", {
                    "tooltip": "RunningHub configuration from RH_Config node"
                }),
                "timeout": ("INT", {
                    "default": 600,
                    "min": 60,
                    "max": 3600,
                    "tooltip": "Maximum time to wait for task completion (seconds)"
                }),
            },
            "optional": {
                "params": ("RH_PARAMS", {
                    "default": None,
                    "tooltip": "Parameters from RH_Param nodes (optional)"
                }),
                "use_high_performance": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Use RTX 4090 48GB instance (costs more credits)"
                }),
                "save_to_local": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Save images and videos to ComfyUI output directory"
                }),
                "output_prefix": ("STRING", {
                    "default": "RH",
                    "multiline": False,
                    "tooltip": "Prefix for saved files (e.g., 'RH' -> 'RH_001.png')"
                }),
            },
        }
    
    RETURN_TYPES = ("IMAGE", "IMAGE", "STRING", "AUDIO", "VIDEO", "LATENT", "STRING")
    RETURN_NAMES = ("images", "video_frames", "text", "audio", "video", "latent", "task_id")
    FUNCTION = "execute"
    CATEGORY = "Ken-Chen/RH-API"
    OUTPUT_NODE = True
    
    def execute(self, config, params=None, timeout=600, use_high_performance=False,
                save_to_local=True, output_prefix="RH"):
        """
        Execute RunningHub workflow or AI app

        Args:
            config: Configuration from RH_Config node
            params: Parameters from RH_Param nodes
            timeout: Maximum execution time
            use_high_performance: Use high-performance instance
            save_to_local: Save outputs to local directory
            output_prefix: Prefix for saved files

        Returns:
            Tuple of (images, video_frames, text, audio, video)
        """
        print("=" * 60)
        print("🚀 Starting RunningHub Execution")
        print("=" * 60)

        # Validate config
        self._validate_config(config)
        
        # Create task
        task_id = self._create_task(config, params or [], use_high_performance)
        print(f"✓ Task created: {task_id}")
        
        # Monitor task using shared utility function
        _monitor_task(task_id, config, timeout)
        print("✓ Task completed")

        # Get and process outputs using shared utility function
        outputs = _get_outputs(task_id, config, save_to_local, output_prefix)
        print("✓ Outputs processed")

        # Handle case where task completes with no output
        if outputs is None:
            outputs = (
                _create_placeholder_image("No image output"),
                _create_placeholder_image("No video output"),
                "",
                None,
                None,
                _create_placeholder_latent(),
            )

        print("=" * 60)
        print("✅ Execution completed successfully")
        print("=" * 60)

        return outputs + (task_id,)



    def _validate_config(self, config):
        """Validate configuration"""
        if not isinstance(config, dict):
            raise ValueError("Invalid config: must be a dictionary from RH_Config node")

        required_fields = ["api_key", "workflow_or_app_id", "base_url"]
        for field in required_fields:
            if field not in config or not config[field]:
                raise ValueError(f"Missing required config field: {field}")

    def _create_task(self, config, params, use_high_performance):
        """Create task through the shared RH client safety boundary."""
        print("Creating task (single safe attempt)...")
        task_id = RHClient(config["api_key"], config["base_url"]).create_task(
            workflow_or_app_id=config["workflow_or_app_id"],
            params=params,
            is_ai_app=config.get("is_ai_app", False),
            use_high_performance=use_high_performance,
        )
        print("ℹ Using HTTP polling for task monitoring (WebSocket disabled for stability)")
        return task_id











