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
- 优先把本地凭据放在 Git 忽略的 `config.local.json`，避免写入工作流 JSON。

长期兼容规则见 [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)。

## 安装

### ComfyUI Manager

搜索 `ComfyUI_RH_API`，安装后重启 ComfyUI。

### 手动安装

把仓库放到 `ComfyUI/custom_nodes/ComfyUI_RH_API`，然后只安装本插件自身声明的依赖：

```bash
pip install -r requirements.txt
```

本插件不会主动固定或升级 ComfyUI 已有的 Torch / CUDA 栈。

## 快速使用

1. 添加 `RH Config`，填写 RunningHub 工作流/应用 ID。
2. 建议把节点里的凭据字段留空，通过 `config.local.json` 提供。
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

在插件目录创建不会被 Git 跟踪的 `config.local.json`：

```json
{
  "api_key": "[REDACTED_SECRET]",
  "base_url": "https://www.runninghub.cn"
}
```

加载优先级：

```text
RH Config 节点非空输入
    > config.local.json
    > 旧版 config.json
```

旧 `config.json` 仍保留读取能力，仅用于兼容已有安装。

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
