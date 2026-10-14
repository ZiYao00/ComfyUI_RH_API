# RH AI App 阶段 2：执行前设计与风险清单

> 状态：**PREPARED / NOT IMPLEMENTED**。日期：2026-10-13。此文档仅供下一轮执行时使用。
> 范围：国际站 www.runninghub.ai 的 **AI App（webappId）**，并保留现有 Workflow 兼容路径。
> 禁止：本阶段未授权的付费任务创建、上传用户媒体、修改 8188、自动提交 Git 或推送远端。

## 1. 现有事实

- 目标 ComfyUI Core 0.39.0 / Frontend 1.55.14；测试环境 8190。
- `RH_Config` 已有 `is_ai_app`；`RHClient.create_task(..., is_ai_app=True)` 已实现 `POST /task/openapi/ai-app/run` 并以 `webappId` 和 `nodeInfoList` 组包。
- 当前 App 路径的**离线 HTTP mock**通过；没有执行真实 AI App 付费任务。
- `RH Workflow Inspect` 及其 `RH_WORKFLOW_SCHEMA` 明确拒绝 App。Workflow 的 schema 不适用于 App 的 `inputNodes/nodeInfoList`。
- 当前 `RHClient` **拒绝 AI App 的显式非 auto Instance Type**。Workflow 的 Plus 已由用户实测通过，但不能据此推出 AI App Plus 也可用。
- 现有 `RH_Params2` 可手动构造任意 `nodeId / fieldName / fieldValue`；自动 App 字段选择尚不存在。
- 8188 / 8190 原 output Junction 已在阶段 1 解除；8190 本地 SaveImage 实测写入独立 output。两个启动 BAT 已改为 `127.0.0.1:8190` 和明确 `--output-directory`。正在运行的旧进程尚未重启，其监听地址不因 BAT 改动而自动改变。
- 本地任务历史路径 `.rh-task-history` 位于插件仓库中，仍由两个 ComfyUI 环境共同访问；阶段 1 只隔离**视频/图片输出目录**，没有修改任务历史策略。

## 2. 接口与证据

官方 API 文档（2026-10-13 查阅）：

1. `GET /api/webapp/apiCallDemo`：https://www.runninghub.cn/runninghub-api-doc-cn/api-425749011 。文档展示 `nodeInfoList`、`fieldType`、`fieldData`、`description` 等；有 `STRING`、`IMAGE`、`LIST` 等样例。
2. `POST /task/openapi/ai-app/run`：https://www.runninghub.cn/runninghub-api-doc-cn/api-425749010 。现有 RHClient 已调用此接口。
3. 官方交互示例：https://www.runninghub.ai/runninghub-api-doc-en/doc-8287470 。例子展示从 `apiCallDemo` 读 App 节点列表，并把 `nodeInfoList` 用于运行。
4. 官方国际站首次支持情况必须以 **www.runninghub.ai** 的实际只读响应确认为准，不能假设国内站全部字段格式完全相同。

**接口安全门槛**：官方 `apiCallDemo` 示例把 API Key 放入 **GET 查询字符串**。URL 可能进入代理、异常记录或日志。不得直接将该 URL 记录到节点日志、ComfyUI workflow、浏览器日志或 Git。先研究是否有受支持的安全 Header/POST 等价方式；如果没有，明确限制：HTTPS 官方域名 allowlist、禁止重定向、短超时、禁用 URL/响应正文日志、仅在用户授权的读取行为中调用，并披露风险。禁止把 App 原始默认 Prompt、私有文件名或密钥存入持久缓存。

**大整数门槛**：例子 App ID `2109843724737204225` 大于 JavaScript 的安全整数范围。在浏览器/组件 state 中必须一直使用 **字符串**，只在 Python 构造 API 请求时按协议转换，绝不能在 JS 中使用 `Number(webappId)`。

**实例门槛**：当前官方 `ai-app/run` 示例未证实 `ultra` 支持，亦未完成 App Plus 的真实权限/计费验证。先保留 `auto`；其他实例应在确认接口正式契约及单独付费授权后解锁，不得因为 Workflow Plus 可用而无条件放通。

## 3. 建议架构

- **客户端层**：为 `RHClient` 新增只读 App 元数据读取适配器。不改动稳定的 Workflow `getJsonApiFormat`。
- **纯解析层**：新增 `rh_ai_app_schema.py`，将 App `data.nodeInfoList` 转为受控 `RHAppSchema`。每项携带原始 **nodeId（字符串）+ fieldName + fieldType + fieldData/选项 + 描述**，同时生成不含私有输入值的结构指纹。允许多个字段共享同一 nodeId；主键应为 `(nodeId, fieldName)`。
- **类型映射**：STRING -> 文本；LIST -> 选项（验证 `fieldData` JSON，仅接受合法的 `index/name`；单独识别 `default` 元信息）；IMAGE/AUDIO/VIDEO -> 媒体占位/文件值；未知类型应报告“不受支持”而非静默转换。
- **身份与有效期**：`RHAppInspection` 绑定 App ID、账号 credential scope、区域域名、检查时间；App ID/账号切换、区域切换、过期后需要重新检查。格式与既有 Workflow schema 的安全原则一致，但 **禁止把两种结构互当作另一种**。
- **新节点**：推荐新增 `RH_AIAppInspect`（显示名 RH AI App Inspect），输出 `RH_APP_SCHEMA` + `STRING field_report`。优先独立节点；避免扩充现有 `RH_WorkflowInspect` 而影响旧工作流。
- **执行校验**：给 `RH_Execute` **追加可选**的 `app_schema` socket；当 `is_ai_app=True` 且连接此 socket 时，检查最终合并的 `RH_PARAMS`，错误时必须在付费 `create_task` 前停止。禁止 App 同时连接 Workflow schema；不连校验的旧工作流仍按原逻辑运行。现有输出 7 项保持不变。
- **用户体验范围**：阶段 2 先提供一个可以单独 Queue 的只读 App 字段检查节点和安全校验；**直接把 RH Params V2 变成动态 Node/Field 下拉**属于后续 E1，不应与阶段 2 第一轮混做。

## 4. 分段实施与 Gate

### 2A：官方元数据可用性 / 凭证保护验证

- 以 `2109843724737204225`（此前已配置的 RH AI App ID）作为候选，只进行**获得明确授权的只读元数据查询**。
- 确认 `.ai` 响应码、字段类型、完整性、`fieldData` 格式与鉴权；不发送 `ai-app/run`、不上传任何媒体。
- 只有解析接口与安全方案通过才继续；若接口在国际站不可用，先提供可导入的手动脱敏 `nodeInfoList` JSON 回退方案。

### 2B：离线解析、App 节点及类型验证

- 建立真实形状的**脱敏 JSON fixture**，覆盖 STRING、LIST、IMAGE、AUDIO、VIDEO、未知/不规则 fieldData。
- 确认同一 Node ID 的多个 Field、空字符串、零、布尔值、顺序、重复键、无效 ID 和大整数。
- 纯解析/校验与 UI schema 分层，测试不依赖 ComfyUI 和真实账户。

### 2C：执行前 App schema 校验

- 在稳定的 `RH Execute` 旁追加可选 `app_schema`，严格检查 App ID、账号、区域、过期、nodeId+fieldName、LIST 选择。
- AI App 与 Workflow schema 互斥；错误参数必须产生 **0 次付费 create-task POST**。
- 刷新、保存/打开、复制粘贴、旧工作流迁移及 RH_PARAMS fan-in 的断言不能降低。

### 2D：实例类型与后续联动

- 研究 AI App `instanceType` 的当前国际站契约；仅官方确认并单独授权时才真实测试 Plus/Ultra。
- 与阶段 3 的智能 Params UI / 上传前统一 Preflight 对接，避免重复制造第二套动态输入系统。
- 只在 8190 通过真实 UI 和无付费后台测试后提出主环境升级方案。

## 5. 预计修改文件（**尚未修改**）

- `nodes/rh_client.py`：只读 App 元数据客户端适配器，实例类型策略待证实。
- `nodes/rh_ai_app_schema.py`（新）：解析、类型和校验规则。
- `nodes/rh_ai_app_inspector.py`（新）：字段报告与元数据查询。
- `nodes/rh_native.py`：注册只读检查节点与附加 Execute 可选输入，保留所有旧控件的位置。
- `nodes/rh_execute.py`：分派 App/Workflow schema 校验、互斥与 paid POST 闸门。
- `__init__.py`：保留已有公开 node id，追加新节点注册。
- `tests/test_rh_ai_app_*.py`（新）、`tests/verify_native_schema.py`、`tests/native_ui_cases.js`：完整兼容回归。
- `docs/ARCHITECTURE.md` / `docs/QUICKSTART.md` / `docs/NATIVE_UI.md`：仅在实施后同步真实行为。

## 6. 明确不包含

- 不进行任何真实云端付费生成；不重复 2 秒 / 30 秒 H3 性能测试。
- 不改 `RH_Params2` 现有输入和保存格式，不新增通用“自动生成整个 App UI”的第二套 Widget 系统。
- 不实施全图上传前的统一 Preflight：该功能需要单独解决 ComfyUI 上游执行顺序，不能伪称靠 Execute 可选连线完成。
- 不对 8188 主包、共享 Python 依赖或本机密钥做任何修改。

**下一轮开工判断：** 先通过 2A 的 read-only metadata 与凭证安全 Gate，确认国际站 App ID 的真实返回结构，再批准 2B / 2C 的代码修改。此文档是实现方案，非实现/验收结果。

## Preconditions after R0–R4 isolated Config work (2026-10-13)

An unpromoted maintenance worktree is preparing an ignored **single** `config.json` with region-scoped keys and an appended RH Config `site` selector. This does not mean the international AI App metadata read (stage 2A) was verified. Implement the App Inspector only after the security/config worktree is reviewed, the test 8190 plugin code is isolated from 8188, and real metadata shape/authorization is confirmed without a paid task. Never reintroduce a second credential file or put API keys into a GET URL without a separately accepted risk gate.
