"""
RH_UploadVideo Node - Upload videos to RunningHub
Simplified video upload
"""

import io
import os
import folder_paths
from .rh_utils import upload_file_to_rh


class RH_UploadVideo:
    """
    Upload video file to RunningHub and get filename for use in workflows.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        # Common field names for video inputs
        field_names = [
            "video",          # Video input
            "init_video",     # Initial video
            "reference",      # Reference video
            "custom",         # Custom field name
        ]

        return {
            "required": {
                "config": ("RH_CONFIG", {
                    "tooltip": "RunningHub configuration from RH_Config node"
                }),
                "video": ("VIDEO", {
                    "tooltip": "Video input from Load_AF_Video or other video nodes"
                }),
            },
            "optional": {
                "node_id": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Node ID to set parameter (leave empty to skip parameter setting)"
                }),
                "field_name": (field_names, {
                    "default": "video",
                    "tooltip": "Field name to set (only used if node_id is provided)"
                }),
                "custom_field_name": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Custom field name (only used when field_name is 'custom')"
                }),
                "previous_params": ("RH_PARAMS", {
                    "default": None,
                    "tooltip": "Connect previous params to chain parameters"
                }),
            }
        }

    RETURN_TYPES = ("STRING", "RH_PARAMS")
    RETURN_NAMES = ("filename", "params")
    FUNCTION = "upload"
    CATEGORY = "Ken-Chen/RH-API"
    
    def upload(self, config, video, node_id="", field_name="video", custom_field_name="", previous_params=None):
        """
        Upload video to RunningHub and optionally set parameter

        Args:
            config: Configuration from RH_Config node
            video: VIDEO object from Load_AF_Video or video path string
            node_id: Node ID to set parameter (optional)
            field_name: Field name to set (optional)
            custom_field_name: Custom field name (optional)
            previous_params: Previous parameter list (optional)

        Returns:
            Tuple of (filename, params)
        """
        print("📤 Uploading video to RunningHub...")

        # Validate config
        if not isinstance(config, dict) or "api_key" not in config or "base_url" not in config:
            raise ValueError("Invalid config: must be from RH_Config node")

        if not video:
            raise ValueError("Video input is required")

        api_key = config["api_key"]
        base_url = config["base_url"]

        # Resolve the VIDEO input into either a filesystem path or a stream.
        # ComfyUI 0.34+ wraps uploaded videos in VideoInput/VideoFromFile and
        # exposes the underlying source through get_stream_source(). Older
        # video nodes may still provide a string path or path-like attributes.
        video_source = video
        if hasattr(video, "get_stream_source") and callable(video.get_stream_source):
            video_source = video.get_stream_source()
        elif isinstance(video, os.PathLike):
            video_source = os.fspath(video)
        elif hasattr(video, "file_path"):
            video_source = video.file_path
        elif hasattr(video, "filename"):
            video_source = video.filename

        def _upload_stream(file_buffer, file_name):
            return upload_file_to_rh(
                api_key=api_key,
                base_url=base_url,
                file_buffer=file_buffer,
                file_name=file_name,
                content_type="application/octet-stream",
                file_type="video",
            )

        try:
            if isinstance(video_source, os.PathLike):
                video_source = os.fspath(video_source)

            if isinstance(video_source, str):
                if not os.path.exists(video_source):
                    raise FileNotFoundError(f"Video file not found: {video_source}")

                print(f"📹 Found video: {video_source}")
                with open(video_source, "rb") as f:
                    filename = _upload_stream(f, os.path.basename(video_source))

            elif isinstance(video_source, io.BytesIO) or hasattr(video_source, "read"):
                if hasattr(video_source, "seek"):
                    video_source.seek(0)

                source_name = getattr(video_source, "name", "")
                file_name = os.path.basename(source_name) if isinstance(source_name, str) and source_name else "video.mp4"
                print(f"📹 Found in-memory video stream: {file_name}")
                filename = _upload_stream(video_source, file_name)

            else:
                raise TypeError(
                    "Unsupported VIDEO input type: "
                    f"{type(video).__module__}.{type(video).__name__}. "
                    "Expected a file path, readable stream, or ComfyUI VideoInput."
                )
        except Exception as e:
            raise Exception(f"Failed to upload video: {e}") from e

        # Create parameter if node_id is provided
        params = list(previous_params) if previous_params else []

        if node_id and node_id.strip():
            # Determine actual field name
            actual_field_name = field_name
            if field_name == "custom" and custom_field_name.strip():
                actual_field_name = custom_field_name.strip()
            elif field_name == "custom" and not custom_field_name.strip():
                print("⚠ Warning: field_name is 'custom' but custom_field_name is empty. Using 'custom' as field name.")

            # Add parameter
            new_param = {
                "nodeId": str(node_id).strip(),
                "fieldName": actual_field_name.strip(),
                "fieldValue": filename
            }
            params.append(new_param)
            print(f"✓ RH Param added: Node {node_id}.{actual_field_name} = {filename}")

        return (filename, params)

