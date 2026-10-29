# 工具路由与前置条件

以下名称来自 2026-10-29 当前可发现的造世界 MCP 工具元数据。它们是识别提示，不是永久接口契约；每次先发现可用工具并读实际参数。不要从一个工具描述里提到的旧名称猜测另一个工具仍存在。

## 先判断缺的是知识还是能力

先按 [指南与 MCP](guide-and-mcp.md) 主动定位并读取本轮有关的操作说明，再用当前工具目录确认哪些动作可以执行。文档里有按钮，不代表 MCP 已封装；MCP 返回工具，不代表该功能在当前平台实测通过。保存一份本轮的“动作 → 当前工具或 UI → 前提 → 验证证据”简表即可。

已有用户授权和已安装适配器优先复用。社区仓库只作为来源与实现参考；需要安装、启用内部编辑连接或改变写入范围时，使用本次明确授权，不从历史校园案例继承权限。新接入环境先在适当的测试工程验证最小读写、保存与重开，再进入实际校园。

## 前置条件

- 已开通造世界编辑器权限，使用申请时同一抖音账号登录。
- 编辑器已按所装 MCP 适配器要求启动并连接；通过当前实际提供的状态工具（例如 `worldcreator_status`）核对连接。connected=true 仍可能处在加载中，要继续核项目、节点和预览状态。
- 用 `worldcreator_project_list` / `worldcreator_list_workspaces` 返回的 ID，核对当前校园项目；`project_open` 不能强行替换另一个已开的工程。
- 用户若还没获权，参考当前官方指南申请邀请码。2026-10-28 核实入口：创作者中心 → 邀请码群 → 与机器人单聊申请 → 问卷渠道选“校园活动” → 获得邀请码 → 返回兑换权限 → 下载登录。同一流程未来可能变，必须核实当前指南，不能保留旧加白表。
  - 创作者中心：https://creator.douyin.com/creator-micro/hamlet_world
  - 官方指南：https://larkcommunity.feishu.cn/wiki/IhxtwgFFPiOmcakXZmVcqsNTnjb

## 当前能力地图

下表数值为整理当日元数据，不作为未来版本的硬编码限制；运行时读当前 schema 和编辑器实际返回。

| 目的 | 发现这些工具 | 关键边界 |
|---|---|---|
| 读取场景 | `canvas_scene` / `canvas_node` / `canvas_assets` | allNodes 最多返回 1000 个后代；大场景不能把截断结果当完整清单 |
| 查找已有资产 | `asset_search` | public/personal/favorite；返回资产 ID，避免重复生成 |
| 资产导入和摆入 | `canvas_import_glb` → `canvas_add_asset` | GLB 最大 20 MiB；导入可能把模型写入平台存储，须在用户构建范围内；它与作品上传/公开发布不同，导入也不等于已落位 |
| 组件/外观修改 | `canvas_component_schema` → `canvas_component_update` | 仅支持实际 schema 字段；变换若未在当前会话暴露，先核已有且获权适配器 CLI 的实际 schema；只有已验证入口可用时才调用，否则用原生 UI，不编造 `canvas_update` 参数 |
| 碰撞 | `canvas_physics` | 先读现有组件，不混淆碰撞/刚体/重力 |
| 替换资产 | `canvas_replace_asset` | 返回新实例 ID；后代、脚本会被替换，需核对重绑 |
| 原生地形笔刷 | 当前编辑器 UI 或已发现工具 | 先核原生 terrain；导入的 GLB 地面不自动支持地形/物品笔刷；原生地形采样也不替代 GLB 碰撞与实走 |
| 地图 PCG | `pcg_context` / `pcg_start` / `job_status` | terrain/sprinkle/compose 是地图链路；先 dryRun；未知结果沿同一 requestId 查询；激活可能替换场景，遵循工具确认要求 |
| 原生资产 Agent | 读取当前已安装能力和 UI | 当前目录未提供通用“发起模型 Agent”工具；用实际可用原生 UI 或受支持工具，不用 PCG 冒充资产 Agent |
| 模组读/改/归档 | `list_files` / `read_file` / `write_file` / `inspect_model` / `archive_module` | author 文件用 SHA 乐观锁；派生 package 不能直接写；inspect_model 可能执行受信的本地预览 JS；只处理可信源 |
| Lua | `script_read` / `script_write` / `validate_lua` / `canvas_script_bind` | 先对照安装版本 SDK；保留身份注释，编译无误才绑定；脚本在 preview 执行 |
| 预览与截图 | `canvas_preview` / `canvas_focus` / `canvas_capture` | 场景修改前停 preview；capture 为原生视口截图，需实际查看；Lua 断点能力不能用 JS 调试冒充 |
| 保存 | `canvas_save` | 原生备份 + 保存 + clean 状态 + SHA；回读后才标完成 |
| 发布 | `publish_prepare` / `publish_submit` / `publish_status` | 计划有时限；改场景使计划失效；只在用户授权上传时 submit；上传接受、处理完成、公开上线分开报告 |

没有相应能力时，先明确缺的是连接、账号、工具还是数据。不要通过写缓存、未公开接口或假造 task ID 绕过。可在受支持 UI 里继续的工作直接继续；真正被阻塞时保留状态，报告具体入口与待办。
