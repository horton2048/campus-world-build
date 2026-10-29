# 校园复刻全自动造世界 Skill

给出学校、校区与总体目标，让 Agent **自行查官方地图、逐栋找真实照片、生成与落位，并按全校园清单连续补齐和验收**。不用先把每栋楼的照片准备好，也不需要一栋栋催“继续”。

这份 Skill 依据真实校园复刻对话重新整理。它最重要的约束是：官方地图决定范围，照片决定外形；小样验证技术，完整校园仍是交付目标；先把建筑、道路、场地和接地做好，再美化与设计玩法。原始需求与执行偏差如何转成规则，见[工作流说明](campus-world-build/references/intent-and-workflow.md)。

“全自动”表示尽可能把资料检索和重复执行交给 Agent，在已有权限与资源边界内持续推进；它不会自动获得编辑器权限，也尚未证明任意校园都能一次提示达到相同质量。

## 开始只需给什么

- **必需：学校、校区、想复刻的整体范围。**已在会话中明确的直接沿用。
- **可选：已有地图、照片、工程和个人偏好。**缺地图或照片时，Agent 应先主动公开检索。
- 实际改场景前，需要有可用的造世界编辑器账号/工程、获权工具或界面，以及本轮成本和时间边界。不能自行确定的事项集中确认，不逐栋询问。

## 安装与使用

从 **Code → Download ZIP** 下载解压，将 `campus-world-build` 文件夹放进你的 Agent 支持的 Skill 目录，再按所用工具的方式重新加载。若其支持 `~/.agents/skills/`，可运行：

```bash
git clone https://github.com/horton2048/campus-world-build.git
mkdir -p ~/.agents/skills
cp -R campus-world-build/campus-world-build ~/.agents/skills/
```

目录因工具而异；也可以直接让 Agent 读取 `campus-world-build/SKILL.md`。然后说：

> 使用 `$campus-world-build`，复刻【学校】【校区】。请自行找官方地图和逐栋建筑照片，按全图清单持续生成、落位、接地与验收；先完整基础设施，再美化玩法。普通步骤自行继续，只有真实身份冲突、预算权限和重要取舍集中问我。

需要更多范围和资源约定时，复制[完整启动任务](campus-world-build/assets/start-prompt.md)。工作记录可从[全校园清单模板](campus-world-build/assets/campus-ledger.template.json)开始；这是 Agent 的任务台账，不是编辑器配置文件。

## 它怎样减少重复对话

1. 自行建立官方地图要素全集和逐楼照片库，避免用户逐个喂图、指出缺楼。
2. 将已确认的全校园范围、先基础后玩法、完整楼体与接地门槛写入每批任务。
3. 用同来源小样验证导入规则，随后自动逐栋/分区循环；遇一处缺图或失败，记录并换下一处可做项目。
4. 分清占位、局部、整栋、照片精修、保存与运行状态，报告全图覆盖变化，避免用局部成功掩盖缺项。
5. 保存来源、当前场景、在途任务和下一步；中断先读回，减少重复生成与重新配置。

## 编辑器与工具前提

先开通并登录造世界编辑器；权限入口和步骤可能变化，以[创作者中心](https://creator.douyin.com/creator-micro/hamlet_world)及当前官方指引为准。没有编辑器连接时，Agent 可以先做资料库和施工清单，真实建造要使用可用工具或原生界面。

历史案例后期接入了社区项目 [WilderNoTrack/world-creator-mcp](https://github.com/WilderNoTrack/world-creator-mcp)，实际用于结构化编辑、落位、回读和保存。它是独立第三方适配器；当时 Mac 实测使用本地适配版本，不能承诺上游在所有设备开箱可用。本仓库不附带该 MCP、编辑器或账号权限。部分历史指南需要访问权限，不能打开时使用当前公开入口或自己已获权的资料。

## 内容与验证范围

- [`SKILL.md`](campus-world-build/SKILL.md)：地图、照片、批量制作、验收和续接的主流程。
- [`references/`](campus-world-build/references/)：原始诉求、工具边界和失败经验。
- [`scripts/inspect_glb.py`](campus-world-build/scripts/inspect_glb.py)：Python 3 标准库的只读容器检查；不负责生成、导入或视觉验收。

已做文档/模板和离线脚本检查；未以新校园完整重跑验证“最少对话达到同等效果”。本仓库原创代码与文档按 [MIT License](LICENSE) 发布，不包含原始聊天、校园图片、编辑器或场景数据，第三方工具及其资源遵循各自许可。
