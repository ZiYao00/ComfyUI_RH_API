"""Offline CPU codec probe for bounded RH legacy video-frame extraction.

Uses the installed ComfyUI Python, creates a tiny temporary AVI and checks
one-frame preview versus full extraction. Never calls RunningHub.
"""
from __future__ import annotations
import argparse
import importlib
from pathlib import Path
import sys
import tempfile
import types


def main():
    parser = argparse.ArgumentParser()
    parser.parse_args()
    # Keep this CPU-only: use packages from ComfyUI embedded Python without
    # importing ComfyUI Core, which may initialize unsupported local CUDA.

    print("Probe stage: imports", flush=True)
    import cv2
    import numpy as np
    print("Probe stage: codec dependencies ready", flush=True)
    import torch
    print("Probe stage: torch CPU available", flush=True)

    # Isolate unrelated ComfyUI video/audio initialization. This exercise
    # targets the real CV2 + Torch frame decoder, NOT the lazy VIDEO adapter.
    optional_video = types.ModuleType("comfy_api.latest")
    optional_video.InputImpl = None
    sys.modules["comfy_api.latest"] = optional_video
    optional_audio = types.ModuleType("comfy_extras.nodes_audio")
    optional_audio.load = None
    sys.modules["comfy_extras.nodes_audio"] = optional_audio
    sys.modules["torchaudio"] = types.ModuleType("torchaudio")

    root = Path(__file__).resolve().parents[1]
    package = types.ModuleType("rh_video_local_probe")
    package.__path__ = [str(root / "nodes")]
    sys.modules[package.__name__] = package
    media = importlib.import_module("rh_video_local_probe.rh_media")
    print("Probe stage: RH media module ready", flush=True)

    if media.cv2 is None or media.torch is None or media.np is None:
        raise RuntimeError("Installed ComfyUI Python lacks the required CPU video decoder dependencies.")

    with tempfile.TemporaryDirectory(prefix="rh-video-cpu-probe-") as temp:
        file = str(Path(temp) / "sample.avi")
        writer = cv2.VideoWriter(
            file,
            cv2.VideoWriter_fourcc(*"MJPG"),
            12,
            (48, 32),
        )
        if not writer.isOpened():
            raise RuntimeError("OpenCV could not create the local synthetic AVI.")
        try:
            for index in range(6):
                frame = np.full((32, 48, 3), 20 + 20 * index, dtype=np.uint8)
                writer.write(frame)
        finally:
            writer.release()

        print("Probe stage: synthetic AVI ready", flush=True)
        preview = media.extract_video_frames(file, max_frames=1)
        all_frames = media.extract_video_frames(file)
        if len(preview) != 1 or len(all_frames) != 6:
            raise AssertionError(
                f"Unexpected decoded frame counts: preview={len(preview)}, full={len(all_frames)}."
            )
        if preview[0].shape != (1, 32, 48, 3):
            raise AssertionError(f"Unexpected preview shape: {preview[0].shape}.")

        print("Local CPU video decoding: PASS")
        print("preview_only frame count:", len(preview))
        print("all_frames frame count:", len(all_frames))
        print("preview_only shape:", tuple(preview[0].shape))
        print("Original video remained readable:", Path(file).is_file())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
