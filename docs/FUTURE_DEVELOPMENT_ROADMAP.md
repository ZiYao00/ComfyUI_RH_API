# ComfyUI RH API — 未来开发路线图与恢复入口

> 更新：2026-10-14
> 状态：**PARKED / 需求已记录，未授权立即开发新功能**。这是待办和验收约束，不代表相应功能已经实现。
> 本文优先级以本次会话确认的“**8188 主包禁止操作；8190 仅在明确允许的范围内使用；暂不隔离 8190 插件代码**”为准。用户未来可以调整这些限制，但旧授权不能自动延续。
> 当前开发版位于独立 Git 工作树 `[workspace:ws_720d21c89978685ec1f0b855]`，不要误认为它就是 8190 当前正在加载的插件。

## 0. 项目位置、现状和已有能力

| 范围 | 已确认的状态 | 对用户的价值 |
|---|---|---|
| 原有 A1–C3 | Workflow Inspector、Workflow Plus/H3、Task ID 记录、查询/恢复下载、原 MP4 保存和自定义命名已开发；其中 Plus 生成和任务下载有此前真实成功记录 | 当前可继续使用成熟 Workflow 路径 |
| 配置归一 | 唯一私有运行配置为 Git 忽略、不跟踪的 `config.json`；旧 8188 兼容字段暂留在同一文件 | 减少多份配置与 Key 意外入库 |
| R0–R4 安全与 Config UI | **独立开发版已实现、离线验收通过，尚未部署到真实 8190** | 后续部署后才会获得国际/国内/自定义下拉、安全加固及迁移能力 |
| 测试证据 | 129 Python + 24 JS 迁移 + 20 Core Schema + 136 隔离前端交互 = **309/309**；见 `R0_R4_TEST_CLOSEOUT_2026-10-14.md` | 证明开发版当前测试范围内的行为 |
| 8190 实际运行 | Core `0.39.0`、Frontend `1.55.14`；旧 `RH_Config` 尚无 `site` 下拉，尚未加载上面的开发版 | 不把“离线 PASS”误当“正式可用” |
| AI App | `RHClient.create_task(is_ai_app=True)` 有已有路径；AI App 的**专用元数据 Inspect / 类型校验 / 动态字段**仍未开发或实测 | 下一大功能方向，而非已有 Workflow Inspector 的重复开发 |

**起步顺序：保持现有开发版冻结 → 以后经用户明确授权才解除 8190 隔离/部署限制 → 安全地验收现有改动 → 2A → 2B → 2C → 2D → 3 → 4 → 5。**

该顺序是依赖顺序，不是工期承诺。第 2A 的文档/接口研究可先做，但将其接入真实插件运行仍有部署 Gate。

## 1. P0：现有开发版的未决部署与安全门槛（当前暂缓）

**目标**：在不影响 8188 的前提下，让真实 8190 使用已通过离线回归的版本。用户目前**明确不允许**开展插件代码隔离，故此阶段标记为 **BLOCKED BY USER CHOICE / DEFERRED**；不得擅自修改任何运行中插件或重启服务。

需要在未来重新授权后完成：

1. 核实 8190 真正加载的自定义节点绝对路径，先设计**不会使 8188 被动获取新版 JS/Python 的独立加载方案**；测试输出目录隔离不等于插件源码隔离。
2. 保留既有工作流、旧 `RH_Config.base_url` STRING 连线、`RH_CONFIG` 输出、原节点 ID、所有输入参数与 Widget 位置；对复杂子图与旧 API Prompt 采用显式失败保护，不静默转换。
3. 在 8190 实机验证 Base URL 三选项、Custom URL、保存/打开、刷新、复制粘贴、Undo/Redo、旧图迁移、关联下载；只使用**不收费**的检查/已有 Task ID。
4. 完成自定义域名 DNS 解析/重绑定与媒体下载 SSRF 风险评估；注意现在有 HTTPS Origin/重定向限制，但还没有全面的 DNS 地址绑定级防护。不得宣称完全 SSRF 安全。
5. 复核 `config.json` 的国际/国内 Key 绑定和旧版根级兼容字段；**禁止复制/覆盖原环境或工作树的真实私有 Key 文件**，不得在 Git 中跟踪该文件。
6. 8190 当前运行进程是否仍监听 `0.0.0.0` 需要未来独立验证；启动脚本中的 `127.0.0.1` 设置并不代表旧进程已生效。重启须另行授权。
7. 评估 `.rh-task-history/` 当前共用路径是否需要按服务实例隔离；避免误认为 8190 的 output 隔离涵盖任务历史。

**完成标准**：确认新 JS/Python **实际从 8190 载入**，完整原生 UI/后端/旧流程回归可追溯，8188 未受影响；用户审阅部署和安全报告。**目前未满足。**

## 2. 阶段 2 — RH 国际站 AI App 智能参数识别

详细执行前方案见 [AI_APP_STAGE2_PLAN.md](AI_APP_STAGE2_PLAN.md)。已有 `RH_WorkflowInspect` 专门面向 **Workflow**；新功能必须识别 **AI App/webappId**，不要让两个 Schema 相互伪装。

### 2A — 官方接口与账号安全验证（第一优先功能研究）

- **只读**调查国际站 `https://www.runninghub.ai/api/webapp/apiCallDemo` 当前支持情况、正式请求方式和是否可使用安全的 Header / POST 等价鉴权。官方示例可能使用 GET URL 携带 API Key，不能未经风险批准照搬。
- 候选 App ID：`2109843724737204225`（JS 和 workflow 内始终作为 **STRING**，绝不转换为 JS Number）。
- 用脱敏数据确定实际返回是 `data.curl`、直接 `nodeInfoList`，还是其他包装形式；不能只依赖某一个官方文档中的示例。
- 验证 `nodeId`、`fieldName`、`fieldValue`、`fieldType`、`fieldData`、`description` 是否存在；LIST 的 `fieldData` 可能是 JSON 字符串并含独立 default 条目。
- 不执行返回的 cURL、Shell 或 POST 示例；不保存原始默认 Prompt、真实私有文件名、签名 URL、API Key；不调用 `ai-app/run`，不上传素材，不产生付费任务。
- 由于之前真实元数据请求未完成安全验收，**2A 仍为 PENDING**；若官方接口不可用，提出“手动导入脱敏 nodeInfoList JSON”的只读回退路线，不伪称能在线识别。

**Gate**：国际站真实只读响应的真实性、鉴权、脱敏和 JSON 结构已确认；未拿到安全数据就不开始 2B 的在线数据路径。

### 2B — 独立 AI App Inspector + 类型解析（高优先）

- 计划新增 `RH_AIAppInspect`，输出 `RH_APP_SCHEMA` 和可读的 `field_report`；与现有 Workflow Inspector **分开**。
- 解析支持实际证实的 `data.curl` 包装和直接结构，**只解析文本，不执行命令**。
- 纯解析层处理 `STRING`、`LIST`、`IMAGE`、以及经真实响应证实的 `AUDIO`、`VIDEO` 等；未知类型明确报告不支持，不静默猜成 STRING。
- 以复合键 `(nodeId, fieldName)` 区分字段；一个 Node ID 可有多个字段。保留空字符串、数字零、false、顺序以及可选默认值。验证 LIST 可选项的 `index/name` 与 `default` 分界。
- Schema 应绑定账号凭证 Scope、区域、App ID、时间/有效期；结构指纹不得包含私有值。准备真实形状的**脱敏 fixture** 后再做解析和 UI。
- 单独 Queue 只读 Inspector 时不得误运行同一图里的其他付费输出节点；应使用独立检查工作流。

**Gate**：纯解析不联网测试 + 当前 8190 Core/Frontend Schema/UI 测试通过，Workflow Inspector 行为未变化。

### 2C — Execute 提交前 App 参数安全校验（高优先）

- 向既有 `RH Execute` **末尾追加可选**的 `app_schema` Socket，不移动旧 Widget/输入位置，不改变 7 个输出类型及下标。
- 当 `is_ai_app=True` 且连接有效 App Schema 时，校验 App ID、账号、区域、元数据时效、Node ID + Field Name、LIST 选项、最终合并的 `RH_PARAMS`。
- AI App Schema 与 Workflow Schema **互斥**；无效参数要求 **0 次付费 create-task POST**。不连接新 Socket 的旧工作流按原有行为，不能静默改成强制新协议。
- **边界**：校验发生在 Execute 之前，并不证明上游 Image/Video Upload 尚未执行。因此 2C 不能宣称“上传前全图预检”。
- 旧 Autogrow 16 路、字段冲突覆盖顺序、值类型、连线、子图和工作流持久化必须回归。

**Gate**：App/Workflow 两条校验路径独立通过，非法请求没有付费 POST，旧工作流输入和输出契约未破坏。

### 2D — AI App Plus/Ultra 实例策略（中优先，需单独批准）

- 不能从 **Workflow Plus/H3 已成功**推导 **AI App Plus/Ultra** 也可用。
- 先核实官方 AI App `instanceType` 合法值、国际站是否开放以及计费影响。
- 默认保持 `auto`；只有官方契约明确且用户**单独授权付费测试**后，才研究开放 Plus/Ultra。
- 不重复用户已完成的 30 秒 H3 性能测试。

## 3. 阶段 3 — RH Params V2 智能参数配置（高收益）

**目标**：由“人工查 Node ID、复制字段名、填值”变为“按 Workflow/App Schema 可视化选字段，按类型设置参数”。

- 从有效 Schema 驱动 Node ID、Field Name、字段类型和 LIST 选项下拉；保留 `Custom` 入口与用户自由文本、自定义值、外部 STRING/多类型输入连接。
- 适配 TEXT/STRING、数值、BOOLEAN、LIST、图片/音频/视频字段；类型支持以官方接口实际证据为准，不能将所有值强行当 STRING。
- 优先当前 ComfyUI Frontend 正式 `DynamicCombo` / V3 已验证机制；保留原 `RH_Params2` 节点 ID、现有动态输入与保存格式，不为了下拉重写第二套 DOM Widget 系统。
- 强调状态来源唯一：Schema → 字段选择 → 有效值；切换字段或 App 时不能让过期值静默流入另一项。
- 对已连接值、稀疏编号、空值、0/false、复制粘贴、撤销重做、Save/Open 和子图制作专门的失败回归。

**收益**：重复使用 RH App/Workflow 时不用手查 fieldName，减少字段名称错误和人工维护成本。**前置**：2B/2C 的类型语义及安全闸门稳定。

## 4. 阶段 4 — 全图 Preflight / 批量和 Agent 自动化（分开决定）

### 4A — 真正发生在媒体上传之前的 Preflight（高优先）

- 独立无上传检查工作流或正式可证明的执行闸门，验证 App/Workflow 身份、必需字段、字段类型、媒体来源、图片/视频路由、实例、预估计费等。
- 必须依据 ComfyUI 实际调度和输出节点依赖关系设计。**只在 Execute 追加 `app_schema` 无法阻止上游 Upload**，不能作为 4A 交付。
- 提供“检查通过 / 错误原因 / 用户确认提交”的清晰边界；未通过不上传、不创建付费任务。

### 4B — 批量任务与 Agent 编排（候选，不自动启动）

- 只有用户确实需要时再单独设计多任务队列、并发/额度上限、逐任务 ID 记录、断点恢复与下载目录规则；避免为了预期需求提前实现复杂调度器。
- 已经有 `rh-agent-service` 等外部 Agent 编排方向；应先调查是否由独立服务负责批量调度、插件只负责稳定节点和任务查询，防止重复造轮子。
- 任何“再次提交”必须区分已创建 Task ID 的**查询/下载恢复**与可能扣费的**新建任务**，不能因网络超时自动重试 paid POST。
- 付费批量、真实素材上传、云端任务删除/取消均需独立授权。

**收益**：先挡住无效上传/付费任务；自动化在需求成熟后再接入，降低重复开发和运维成本。

## 5. 阶段 5 — 版本验收、文档和发布准备（当前不执行）

- 在用户另行允许时，以真实 8190 为唯一开发/测试目标，核对插件来源、节点注册、Frontend/Core 版本、回归、复杂旧工作流、任务下载；**不操作 8188**。
- 维护两个状态：**已通过离线测试的代码**与**8190 已装载并真实验收的版本**，不能混写。
- 统一 `README.md`、`README_CN.md`、`QUICKSTART`、`ARCHITECTURE`、接口文档、示例工作流和版本发布说明。
- Git 开发分支与 `main` 分开。未来是否合并主分支、升级 8188、打包发布，均需要**新的显式授权**。
- 复核 Git 忽略（`config.json`、运行日志、`.rh-task-history/`、真实媒体/Key）、外部远端和未提交状态；不自动复制私有配置。
- 不重复已跑通的 30 秒 H3 压力测试。

## 6. 不做和不能假设的事情

- 暂不隔离 8190 插件代码；禁止碰 8188，包括代码/配置、服务操作和间接共享文件修改。
- 暂不运行 AI App 付费任务、不上传真实媒体、不安装共享 Python 依赖、不自动重启服务。
- `RH_WorkflowInspect` 已存在 ≠ `RH_AIAppInspect` 已存在；`RH_PARAMS` 自定义字段功能已存在 ≠ 智能下拉已实现。
- 8190 有独立 `output` ≠ Python/JS、插件源码、任务历史都已隔离。
- 离线通过 309 项回归 ≠ 实际 8190 新版已安装 ≠ 防护已能抵抗所有 DNS/SSRF 风险。
- 实际 Git 推送了隔离开发分支 ≠ `main` 已更新/运行中的插件已升级。

## 7. 以后继续开发时，从哪里开始？

先阅读，**不要直接写代码**：

1. 本文 `docs/FUTURE_DEVELOPMENT_ROADMAP.md` — 长期路线、优先级、用户边界。
2. `docs/HANDOFF_NEXT_STAGES.md` — 已有成果、真实运行历史、恢复入口。
3. `docs/R0_R4_TEST_CLOSEOUT_2026-10-14.md` — 配置与安全加固真实测试证据、未部署 Gate。
4. `docs/AI_APP_STAGE2_PLAN.md` — 2A–2D 官方接口、类型、节点契约与开发细节。
5. `docs/ARCHITECTURE.md`、`docs/NATIVE_UI.md`、`docs/QUICKSTART.md` — 原节点契约和兼容性说明。

建议第一轮的问题是：“现在是否允许为 8190 建立真正独立的插件加载路径，并进行部署验收？”如果仍不允许，只做文档研究/离线解析与 mock，不把新版代码送入任何运行环境。

### 恢复时的基线测试

从实际开发工作树执行，测试命令本身不创建 RH 付费任务：

```bash
python -B tests/run_tests.py
node --test tests/native_migration.test.mjs
G:/AIGC/ComfyUI/python_embeded/python.exe -B tests/verify_native_schema.py --comfy-root G:/AIGC/ComfyUI_test/ComfyUI --export
node tests/verify_native_ui.mjs
git diff --check
```

**完成标准与提交规则**：每项 Gate 分别给出实现、离线单元、真实 Schema/前端测试、8190 实机验收及（如授权）外部服务实测的独立状态；修改前检查 `git status --short`，不得触碰 8188。后续提交/推送按届时用户授权执行，不能把本文当作永久授权。
