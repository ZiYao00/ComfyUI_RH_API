# ComfyUI RH API — 新窗口接手交接（2026-10-13）

> **此文件是接手入口，不代表待办已经实施。**
> 仓库：`G:\GitHub\ComfyUI_RH_API`；分支 `main`；优先使用本机 CodexPro。
> 后续开发总方案：`docs/AI_APP_STAGE2_PLAN.md`。
> 开工前重新核对本机 Git 状态、8190 实际服务与官方 API；不能把本记录的测试结论自动推广到以后版本。

## 0. 新 Agent 从哪里开始

1. 使用 **ComfyUI Agent Rules**，再通过 CodexPro 打开 `G:\GitHub\ComfyUI_RH_API`，检查未提交改动、最新提交；不要覆盖其他 Agent 的改动。
2. **先阅读**本文件、`docs/AI_APP_STAGE2_PLAN.md`、`docs/ARCHITECTURE.md`、`docs/NATIVE_UI.md`、`docs/QUICKSTART.md`。
3. 核实 8190 是测试包（Core 0.39.0 / Frontend 1.55.14 的已测组合）、`custom_nodes/ComfyUI_RH_API` 指向本仓库，并确认现有节点真实注册；8188 是日常正式包，不能顺手改动。
4. **从阶段 2A 开始**：先研究 RH 国际站 AI App 元数据接口、鉴权安全、返回形状，只读测试通过后再编写 2B。不要跳到付费创建 App 任务。
5. 后续每个阶段独立提交/测试的需求需由用户明确授权；本交接本身不等于授权修改插件、重启、收费、推送远端。

## 1. 已完成且有证据的内容

### 插件 A1–C3（已实现，既有提交）

- A1/A2：通过 `RH Workflow Inspect` 解析 RH Workflow API JSON、建立字段 Schema，并在 `RH Execute.workflow_schema` 已连接时校验最终的 `RH_PARAMS`。真实 H3 案例节点 `28` 的字段是 `prompt`，不是 `text`。
- B1：Execute Instance Type `auto/default/plus/ultra`，旧 BOOLEAN false→auto、true→plus 的迁移；安全拒绝无法保留外部 BOOLEAN 连线的迁移。
- B2：成功创建任务即记录 Task ID 到忽略 Git 的 `.rh-task-history/`；不确定提交不自动重试，批量明确失败停止。
- C1/C2/C3：下载失败不伪装成功；视频帧 `all_frames/preview_only/disabled`；参数与上传节点不静默漏项。
- 之前自动化回归：Python **109/109**、JS 迁移 **20/20**、ComfyUI V3 Schema **20/20**；目标 8190 的实际后端注册、单独本地 Inspector 运行、真实官方 Save/Open/F5（RH 专项 4 项）均通过。此数为当时已测基线，升级后必须重测。

### 用户实际 RH 云端验收（非模拟）

- 国际站 Workflow `Instance Type=plus` 已生成 H3 **2 秒视频**；用户另已验证 30 秒生成，不再安排重复压力测试。
- 原始视频：`G:\AIGC\ComfyUI\ComfyUI\output\RH_2109923182008385537_001_video.mp4`。
- 自定义保存：`G:\AIGC\ComfyUI\ComfyUI\output\Video\ComfyUI_00003_.mp4`。
- **已有任务恢复查询 + 下载**真实验收通过：Task ID `2109923182008385537` 经国际站查为 SUCCESS，输出 1 个 MP4；8190 用 `RH Config + RH Download Results`（无 `RH Execute`）重新下载，内容 SHA-256 与原始 MP4 相同。没有新建付费生成任务。
- 任务记录中已核对存在该 Task ID；历史目录位于**插件仓库**（8188 与 8190 共同可见），不是各自 output。

### 阶段 1（8190 输出隔离，已执行，外部测试包配置）

- 8190 的 `ComfyUI/output` 原为指向 8188 正式 output 的 **Junction**；已安全解除，改成真实独立目录。
- 8190：`G:\AIGC\ComfyUI_test\ComfyUI\output`；
  8188：`G:\AIGC\ComfyUI\ComfyUI\output`。
- 8190 已实际执行 `EmptyImage → SaveImage`，本地 PNG 仅存在测试目录，正式目录没有同名文件；正式 H3 MP4 SHA-256 经校验未变。
- **只修改测试包**的 `run_test_cpu_8190.bat` 与 `run_test_8190.bat`：下次启动使用 `--listen 127.0.0.1 --port 8190 --output-directory "%ROOT%ComfyUI\output"`。
- **启动状态注意**：上一轮没有重启 8190。最后检查时当前进程仍监听 `0.0.0.0:8190`，这是旧启动参数，并非 BAT 更新失效。要验证新监听地址需经用户允许后，确认无任务运行再重启测试包；不要触碰 8188。
- 备份与核验：`G:\AIGC\ComfyUI_test\_backups\RH_STAGE1_8190_20261013_174832\`，含原 BAT、`before_isolation.json`、`stage1_verified.json`。
- 使用说明：`G:\AIGC\ComfyUI_test\OUTPUT_ISOLATION_8190.md`。
- **作用范围**：仅隔离 output，不代表共享 Python、模型、input 或插件代码也已隔离。两个测试包当前共享 Python 环境，**禁止在 8190 擅自 pip 安装/卸载依赖**。

### 清理历史

- `G:\GitHub\ComfyUI_RH_API-v3-lab` 旧独立实验仓库：含 6 个未提交文件的完整 69 文件归档已保存到
  `G:\AIGC\ComfyUI_test\_backups\ComfyUI_RH_API-v3-lab_20261013.zip`；
  原目录已移入 Windows 系统回收站。**无需重新恢复旧 Lab 开发**，除非有具体证据需要。

## 2. 即将开始：阶段 2 — AI App 参数识别和执行前校验

**当前状态：设计和交接已完成；AI App 新解析节点尚未开发；真实 App 付费任务尚未验收。**

### 2A：国际站 AI App 只读元数据 + 安全 Gate（下一窗口第一项）

- 查验官方 `GET /api/webapp/apiCallDemo` 是否支持国际站 `www.runninghub.ai`、鉴权方式、字段结构。候选 App ID `2109843724737204225`（用户已配置的 RH 应用）；**先核实其 App 身份**。
- 官方示例存在 API Key 经 **GET URL 参数**传递的风险，不能直接复制到浏览器、日志或工作流。优先调查 Header/POST 等价方案；若必须使用 GET，则先明确风险与约束：仅 HTTPS 官方域名、禁止重定向、隐藏 URL/日志、限制请求规模与超时、限制敏感响应保留。
- 只读接口属于外部账户访问，**先取得对应授权**；不得为了研究元数据误调用 `POST /task/openapi/ai-app/run`，也不得上传图片/视频。
- 用**脱敏后的实际响应结构**固定 fixture；如国际站元数据不可用，停止并讨论可导入的脱敏 JSON 回退。

**通过标准**：能确定 App 输入定义的可信字段名、类型、选项格式、账号与 App ID 边界，且不泄露凭证。

### 2B：独立纯解析器与 RH AI App Inspect（第二项）

- 客户端：`nodes/rh_client.py` 新增只读 App 元数据访问。
- 新增 `nodes/rh_ai_app_schema.py`（`RHAppSchema`），`nodes/rh_ai_app_inspector.py`（`RH_AIAppInspect`）；由 `__init__.py` 注册、`nodes/rh_native.py` 暴露 V3 Schema（实施前先检查当前官方 V3 接口）。
- 允许 `STRING/IMAGE/LIST`；根据真实响应再确认 AUDIO、VIDEO、UNKNOWN 的准确契约；不能把媒体字段猜成文本。
- `nodeId` / `webappId` **在 JS/UI 保存时必须是字符串**。例如 `2109843724737204225` 超过 `Number.MAX_SAFE_INTEGER`；绝对不要使用 `Number(webappId)`。
- LIST 必须验证 `fieldData` 选项结构，不静默丢失 0、空值、多字段同 Node ID、无效字段。
- 不记录原始 Prompt、媒体地址、API Key；结构指纹不存私有默认输入内容。

**通过标准**：独立 Inspector 能在 8190 只读 Queue，输出 `RH_APP_SCHEMA` 和可读的字段报告；原 `RH Workflow Inspect` 行为未改变。

### 2C：AI App 提交前校验（第三项）

- 在 `RH Execute` **追加可选 `app_schema`**，不能移动现有固定 widget/input 位置或修改 7 输出索引。
- AI App 与 Workflow schema 严格互斥；验证 App ID、区域、账号 Scope、时效、`nodeId+fieldName`、LIST 值；无合法 schema 的旧 App 工作流仍保留原有行为。
- 非法参数须在 **任何可能计费的 create-task POST 前**停止；补充 0 次 paid POST 的模拟回归。
- 检查 `RH_PARAMS` Autogrow 最多 16 路、参数覆盖次序、UI 输入连线、迁移、保存/重载/刷新、复制粘贴、撤销重做、subgraph 边界。
- **注意**：Execute 的校验发生在上游上传节点之后，因此不能声称“统一上传前预检”已由 2C 实现。

**通过标准**：App 检查路径和 Workflow 检查路径各自通过，而且旧工作流保持兼容。

### 2D：AI App 实例策略与实测边界（第四项）

- 现有 `RHClient` 对 **AI App 非 auto 实例**会主动报错；这不能直接用 Workflow Plus 已跑通来推导 App Plus 可用。
- 先确认国际站 App API 的 `instanceType` 合法值及账单影响，再决定是否开放 Plus / Ultra。**真实 App 付费测试必须单独授权**。
- 默认行为仍 `auto`；不要为了让下拉能选择而直接删除验证。

## 3. 阶段 3 / 阶段 4 / 阶段 5（后续独立推进）

| 阶段 | 内容 | 前置条件与边界 | 业务价值 |
|---|---|---|---|
| 3：智能 Params V2 | 从可信的 Workflow/App Schema 联动 Node ID / Field 下拉，按字段类型显示编辑能力，保留 Custom、自定义值和连线 | 必须先稳定阶段 2 的统一类型语义；保留 `RH_Params2` 节点 ID 与历史序列化；使用目标 Frontend 的 DynamicCombo 原生机制，不造第二套 Widget 系统 | **很高**：减少手动查字段、错填和跨 App 重复配置 |
| 4：完整 Preflight | 设计真正发生于媒体上传之前的独立校验阶段，覆盖 Node/Field、实例、图片/视频路由与必需输入 | 必须证明 ComfyUI 执行顺序；仅往 Execute 添加输入无法阻止上游上传。优先做独立无上传检查流程，然后讨论安全的执行闸门 | **高**：减少误上传、无效任务、扣费风险 |
| 5：正式发布收尾 | 用真实旧 H3 工作流和 AI App 的非收费路径回归，文档/示例版本统一，评估 8188 更新、测试包稳定性、批量需求，最后 Git commit/push | 8188 重启/发布、远端 push、真实付费/批量执行均需单独授权；30 秒压力测试用户已实测，**不重复安排** | 高：可以长期维护与跨 Agent 接手 |

**执行优先顺序：2A → 2B → 2C → 2D → 3 → 4 → 5。**
阶段 3 的 UI 目标可以提前讨论，但不要与 2A 的外部接口安全验证混在同一次代码提交中。

## 4. 关键代码与入口

| 关注点 | 当前文件 |
|---|---|
| RH 请求、Workflow/App 任务分派 | `nodes/rh_client.py` |
| RH Config、`is_ai_app` | `nodes/rh_config.py` |
| 活动 V3 节点 Schema、Execute、Params V2 | `nodes/rh_native.py` |
| 参数列表组装、兼容层 | `nodes/rh_params2.py`、`nodes/rh_param_bundle.py` |
| Workflow Inspector / 字段 Schema | `nodes/rh_workflow_inspector.py`、`nodes/rh_workflow_schema.py` |
| Execute 真实提交/预检 | `nodes/rh_execute.py`、`nodes/rh_execute2.py` |
| 已确认 Task ID 保存 / 重下 | `nodes/rh_task_journal.py`、`nodes/rh_download.py`、`nodes/rh_task_manager.py` |
| V3 迁移、动态输入前端 | `js/rh_native_migration.js`、`js/rh_native_ui.js`、`js/rh_native_groups.js` |
| 阶段 2 具体接口和预期文件清单 | `docs/AI_APP_STAGE2_PLAN.md` |

历史 `RH_MultiParams` 源码尚未注册给 ComfyUI；正式参数节点是 `RH_Params2`，勿因找到源文件就误当作在用节点。

## 5. 回归与安全操作

在 `G:\GitHub\ComfyUI_RH_API` 根目录执行：

```bash
python -B tests/run_tests.py
node --test tests/native_migration.test.mjs
G:/AIGC/ComfyUI/python_embeded/python.exe -B tests/verify_native_schema.py --comfy-root G:/AIGC/ComfyUI/ComfyUI
python -B tests/probe_live_8190.py
node tests/probe_live_ui_8190.mjs
node tests/probe_live_official_8190.mjs
git diff --check
```

- 每个真实后端/浏览器测试先检查 8190 进程是否已启动、队列是否为空；不要因为断言失败直接重启服务或清空队列。
- `tests/probe_live_official_8190.mjs` 依赖本机 WorkspaceKit 已安装的 Playwright，并通过 **8190 测试包**专属流程暂存和清理测试工作流；不能拿去对 8188 运行。
- 禁止打印任何密钥、含鉴权参数的 URL、完整 App 请求体；禁止提交 `config.local.json`、`.rh-task-history/`、用户工作流 JSON 或媒体文件。
- 由于旧 Lab 已回收、两个测试包共享 Python，严禁未经授权清理 Lab 归档、安装依赖、对用户正式 output 目录做批量操作。

## 6. 状态边界、故障恢复

- **当前已验证：** 用户 Workflow Plus 生成、原 MP4、自定义保存、原 Task ID 查询/下载；8190 独立 SaveImage；既有 Schema/UI/保存重载基线。
- **仍未验证：** 国际站真实 AI App 参数只读接口返回格式；AI App 真实任务；AI App Plus/Ultra；新版自动字段下拉；真正的全链路上传前闸门。
- **阶段 1 的唯一未生效项**：正在运行的 8190 进程还可能监听 `0.0.0.0`；BAT 已改为本机监听，**下一次经授权重启才生效**。
- **如果当前 Git 目录中有未知未提交文件**，先列出并确认所有权，绝不清理/重置/覆盖；不要以本文的时间点假定工作区永远干净。
- **测试环境不能证明主环境 8188 已使用同样的新版 Python 代码**：以实时版本/节点注册/重启状态为准。

## 7. 下一窗口建议的第一条任务

> 使用 CodexPro 打开 `G:\GitHub\ComfyUI_RH_API`，先读 `docs/HANDOFF_NEXT_STAGES.md` 和 `docs/AI_APP_STAGE2_PLAN.md`，核对 Git 与 8190 测试环境状态。先执行 **阶段 2A：RH 国际站 AI App 的只读元数据接口和凭证风险检查**，给出官方响应结构及安全实现结论，再按 Gate 决定 2B 开发。不要修改 8188、安装共享依赖、重启服务、运行付费 AI App 或 push；除非另行得到授权。
