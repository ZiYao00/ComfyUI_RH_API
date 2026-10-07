"""Inspect the installed ComfyUI API without modifying or starting ComfyUI."""
from __future__ import annotations
import argparse
import importlib.metadata
import inspect
import json
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfy-root", required=True)
    args = parser.parse_args()
    sys.path.insert(0, args.comfy_root)
    from comfy_api.latest import io

    result = {"python": sys.executable}
    try:
        result["frontend_package"] = importlib.metadata.version("comfyui-frontend-package")
    except importlib.metadata.PackageNotFoundError:
        result["frontend_package"] = None
    for name in ("String", "MultiType", "DynamicCombo", "DynamicGroup", "Autogrow", "Boolean", "Int"):
        cls = getattr(io, name, None)
        result[name] = str(inspect.signature(cls.Input)) if cls is not None else "NOT_AVAILABLE"
    result["Schema"] = str(inspect.signature(io.Schema))
    result["ComfyNode_methods"] = [name for name in dir(io.ComfyNode) if not name.startswith("__")]
    result["Schema_methods"] = [name for name in dir(io.Schema) if not name.startswith("__")]
    value = io.MultiType.Input(io.String.Input("value", default=""), types=[io.String, io.Int, io.Float, io.Boolean])
    result["MultiType_dict"] = value.as_dict() if hasattr(value, "as_dict") else vars(value)

    class Probe(io.ComfyNode):
        @classmethod
        def define_schema(cls):
            return io.Schema(node_id="RH_UITestProbe", inputs=[
                io.DynamicCombo.Input("count", options=[
                    io.DynamicCombo.Option("1", [value]),
                    io.DynamicCombo.Option("2", [value, io.String.Input("second", default="")]),
                ])
            ], outputs=[io.String.Output()])

        @classmethod
        def execute(cls, count):
            return io.NodeOutput(str(count))

    result["Probe_input_types"] = Probe.INPUT_TYPES()
    if hasattr(Probe, "GET_NODE_INFO_V1"):
        result["Probe_node_info"] = Probe.GET_NODE_INFO_V1()
    print(json.dumps(result, ensure_ascii=True, indent=2, default=str))


if __name__ == "__main__":
    main()
