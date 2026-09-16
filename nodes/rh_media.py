"""Adapters from preserved RH files to ComfyUI media types.

Raw-file persistence belongs to rh_outputs.py. This module only performs local
conversion after the original RunningHub file has already been preserved.
"""

from __future__ import annotations

import os


try:
    import torch
except ImportError:  # pragma: no cover - ComfyUI runtime normally provides torch
    torch = None

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

try:
    from comfy_extras.nodes_audio import load as comfy_load_audio
except Exception:  # ComfyUI versions before the PyAV loader, or non-Comfy test runtimes
    comfy_load_audio = None

try:
    import torchaudio
except Exception:  # torchaudio can fail with DLL/backend errors, not only ImportError
    torchaudio = None

try:
    from comfy_api.latest import InputImpl
except Exception:  # Older ComfyUI releases do not expose the current Video API
    InputImpl = None

try:
    from safetensors.torch import load_file as load_safetensors_file
except ImportError:  # pragma: no cover
    load_safetensors_file = None


def load_image(filepath: str):
    if torch is None or np is None or Image is None:
        raise RuntimeError("IMAGE conversion requires torch, numpy and Pillow")

    with Image.open(filepath) as image:
        rgb = image.convert("RGB")
        array = np.array(rgb).astype(np.float32) / 255.0
    return torch.from_numpy(array).unsqueeze(0)


def load_text(filepath: str) -> str:
    with open(filepath, "rb") as handle:
        raw = handle.read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def load_audio(filepath: str):
    """Return the standard ComfyUI AUDIO mapping from a preserved local file."""
    if comfy_load_audio is not None:
        waveform, sample_rate = comfy_load_audio(filepath)
        return {"waveform": waveform.unsqueeze(0), "sample_rate": sample_rate}

    if torchaudio is not None:
        waveform, sample_rate = torchaudio.load(filepath)
        return {"waveform": waveform.unsqueeze(0), "sample_rate": sample_rate}

    raise RuntimeError("No compatible ComfyUI/PyAV or torchaudio audio decoder is available")


def load_video(filepath: str):
    """Create the current lazy ComfyUI VIDEO object without decoding all frames."""
    if InputImpl is None:
        raise RuntimeError("This ComfyUI version does not expose InputImpl.VideoFromFile")
    return InputImpl.VideoFromFile(filepath)


def extract_video_frames(filepath: str):
    """Legacy compatibility path for RH_Execute.video_frames.

    This intentionally remains separate from VIDEO creation. It may use substantial
    memory for long videos and should not be used by new workflows.
    """
    if cv2 is None or torch is None or np is None:
        return []

    cap = cv2.VideoCapture(filepath)
    frames = []
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(torch.from_numpy(frame_rgb.astype(np.float32) / 255.0).unsqueeze(0))
    finally:
        cap.release()
    return frames


def load_latent(filepath: str):
    if load_safetensors_file is None:
        raise RuntimeError("safetensors is not available")
    return load_safetensors_file(filepath)


def describe_media_support() -> dict:
    """Small diagnostic surface used by logs/tests without exposing secrets."""
    return {
        "image": torch is not None and np is not None and Image is not None,
        "audio": comfy_load_audio is not None or torchaudio is not None,
        "video": InputImpl is not None,
        "video_frames": cv2 is not None and torch is not None and np is not None,
        "latent": load_safetensors_file is not None,
    }
