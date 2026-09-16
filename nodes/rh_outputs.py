"""RunningHub output normalization and raw-file download helpers.

This module intentionally avoids ComfyUI media decoding. Its responsibility is to
turn RunningHub API result records into a stable internal shape and preserve the
original remote file before any IMAGE/AUDIO/VIDEO/TEXT/LATENT conversion occurs.
"""

from __future__ import annotations

from dataclasses import dataclass
import mimetypes
import os
import re
from typing import Iterable, Optional
from urllib.parse import urlparse

import requests


IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp", "gif", "tif", "tiff"}
VIDEO_EXTENSIONS = {"mp4", "avi", "mov", "webm", "mkv", "m4v"}
AUDIO_EXTENSIONS = {"wav", "mp3", "flac", "ogg", "m4a", "aac", "mpeg", "mpga", "opus"}
TEXT_EXTENSIONS = {"txt", "text", "md", "json", "csv", "tsv", "log"}
LATENT_EXTENSIONS = {"safetensors", "latent"}

_MEDIA_BY_EXTENSION = {
    **{ext: "image" for ext in IMAGE_EXTENSIONS},
    **{ext: "video" for ext in VIDEO_EXTENSIONS},
    **{ext: "audio" for ext in AUDIO_EXTENSIONS},
    **{ext: "text" for ext in TEXT_EXTENSIONS},
    **{ext: "latent" for ext in LATENT_EXTENSIONS},
}

_MIME_EXTENSION_OVERRIDES = {
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/aac": ".aac",
    "audio/ogg": ".ogg",
    "audio/flac": ".flac",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "text/plain": ".txt",
    "application/json": ".json",
    "application/octet-stream": "",
}


@dataclass
class RHOutputItem:
    index: int
    url: str
    declared_type: str = ""
    media_type: str = "unknown"
    extension: str = ""
    content_type: str = ""
    local_path: Optional[str] = None
    source: Optional[dict] = None


def _clean_type(value: object) -> str:
    return str(value or "").strip().lower().lstrip(".")


def _extension_from_url(url: str) -> str:
    path = urlparse(url).path
    _, extension = os.path.splitext(path)
    return extension.lower()


def _media_from_mime(content_type: str) -> str:
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("text/") or mime in {"application/json", "application/xml"}:
        return "text"
    return "unknown"


def infer_media_type(declared_type: object, url: str = "", content_type: str = "") -> str:
    declared = _clean_type(declared_type)

    if "/" in declared:
        media = _media_from_mime(declared)
        if media != "unknown":
            return media

    if declared in {"image", "video", "audio", "text", "latent"}:
        return declared

    if declared in _MEDIA_BY_EXTENSION:
        return _MEDIA_BY_EXTENSION[declared]

    extension = _extension_from_url(url).lstrip(".")
    if extension in _MEDIA_BY_EXTENSION:
        return _MEDIA_BY_EXTENSION[extension]

    return _media_from_mime(content_type)


def infer_extension(declared_type: object, url: str = "", content_type: str = "") -> str:
    url_extension = _extension_from_url(url)
    if url_extension:
        return url_extension

    declared = _clean_type(declared_type)
    if declared in _MEDIA_BY_EXTENSION:
        return f".{declared}"

    mime = (content_type or "").split(";", 1)[0].strip().lower()
    if mime in _MIME_EXTENSION_OVERRIDES:
        return _MIME_EXTENSION_OVERRIDES[mime]

    guessed = mimetypes.guess_extension(mime) if mime else None
    return guessed or ""


def normalize_outputs(outputs: Iterable[dict]) -> list[RHOutputItem]:
    """Normalize legacy or V2-like output records while preserving API order."""
    normalized: list[RHOutputItem] = []
    for index, output in enumerate(outputs or []):
        if not isinstance(output, dict):
            continue

        url = output.get("fileUrl") or output.get("url") or output.get("downloadUrl") or ""
        if not url:
            continue

        declared_type = output.get("fileType") or output.get("outputType") or output.get("type") or ""
        content_type = output.get("contentType") or output.get("content_type") or ""
        normalized.append(
            RHOutputItem(
                index=index,
                url=url,
                declared_type=_clean_type(declared_type),
                media_type=infer_media_type(declared_type, url, content_type),
                extension=infer_extension(declared_type, url, content_type),
                content_type=str(content_type or ""),
                source=output,
            )
        )
    return normalized


def _safe_token(value: object, fallback: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip()).strip("_")
    return token[:48] or fallback


def _filename_for(item: RHOutputItem, output_prefix: str, task_id: Optional[str]) -> str:
    prefix = _safe_token(output_prefix, "RH")
    task = _safe_token(task_id, "task")
    media = _safe_token(item.media_type, "file")
    extension = item.extension if item.extension.startswith(".") else (f".{item.extension}" if item.extension else "")
    return f"{prefix}_{task}_{item.index + 1:03d}_{media}{extension}"


def download_output_item(
    item: RHOutputItem,
    destination_dir: str,
    output_prefix: str = "RH",
    task_id: Optional[str] = None,
    session=requests,
    timeout: int = 120,
) -> RHOutputItem:
    """Stream one RH output to disk using an atomic .part -> final rename."""
    os.makedirs(destination_dir, exist_ok=True)

    response = session.get(item.url, timeout=timeout, stream=True)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "") if hasattr(response, "headers") else ""
    if content_type:
        item.content_type = content_type
        if item.media_type == "unknown":
            item.media_type = infer_media_type(item.declared_type, item.url, content_type)
        if not item.extension:
            item.extension = infer_extension(item.declared_type, item.url, content_type)

    filename = _filename_for(item, output_prefix, task_id)
    final_path = os.path.join(destination_dir, filename)
    part_path = f"{final_path}.part"

    try:
        with open(part_path, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
        os.replace(part_path, final_path)
    except Exception:
        try:
            if os.path.exists(part_path):
                os.unlink(part_path)
        except OSError:
            pass
        raise

    item.local_path = final_path
    return item
