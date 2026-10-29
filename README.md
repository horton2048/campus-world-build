# 校园复刻全自动造世界 Skill

把校园地图、建筑照片与玩法构想，变成一份 Agent 可以持续执行、检查和续做的造世界制作任务。这份 Skill 源于真实校园世界的制作与复盘：阅读编辑器指南、连接社区 MCP、生成独立模块、校准落位、看图和实走，再把成功与失败整理成下一轮可复用的工作流。

**下载与使用是免费的。**“全自动”指在具备权限和可用工具后，让 Agent 尽可能完成可重复工作；创作方向、参考资料、审美判断与体验验收仍需要人参与。它不是造世界编辑器，也不会自动获取编辑权限或替你发布作品。

## 开始之前

1. 准备校园地图、建筑照片，以及你希望玩家在校园里做什么。
2. 开通并登录造世界编辑器。申请入口和步骤可能变化，请以[创作者中心](https://creator.douyin.com/creator-micro/hamlet_world)及当前官方指引为准。
3. 准备支持读取 Skill 的 Agent 环境。如果希望 Agent 直接读写编辑器，还需要单独配置已获授权的工具连接或兼容的 MCP；本仓库不附带编辑器、MCP 服务或账号权限。没有连接时，Agent 可先整理任务，实际制作须通过可用工具或编辑器界面完成。
4. 具备 Python 3 时，可使用随附的只读 GLB 检查脚本；脚本仅检查文件容器，不负责生成、导入或视觉验收。

## 安装和使用

从本仓库的 **Code → Download ZIP** 下载后解压，把其中的 `campus-world-build` 文件夹放到你所用 Agent 支持的 Skill 目录，再按照该工具的方式刷新或重新加载技能。若你的工具支持 `~/.agents/skills/`，也可以在终端运行：

```bash
git clone https://github.com/horton2048/campus-world-build.git
mkdir -p ~/.agents/skills
cp -R campus-world-build/campus-world-build ~/.agents/skills/
```

目录因 Agent 而异；如果以上目录不被识别，请查看你所用工具的 Skill 安装说明，或直接让 Agent 读取 `campus-world-build/SKILL.md`。

把自己的资料交给 Agent 后，可以从这里开始：

> 使用 `$campus-world-build`，根据我提供的校园地图、建筑照片和造世界编辑器指南，先检查连接和当前场景。先做一栋楼与一段路线：核对比例、朝向、入口、保存和验收，提供规则、实际动作、截图与未验证事项；通过后再分区推进。

更完整的输入模板在 [`assets/start-prompt.md`](campus-world-build/assets/start-prompt.md)。

## 它具体沉淀了什么

- **先看前提**：阅读相关操作指南；GLB 地面与原生地形不是同一对象，不能假定笔刷都能用。
- **让工具真正执行**：识别当前 MCP 能力，分别记录生成、入库、落位、保存、看图和实走；中断后先读回，避免重复写入。
- **用小样减少返工**：先确认来源与导入尺度，再批量制作；发现文字镜像时只修对应纹理，并重新看图。
- **证据与结果对应**：记录规则、实际动作、文件/场景和验收结果；把已通过、待验证、失败分开。

校园案例中参考了社区开源项目 [WilderNoTrack/world-creator-mcp](https://github.com/WilderNoTrack/world-creator-mcp)。它是独立的第三方项目，不是本 Skill 或官方插件；案例里的 Mac 验证使用了当时的本地适配版本，不代表上游版本在所有设备上开箱可用。先核对该项目的当前说明、平台支持及自己的授权范围。

部分历史教程链接可能需要访问权限或发生变更；无法打开时，可使用当前创作者中心提供的资料或自己已经获得的编辑器指南。操作、功能和平台限制都以当前实际版本为准。

## 文件与许可

- [`campus-world-build/SKILL.md`](campus-world-build/SKILL.md)：技能入口与主要流程。
- [`references/`](campus-world-build/references/)：指南、工具路由和实践教训。
- [`scripts/inspect_glb.py`](campus-world-build/scripts/inspect_glb.py)：只读文件检查。

本仓库代码与原创文档按 [MIT License](LICENSE) 发布。引用的第三方工具及其资源遵循各自许可；本仓库不包含编辑器、校园地图、照片或聊天记录。
