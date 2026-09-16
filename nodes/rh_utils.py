"""
RH Utility Nodes - Helper nodes for working with RunningHub outputs
"""

import torch
import requests
import time
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from .rh_client import RHClient

# Dependency checks
try:
    import comfy.utils
    COMFY_AVAILABLE = True
except ImportError:
    COMFY_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import torchaudio
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

try:
    from safetensors.torch import load_file
    SAFETENSORS_AVAILABLE = True
except ImportError:
    SAFETENSORS_AVAILABLE = False

def upload_file_to_rh(
    api_key,
    base_url,
    file_buffer,
    file_name,
    content_type,
    file_type,
    api_mode="legacy",
):
    """Upload a file through the RH compatibility client.

    Existing nodes keep using the legacy endpoint by default. V2 is available as
    an explicit compatibility path but is not selected automatically.
    """
    client = RHClient(api_key, base_url)
    api_mode = str(api_mode or "legacy").strip().lower()
    if api_mode not in {"legacy", "v2"}:
        raise ValueError("api_mode must be 'legacy' or 'v2'.")

    max_retries = 5
    for attempt in range(max_retries):
        try:
            print(f"Upload attempt {attempt + 1}/{max_retries} via {api_mode} API...")
            if api_mode == "v2":
                filename = client.upload_file_v2(
                    file_buffer=file_buffer,
                    file_name=file_name,
                    content_type=content_type,
                )
            else:
                filename = client.upload_file_legacy(
                    file_buffer=file_buffer,
                    file_name=file_name,
                    content_type=content_type,
                    file_type=file_type,
                )
            print(f"✓ File uploaded successfully: {filename}")
            return filename
        except Exception as e:
            print(f"Upload attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise Exception(f"Failed to upload file after {max_retries} attempts: {e}") from e
            wait_time = 2 ** attempt
            print(f"Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

    raise Exception("Failed to upload file and exhausted all retries.")


# --- Task Monitoring and Output Processing Logic ---
# These functions are moved from rh_execute.py to be shared with rh_download.py

def _check_task_status(task_id, api_key, base_url, query_api="legacy"):
    """Query RunningHub through the compatibility client and keep legacy return shapes."""
    result = RHClient(api_key, base_url).query_task(task_id, mode=query_api)

    if result.status == "SUCCESS":
        return result.outputs
    if result.status == "NO_OUTPUT":
        return {"taskStatus": "completed_no_output"}
    if result.status in {"QUEUED", "RUNNING", "NETWORK_ERROR"}:
        payload = {"taskStatus": result.status}
        if result.error:
            payload["error"] = result.error
        return payload
    if result.status in {"ERROR", "API_ERROR"}:
        return {
            "taskStatus": "error",
            "error": result.error or f"RunningHub query failed via {result.api_mode}",
        }

    return {
        "taskStatus": "error",
        "error": f"Unexpected normalized RunningHub task status: {result.status}",
    }


def _monitor_task(task_id, config, timeout):
    """Monitor task until completion"""
    api_key = config["api_key"]
    base_url = config["base_url"]
    query_api = config.get("query_api", "legacy")

    start_time = time.time()
    poll_interval = 5
    last_poll = 0
    last_status = None
    last_log_time = 0
    log_interval = 15
    consecutive_network_errors = 0
    max_network_errors = 3

    print("Monitoring task...")
    print(f"Task URL: https://www.runninghub.cn/task/detail/{task_id}")

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            raise TimeoutError(f"Task timeout after {timeout} seconds")

        if time.time() - last_poll >= poll_interval:
            last_poll = time.time()
            status = _check_task_status(task_id, api_key, base_url, query_api=query_api)

            if isinstance(status, list):
                print(f"✓ Task completed successfully!")
                break
            elif isinstance(status, dict):
                task_status = status.get("taskStatus")

                if task_status != last_status:
                    print(f"[{int(elapsed)}s] Task status changed to: {task_status}")
                    last_status = task_status
                    last_log_time = time.time()
                elif time.time() - last_log_time > log_interval:
                    print(f"[{int(elapsed)}s] Task is still {task_status}...")
                    last_log_time = time.time()

                if task_status == "NETWORK_ERROR":
                    consecutive_network_errors += 1
                    error_msg = status.get("error", "Unknown network error")
                    print(
                        f"⚠ Network error while checking task "
                        f"({consecutive_network_errors}/{max_network_errors}): {error_msg}"
                    )
                    if consecutive_network_errors >= max_network_errors:
                        raise ConnectionError(
                            f"Failed to query RunningHub task after {max_network_errors} consecutive network errors: {error_msg}"
                        )
                else:
                    consecutive_network_errors = 0

                if task_status == "error":
                    error_msg = status.get('error', 'Unknown error')
                    raise Exception(f"Task failed on RunningHub server: {error_msg}")
                if task_status == "completed_no_output":
                    print("✓ Task completed with no output files.")
                    break
            else:
                if time.time() - last_log_time > log_interval:
                    print(f"[{int(elapsed)}s] Unexpected status response. Retrying...")
                    last_log_time = time.time()

        time.sleep(0.5)


def _get_outputs(task_id, config, save_to_local, output_prefix):
    """Get and process task outputs"""
    api_key = config["api_key"]
    base_url = config["base_url"]
    query_api = config.get("query_api", "legacy")

    max_retries = 30
    consecutive_network_errors = 0
    max_network_errors = 3
    for attempt in range(max_retries):
        status = _check_task_status(task_id, api_key, base_url, query_api=query_api)

        if isinstance(status, list):
            return _process_outputs(status, save_to_local, output_prefix, task_id=task_id)

        if isinstance(status, dict):
            task_status = status.get("taskStatus")
            if task_status == "NETWORK_ERROR":
                consecutive_network_errors += 1
                error_msg = status.get("error", "Unknown network error")
                if consecutive_network_errors >= max_network_errors:
                    raise ConnectionError(
                        f"Failed to fetch RunningHub outputs after {max_network_errors} consecutive network errors: {error_msg}"
                    )
            else:
                consecutive_network_errors = 0

            if task_status == "error":
                raise Exception(f"Task failed: {status.get('error')}")
            elif task_status == "completed_no_output":
                print("Task completed but produced no output.")
                return None

        time.sleep(2)

    raise Exception("Timeout waiting for outputs")

def _download_and_process_file(output):
    """Downloads and processes a single file, returning the data and type."""
    file_url = output.get("fileUrl")
    file_type = output.get("fileType", "").lower()
    if not file_url:
        return None

    try:
        if file_type in ["png", "jpg", "jpeg", "webp", "bmp"]:
            data = _download_image(file_url)
            return {"type": "image", "data": data, "original_type": file_type} if data is not None else None
        elif file_type in ["mp4", "avi", "mov", "webm"]:
            frames = _extract_video_frames(file_url) if CV2_AVAILABLE else []
            # Also return the original URL for direct saving
            return {"type": "video", "frames": frames, "url": file_url, "original_type": file_type}
        elif file_type == "txt":
            data = _download_text(file_url)
            return {"type": "text", "data": data} if data is not None else None
        elif file_type in ["wav", "mp3", "flac", "ogg"] and AUDIO_AVAILABLE:
            data = _download_audio(file_url)
            return {"type": "audio", "data": data} if data is not None else None
        elif file_type == "safetensors" and SAFETENSORS_AVAILABLE:
            data = _download_latent(file_url)
            return {"type": "latent", "data": data} if data is not None else None
    except Exception as e:
        print(f"Warning: Failed to download or process {file_type} file from {file_url}: {e}")
    return None

def _process_outputs(outputs, save_to_local, output_prefix, task_id=None):
    """Preserve RH files first, then adapt them to ComfyUI output types."""
    import tempfile
    from .rh_outputs import download_output_item, normalize_outputs
    from . import rh_media

    items = normalize_outputs(outputs or [])
    print(f"Processing {len(items)} RunningHub output files...")

    try:
        import folder_paths
        if save_to_local:
            working_dir = folder_paths.get_output_directory()
        else:
            get_temp_directory = getattr(folder_paths, "get_temp_directory", None)
            working_dir = get_temp_directory() if callable(get_temp_directory) else tempfile.gettempdir()
    except ImportError:
        working_dir = os.path.join(os.getcwd(), "output") if save_to_local else tempfile.gettempdir()

    os.makedirs(working_dir, exist_ok=True)
    if save_to_local:
        print(f"✓ Preserving original RH outputs in: {working_dir}")
    else:
        print(f"ℹ Staging RH outputs in temporary storage: {working_dir}")

    # Download in parallel, but restore the original RH result order by item.index.
    downloaded_by_index = {}
    download_errors = []
    with ThreadPoolExecutor(max_workers=min(10, len(items) or 1)) as executor:
        future_to_item = {
            executor.submit(
                download_output_item,
                item,
                working_dir,
                output_prefix,
                task_id,
            ): item
            for item in items
        }
        for future in as_completed(future_to_item):
            item = future_to_item[future]
            try:
                downloaded = future.result()
                downloaded_by_index[downloaded.index] = downloaded
                print(
                    f"✓ Preserved RH output #{downloaded.index + 1}: "
                    f"{os.path.basename(downloaded.local_path)} "
                    f"[{downloaded.media_type}]"
                )
            except Exception as e:
                download_errors.append((item, e))
                print(f"❌ Failed to preserve RH output #{item.index + 1} from {item.url}: {e}")

    if download_errors:
        details = "; ".join(
            f"#{item.index + 1} {item.url}: {error}" for item, error in download_errors
        )
        raise RuntimeError(f"Failed to download {len(download_errors)} RunningHub output file(s): {details}")

    downloaded_items = [downloaded_by_index[index] for index in sorted(downloaded_by_index)]

    images, video_frames = [], []
    text_content, audio_data, video_data, latent_data = None, None, None, None
    present_types = {item.media_type for item in downloaded_items if item.media_type != "unknown"}
    successful_types = set()
    conversion_errors = []

    for item in downloaded_items:
        try:
            if item.media_type == "image":
                images.append(rh_media.load_image(item.local_path))
                successful_types.add("image")
            elif item.media_type == "text":
                if text_content is None:
                    text_content = rh_media.load_text(item.local_path)
                    successful_types.add("text")
            elif item.media_type == "audio":
                if audio_data is None:
                    audio_data = rh_media.load_audio(item.local_path)
                    successful_types.add("audio")
            elif item.media_type == "video":
                if video_data is None:
                    video_data = rh_media.load_video(item.local_path)
                    successful_types.add("video")
                if not video_frames:
                    video_frames.extend(rh_media.extract_video_frames(item.local_path))
            elif item.media_type == "latent":
                if latent_data is None:
                    latent_data = rh_media.load_latent(item.local_path)
                    successful_types.add("latent")
            else:
                print(
                    f"⚠ RH output #{item.index + 1} has an unknown media type; "
                    f"the original file was preserved at {item.local_path}"
                )
        except Exception as e:
            conversion_errors.append((item, e))
            print(
                f"❌ Failed to convert preserved RH output #{item.index + 1} "
                f"({item.media_type}) for ComfyUI: {e}"
            )

    failed_required_types = sorted(present_types - successful_types)
    if failed_required_types:
        details = "; ".join(
            f"#{item.index + 1} {item.media_type}: {error}"
            for item, error in conversion_errors
            if item.media_type in failed_required_types
        )
        raise RuntimeError(
            "RunningHub files were preserved locally, but ComfyUI conversion failed for "
            f"{', '.join(failed_required_types)}. {details}"
        )

    if not images:
        images.append(_create_placeholder_image("No images"))
    if not video_frames:
        video_frames.append(_create_placeholder_image("No video frames"))
    if text_content is None:
        text_content = ""
    if latent_data is None:
        latent_data = _create_placeholder_latent()

    # AUDIO and VIDEO intentionally remain None when the RH task did not produce
    # those media types. A conversion failure raises above instead of fabricating
    # placeholder media that looks like a successful result.
    return (
        torch.cat(images, dim=0),
        torch.cat(video_frames, dim=0),
        text_content,
        audio_data,
        video_data,
        latent_data,
    )


def _download_image(url):
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content)).convert("RGB")
        return torch.from_numpy(np.array(img).astype(np.float32) / 255.0).unsqueeze(0)
    except Exception as e:
        print(f"Error downloading image: {e}")
        return None

def _extract_video_frames(url):
    if not CV2_AVAILABLE: return []
    try:
        import tempfile
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name
        cap = cv2.VideoCapture(tmp_path)
        frames = []
        while True:
            ret, frame = cap.read()
            if not ret: break
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(torch.from_numpy(frame_rgb.astype(np.float32) / 255.0).unsqueeze(0))
        cap.release()
        os.unlink(tmp_path)
        return frames
    except Exception as e:
        print(f"Error extracting video frames: {e}")
        return []

def _download_text(url):
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        # RunningHub text outputs are UTF-8 files. Decode the raw bytes explicitly
        # instead of relying on requests' charset guessing, which can turn Chinese
        # text into mojibake such as "èº«ç©¿..." when no charset is declared.
        return response.content.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Keep a conservative fallback for unexpected legacy text files.
        response.encoding = response.apparent_encoding or "utf-8"
        return response.text
    except Exception as e:
        print(f"Error downloading text: {e}")
        return ""

def _download_audio(url):
    if not AUDIO_AVAILABLE: return None
    try:
        import tempfile
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name
        waveform, sample_rate = torchaudio.load(tmp_path)

        if waveform.shape[0] == 1: waveform = waveform.repeat(2, 1)
        os.unlink(tmp_path)
        return {"waveform": waveform.unsqueeze(0), "sample_rate": sample_rate}
    except Exception as e:
        print(f"Error downloading audio: {e}")
        return None

def _download_latent(url):
    if not SAFETENSORS_AVAILABLE:
        return None

    tmp_path = None
    try:
        import tempfile

        response = requests.get(url, timeout=60)
        response.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".safetensors") as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name

        return load_file(tmp_path)
    except Exception as e:
        print(f"Error downloading latent: {e}")
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

def _create_placeholder_image(text):
    img = Image.new('RGB', (512, 128), color=(50, 50, 50))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    draw.text((10, 50), text, fill=(200, 200, 200), font=font)
    return torch.from_numpy(np.array(img).astype(np.float32) / 255.0).unsqueeze(0)

def _create_placeholder_audio():
    if not AUDIO_AVAILABLE: return None
    sample_rate = 44100
    waveform = torch.zeros(1, 2, sample_rate, dtype=torch.float32)
    return {"waveform": waveform, "sample_rate": sample_rate}

def _save_image_to_file(img_tensor, filepath):
    try:
        img_np = (img_tensor.squeeze(0).cpu().numpy() * 255).astype(np.uint8)
        Image.fromarray(img_np, 'RGB').save(filepath)
    except Exception as e:
        print(f"Error saving image to {filepath}: {e}")


def _create_placeholder_latent():
    # Create an empty latent structure
    return {"samples": torch.zeros(1, 4, 64, 64)}
def _download_and_save_video(url, filepath):
    try:
        response = requests.get(url, timeout=120, stream=True)
        response.raise_for_status()
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk: f.write(chunk)
    except Exception as e:
        print(f"Error saving video to {filepath}: {e}")

def _save_audio_to_file(audio_data, filepath):
    if not AUDIO_AVAILABLE or not audio_data: return
    try:
        waveform = audio_data.get("waveform").squeeze(0)
        sample_rate = audio_data.get("sample_rate", 44100)
        torchaudio.save(filepath, waveform, sample_rate)
    except Exception as e:
        print(f"Error saving audio to {filepath}: {e}")



class RH_ImageSelector:
    """
    Select specific image(s) from a batch of images.
    Useful for extracting individual images from RunningHub output.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {
                    "tooltip": "Batch of images"
                }),
                "index": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 9999,
                    "tooltip": "Index of image to select (0-based)"
                }),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "select"
    CATEGORY = "Ken-Chen/RH-API"

    def select(self, images, index):
        """
        Select image at specified index

        Args:
            images: Batch of images
            index: Index to select

        Returns:
            Selected image
        """
        if index >= images.shape[0]:
            raise ValueError(f"Index {index} out of range (batch size: {images.shape[0]})")

        selected = images[index].unsqueeze(0)
        print(f"✓ Selected image {index} from batch of {images.shape[0]}")

        return (selected,)


class RH_TextDisplay:
    """
    Display text output from RunningHub.
    Useful for viewing text results.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Text to display"
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "display"
    CATEGORY = "Ken-Chen/RH-API"
    OUTPUT_NODE = True

    def display(self, text):
        """
        Display text

        Args:
            text: Text to display

        Returns:
            Same text (pass-through)
        """
        print("=" * 60)
        print("📝 Text Output:")
        print("-" * 60)
        print(text)
        print("=" * 60)

        return (text,)



def _validate_config(config):
    """Validate the config dictionary"""
    if not isinstance(config, dict):
        raise ValueError("Invalid config: must be a dictionary from RH_Config node")

    required_fields = ["api_key", "base_url"]
    for field in required_fields:
        if field not in config or not config[field]:
            raise ValueError(f"Missing required config field: {field}")

def get_task_status(config, task_id):
    """
    Gets the current status of a single task without waiting.
    """
    api_key = config["api_key"]
    base_url = config["base_url"]
    query_api = config.get("query_api", "legacy")
    return _check_task_status(task_id, api_key, base_url, query_api=query_api)

def cancel_task(config, task_id):
    """
    Requests to cancel a task on RunningHub.
    """
    api_key = config["api_key"]
    base_url = config["base_url"]
    url = f"{base_url}/task/openapi/cancel"
    payload = {
        "taskId": task_id,
        "apiKey": api_key
    }
    try:
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        result = response.json()
        if result.get("code") == 0:
            return True
        else:
            print(f"API Error when cancelling task: {result.get('msg', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"Exception when cancelling task: {e}")
        return False
