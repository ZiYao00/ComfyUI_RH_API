# ComfyUI RunningHub API 连接器

[English](./README.md) | [中文](./README_CN.md)

用于在本地 ComfyUI 中调用 RunningHub 工作流和 AI 应用的一组自定义节点。

## 核心能力

- 在 ComfyUI 内直接调用 RunningHub 工作流和 AI 应用。
- 支持文本参数以及图片、音频、视频、通用文件等输入上传。
- **Raw-first 输出链**：先保存 RunningHub 原始文件，再转换为 ComfyUI 媒体对象。
- 在支持的环境中输出 `IMAGE`、`AUDIO`、`VIDEO`、`STRING`、`LATENT`。
- 下载或转换失败时明确报错，不再用“看似成功”的占位媒体掩盖错误。
- 默认继续使用 RH Legacy 结果查询，同时提供显式 V2 查询模式用于迁移验证。
- 优先把本地凭据放在 Git 忽略的 `config.json`，避免写入工作流 JSON。

新用户优先阅读：[安装与首次使用](./docs/INSTALL_CN.md)；英文：[Installation](./docs/INSTALL.md)。发布维护人员见 [Release Checklist](./docs/RELEASE_CHECKLIST.md)。

长期兼容规则见 [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)。

## 安装

### ComfyUI Manager（原作者版本提示）

Manager 的同名搜索结果可能属于上游原作者，不保证包含本 Fork 的改动。使用本 Fork 请按下面 Git 地址克隆。

### Git Clone 安装本 Fork

在 `ComfyUI/custom_nodes` 运行 `git clone https://github.com/ZiYao00/ComfyUI_RH_API.git`。再用 **ComfyUI 自身的 Python** 安装本插件声明的依赖，完整步骤见 [安装指南](./docs/INSTALL_CN.md)：

```bash
<ComfyUI 的 Python> -m pip install -r requirements.txt
```

本插件不会主动固定或升级 ComfyUI 已有的 Torch / CUDA 栈。

## 快速使用

1. 添加 `RH Config`，填写 RunningHub 工作流/应用 ID。
2. 建议把节点里的凭据字段留空，通过 `config.json` 提供。
3. 添加 `RH Execute` 并连接 `config`。
4. 如需覆盖云端工作流输入，添加 `RH Param` 或对应上传节点。
5. Queue Prompt 执行。

`RH Execute` 当前输出：

- `images`
- `video_frames`（旧工作流兼容输出）
- `text`
- `audio`
- `video`
- `latent`
- `task_id`

新的视频工作流应优先使用 `video`。`video_frames` 对长视频可能占用大量内存，只作为兼容能力保留。

## 配置

新安装应复制 `config.json.example` 为私有 `config.json` 并填写自己的 Key。该私有文件已被 Git 忽略。兼容旧版时，若存在 `config.local.json`，其非空同名字段仍会覆盖 `config.json`；新用户无需创建旧文件。新建节点的 `base_url` 默认留空并从私有文件读取，旧工作流中已保存的非空 URL 仍优先。

当前过渡期的同一份配置文件可以包含以下字段：

```json
{
  "api_key": "[REDACTED_SECRET]",
  "base_url": "https://www.runninghub.ai",
  "api_keys": {
    "international": "[REDACTED_SECRET]",
    "domestic": ""
  },
  "trusted_custom_endpoints": {}
}
```

当前本 Fork 的 `RH Config` 实际读取的是**根级** `api_key` 和 `base_url`；上述嵌套 `api_keys` 字段属于尚未发布的多站点下拉方案，不能替代根级 Key。已有工作流若保存了非空 `base_url`，该节点值优先；新节点留空时读取私有配置。

国际站／国内站／自定义站点下拉仍在隔离工作树，**没有部署到 8188/8190**。本 Fork 使用 STRING `base_url`，默认仅允许 RH 官方 HTTPS 站点；确需自定义代理时，在私有 `config.json` 中显式配置 `trusted_custom_endpoints`。完整设置见 [安装指南](./docs/INSTALL_CN.md)。不要在可分享的工作流内保存真实 API Key。

### query_api

`RH Config` 新增可选 `query_api`：

- `legacy`：默认，兼容已有工作流。
- `v2`：显式调用 RunningHub V2 查询接口，用于迁移测试。

在同一个真实 task 上完成 Legacy/V2 A-B 验证前，不会自动切换默认查询接口。

## 输出机制

当前输出链固定为：

```text
RH 返回结果
  -> 统一解析类型和顺序
  -> 原子下载远端原始文件
  -> 保存/暂存原始文件
  -> 从本地文件转换为 ComfyUI 媒体对象
```

如果文件已经从 RH 下载成功，但本地媒体转换失败：

- 原始文件仍会保留；
- 节点明确报出转换错误；
- 不会再用 1 秒静音等占位内容伪装成功。

`save_to_local=true` 时，原始 RH 输出保存在 ComfyUI `output` 目录。关闭时，为了支持 `VIDEO` / `AUDIO` 等对象，文件会暂存在 ComfyUI 或系统临时目录。

## 上传节点

现有节点包括：

- `RH Upload Image`
- `RH Load Audio Path` + `RH Upload Audio`
- `RH Upload Video`
- `RH Upload File`
- `RH Upload Latent`
- Batch / Multi Image 上传节点

当前上传默认继续使用 Legacy 接口。内部 `RHClient` 已包含 V2 文件上传适配器，后续迁移无需重写每个上传节点。

## 任务提交安全

RunningHub 云端任务可能产生费用，所以任务创建采用**单次安全提交**。

如果出现以下情况：

- POST 请求可能已经到达 RH，但响应丢失；
- 返回内容无法解析；
- 返回成功但没有 `taskId`；

插件会报告“任务提交状态不确定”，不会自动再次创建付费任务。

此时应先进入 RunningHub 后台确认任务是否已经存在，再决定是否手动重试。

## 常见问题

### RH 后台有文件，但 ComfyUI 报转换失败

表示 Raw 下载已经成功，但本地 ComfyUI 媒体适配失败。先检查控制台日志和已经保存的原始文件，不要立即重新跑一次付费云端任务。

### 轮询过程中网络异常

网络错误与 `RUNNING` 已明确区分。连续查询失败后会停止并报告连接错误，不会继续假装云端仍在正常运行。

### 视频输出

当前 ComfyUI 使用 lazy `VideoFromFile` 路线生成 `VIDEO`，不会为了标准视频输出而把整段 MP4 全部解成 float32 图片批次。

如果 ComfyUI 版本过旧、缺少该 API，原始 MP4 仍会保存，并明确报告本地转换失败。

### 可选旧兼容依赖

- OpenCV：只用于旧 `video_frames` 抽帧输出。
- Torchaudio：只作为旧 ComfyUI 环境下的音频解码 fallback。

不要为了本插件单独升级 Torchaudio，从而破坏 ComfyUI 当前 Torch / CUDA 版本匹配。

## 测试

项目测试只使用 Python 标准库 mock/stub，不会另外安装一套 Torch：

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
python3 -m compileall -q nodes tests
git diff --check
```

单元测试不能替代真实 ComfyUI + RunningHub 回归。正式发布或后续自建仓库前，至少验证 Text / Image / Audio / Video 四类真实 RH 输出。

## License

MIT，详见 [LICENSE](./LICENSE)。
