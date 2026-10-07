"""
ComfyUI_RH_API - A simplified and user-friendly RunningHub API integration for ComfyUI
Author: AI Assistant
Version: 2.0.0
Description: Easy-to-use nodes for calling RunningHub cloud workflows and AI apps
"""

from .nodes.rh_config import RH_Config
from .nodes.rh_execute import RH_Execute
from .nodes.rh_execute2 import RH_Execute2
from .nodes.rh_param import RH_Param
from .nodes.rh_params2 import RH_Params2
from .nodes.rh_upload_image import RH_UploadImage
from .nodes.rh_upload_image2 import RH_UploadImage2
from .nodes.rh_upload_video import RH_UploadVideo
from .nodes.rh_upload_audio import RH_UploadAudio
from .nodes.rh_load_audio_path import RH_LoadAudioPath
# from .nodes.rh_upload_mask import RH_UploadMask
from .nodes.rh_upload_file import RH_UploadFile
from .nodes.rh_upload_latent import RH_UploadLatent
from .nodes.rh_batch_upload_image import RH_BatchUploadImage
from .nodes.rh_multi_input_image import RH_MultiInputImage
from .nodes.rh_utils import RH_ImageSelector, RH_TextDisplay
from .nodes.rh_download import RH_Download
from .nodes.rh_param_bundle import RH_ParamBundle
from .nodes.rh_batch_execute import RH_BatchExecute
from .nodes.rh_task_manager import RH_TaskManager

NODE_CLASS_MAPPINGS = {
    # Core nodes
    "RH_Config": RH_Config,
    "RH_Execute": RH_Execute,
    "RH_Execute2": RH_Execute2,
    "RH_Param": RH_Param,
    "RH_Params2": RH_Params2,

    # Upload nodes
    "RH_UploadImage": RH_UploadImage,
    "RH_UploadImage2": RH_UploadImage2,
    "RH_UploadVideo": RH_UploadVideo,
    "RH_UploadAudio": RH_UploadAudio,
    "RH_LoadAudioPath": RH_LoadAudioPath,
    # "RH_UploadMask": RH_UploadMask,
    "RH_UploadFile": RH_UploadFile,
    "RH_UploadLatent": RH_UploadLatent,
    "RH_BatchUploadImage": RH_BatchUploadImage,
    "RH_MultiInputImage": RH_MultiInputImage,

    # Utility nodes
    "RH_ImageSelector": RH_ImageSelector,
    "RH_TextDisplay": RH_TextDisplay,

    # Download nodes
    "RH_Download": RH_Download,

    # Batch nodes
    "RH_ParamBundle": RH_ParamBundle,
    "RH_BatchExecute": RH_BatchExecute,

    # Advanced nodes
    "RH_TaskManager": RH_TaskManager,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    # Core nodes
    "RH_Config": "🌐 RH Config",
    "RH_Execute": "▶️ RH Execute",
    "RH_Execute2": "▶️ RH Execute 2",
    "RH_Param": "⚙️ RH Param",
    "RH_Params2": "⚙️ RH Params 2",

    # Upload nodes
    "RH_UploadImage": "📤 RH Upload Image",
    "RH_UploadImage2": "📤 RH Upload Image 2",
    "RH_UploadVideo": "📤 RH Upload Video",
    "RH_UploadAudio": "📤 RH Upload Audio",
    "RH_LoadAudioPath": "🎵 RH Load Audio Path",
    # "RH_UploadMask": "📤 RH Upload Mask",
    "RH_UploadFile": "📤 RH Upload File",
    "RH_UploadLatent": "📤 RH Upload Latent",
    "RH_BatchUploadImage": "📤 RH Batch Upload Image",
    "RH_MultiInputImage": "📤 RH Multi-Input Image",

    # Utility nodes
    "RH_ImageSelector": "🖼️ RH Image Selector",
    "RH_TextDisplay": "📝 RH Text Display",

    # Download nodes
    "RH_Download": "📥 RH Download Results",

    # Batch nodes
    "RH_ParamBundle": "📦 RH Param Bundle",
    "RH_BatchExecute": "⏯️ RH Batch Execute",

    # Advanced nodes
    "RH_TaskManager": "🛠️ RH Task Manager",
}

# V3 ComfyNode classes also implement the standard registry bridge. Keep the
# mixed registry so unrelated execution nodes are not needlessly migrated.
from .nodes.rh_native import NATIVE_NODE_CLASS_MAPPINGS
NODE_CLASS_MAPPINGS.update(NATIVE_NODE_CLASS_MAPPINGS)

WEB_DIRECTORY = "js"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

