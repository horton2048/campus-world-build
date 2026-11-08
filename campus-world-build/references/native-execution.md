# 原生执行与依赖

## 开工查询

通过已注册的 `awc_editor_status`、`awc_project_list`、`awc_cli_help` 核对编辑器、项目和命令；`awc_cli_read` 执行允许的只读命令，`awc_cli_run` 内部执行 CLI，写入传 `confirm:true`。先读取相关命令的真实 JSON 合约，不猜字段。MCP 可用不等于每个 CLI 功能存在或已实测。

当前常用执行族：

| 阶段 | CLI 命令族，经 MCP 调用 |
|---|---|
| 测试工程 | `project list/copy-test`、`editor create-test/open/scene/save/close`；copy-test 仅在实际版本支持时使用 |
| 资产 | `library search/fetch/snapshot`、`asset inspect/import`、`resource *` |
| 摆放 | `surface geometry/sample`、`scene edit-inspect/edit-apply`；先从帮助和原生测量结果核对支持的动作 |
| 地形 | `terrain survey/sample/flatten-plan/flatten/smooth-plan/smooth` |
| 正常试玩与实图 | `runtime start/status/input/observe/media/stop` |
| 质量与续做 | `world progress/next/audit`、`world control`；按实际工具支持读取任务与证据 |

这里只列路由，不保证所有子命令适用于任意工程。整栋建筑保留真实尺度，不套用摆件限制；真实网格、朝向、支持点和地形决定接地。项目中文重命名会退出旧 TEST 名称保护，不能为了继续写入自动放宽检查或把正式作品改名。

## 生成路由和费用

先通过 `awc_cli_help` 和 `generate capabilities` 核对当前枚举，再用 `awc_cli_run` 调用固定生成命令：`generate image/model/status/wait/cancel/asset`。查询命令能否经 `awc_cli_read` 以实际注册表为准。`image` 返回真实任务ID，完成后取得图片URI及 creationsId 才提交 `model`；`status/wait` 追踪原任务，`cancel` 仅取消已核身份的在途任务，`asset` 的下载/导入副作用先读实际合约。旧 `awc_generate_*` 不在当前底座的公开工具中，不能假定可用。能力或版本不匹配时复用已批准资源并保留缺口，不绕开当前入口要求。

具备合法生成路由后，沿用用户本次费用授权。有限预算且无法核实收费上界时先暂停收费提交；用户明确取消上限时不重复设置限制。任务ID先落盘，等待全部已报告阶段完成后才下载最终模型；中间粗模不能算最终产物。生成接口不等于免费，不改账号计费模式。

## 质量与依赖

先读取当前底座的 `awc://docs/agent-production` 或仓库 `cli/skills/world-production/SKILL.md`。新生产底座以 `world create/next/dispatch/settle/control` 管理制作：主 Agent 调用 MCP→CLI 登记任务并取得派发工作单，再由宿主运行器启动真实会话；完成后将真实会话结果通过 `world settle` 写回。CLI 不会自己启动 Agent。登记校园施工或审查任务时，在任务 `skills` 中加入 `campus-world-build`，让 dispatch 将校园 Skill 及施工、原生操作参考连同 hash 固定到会话；主 Agent 仍须先读取校园 Skill 并完成需求对齐。生产会话通过 `production_native` 调用 MCP→CLI 原子能力；宿主缺少所需会话运行能力时记录阻塞，不把工作单当成已执行。先完成设计合同、真实参考和独立审查，施工任务使用已批准设计，验收使用 `world audit/deliver` 和真实场景证据。旧版 `world make/plan/build/run/resume`、`world continue/pause`、`layout *`、`world quality-*` 已从此底座移除，不能按旧说明调用；不同版本先查询实际帮助，缺接口就记录缺口，不能猜参数或回退到其他未经授权的入口。

已完成设计、工具调用成功和世界验收是不同状态。实际查看各区域截图，进行正常输入试玩，保存并完整关闭后重开；不把模拟测试或设计字段齐全当作原生完成。

没有可用 MCP 或原生连接时，若用户允许且电脑操作工具和编辑器可用，可按 [电脑操作](computer-use.md) 继续；否则完成资料和计划并报告缺项。匹配工程身份无法核实时不得写入。不让用户手摆模型来冒充自动制作。登录和必要权限仍由本人完成。Unity/SDK是单独依赖，不因为原生编辑器可用就自动安装或激活。
