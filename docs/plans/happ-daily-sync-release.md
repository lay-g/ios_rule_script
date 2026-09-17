# 每日同步全部客户端规则并发布 Happ 数据快照

本 ExecPlan 是一份持续更新的文档。实施过程中必须始终维护“进度”、“意外与发现”、“决策记录”和“成果与复盘”四个章节。

## 目标与整体说明

为 `lay-g/ios_rule_script` 创建独立 GitHub Actions：每天 UTC 21:23（北京时间次日 05:23）或手动从 `blackmatrix7/ios_rule_script` 的 `master` 固定一次源 SHA，只替换整个 `rule/` 树（所有客户端新增、修改、删除）。默认分支中的自有 `tools/`、`.github/`、`docs/` 及其他根目录不随上游替换。复用现有 Happ 全量转换、固定编译器及逐分类二进制回读，全部验证通过后才提交规则变更、普通 push，随后发布 draft Release 中的两个 dat、校验和、精简 manifest/notes。无规则变更不创建空提交，但仍发布新数据快照；同日多次及 rerun 使用时间、run_id、run_attempt 区分。

本任务只创建自动化和本地验证，不对真实仓库执行 commit、push、tag、gh release 或 workflow run。临时 Git 夹具可使用本地 bare remote 模拟。Happ 实机及 GitHub 托管权限边界单独列为未验证。

## 进度

- [x] (2026-09-17 13:10Z) 完整读取 tools/happ 四文件、旧计划、项目 README、ExecPlan skill；初始工作树干净，HEAD 为 `31cdb642d1d08807206b049202212c8eabd88863`，无项目 AGENTS.md/PLANS.md。
- [x] (2026-09-17 13:10Z) 读取官方 GitHub Actions/gh 文档、两个固定 commit 的真实 go.mod、Go 下载列表、action tag SHA 和固定 CLI checksum。
- [x] (2026-09-17 13:15Z) 实现 workflow、最小快照/manifest 辅助和六项 Git 夹具测试，保持转换逻辑及 pins 不变；23 测试通过。
- [x] (2026-09-17 13:20Z) 固定 actionlint 1.7.7 + ShellCheck 0.11.0、所有多行 shell 的 bash -n 通过；本地、隔离上游、按 workflow 重新安装工具的三次真实全量编译/逐分类回读通过。
- [x] (2026-09-17 13:22Z) README 和计划补充真实证据；真实报告 gate 验证 690 个源文件哈希和两库哈希/大小；23 测试复跑通过，无暂存、无真实仓库写远端动作。
- [x] (2026-09-17 13:33Z) 独立 reviewer 审查完成；原恢复文档 P2 已修正并由 reviewer 复核。主会话复跑24测试、actionlint+ShellCheck、计划校验及差异检查通过；两个子任务和 workflow 均已结束。
- [ ] 用户自行提交启用后执行 GitHub 托管端到端及 Happ 实机验收（当前未执行）。

## 意外与发现

- 观察：独立审查发现原恢复说明把标签去重误写成任意阶段可 Re-run。已修正 README 和恢复章节，并新增本地 bare remote 回归测试：首次同步 push 成功后模拟旧 base 的第二次 attempt，确认在发布前安全拒绝且远端提交保持不变。这是文档澄清，不改变安全 push 策略。

- 观察：隔离抓取当前上游 master 为 `4435ba4141d82aab94e541e29023fc6a1f627723`，其整个 rule tree 与本 fork 当前 HEAD 完全相同：`4482727aa422f8a4a1a279c0d873cdbca375ef76`。因此三次真实构建统计/产物 hash 一致不是假数据；跨客户端新增修改删除另由夹具模拟。
  证据：隔离目录 `/tmp/happ-upstream.kNVhoW` 的 FETCH_HEAD，当前 `git rev-parse HEAD:rule`，以及 `/tmp/happ-actions-evidence/build-summary.json`。
- 观察：最初检查发现 `git rev-parse :rule` 不能解析 index 的目录，且 job 级 env 不允许 runner context。
  证据：初次测试与 actionlint 失败；改为 `git write-tree` 后解析其 `:rule`，临时目录通过运行步骤写 GITHUB_ENV。修正后 23 测试及 actionlint+ShellCheck 全通过，没有带着失败跳过验收。
- 观察：不能根据日期猜 Go 版本。固定 domain-list-community 的 go.mod 为 `go 1.24.0`，固定 geoip 为 `go 1.26`；当前官方 `https://go.dev/dl/?mode=json` 实际返回 `go1.27.1` 和 `go1.26.8`。本地已有 Go 1.27.1 和此前固定工具。
  证据：`/tmp/happ-actions-evidence/{geosite.go.mod,geoip.go.mod,go-downloads.json}`。选择确实存在且已用于现有工具的 Go 1.27.1，设置 GOTOOLCHAIN=local 防止自动升级。
- 观察：GitHub 并发组不保证所有排队运行均执行（最多一个 running 和一个 pending），cancel-in-progress:false 只保证不取消正在运行者；schedule 也可能延迟或被丢弃。
  证据：GitHub 官方 events/concurrency 文档本次下载到 `/tmp/happ-actions-evidence/`。本功能不是严格时效队列。

## 决策记录

- 决策：同步在 Actions checkout 的临时工作区使用 Git 的路径受限 restore，仅限 `rule/`；先验证上游目录为普通文件树，拒绝 symlink/gitlink。使用源 tree SHA 和 staged tree SHA 比较确保删除及所有客户端精确同步，不 merge/reset 上游仓库。
  理由：原生 Git 保留字节和文件模式，避免 tar 路径穿越/不完整复制；上游其他文件及脚本不执行。日期/作者：2026-09-17 / implementation。
- 决策：workflow 只 schedule/workflow_dispatch、只指定 fork 和默认分支；checkout 固定事件 SHA，不追随构建中变化的 HEAD。提交后普通 push 被拒绝就结束，不 rebase、不发布旧产物；无变化也检查远端默认分支 SHA。
  理由：保证编译源码与最终 target commit 一致；不让外部并发推进被覆盖。日期/作者：2026-09-17 / 用户约束。
- 决策：发布非语义版本数据标签；先 create --draft，再显式上传五个精简附件，最后 edit --draft=false --latest。完整报告/readback 仅上传 Actions artifact，失败保留 draft 但不设置 latest，不删除历史。
  理由：每次快照可追溯、重复数据允许，失败不公开半成品。日期/作者：2026-09-17 / 用户约束。

## 成果与复盘

实施及独立审查已完成，当前无未解决发现。审查发现的恢复说明偏差已修复，新增真实本地 Git 回归测试；主会话复跑24项测试全部通过（`/tmp/happ-daily-parent-tests.log`），actionlint+ShellCheck、计划校验和差异检查通过。workflow `d41dfa44-5c76-45c5-9368-90b0e88a816c` 的实施和审查子任务均已完成。变更为新 workflow、`tools/happ/daily.py`、`tools/happ/test_daily.py`、更新 README 和本独立计划。现有 `build.py`、`test_build.py`、`geo-reader.go`、pins 和当前 `rule/` 均未修改。当前真实仓库 HEAD 仍为 `31cdb642d1d08807206b049202212c8eabd88863`，无暂存；真实仓库没有 commit/push/tag/gh release/workflow run。

### 自动化及本地失败保护

最终24个 unittest（原有17 + 新增7，含审查后的旧 run 恢复回归）退出0。新增夹具全部创建在 TemporaryDirectory：跨 Surge/Clash/QuantumultX/新客户端精确同步 A=2、D=1、M=2；保留 tools/.github/docs/rewrite/script 自有文件；提交父链/target 正确；无变化不造空 commit 但生成发布元数据；缺报告、失败报告、部分分类、回读不相等、dat 篡改、源 hash 不一致全部阻止提交；脏目录及 symlink 上游在修改前拒绝。实际 workflow 的普通 push shell 在本地 bare remote 夹具中成功，并模拟首次 ls-remote 后另一写者推进，真实 Git 返回 rejected，既不 rebase 也不进入发布标记；无变化分支也拒绝已推进远端。

实际 release shell 使用 mock gh 验证 create --draft / --target、仅五个附件、upload 失败不调用 edit；rerun attempt 标签不同，成功才调用 edit --draft=false --latest。这只能证明控制流，不能当作真实 GitHub API 上传或权限验证。

### 三次真实全量编译/回读

三次均为全部 690 分类（692 目录、2 容器），纳入 688，跳过 2；转换 1,432,480 行、跳过 1,950，mapped IPv6 实际 116 行。GeoSite 659 类、1,340,367 条；GeoIP 108 类，输入 92,113 条聚合为 65,350（IPv4 47,024、IPv6 18,326）。category_sets/domain_types_and_values/cidr_coverage 都为 equal，不是仅比较数量。

- 本地源码 `31cdb642d1d08807206b049202212c8eabd88863`：`/home/lay/projects/rules/ios_rule_script/build/happ/daily-local.EKUaxs/`，38.03 秒、峰值 RSS 812,236 KiB；用原有 `/tmp/happ-tools.hzeRY0/bin/` 三工具。
- 隔离上游源码 `4435ba4141d82aab94e541e29023fc6a1f627723`：只在 `/tmp/happ-upstream.kNVhoW/` restore rule 并复制本 fork 的 build.py/reader；产物 `/home/lay/projects/rules/ios_rule_script/build/happ/daily-upstream.f7IqGT/`，39.23 秒、812,132 KiB；未更新当前工作树 rule。
- 实际抽取 workflow 安装步骤，在 `/tmp/happ-actions-install.tPMzk3/` 重新 fetch 固定工具、go build -mod=readonly、构建 reader、下载校验 gh 2.100.0；工具元数据 gate 全通过。使用这些新工具重新构建隔离上游全量，产物 `/home/lay/projects/rules/ios_rule_script/build/happ/daily-workflow-tools.Fr1AMg/`，38.65 秒、812,036 KiB。不能把已有缓存工具成功替代 workflow 安装链路验证，本次两者均执行。

三份报告的两个数据库 hash 一致：

- geosite.dat：29,349,986 bytes，SHA-256 `88244a1415ffaae0bdcf175079ff890dea20c5bffa4d48fb65a28f2a23e38e7d`。
- geoip.dat：874,961 bytes，SHA-256 `a238391189ef75753af3d8ee0b1a409addc2b1d922759d0b87a5b9b7a6165840`。

另对真实本地报告调用 `daily.validated_report`：完整构建状态/三项 equal、两个 dat hash/大小、固定工具身份、690 个源文件 hash 全部通过（日志 `validated-report.log`）。manifest 中 mapped 计数由逐行 reason 统计，夹具以实际 1 行证明不会把历史 116 硬编码为本次数量。

### 实际命令和静态证据

以下在仓库根执行，计时日志写输出目录之外避免破坏 build 的非空保护：

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools/happ -p 'test_*.py' -v
    /usr/bin/time -v -o /tmp/happ-actions-evidence/local-resources.log python3 tools/happ/build.py --geosite-tool /tmp/happ-tools.hzeRY0/bin/domain-list-community --geoip-tool /tmp/happ-tools.hzeRY0/bin/geoip --geo-reader /tmp/happ-tools.hzeRY0/bin/geo-reader --output build/happ/daily-local.EKUaxs
    git init /tmp/happ-upstream.kNVhoW
    git -C /tmp/happ-upstream.kNVhoW fetch --no-tags --depth=1 https://github.com/blackmatrix7/ios_rule_script.git refs/heads/master
    git -C /tmp/happ-upstream.kNVhoW restore --source=FETCH_HEAD --staged --worktree -- rule/
    /usr/bin/time -v -o /tmp/happ-actions-evidence/upstream-resources.log python3 /tmp/happ-upstream.kNVhoW/tools/happ/build.py --geosite-tool /tmp/happ-tools.hzeRY0/bin/domain-list-community --geoip-tool /tmp/happ-tools.hzeRY0/bin/geoip --geo-reader /tmp/happ-tools.hzeRY0/bin/geo-reader --output build/happ/daily-upstream.f7IqGT
    /usr/bin/time -v -o /tmp/happ-actions-evidence/workflow-tools-resources.log python3 /tmp/happ-upstream.kNVhoW/tools/happ/build.py --geosite-tool /tmp/happ-actions-install.tPMzk3/happ-tools/bin/geosite --geoip-tool /tmp/happ-actions-install.tPMzk3/happ-tools/bin/geoip --geo-reader /tmp/happ-actions-install.tPMzk3/happ-tools/bin/geo-reader --output build/happ/daily-workflow-tools.Fr1AMg
    PATH="/tmp/happ-actions-evidence/shellcheck-v0.11.0:$PATH" /tmp/happ-actions-evidence/actionlint .github/workflows/happ-daily.yml
    python3 /home/lay/.agents/skills/exec-plans/scripts/validate_exec_plan.py docs/plans/happ-daily-sync-release.md
    git diff --check
    git diff --cached --name-only

以上构建输出目录现在非空，复跑须用新目录（mktemp -d），不可原样覆盖。安装链路通过 test_daily.step_shell 读取 workflow 的 `Build existing pinned compilers and reader; install fixed gh` 原文，设置 RUNNER_TEMP/GITHUB_ENV/GITHUB_PATH/GITHUB_WORKSPACE/GOTOOLCHAIN 后用 `bash -e -o pipefail -c` 执行，完整输出为 `install.log`。没有修改安装源码或工具 pins。

所有多行 workflow run 块通过 `bash -n`；Python AST 解析通过。actionlint 1.7.7 官方包 SHA256 为 `023070a287cd8cccd71515fedc843f1985bf96c436b7effaecce67290e7e0757`；ShellCheck 0.11.0 包 SHA256 为 `8c3be12b05d5c177a04c29e3c78ce89ac86f1595681cab149b65b97c4e227198`，后者与官方 GitHub release asset digest 一致。工具均在仓库外。actionlint 同时解析 YAML/表达式/权限/事件和调用 ShellCheck，退出 0，无输出。ExecPlan validator 返回 `OK: ExecPlan format is valid (0 warning(s))`。

证据总目录 `/tmp/happ-actions-evidence/`：`tests.log`、`actionlint.log`、`install.log`、`gh-version.log`、`tool-verification.json`、三组 build/resources 日志、`build-summary.json`、`validated-report.log`、官方文档/Go模块/actionlint/CLI checksum 源。完整 conversion-report/readback/编译器日志保留在上述三个 build 目录，均由现有 .gitignore 排除。

### 未验证边界

没有对 GitHub 创建 Release 或验证托管 runner、GITHUB_TOKEN/org policy、分支保护、实际 artifact 上传及 latest 下载。公开 release edit 成功但网络响应丢失属于远端分布式请求的不可消除边界，需按 GitHub UI 检查；脚本不会为此删除历史。Happ 设备兼容和路由行为仍待实机。上游以后加入未知规则/非法路径会安全失败，需要维护者审查，不能自动降低回读门槛。

## 背景与定位

仓库根目录为 `/home/lay/projects/rules/ios_rule_script`。`tools/happ/build.py` 默认递归读取 `rule/Surge` 所有分类，优先 `_All.list`，两个编译器显式接收生成的本地输入。读取二进制再逐分类比较域名类型和值及 IPv4/IPv6 覆盖；失败返回非零。`PINS` 已固定两个工具 commit，geo-reader 复用域名工具的 module。所有其他客户端也同步，但 Happ 只从 Surge 表示构建，不把其他客户端重复转换。

`conversion-report.json` 包含 status、selection、summary、validation、tools、artifacts 和逐行 categories。全量有损边界保留：ASN/组合/UA/进程/URL 不支持；no-resolve 不能逐条保留；IPv4-mapped IPv6 固定工具不能保留（原快照 116 行，发布须统计本次实际数）。

## 工作计划

里程碑一增加 `.github/workflows/happ-daily.yml`，串行完成 checkout、固定工具准备、上游快照同步、测试、全量构建、规则提交/push、精简发布准备、draft 上传及公开，最后 always 上传诊断。辅助脚本 `tools/happ/daily.py` 只处理路径限制同步、validated 数据校验、manifest 生成，不重写现有转换器。

里程碑二以 `tools/happ/test_daily.py` 的临时仓库覆盖跨客户端变更、根目录保护、无变更、非法树/失败报告/篡改产物保护，以及普通 push 的并发失败行为。测试不得接触真实 origin。

里程碑三运行现有本地全量，再在仓库外隔离 clone 只读获取当前上游 rule 快照；复制自有工具入口到隔离目录编译，不更新当前 rule 树。所有源码 SHA、统计、命令和路径记入计划。最后验证 YAML/actionlint/shell、ExecPlan 格式、diff check、无暂存。

## 具体步骤

除另注明外在仓库根执行：

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools/happ -p 'test_*.py' -v
    python3 tools/happ/build.py --geosite-tool /tmp/happ-tools.hzeRY0/bin/domain-list-community --geoip-tool /tmp/happ-tools.hzeRY0/bin/geoip --geo-reader /tmp/happ-tools.hzeRY0/bin/geo-reader --output build/happ/daily-local
    python3 /home/lay/.agents/skills/exec-plans/scripts/validate_exec_plan.py docs/plans/happ-daily-sync-release.md
    git diff --check
    git diff --cached --name-only

固定 actionlint 1.7.7 下载到 `/tmp/happ-actions-evidence/`，官方 checksum 核验后执行；不新增项目依赖。GitHub CLI 2.100.0 使用官方 linux_amd64 包及固定 SHA256。Git 和 Python 使用 ubuntu-24.04 原生工具，不自建运行框架。

## 验证与验收

观察标准：夹具同步后的 rule tree 与指定源 SHA 的 rule tree 完全一致，其他根目录 tree 不变；无变化无空提交；编译或 readback 失败时没有提交/push/公开 release；外部提交使普通 push 拒绝且不进入发布。manifest 必须只接受 validated/all/三项 equal 的报告且校验两个 dat 的真实 hash/大小，记录 source/target/工具/统计/限制。最终 release target 是同步 commit 或无变化时 checkout commit。

实际 GitHub 运行、Token 权限、分支保护、上传及 latest 行为本地无法端到端证明；不能将 mock 或静态检查说成远端验证。Happ 实机加载/流量匹配不在本次本地验收范围。

## 幂等性与恢复

每次 Actions 使用全新工作区/输出目录；concurrency 固定组，cancel-in-progress:false。标签 `happ-UTC时间-run_id-run_attempt`，同一 run rerun 不冲突。无变更照常生成新的快照；不会清理旧 Release，磁盘/历史增长由维护者手工处理。push 失败或构建失败直接停止；上传失败留下未公开的 draft 用于诊断，不自动删旧 draft。若此前规则提交已经 push，旧 run 的 Re-run 保留旧 github.sha，会被远端推进检查拒绝；必须新发起 workflow_dispatch 或等待下一次 schedule。仅在未推进远端且默认分支仍为原 base 时可以 Re-run，run_attempt 只解决标签冲突，不绕过分支安全检查。分支保护不允许机器人普通 push 时需维护者配置允许写入或接受任务失败，不使用 PAT/force/绕过保护。

## 产物与备注

本地证据在 `/tmp/happ-actions-evidence/` 和已忽略的 `build/happ/` 新独立目录。release 只包含 `geosite.dat`、`geoip.dat`、`SHA256SUMS`、`build-manifest.json`、`release-notes.md`；完整诊断作为 Actions artifact，有限保留期，不把百万行回读作为默认 release 附件。

稳定 URL 为 `https://github.com/lay-g/ios_rule_script/releases/latest/download/geosite.dat` 和对应 `geoip.dat`。只有第一次自动化成功发布后这些地址才存在；当前不声称可下载。

## 接口与依赖

Actions checkout v4.2.2 = `11bd71901bbe5b1630ceea73d27597364c9af683`；setup-go v5.5.0 = `d35c59abb061a4a6fb18e82ac0862c26744d6ab5`；upload-artifact v4.6.2 = `ea165f8d65b6e75b540449e92b4886f43607fa02`。均经 git ls-remote 官方仓库 tag 核实。

domain-list-community = `6f3acc3ba95299031cf408232e2e65e2c892fd2d`；geoip = `1503074d8aee4c623791210e90c04d586c86c8f7`。从现有 build.PINS 读取，固定 Go 1.27.1，geo-reader 源码来自本 fork checkout，两个工具源只用于编译、不使用其第三方规则。

官方原文：`https://cli.github.com/manual/gh_release_create` 的 --draft/--target，`https://cli.github.com/manual/gh_release_upload` 的附件上传及默认不覆盖，`https://cli.github.com/manual/gh_release_edit` 的 --draft=false/--latest；GitHub events、concurrency、automatic-token-authentication 文档确认 schedule/default branch、并发和 GITHUB_TOKEN 行为。下载原文位于证据目录；不打印任何 token。

修订说明：2026-09-17 创建独立计划，承接已完成本地 Happ 全量构建；新需求增加整个 rule 树同步和数据发布，不扩大到 rewrite/script 或更改转换语义。
