# 当前 MCP、CLI 与校园制作入口

校园创意、资料、需求和验收由本 Skill 组织；当前执行优先使用 **Agent → MCP → CLI → 编辑器**。先读 [原生执行](native-execution.md) 和当前实际返回的工具 schema、CLI 帮助；旧案例与历史工具名不是现行接口契约。用户指定的入口、工程范围、费用及复制/备份约定沿用会话，不因换底座重新推导权限。

## 怎样开工与续做

1. 用实际注册的 `awc_editor_status`、`awc_project_list`、`awc_project_get`、`awc_cli_help` 核对连接、项目身份和能力。连接成功、已登录和支持修改目标工程分别确认。
2. 从当前底座读取 `world-production` 与 `tool-guide`，再按 [工具路由](tool-routing.md) 只查本轮需要的原子操作合约。`awc_cli_read` 仅调用其允许的只读命令，其他受支持命令经 `awc_cli_run`；需确认的操作传 `confirm:true`。
3. 新制作使用 `world create/next/dispatch/settle/control`：主 Agent 组织合同、任务与会话派发，宿主运行器启动真实子会话，CLI 登记状态并执行原子能力。CLI 不会自行启动模型。校园任务在 `skills` 中声明 `campus-world-build`，以固定本轮 Skill 引用与 hash。
4. 已有校园先恢复真实工程、保存状态、任务与未知操作，只处理本次差量。先核目标工程的实际读、施工、保存和试玩准入；制作会话必须满足当前设计合同及独立审查要求。读取工作单、注册会话或工具返回成功均不代表校园完成。
5. 按 [自主循环](autonomous-loop.md) 看实图、正常试玩、保存冷开并更新清单。未知生成或写入先查询原任务和现场，不新建一轮来覆盖原结果。以 `world audit/deliver` 和当前真实场景证据交付，不凭文件齐全代替质量验收。

## 现有工程与能力缺口

正式工程可能仍受 TEST-only 施工保护。当前版本若支持显式的已保存工程审计，其用途是锁定名称、路径和源 SHA 后只读查看及正常试玩；**审计不开放施工或保存**。按实际帮助及底座的已保存工程审计说明读取参数，不能把审计权限扩写为编辑权限。

复制与备份遵守当前会话约定。用户拒绝复制、恢复文件或备份时，不创建这些文件；当前保存若强制备份，或施工仅支持 TEST 工程，就记录该项能力缺口，保留现场并继续可完成的研究或只读验收。不能改项目名绕过保护、偷偷使用旧桥、手改工程或回退到被禁止的电脑操作。

## 官方指南与历史经验

官方指南帮助理解功能前提和验收，当前工具 schema、CLI 合约及实机结果决定怎样执行。历史案例只用于诊断，不能证明当前入口已可用、费用为零或全平台已通过。曾使用的社区桥和 `canvas_*` 等名称不作为默认调用路径；当前工具未注册就不构造调用。

保留的历史资料来源：[官方使用指南](https://bytedance.larkoffice.com/wiki/L62IwH7IViyqVjkcJtscVHwRndc)、[静态模型、Agent 与 MIX](https://bytedance.larkoffice.com/docx/C1nBdcjSfomdBrxqSqBciHVln9c)、[AI 地形与环境编辑](https://bytedance.larkoffice.com/docx/RjT6d0i4ioOVHJx769rc1xpjnWb)、[保存、真机预览与调试](https://bytedance.larkoffice.com/docx/R08udaO3ioaUdRxg1HJcGjhin1c)。这些链接可能需要权限，内容需按当前版本核实；[案例教训](case-lessons.md) 保留已知失败与恢复方法。
