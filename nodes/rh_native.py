"""Native V3 schemas for RH parameter and upload nodes.

UI schemas live here; existing upload implementations still own media encoding and
RH HTTP calls. There is no legacy-UI fallback. The package keeps its established
node IDs and mixed registry while unrelated execution nodes remain unchanged.
"""
from __future__ import annotations

from comfy_api.latest import io

from .rh_params2 import RH_Params2 as ParamsBuilder, FIELD_NAMES
from .rh_upload_image import RH_UploadImage as ImageUploader
from .rh_upload_image2 import RH_UploadImage2 as MultiImageUploader, IMAGE_FIELD_NAMES
from .rh_upload_video import RH_UploadVideo as VideoUploader
from .rh_upload_audio import RH_UploadAudio as AudioUploader
from .rh_upload_file import RH_UploadFile as FileUploader
from .rh_upload_latent import RH_UploadLatent as LatentUploader
from .rh_batch_upload_image import RH_BatchUploadImage as BatchImageUploader
from .rh_multi_input_image import RH_MultiInputImage as MultiInputUploader

CATEGORY = "Ken-Chen/RH-API"
Config = io.Custom("RH_CONFIG")
Params = io.Custom("RH_PARAMS")
SCALAR_TYPES = (str, int, float, bool)


def scalar_input(name: str, label: str):
    return io.MultiType.Input(
        io.String.Input(name, display_name=label, default="", multiline=False,
                        tooltip="Enter a value here or connect STRING, INT, FLOAT or BOOLEAN to this same input."),
        types=[io.String, io.Int, io.Float, io.Boolean],
    )


def field_selector(slot: int, names: list[str], default: str):
    name = f"field_name_{slot}"
    ordered = [default] + [field for field in names if field != default]
    return io.DynamicCombo.Input(name, display_name=f"Field {slot}", options=[
        io.DynamicCombo.Option(field, [
            io.String.Input(f"custom_field_name_{slot}", display_name=f"Custom Field {slot}", default="")
        ] if field == "custom" else []) for field in ordered
    ])


def row_inputs(slot: int, media: bool = False, legacy_multi: bool = False):
    fields = IMAGE_FIELD_NAMES if media else FIELD_NAMES
    inputs = [io.String.Input(f"node_id_{slot}", display_name=f"Node {slot}", default="",
                              tooltip="Target node ID in the remote RunningHub workflow.")]
    if legacy_multi:
        inputs.append(io.Combo.Input(f"field_name_{slot}", display_name=f"Field {slot}",
                                     options=["image", "control_image", "mask"], default="image"))
    else:
        inputs.append(field_selector(slot, fields, "image" if media else "text"))
    if media:
        inputs.append(io.Image.Input(f"image_{slot}", display_name=f"Image {slot}", optional=True))
    else:
        inputs.append(scalar_input(f"value_{slot}", f"Value {slot}"))
    if media and not legacy_multi:
        # Image 2 still supports temporarily disabling a media row.
        inputs.append(io.Boolean.Input(f"enabled_{slot}", display_name=f"Enable {slot}", default=True,
                                       advanced=True, socketless=True))
    return inputs


def count_group(name: str, maximum: int, *, media=False, legacy_multi=False):
    return io.DynamicCombo.Input(name, display_name="Image Count" if media else "Param Count", options=[
        io.DynamicCombo.Option(str(count), [
            item for slot in range(1, count + 1)
            for item in row_inputs(slot, media=media, legacy_multi=legacy_multi)
        ]) for count in range(1, maximum + 1)
    ])


def selected_count(group: dict, key: str, maximum: int) -> int:
    if not isinstance(group, dict):
        raise ValueError(f"{key} must use the native V3 grouped input format; re-save the workflow in ComfyUI.")
    try:
        count = int(group[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {key}.") from exc
    if not 1 <= count <= maximum:
        raise ValueError(f"{key} must be between 1 and {maximum}.")
    return count


def row_field(group: dict, slot: int):
    key = f"field_name_{slot}"
    value = group.get(key, "text")
    if isinstance(value, dict):
        return str(value.get(key, "text")), str(value.get(f"custom_field_name_{slot}", ""))
    return str(value), str(group.get(f"custom_field_name_{slot}", ""))


def validate_route(node_id, field_name, custom_field_name="", *, required=False):
    node_id = str(node_id or "").strip()
    if required and not node_id:
        raise ValueError("RunningHub Node ID is required.")
    if node_id:
        actual = str(custom_field_name if field_name == "custom" else field_name or "").strip()
        if not actual:
            raise ValueError("RunningHub field name is required; fill Custom Field when Field is custom.")
    return node_id


class RH_Params2Native(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="RH_Params2", display_name="\u2699\ufe0f RH Params 2", category=CATEGORY,
                         description="Native RH parameter groups. A single Value input supports both typing and links.",
                         inputs=[count_group("param_count", 16), Params.Input("previous_params", optional=True)],
                         outputs=[Params.Output(display_name="params")])

    @classmethod
    def execute(cls, param_count, previous_params=None):
        count = selected_count(param_count, "param_count", 16)
        arguments = {}
        for slot in range(1, count + 1):
            field, custom = row_field(param_count, slot)
            value = param_count.get(f"value_{slot}", "")
            if value is not None and not isinstance(value, SCALAR_TYPES):
                raise TypeError(f"Value {slot} accepts only text, integers, decimals and booleans.")
            arguments[f"param_{slot}"] = {
                "node_id": param_count.get(f"node_id_{slot}", ""),
                "field_name": field,
                "custom_field_name": custom,
                "local_value": value,
            }
        return io.NodeOutput(*ParamsBuilder().build_params(param_count=count, previous_params=previous_params, **arguments))


class RH_UploadImage2Native(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="RH_UploadImage2", display_name="\U0001f4e4 RH Upload Image 2", category=CATEGORY,
                         inputs=[Config.Input("config"), count_group("image_count", 12, media=True),
                                 Params.Input("previous_params", optional=True)],
                         outputs=[Params.Output(display_name="params")])

    @classmethod
    def execute(cls, config, image_count, previous_params=None):
        count = selected_count(image_count, "image_count", 12)
        arguments = {}
        # Validate all mappings before the first upload, rather than half-uploading a malformed group.
        for slot in range(1, count + 1):
            field, custom = row_field(image_count, slot)
            row = {
                "node_id": image_count.get(f"node_id_{slot}", ""),
                "field_name": field, "custom_field_name": custom,
                "enabled": image_count.get(f"enabled_{slot}", True),
            }
            image = image_count.get(f"image_{slot}")
            if row["enabled"] and image is not None:
                validate_route(row["node_id"], field, custom, required=True)
            arguments[f"image_meta_{slot}"] = row
            arguments[f"image_{slot}"] = image
        return io.NodeOutput(*MultiImageUploader().upload(config, previous_params=previous_params, **arguments))


def single_upload_schema(node_id, title, source, field_names, default):
    # Keep the established flat names/order for saved workflows and API callers.
    # Advanced is ComfyUI's native optional-controls surface, not custom DOM hiding.
    return io.Schema(node_id=node_id, display_name=title, category=CATEGORY, inputs=[
        Config.Input("config"), source,
        io.String.Input("node_id", display_name="Node ID", default="", optional=True,
                        tooltip="Leave empty to upload only, without adding a parameter."),
        io.Combo.Input("field_name", display_name="Field", options=field_names, default=default, optional=True),
        io.String.Input("custom_field_name", display_name="Custom Field", default="", optional=True, advanced=True,
                        tooltip="Used when Field is custom. Expand Advanced to edit this field."),
        Params.Input("previous_params", optional=True),
    ], outputs=[io.String.Output(display_name="filename"), Params.Output(display_name="params")])


class RH_UploadImageNative(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return single_upload_schema("RH_UploadImage", "\U0001f4e4 RH Upload Image", io.Image.Input("image"),
                                    IMAGE_FIELD_NAMES, "image")

    @classmethod
    def execute(cls, config, image, node_id="", field_name="image", custom_field_name="", previous_params=None):
        validate_route(node_id, field_name, custom_field_name)
        return io.NodeOutput(*ImageUploader().upload(config, image, node_id, field_name, custom_field_name, previous_params))


class RH_UploadVideoNative(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return single_upload_schema("RH_UploadVideo", "\U0001f4e4 RH Upload Video", io.Video.Input("video"),
                                    ["video", "init_video", "reference", "custom"], "video")

    @classmethod
    def execute(cls, config, video, node_id="", field_name="video", custom_field_name="", previous_params=None):
        validate_route(node_id, field_name, custom_field_name)
        return io.NodeOutput(*VideoUploader().upload(config, video, node_id, field_name, custom_field_name, previous_params))


class RH_UploadAudioNative(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return single_upload_schema("RH_UploadAudio", "\U0001f4e4 RH Upload Audio",
                                    io.String.Input("audio_path", display_name="Audio Path", default="",
                                                    tooltip="Existing audio file path, or connect RH Load Audio Path."),
                                    ["audio", "init_audio", "reference", "custom"], "audio")

    @classmethod
    def execute(cls, config, audio_path, node_id="", field_name="audio", custom_field_name="", previous_params=None):
        validate_route(node_id, field_name, custom_field_name)
        return io.NodeOutput(*AudioUploader().upload(config, audio_path, node_id, field_name, custom_field_name, previous_params))


class RH_UploadFileNative(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="RH_UploadFile", display_name="\U0001f4e4 RH Upload File", category=CATEGORY, inputs=[
            Config.Input("config"), io.String.Input("node_id", display_name="Node ID", default=""),
            io.Combo.Input("field_name", display_name="Field", options=["text", "image", "audio", "video", "latent", "mask", "file"]),
            io.String.Input("file_path", display_name="File Path", default=""),
        ], outputs=[io.Custom("RH_PARAM").Output()])

    @classmethod
    def execute(cls, config, node_id, field_name, file_path):
        validate_route(node_id, field_name, required=True)
        return io.NodeOutput(*FileUploader().upload(config, node_id, field_name, file_path))


class RH_UploadLatentNative(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="RH_UploadLatent", display_name="\U0001f4e4 RH Upload Latent", category=CATEGORY, inputs=[
            Config.Input("config"), io.Latent.Input("latent"),
            io.String.Input("node_id", display_name="Node ID", default=""),
            io.String.Input("field_name", display_name="Field", default="",
                            tooltip="Exact latent field name in the RunningHub workflow."),
        ], outputs=[io.Custom("RH_PARAM").Output()])

    @classmethod
    def execute(cls, config, latent, node_id, field_name):
        validate_route(node_id, field_name, required=True)
        return io.NodeOutput(*LatentUploader().upload(config, latent, node_id, field_name))


class RH_BatchUploadImageNative(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="RH_BatchUploadImage", display_name="\U0001f4e4 RH Batch Upload Image", category=CATEGORY,
                         inputs=[Config.Input("config"), io.String.Input("node_id", display_name="Node ID", default=""),
                                 io.Combo.Input("field_name", display_name="Field", options=["image", "control_image", "mask"]),
                                 *[io.Image.Input(f"image_{slot}", display_name=f"Image {slot}", optional=True)
                                   for slot in range(1, 9)]],
                         outputs=[io.Custom("RH_PARAM_BUNDLE").Output()])

    @classmethod
    def execute(cls, config, node_id, field_name, **images):
        validate_route(node_id, field_name, required=True)
        return io.NodeOutput(*BatchImageUploader().upload_batch(config, node_id, field_name, **images))


class RH_MultiInputImageNative(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="RH_MultiInputImage", display_name="\U0001f4e4 RH Multi-Input Image", category=CATEGORY,
                         inputs=[Config.Input("config"), Params.Input("previous_params", optional=True),
                                 *[item for slot in range(1, 9) for item in (
                                     io.Image.Input(f"image_{slot}", display_name=f"Image {slot}", optional=True),
                                     io.String.Input(f"node_id_{slot}", display_name=f"Node {slot}", default="", optional=True),
                                     io.Combo.Input(f"field_name_{slot}", display_name=f"Field {slot}",
                                                    options=["image", "control_image", "mask"], optional=True),
                                 )]],
                         outputs=[Params.Output(display_name="params")])

    @classmethod
    def execute(cls, config, previous_params=None, **arguments):
        # This established node keeps its flat eight-slot API contract. Image 2
        # is the grouped UI; changing this node's API would break batch scripts.
        for slot in range(1, 9):
            if arguments.get(f"image_{slot}") is not None:
                validate_route(arguments.get(f"node_id_{slot}"), arguments.get(f"field_name_{slot}", "image"), required=True)
        return io.NodeOutput(*MultiInputUploader().upload_single_run(config, previous_params=previous_params, **arguments))


NATIVE_NODE_CLASS_MAPPINGS = {
    "RH_Params2": RH_Params2Native,
    "RH_UploadImage2": RH_UploadImage2Native,
    "RH_UploadImage": RH_UploadImageNative,
    "RH_UploadVideo": RH_UploadVideoNative,
    "RH_UploadAudio": RH_UploadAudioNative,
    "RH_UploadFile": RH_UploadFileNative,
    "RH_UploadLatent": RH_UploadLatentNative,
    "RH_BatchUploadImage": RH_BatchUploadImageNative,
    "RH_MultiInputImage": RH_MultiInputImageNative,
}
