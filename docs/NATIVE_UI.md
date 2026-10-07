# RH 原生输入与 Upload 界面规范

更新日期：2026-10-07。适用于本项目此次原生 UI 改造，不代表已发布版本或真实云端任务验收。

## 1. 当前实现与启用方法

本轮在 ComfyUI 0.39.0、前端 1.53.10 的实际安装环境验证，使用已有 V3 API，没有安装或升级依赖。这里记录的是已测组合，不是未经验证的最低版本声明。

先保存当前工作流的原始副本，再重启 ComfyUI 后端，随后在浏览器按 Ctrl+F5。仅刷新网页不能重新注册 Python 节点。本轮自动化没有启动或重启用户的 ComfyUI 服务；浏览器回归直接读取本机已安装的 frontend package，因此与 8188 是否运行无关。

旧工作流应从原始副本打开，检查参数和连线后另存为新文件，不直接覆盖唯一原件。首次检查优先查看 RH Params V2、RH Upload Image V2、RH Execute、Upload Video、Upload Audio。

## 2. 使用与界面规则

### RH Params V2

每组只有一个正式 Value 输入：可以本地填写，也可以在同一个输入上连接 STRING、INT、FLOAT、BOOLEAN。连接方式和控件显示由 ComfyUI 原生前端管理，不再手工创建顶部 wildcard value_N 与下方 local_value_N 两套字段。不能向标量 Value 连接 IMAGE 等媒体对象。

Param Count 控制 1 至 16 组。每组只保留 Node、Field、Value；Field 选择 custom 时，由原生 DynamicCombo 显示 Custom Field。RH Params V2 不提供 Enable：空 Node ID 的空行自然不会输出，不再维护第二套“是否启用”状态。相邻可见参数组之间使用实际 4 px 的纯视觉 spacer，仅参与画布布局，不序列化、不进入 prompt、不参与 RH 参数执行。

修改普通 Value 内容不应改变节点宽高。减少 Param Count 不弹确认框：超出 Count 的行立即从活动 UI 和本次执行中消失；在同一编辑会话里再次增大 Count，会恢复该行先前的值和外部连线。这里的额外连线恢复由本扩展的会话缓存补足官方 DynamicCombo 的值缓存。该缓存不是持久化存储：如果在缩减状态保存、关闭或刷新后再打开，未激活行不承诺跨会话恢复，因此需要长期保留的隐藏行应先恢复 Count 再保存。

### Upload 系列

公共字段统一由原生 schema 定义。保留媒体类型与业务差异，不强行把所有节点改成多文件或统一返回类型。

| 节点 ID | 输入与业务边界 | 输出 |
| --- | --- | --- |
| RH_UploadImage2（显示名 RH Upload Image V2） | 1 至 12 组原生配置；真实 IMAGE 输入；每组独立 Node/Field/Custom；无 Enable；可见组间 4 px | RH_PARAMS |
| RH_UploadImage | 单路 IMAGE；可仅上传，也可加入参数列表 | STRING filename、RH_PARAMS |
| RH_UploadVideo | 原有 VIDEO 输入，不改为路径或帧数组 | STRING filename、RH_PARAMS |
| RH_UploadAudio | 原有 audio_path 文件路径，可连接 RH Load Audio Path；不是 AUDIO 波形输入 | STRING filename、RH_PARAMS |
| RH_UploadFile | 保留文件路径与目标字段的平面 API | RH_PARAM |
| RH_UploadLatent | 保留 LATENT 和明确的远端字段名 | RH_PARAM |
| RH_BatchUploadImage | 八个既有图片入口，共享目标，保持批量任务语义 | RH_PARAM_BUNDLE |
| RH_MultiInputImage | 八组既有图片/节点/字段平面输入，保持单次运行的多图语义 | RH_PARAMS |

单路 Image/Video/Audio 的 Custom Field 保持普通原生字符串输入并标记 advanced，仅 Field=custom 时使用；保留字段名和序列化顺序，不用改变已发布 API 来换取隐藏效果。

RH_UploadMask 的源文件原本就存在，但包入口的导入和注册均被注释。本轮没有擅自启用它，也不把它计入已改造的八个在用 Upload 节点。

## 3. 实现分层与接手约束

`nodes/rh_native.py` 是 RH Execute、RH Params V2 与八个在用 Upload 节点的活动 V3 schema 入口；`__init__.py` 保持既有公开节点 ID，再将 `RH_Execute` 映射到新的 V3 实现。Upload 旧模块继续负责媒体编码和 RH HTTP；`rh_execute2.py` 作为共享的多 RH_PARAMS 合并/执行服务，同时保留 `RH_Execute2` 旧节点用于历史工作流兼容。RH HTTP 协议和付费提交策略没有切换。

`js/rh_native_ui.js` 使用扩展生命周期钩子协调迁移与标签。`js/rh_native_groups.js` 为 Params V2 / Upload Image V2 的官方 DynamicCombo 补充同会话的值与连线恢复，并为两类分组插入 4 px 非交互 spacer；它不创建业务输入/接口，不替换 prototype.configure，也不把会话缓存伪装成持久化格式。`js/rh_native_migration.js` 只处理历史图工作流数据。

旧 `js/rh_params2.js` 与 `js/rh_upload_image2.js` 保留为无操作说明入口，避免恢复手写 DOM 或双输入设计。旧 Params Python 解析器作为内部/历史兼容服务保留，不能据此重新暴露旧 UI。

已验证的生命周期事实：DynamicCombo 在切换 Count 时会拆除旧子控件，并由官方 `removedWidgetValues` 恢复重新出现的 widget 值；但被移除输入的图连线会由官方 `replaceNodeInputs` 断开。因此本扩展在拆除前按输入名缓存有效链接，重新增大 Count 后再连接回来。普通值编辑不应主动调用 computeSize/setSize。

当前本机 ComfyUI 已公开提供 DynamicGroup，但本轮不为此重构现有分组：DynamicCombo、MultiType 与 Autogrow 已满足当前方案，继续保留经过验证的连接恢复与迁移逻辑。DynamicGroup 仅作为后续独立评估项，不与本轮稳定性修复绑定。显示名中的 V2 表示本项目第二代节点 UX，不等于 RunningHub HTTP V2 协议。

## 4. 历史工作流迁移边界

支持此次项目已有的顶层图工作流格式：旧 Params 2 的数字数量加位置值数组、对象行/JSON 行、上一版带 Enable 的原生 Params，以及旧 Image 2 对象行/带 Enable 原生格式。迁移在副本上校验，用临时原生节点生成新控件序列化数据，再按输入名重映射连线；保留节点 ID、独立目标、自定义字段和稀疏槽位编号。Params V2 与 Upload Image V2 都已移除 Enable；旧工作流中若某个 disabled 行仍含数据或连线，会明确阻止迁移，不能静默把它激活。

外部 value_N 连线和本地 local_value_N 值迁移到同一个原生 Value。若两份历史输入都连接而产生冲突，不能默默选一个。异常编号、重复槽位、缺失或无法映射的连接需要明确阻止，而不是用默认空值继续。

有两个限制必须明确：

1. 旧 Params 2 / Image 2 位于子图定义内时，不在本轮自动迁移范围。当前前端会在迁移钩子前实例化子图，直接修改 JSON 不能保证活动子图同步。需保留原件，在展开的副本上处理。
2. 旧实验节点的 API 格式 prompt 不包含完整图与迁移数据，不能直接套用新分组格式。应先打开并迁移原图，再重新导出 API prompt；固定输入 Upload 的平面 API 保持不变。

ComfyUI 会记录扩展钩子异常后继续加载，因此仅抛异常不是安全中止。发生迁移异常时，本扩展显示警告，将受影响的顶层组节点/子图入口保留为 `RH_MigrationRequired` 缺失节点占位，携带原类型、错误和历史数据，避免被当成正常空参数节点运行。原始磁盘文件不被修改。不要将警告状态另存覆盖唯一原件。

## 5. 已执行验证

| 层级 | 结果 | 范围 |
| --- | --- | --- |
| 原有 Python 单元测试 | 54/54 通过 | HTTP 客户端、任务提交安全、输出处理、历史解析等；模拟请求 |
| 当前真实 ComfyUI API/schema | 17/17 通过 | 十个 V3 类注册、Execute Autogrow、类型与输出契约、官方动态输入展开与 EXECUTE_NORMALIZED、上传参数传递；网络禁止/上传模拟 |
| JavaScript 迁移单测 | 13/13 通过 | 旧格式、Params/Image 上一版 Enable 格式、位置值回退、稀疏编号、异常拒绝、事务性与子图边界 |
| 实际安装前端的隔离浏览器 | 70/70 通过 | 精确显示名、Execute Autogrow/旧 Execute 兼容、Params/Image 无 Enable、4 px 非序列化分隔、Count 缩减无弹窗、同会话值与连线恢复、四种标量、Primitive/Reroute、保存重载、复制粘贴、撤销重做、迁移保护与主题切换 |

浏览器使用已有 Edge、1920×1080 视口，直接从已安装的 `comfyui_frontend_package/static` 提供真实前端文件，再注入本项目 schema 与测试来源节点；不要求 8188 运行，也没有把测试节点注册到用户服务。所有写请求都在隔离服务器内阻断或 mock。没有使用真实 RH 凭据，没有提交付费任务。

测试过程验证了 DynamicCombo 原生值缓存不足以恢复被移除输入的连线，因此加入按输入名的同会话连线缓存；故意触发的非法迁移会产生预期错误日志和阻断占位，不代表实际正常工作流失败。

本轮没有把以下事项标为通过：重启后当前用户全部第三方扩展混用回归、真实 RH 图片/视频/音频上传和执行、GPU 计算、用户对最终视觉效果的确认。导入真实 ComfyUI API 时出现 CUDA 驱动能力警告；本轮 schema 测试不依赖 CUDA，也没有据此调整驱动或依赖。

### 复测命令

在项目根目录执行。Windows PowerShell 调用带引号的解释器路径需加 `&`。

```powershell
python -B tests/run_tests.py
node --test tests/native_migration.test.mjs
& "G:\AIGC\ComfyUI\python_embeded\python.exe" -B tests/verify_native_schema.py --comfy-root "G:\AIGC\ComfyUI\ComfyUI" --export
node tests/verify_native_ui.mjs
```

路径是本次本机验证示例，生产代码未写死本机安装路径。UI 脚本默认读取本机已安装的 frontend package，不再依赖 8188；可用 `RH_UI_FRONTEND_ROOT` 指定其它已安装前端静态目录，用 `RH_UI_BROWSER` 指定已有 Edge/Chrome。缺少前端或浏览器时直接报告失败，不自动安装。

### 本地诊断产物

以下文件位于项目 `.ui-test/`，已被 Git 忽略，不作为源码提交：

- `ui-result.json`：本轮断言、请求阻断和诊断记录。
- `native-nodes-1920x1080.png`：Params V2 / Upload Image V2 / Video / Audio 场景。
- `native-nodes-theme-toggled.png`、`native-nodes-zoom60.png`：主题与缩放截图。
- `native-object-info.json`：隔离测试定义，包含仅供测试的来源节点。

截图用于后续人工视觉确认；自动化交互通过不等于用户已接受外观。隔离浏览器 profile 和早期失败诊断保留，不自动递归删除。

## 6. 官方依据

- [ComfyUI V3 迁移、MultiType 与动态输入](https://docs.comfy.org/custom-nodes/v3_migration)
- [官方数据类型](https://docs.comfy.org/custom-nodes/backend/datatypes)
- [前端扩展对象与生命周期边界](https://docs.comfy.org/custom-nodes/js/javascript_objects_and_hijacking)
- [前端 v1.53.10 DynamicCombo 实现](https://github.com/Comfy-Org/ComfyUI_frontend/blob/v1.53.10/src/core/graph/widgets/dynamicWidgets.ts)
- [前端 v1.53.10 扩展调用和异常处理](https://github.com/Comfy-Org/ComfyUI_frontend/blob/v1.53.10/src/services/extensionService.ts)
- [前端 v1.53.10 工作流、撤销重做与主题命令](https://github.com/Comfy-Org/ComfyUI_frontend/blob/v1.53.10/src/composables/useCoreCommands.ts)

未来更新先核对目标版本官方实现，再运行上述测试。不能仅因版本编号变化重写控件，也不能只通过旧 Python 测试就宣布新 UI 已完成。
