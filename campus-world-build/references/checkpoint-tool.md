# 检查点工具：保存、查回、续接

`scripts/campus_checkpoint.py` 只用 Python 3 标准库。它管理本地记录，不调用网络/编辑器、不生成模型、不自动唤醒 Agent。Agent 在自己的任务项目内运行，实际证据仍须来自地图、照片、工具查询和场景核验。

下面命令从仓库根运行；安装后把脚本位置换成当前 Skill 中的真实位置。`./校园复刻记录` 是该次任务的运行数据，不放到 Skill 安装目录，也不要提交到公开仓库。

## 1. 初次建立，恢复时不重建

```bash
python3 campus-world-build/scripts/campus_checkpoint.py init ./校园复刻记录 --school "学校全名" --campus "校区全名"
python3 campus-world-build/scripts/campus_checkpoint.py resume ./校园复刻记录 --limit 8
```

窗口较小或容量未知时，先用更短恢复卡：

```bash
python3 campus-world-build/scripts/campus_checkpoint.py resume ./校园复刻记录 --limit 3 --max-bytes 4096
```

`init` 不覆盖已有项目。权威数据是 `campus-checkpoint.sqlite3`：每次写入都在同一事务内更新当前记录和追加历史；`RESUME.md` 是每次更新后重建的短索引，损坏/过旧时用 `resume` 重建。短卡写失败会报告警告，不假装数据库提交失败而再做一次外部操作。

Agent 同时在任务工程根留下 `CAMPUS_TASK.md`，只记学校/校区、此记录目录和真实恢复命令，便于换会话后定位；脚本不会擅自修改记录目录外的文件。已有入口保留其他任务，不用私人全局配置才能恢复。

项目默认 `status=active`、全校园、基础阶段、地图全集未确认、预算未知。Agent 先填任务约定、地图来源/全集、真实工程身份、授权和预算，不把这些默认值当已核事实。数据库保存的是记录，不是编辑器的原生保存。

## 2. 分项读写，避免上下文重新膨胀

只有三类记录：单一项目 `project/main`，每个地图项 `item/<稳定ID>`，每次外部写入/耗额提交 `job/<操作ID>`。ID 使用字母、数字、点、短横线或下划线；中文真实名称写在 `campusName` 等字段里。每条 JSON 最多 64 KiB，这是硬上限，不是记录目标。项目约定和当前建筑核心保持简短，图像、模型、多图源详情和长回包外置，只留索引，避免一次 get 又撑满上下文。

```bash
python3 campus-world-build/scripts/campus_checkpoint.py get ./校园复刻记录 project main
python3 campus-world-build/scripts/campus_checkpoint.py get ./校园复刻记录 item B001
python3 campus-world-build/scripts/campus_checkpoint.py list ./校园复刻记录 item --limit 20 --offset 0
python3 campus-world-build/scripts/campus_checkpoint.py list ./校园复刻记录 job --limit 20 --offset 0
python3 campus-world-build/scripts/campus_checkpoint.py list ./校园复刻记录 job --view unresolved --limit 3 --offset 0
python3 campus-world-build/scripts/campus_checkpoint.py list ./校园复刻记录 item --view unfinished --limit 3 --offset 0
```

`get` 返回 `document` 及 `revision`。保留所有已知字段，把修改后的 **document 本身** 写入 UTF-8 JSON 文件，再更新：

```bash
python3 campus-world-build/scripts/campus_checkpoint.py put ./校园复刻记录 item B001 --file ./B001.json --expected-revision 0
```

新记录 revision 为 0；已有记录用刚读出的版本。`put` 是**整条替换，非合并**，不能只提交改动字段；版本冲突须重新读、合并，不能改一个数字就覆盖。并发事务防止两个旧上下文互相踩掉数据，编辑器仍按单场景写者工作。

`list`/`resume` 默认每类最多 8 条，可选最多 20 条；`total`、`returned`、`hasMore` 和 `nextOffset` 显示总数、实际返回量与下一页。长字段会标截断并提示 `get`。恢复先查所有未终态作业，不能因第一页没看到就认为没有。地图全量验收必须分页遍历所有项，与实际地图/完整场景相比较；窗口小时逐页取 1–3 项，程序可在文件中比较完整ID集，只输出缺项，避免全量内容涌入提示。

摘要页提供 `nextPage` 命令，保持相同集合和排序：作业 `--view unresolved`，逐项 `--view unfinished` 或 `excluded`；普通 `list` 默认 `all`，它的 offset 不能混用。每页有 `eventSeq`，若跨页期间有写入、作业转终态或序号变化，就从 offset 0 重查当前集合，避免集合缩小后跳过未决项。必要时先在固定快照内取全ID再逐个处理，不把旧游标当永久任务队列。

恢复 JSON 和完整 `RESUME.md` 共用整体 UTF-8 字节预算：默认 **16 KiB**，`resume --max-bytes` 可选 **4–64 KiB**。不够时缩字段、减少摘要记录，必要时只留稳定 ID/修订/状态；`byteBudget` 明示压缩，`hasMore/nextOffset` 按实际返回计算，不静默漏作业。完整 `get/export` 不受摘要裁剪影响。自动更新短卡用默认预算；需要更小时，在交接与每次恢复先用 4096 字节命令重建。它给出恢复索引，不代替实时任务选择和原记录。

## 3. 项目和逐栋记录

项目保存 `scope`、`map`、`environment`、`resourceBoundaries`、`budget`、`lastSavedState`、`nextQueue`、`questionsRequiringUserDecision`。其中：

- `map.sources` 为地图来源；`inventoryComplete` 只有全图盘点并复核才为 true；`itemIds` 覆盖约定范围的全部项，`reviewEvidence` 指到实际全图复核依据。
- `environment.projectIdentity` 指当前真实编辑工程；恢复时仍须工具回读，不能沿用另一账号/同名项目。
- `budget` 记录上限、已花、在途预留与最后观察。工具不核平台余额，Agent 在发起收费操作前必须查实际额度和授权。
- `lastSavedState` 包含 `version`、`verifiedAt`、`evidence`，证据应包含原生保存和回读，不是本工具的 JSON 落盘。
- `nextQueue` 是下一动作候选；恢复后按未知任务、依赖、资源和全图缺项重新排序。

逐项可参考 [字段模板](../assets/campus-ledger.template.json)。最小未完成项示例：

```json
{
  "campusName": "图书馆",
  "kind": "building",
  "mapEvidence": [],
  "photoSearch": {
    "queriesTried": [],
    "sourcesViewed": [],
    "identityBasis": null,
    "anglesCovered": [],
    "gaps": []
  },
  "geometryCoverage": "not-started",
  "result": "not-done",
  "checks": {},
  "nextAction": "按官方地图核身份，主动检索并查看照片"
}
```

`kind` 取 `building/road/gate/sports-area/water/greenery/facility/other`。完整楼体、照片身份、图源、场景映射和验收结果必须另有真实证据，不能仅修改状态。

用户明确改变范围时，用 `scopeMembership`（默认 `in-scope`）保留旧项。排除先在活动项目的 `scope.exclude` 写入该稳定ID，再将该项设为 `excluded`，附 `scopeChange`：`requestedBy: "user"`、非空 `reason` 与真实 `evidence`。更新当前地图全集及复核记录；难做不是自行排除的理由。排除项不计当前未完成队列，仍可分页追溯，其未终作业仍必须查清。

重新纳入时，已完成项目先改回 `active`，把该项改为 `in-scope`，再从项目排除表移除并重新核地图全集；保留旧历史和仍有效证据，不要求从零重做。每一步都用刚读回的版本更新。范围变更只改变交付成员，不默认删除真实场景对象。

每项检查可写 `{ "status": "passed", "evidence": ["真实证据文件或查询记录索引"] }`；不适用写 `{ "status": "not-applicable", "reason": "该项在本对象/约定范围下为何无关" }`，不能借此跳过应验部分。兼容旧字符串状态时，对应证据/理由写在 `checkEvidence` / `checkReasons`。

## 4. 外部操作之前先记意图

新作业必须先以 `prepared` 保存。操作 ID 每次尝试唯一；`fingerprint` 对同一逻辑动作保持稳定，宜由工程身份、对象ID、操作类型和输入快照/SHA生成。不能每次随机指纹来绕过查重。

这里的作业只记录**耗额提交或外部写入**。查询原作业、读场景、查资产和看图更新原作业观察/逐项证据，不新建同目标查询作业，也不以查重冲突为由跳过必须的观察。

```json
{
  "intent": "将当前已核候选导入指定校园工程",
  "fingerprint": "由真实工程、对象、操作和源SHA算出的稳定指纹",
  "target": "真实工程身份/B001",
  "operation": "import",
  "sceneMutation": true,
  "strategy": "当前已校准导入方法",
  "status": "prepared",
  "inputSnapshot": {"sourceFile": "当前源文件路径", "sha256": "实际源SHA"},
  "attempt": 1
}
```

保存成功后才调用真实工具；取得回包立即用同一作业记录保存 `handle`、状态、返回资产/实例及证据索引。有句柄不能换掉或删除。同步操作也需要提交前记录；可以从 `prepared` 直接记录有证据的终态。

`inputSnapshot`、指纹、目标、方法及已声明的预期变化/原场景基线属于不变的提交身份，状态更新不能改源路径或原始 SHA。生成返回的产物写在结果/证据字段，不倒填改写输入。源确实改变则先处置原作业，再建关联的新操作，不能让旧校验跟着可变路径自动沿用。

`prepared/submitted/running/unknown` 都视为未解决。相同指纹、相同目标或两个场景写入会被拒绝并行；有生成任务等待时，允许独立对象的非场景生成/资料研究。没有回包的 `prepared` 不代表从未提交过：必须先查原意图与实际资产/场景。

只有工具/原生界面明确证实终态，才写：

```json
{
  "status": "failed",
  "observation": {
    "status": "failed",
    "terminal": true,
    "source": "实际查询入口",
    "observedAt": "实际查询时间",
    "evidence": ["权威终止回包及副作用排查记录"]
  }
}
```

这段是终态需要补充的字段示意，**不能当整条 put 输入**；更新时保留作业身份和句柄。超时、失联或查询入口不可用只能保留未知，不能伪填为终止证据。工具校验字段，无法判断证据是否真实。

重试用新操作 ID、`retryOf` 指向已核终态的原作业，保留历史费用/错误。相同指纹和方法累计两次失败会拒绝再次盲试，需先换有依据的方法，并在 `strategy` 和恢复记录中说明变化。输入确实改变时更新输入快照/指纹，并保存与旧失败的关联；不能为了清零次数改名字。

## 5. 完成与审查导出

工具拒绝将占位、局部或待核候选标为 `meets-agreed-criteria`；通过检查须有证据，建筑须有已查看照片及身份依据。所有项目保留七项核心检查：地图落位、照片相似、完整形态、接地、入口与通行、原生保存、阶段所需运行；真正不适用要写原因。

`project.status=complete` 需要全图复核证据、地图全集ID与当前范围内存储项一致、逐项达标、没有未终态作业（含已排除项的作业）、真实工程身份、原生保存回读及全校园完成证据，且无待本人决策。它检验**记录的一致性**，不证明真实照片、几何和人物实走一定正确；最终仍按 Skill 全量验收，不能为过校验器伪造证据。

```bash
python3 campus-world-build/scripts/campus_checkpoint.py export ./校园复刻记录 --file ./校园复刻记录/审查导出.json
```

导出包含全部记录及追加事件，适合检查尝试历史/版本；不是恢复必读材料。保存备份时关闭所有写入进程，再复制数据库，或使用 SQLite 的标准备份能力；不要在写入中随意只复制一个数据库文件。保护运行数据中的个人账号/工程与未公开资料，公开 Skill 仓库只发布通用方法和工具。

## 6. 从旧台账升级

已有 `campus-state.json` 或旧模板时先保留原件，不重做世界。由 Agent 创建新运行记录，把原任务约定、每项地图资料、产物/实例和未决任务逐项转入；缺字段保持未知，重新查询实时工程和原任务。不能把旧“已完成”批量转成新“已验收”。模板和数据库是不同结构，不把整份旧JSON当作单条 `put` 输入。

若工具无法运行，采用 [长程协议](long-running.md) 的分项文件记录；若数据库或磁盘异常，先停止下一次外部写入，保留现有文件和错误，再修复恢复路径。记录失败时继续无记录地改场景会放大恢复风险。
