# Install & first use — ZiYao00 GitHub fork

This is the [ZiYao00/ComfyUI_RH_API](https://github.com/ZiYao00/ComfyUI_RH_API) fork. You need a working ComfyUI installation, Git, a RunningHub account, and your own API key.

**Important:** The `ComfyUI_RH_API` listing in ComfyUI Manager may belong to the upstream project rather than this fork. Use the Git URL below for this fork. Do not load two copies of the same nodes.

## 1. Clone and install requirements

In the **real ComfyUI instance's** `custom_nodes` directory, run:

```bash
git clone https://github.com/ZiYao00/ComfyUI_RH_API.git
```

The resulting `ComfyUI/custom_nodes/ComfyUI_RH_API` directory should contain `__init__.py`, `nodes/`, `js/`, and `requirements.txt`.

Install dependencies with **that ComfyUI's Python interpreter** (not an unrelated system Python):

```text
<ComfyUI Python> -m pip install -r <plugin directory>/requirements.txt
```

Windows Portable example, run from the Portable root:

```powershell
.\python_embeded\python.exe -m pip install -r .\ComfyUI\custom_nodes\ComfyUI_RH_API\requirements.txt
```

Virtualenv/Desktop/Docker users should use their respective environments. Only `requests>=2.31.0` is declared; this plugin does not force a Torch/CUDA upgrade. **Restart ComfyUI**.

## 2. Configure the service

Copy `config.json.example` to a private `config.json` in the plugin root. Fill in your own API key in the private copy; the template deliberately has an empty value:

```json
{
  "api_key": "",
  "base_url": "https://www.runninghub.ai"
}
```

- International: `https://www.runninghub.ai`; domestic: `https://www.runninghub.cn`. Use credentials from the matching site.
- `config.json` is Git-ignored. Keep the `RH Config` node's key widget blank to avoid storing a key in shared workflow JSON.
- Newly created `RH Config` nodes have an empty `base_url` and read it from `config.json`; a nonempty URL already saved inside an old node **takes precedence** until cleared.
- For backward compatibility, a legacy `config.local.json`, if present, overrides nonempty matching values from `config.json`. New installations should use only `config.json`.
- **Credential protection:** only the official `.ai` and `.cn` HTTPS origins are trusted by default. A custom HTTPS proxy requires a private `config.json` entry such as `"trusted_custom_endpoints": {"my_proxy": "https://my-proxy.example"}` and the exact same origin in the node. That proxy receives your credentials; only opt in when you trust it.

## 3. First-run check

1. Restart ComfyUI and confirm that `RH Config`, `RH Execute`, and `RH Param` appear. Checking node registration does not create paid tasks.
2. Set the RunningHub workflow/AI app ID in `RH Config`, leave its API key widget blank, and check the endpoint.
3. Connect `RH Config.config` to `RH Execute.config`. Use `RH Param`/upload nodes for valid remote input overrides.
4. **Queue Prompt can use paid RunningHub credits.** Start with a known low-cost workflow only after reviewing its inputs.
5. If the task was created but result retrieval failed, reuse the known Task ID with task/download nodes rather than resubmitting an ambiguous request.

For video, prefer the `video` output over memory-intensive legacy `video_frames`.

## 4. Troubleshooting

- Missing nodes: check double-nested folders, duplicate installations, ComfyUI startup logs, and which instance was restarted.
- ImportError after pip: verify you used the same Python environment as ComfyUI.
- Wrong site: check `.ai/.cn`, a previously saved node URL, and any old `config.local.json` override.
- Manager shows different features: it may install upstream; use this fork's URL.
- `VIDEO` conversion unsupported: see [compatibility notes](QUICKSTART.md); raw MP4 may still be preserved.
- Submission timeout: inspect RunningHub task history before considering a new paid request.

Update: review local uncommitted changes before running `git pull --ff-only` in the plugin directory. Preserve private `config.json`.

Issues: [GitHub Issues](https://github.com/ZiYao00/ComfyUI_RH_API/issues); original attribution/license: `LICENSE`.
