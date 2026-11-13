# 安装与首次使用（ZiYao00 GitHub Fork）

本指南针对 [ZiYao00/ComfyUI_RH_API](https://github.com/ZiYao00/ComfyUI_RH_API)。需要已经可运行的 ComfyUI、Git、RunningHub 账号及该账号的 API Key。

**注意：** ComfyUI Manager 搜索到的同名插件可能属于原作者，并不代表本 Fork。若需要本仓库版本，请使用下方 Git 地址；不要在同一个 ComfyUI 同时加载两份同名插件。

## 1. Git 克隆与依赖

在真正使用的 ComfyUI `custom_nodes` 目录运行：

```bash
git clone https://github.com/ZiYao00/ComfyUI_RH_API.git
```

安装完成的目录应为 `ComfyUI/custom_nodes/ComfyUI_RH_API`，内含 `__init__.py`、`nodes/`、`js/`、`requirements.txt`。

请用**该 ComfyUI 所使用的 Python 解释器**安装依赖，不要误用系统 Python：

```text
<ComfyUI 的 Python> -m pip install -r <插件目录>/requirements.txt
```

Windows Portable 可从其根目录执行：

```powershell
.\python_embeded\python.exe -m pip install -r .\ComfyUI\custom_nodes\ComfyUI_RH_API\requirements.txt
```

其他安装形式（虚拟环境、Desktop、Docker）使用对应环境。本项目只声明 `requests>=2.31.0`，不要求单独升级 Torch/CUDA。安装完毕后**重启 ComfyUI**。

## 2. 配置站点与 API Key

将插件根目录的 `config.json.example` **复制**为 `config.json`，在私有副本中填入自己的 API Key，示例为空值：

```json
{
  "api_key": "",
  "base_url": "https://www.runninghub.ai"
}
```

- 国际站 `https://www.runninghub.ai`；国内站 `https://www.runninghub.cn`。两站凭据和工作流 ID 应匹配。
- 真实 Key 只填入私有 `config.json`；它已被 Git 忽略。不要把 Key 填到将分享的 ComfyUI 工作流里。
- 新的 `RH Config` 节点 `base_url` 默认留空，此时读取配置文件；**旧工作流如保存了非空 URL，节点中的 URL 优先**，要使用文件站点需手动清空该字段。
- 为兼容旧版，若还存在 `config.local.json`，其中非空字段会覆盖 `config.json` 同名字段。新用户只创建 `config.json` 即可。
- **安全限制：** 默认仅允许 `https://www.runninghub.ai` / `https://www.runninghub.cn`，防止导入的工作流将本地 Key 发送至陌生服务器。若确实使用自建 HTTPS 代理，需要在自己的 `config.json` 里额外设置 `"trusted_custom_endpoints": {"my_proxy": "https://my-proxy.example"}`，并将节点站点设为相同地址；该代理会收到你的凭据，请自行确认可信。

## 3. 首次使用

1. 重启后打开添加节点菜单，确认 `RH Config`、`RH Execute`、`RH Param` 出现。此步骤不产生 RH 付费任务。
2. 在 `RH Config` 填写自己的工作流/AI 应用 ID，保持节点 `api_key` 为空，确认 `base_url`。
3. 将 `RH Config.config` 连接至 `RH Execute.config`。覆盖工作流字段时，再按实际字段增加 `RH Param` 或上传节点。
4. **Queue Prompt 会提交 RunningHub 任务，可能消耗额度。** 建议首次运行一个已知可用的低成本工作流。
5. 如果云端已经产生 Task ID 但结果下载失败，优先用任务查询/下载节点恢复，不要直接再次创建付费任务。

视频优先使用 `video` 输出；旧 `video_frames` 可能占用较多内存。

## 4. 排查

- 找不到节点：检查是否出现同名双层目录、重复安装、装错 ComfyUI 实例；检查启动日志并重启。
- 安装依赖仍报 ImportError：检查运行 pip 的解释器是不是 ComfyUI 的 Python。
- 国际站 Key 不生效：检查 `.ai/.cn`、节点已保存的 `base_url`、旧 `config.local.json` 覆盖。
- Manager 安装版本功能不同：可能安装了上游版本，请用本 Fork URL。
- `VIDEO` 不可用：核对实际 ComfyUI 版本和 [兼容说明](QUICKSTART.md)；原 MP4 可能仍已保存。
- 创建任务超时：先在 RH 后台确认是否已扣费并创建任务，再考虑重试。

更新：检查本地是否存在未提交修改后，在插件目录运行 `git pull --ff-only`。保留自己的 `config.json`。

反馈：[GitHub Issues](https://github.com/ZiYao00/ComfyUI_RH_API/issues)；许可/原作者署名：`LICENSE`。
