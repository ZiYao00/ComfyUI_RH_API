"""Explicit video frame decoding policy shared by RH Execute and RH Download.

VIDEO remains the lazy file-backed ComfyUI output. Only the legacy IMAGE
video_frames output is affected by these choices.
"""

VIDEO_FRAME_MODES = ("all_frames", "preview_only", "disabled")


def validate_video_frame_mode(mode: str) -> str:
    """Reject unsupported selections before remote task creation or download."""
    if not isinstance(mode, str) or mode not in VIDEO_FRAME_MODES:
        raise ValueError(
            "video_frame_mode must be one of: all_frames, preview_only, disabled."
        )
    return mode
