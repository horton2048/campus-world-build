# 原生执行与依赖

## 开工查询

通过已注册的 `awc_bridge_status`、`awc_list_projects`、`awc_cli_help` 核对编辑器、项目和命令；`awc_cli_read` 执行允许的只读命令，`awc_cli_run` 内部执行 CLI，写入传 `confirm:true`。先读取相关命令的真实 JSON 合约，不猜字段。MCP 可用不等于每个 CLI 功能存在或已实测。

当前常用执行族：

| 阶段 | CLI 命令族，经 MCP 调用 |
|---|---|
| 测试工程 | `editor create-test/open/scene/save/close`；项目清单可用 `project list` |
| 资产 | `library search/fetch/snapshot`、`asset inspect/import`、`resource *` |
| 摆放 | `surface geometry/sample`、`layout *`、`scene edit-inspect/edit-apply` |
| 地形 | `terrain survey/sample/flatten-plan/flatten/smooth-plan/smooth` |
| 正常试玩与实图 | `runtime start/status/input/observe/media/stop` |
| 质量与续做 | `world quality-*`、原任务 `world reconcile/resume` |

这里只列路由，不保证所有子命令适用于任意工程。整栋建筑保留真实尺度，不套用摆件限制；真实网格、朝向、支持点和地形决定接地。项目中文重命名会退出旧 TEST 名称保护，不能为了继续写入自动放宽检查或把正式作品改名。

## 生成路由和费用

先通过 `awc_cli_help` 和 `generate capabilities` 核对当前枚举，再用 `awc_cli_run` 调用固定生成命令：`generate image/model/status/wait/cancel/asset`。查询命令能否经 `awc_cli_read` 以实际注册表为准。`image` 返回真实任务ID，完成后取得图片URI及 creationsId 才提交 `model`；`status/wait` 追踪原任务，`cancel` 仅取消已核身份的在途任务，`asset` 的下载/导入副作用先读实际合约。旧 `awc_generate_*` 只保留为历史兼容入口，不是本 Skill 默认制作路径。能力或版本不匹配时复用已批准资源并保留缺口，不绕开当前入口要求。

具备合法生成路由后，沿用用户本次费用授权。有限预算且无法核实收费上界时先暂停收费提交；用户明确取消上限时不重复设置限制。任务ID先落盘，等待全部已报告阶段完成后才下载最终模型；中间粗模不能算最终产物。生成接口不等于免费，不改账号计费模式。

## 质量与依赖

`world make` 正式制作须有真实填写的 quality 合约，技术样板显式 prototype。`native completed` 与艺术验收分开，`needs_quality_review` 继续用当前源做试玩、实图审查和 quality-status，不重放制作。完整质量输入见仓库 `cli/docs/world-quality.md`；单独安装 Skill 时缺该文件，应从实际 CLI 文档读取，不能猜参数。

没有可用 MCP 或原生连接时，若用户允许且电脑操作工具和编辑器可用，可按 [电脑操作](computer-use.md) 继续；否则完成资料和计划并报告缺项。匹配工程身份无法核实时不得写入。不让用户手摆模型来冒充自动制作。登录和必要权限仍由本人完成。Unity/SDK是单独依赖，不因为原生编辑器可用就自动安装或激活。
