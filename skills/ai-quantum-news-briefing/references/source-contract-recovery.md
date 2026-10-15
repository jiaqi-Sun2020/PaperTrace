# URL、失败 staging 修订与抓取准入

本契约仅描述代码能力。修改、离线测试、保存草稿或推送 GitHub 不代表已经部署到其他运行目录、审核、发布或核验远端；生产状态必须独立核对。

## URL 契约

新生成的 pipeline v4 使用 `source_url_contract_version=2`。`source_url` 保留原始地址的路径、末尾斜线、重复斜线、查询参数、片段及空查询分隔符；`source_identity_url` 只统一协议和主机大小写。不同查询、路径或片段不能由归一化合并。原有显式 `story_id` 保留；没有显式身份时用完整身份地址的摘要生成 ID。

历史未声明版本的输入和发布继续按 v1 验证；不改写其 capture、摘要、故事身份或索引。新生成过程显式升级为 v2，重新计算投影，不修改来源证据。未知版本、混合版本、凭据参数及不安全地址失败关闭。`source_capture.requested_url` 必须与最终选中的 `source_url` 完全一致；重定向地址另存为 `final_url`。读取历史 `retrieved_at` 的 `Z` 时不改写原字符串或证据摘要。

`source_candidate_id` 保留准入前的条目身份，并由账本绑定；Delta 重编号及持续跟踪压缩必须保留它。因此无显式故事 ID 的旧 capture 也无需改写即可在新投影中验证原始身份。

## 失败 staging 的显式修订

仅 protocol 4 的未发布 staging 可以修订，且严格验证已经通过的 staging 不允许修订。操作必须提供运行快照 SHA-256、当前候选 SHA-256 和具体原因，并在同一项目锁内再次核对。

旧 staging 与旧候选保留原路径和原始字节；新草稿位于 `_collection/<发布日>/.revisions/<修订ID>/candidate_<发布日>.json`。`_automation/staging_revisions_<发布日>.json` 是最后写入的原子提交点，绑定旧运行、旧候选摘要与原因。提交中断时旧运行仍有效；重复同一请求不会复制备份或生成另一修订。旧证据被更改或生命周期损坏时停止，不静默恢复。

修订后草稿为 `in_progress` / `not_reviewed`。仅修订当前候选，不能删除或修改 `revision_id` 和 `supersedes_run_id`。重新编写、抓取、staging 和实际审核仍分别完成。所有旧运行的审核写入、verify、seal、finalize 和 publisher 预检都拒绝 `staging_revision_superseded`；搬到正式目录也不能复活旧运行。其他尚未修订的 staging 仍会冻结候选。

完整 staging 先写入 `.staging-preparation/`，核对候选摘要及修订身份后在项目锁内原子安装到 `.staging/`。中断的准备目录不作为有效 staging，不阻止继续编写；本流程不自动清理其诊断材料。

以下命令仅供审核后操作，**本次没有执行恢复**。从当前工作树运行，先填写确切运行 ID：

```powershell
Set-Location 'D:\AI\PaperTrace'
$releaseDate = '<RELEASE-YYYY-MM-DD>'
$runId = '<待修订的RUN-ID>'
$info = & 'D:\AI\Anaconda\python.exe' -B .\skills\ai-quantum-news-briefing\scripts\daily_authoring.py revision-info --date $releaseDate --run-id $runId | ConvertFrom-Json
& 'D:\AI\Anaconda\python.exe' -B .\skills\ai-quantum-news-briefing\scripts\daily_authoring.py revise --date $releaseDate --run-id $runId --expected-run-sha256 $info.run_sha256 --expected-sha256 $info.candidate_sha256 --reason '填写具体错误及拟修改内容'
```

后续 `save` / `patch` 自动寻址当前修订草稿，仍使用当前文件摘要作并发控制。`run --config` 必须使用当前修订路径及身份；不能重用旧候选绕过修订绑定。

## 抓取诊断与候选准入

`source_capture.py` 输出失败阶段、异常类别、HTTP 状态、可否重试、尝试次数和下次重试时间，持久保存在覆盖日的 `capture_attempts/`。不输出异常原文、响应体、请求头或代理地址。来源健康按主机聚合：单篇失败与同主机其他有效证据分别计数，不能推断整站可用或整站没有候选。

一次调用最多为每项发起一次请求；同一身份、URL、引用与来源分类的范围最多自动尝试三次。网络请求前持久预留次数，网络过程不持项目锁；超时、连接失败及指定暂态 HTTP 状态执行持久退避。401/403、404/410、TLS 验证失败及过长 Retry-After 不反复请求。到期或预算耗尽时明确待处理，不能因此降低发布标准。换用实际可访问的来源必须重新抓取并绑定新 URL 和分类，不能改旧 capture 的 hash 来修补匹配。

每个发现都进入独立准入账本：`pending_capture`、`evidence_valid`、`retry_pending`、`excluded`，保留原始 section/item 位置。账本绑定候选输入摘要，记录数与分类计数守恒，选中条目必须指向账本内的有效 capture。嵌入候选 JSON 的 capture 不作为可信输入；只读取并完整校验本地证据文件。

排名前隔离损坏、缺失与失败缓存，排名后仅打包实际选中的 capture。坏的未选中候选不会使整个有效池中止；配额、来源多样性、时间窗、Fable 来源及实际审核要求保持原值。若无足够有效候选，仍停止；不能把候选数量、HTTP 200 或短缺声明当作批准。状态中的 `candidate_ready` 只说明池能满足选择条件，仍为未审核；未选中失败项继续显示在账本及 `missing_capture_ids` 中。

替换损坏 capture 前保存按摘要命名的原字节备份。网络返回后核对候选仍未变化，再原子写入；并发已安装的有效 capture 优先，失败写入保留旧缓存。合法缓存直接离线复用。

## 离线验收

从当前工作树运行：

```powershell
Set-Location 'D:\AI\PaperTrace'
& 'D:\AI\Anaconda\python.exe' -B -m unittest discover -s .\skills\ai-quantum-news-briefing\tests -p 'test_*.py'
git diff --check
```

专项用例位于 `test_url_contract_repair.py`、`test_staging_revision_repair.py`、`test_capture_admission_repair.py`。测试使用临时目录、模拟 HTTP 和严格验证，不读取真实 OSS 配置或执行真实发布。


## 2026-10-10：公式字段与唯一活动 staging

`opening_story.worked_example.steps[*].formula` 默认为无注释的 TeX 显示数学片段。
字面百分号必须使用 `\%`（JSON 文本写作 `\\%`）；裸 `%` 在归一化、渲染及 staging 验证时失败关闭。
已有转义不会被改写。字段不接受自动全局替换；显式 `formula_format: "text"` 表示普通文本，
保留中文、百分号和反斜杠，不进入数学块。`formula_format: "tex"` 显式指定 TeX，其他值拒绝。
新旧合法的隐式 TeX 不增加字段，因此既有合法摘要不改变。MathJax 3 明确忽略普通文本公式容器。
公式修正仅证明传输/显示契约；事实、故事和逐项内容审核仍必须独立完成。

protocol 4 新 staging 声明 `staging_lifecycle_version=1`。安装后在同一发布锁内原子登记
生命周期 `active_run_id`；同一发布日期只允许一个活动 run。已安装但登记前中断的 run
不能通过验证、写入审核、封印、finalize 或上传，可用明确摘要重新发起受控修订。
登记写入失败时尽力退回 `.staging-preparation/`，证据保留，重入不得把旧审核作为新审核。
生命周期仍为 version 1，新增字段是可选兼容扩展；声明了新 staging 契约却缺失活动登记时停止。

历史同日有多个失败 staging 时不能只退回其中一个。`revision-info` 只读列出 `active_runs` 的
run-ID/快照摘要；`revise --expected-peer-runs-base64` 接受显式、完整的其他活动 run 摘要映射。
漏项、额外 run、摘要变化、任何已审核通过或正式发布版本均拒绝。所有旧目录保持原字节，
快照随修订保留；一个原子生命周期提交同时标记所有绑定旧 run 被替代并切换新候选。
同一请求中断后可重复；参数变化要求重新检查。禁止删除冻结目录或删除生命周期来“解冻”。

部署必须同时评审代码能力与当前运行树差异。运行树没有 `revision-info/revise` 和
`daily_revisions.py` 时，直接 patch 仍将返回 `staged_candidate_frozen`；工作树测试通过不代表已部署。
不得盲目覆盖运行树的未提交或较新修改。部署、迁移真实冻结稿、封印、发布、上传是独立授权边界。
专项离线回归：`test_formula_revision_1010.py`、`test_staging_revision_repair.py`。
学术 6–8、社会 6–12、新/重要更新至少 4、完整故事与更严格的有效配置保持原门槛。
