# Happ 本地 Geo 构建

递归扫描本仓库 `rule/Surge/` 全部规则分类，优先读取每个目录中的 `<目录名>_All.list`，没有时才读 `<目录名>.list`，生成 `geosite.dat`、`geoip.dat` 并从实际二进制逐分类回读验证。Geo 只保存匹配集合，代理/拦截动作由 Happ 配置决定。**全量本地构建与回读已通过，Happ 实机待验证。**

“全量”指全分类发现与覆盖审计，**不表示每条 Surge 规则均无损转换**：ASN、组合条件、UA、进程、URL 条件不支持；固定 GeoIP 编译器不能保留 IPv4-mapped IPv6，本次 116 行明确跳过，不转换为 IPv4。每条跳过及 `no-resolve` 损失均在报告中。构建器只用本仓库规则；不另读 `_Resolve` 等变体、不采集第三方数据、不处理复写、MITM 或脚本，构建器本身不联网发布。独立的每日同步/Release 自动化见下节。

## 每日同步与 Happ Release

`.github/workflows/happ-daily.yml` 每天 UTC **21:23**（北京时间次日 **05:23**）运行，也可在 Actions 的 **Daily rule sync and Happ snapshot** 页面手动 `Run workflow`。仅 `lay-g/ios_rule_script` **默认分支**允许执行；非默认分支手动运行或复制到上游/其他 fork 都跳过。没有 push 触发，避免自动提交循环。

维护者需先将本次文件自行提交至默认分支、在 fork 启用 Actions，并允许 `GITHUB_TOKEN` 的 `contents: write`。分支保护若阻止机器人普通 push，任务会失败；不使用 PAT、force push 或绕过保护。本次只创建自动化，**尚未在 GitHub 执行或发布**。schedule 可能延迟；GitHub 对不活跃仓库的定时任务也可能停用。并发组 `cancel-in-progress: false` 不取消正在运行的任务，但 GitHub 只保留一个 pending，不保证密集手动触发每次都执行。

每次运行固定上游 `blackmatrix7/ios_rule_script master` 的一个 commit，仅在 Actions 临时 checkout 精确替换**整个 `rule/`**：所有客户端的新增、修改和删除都同步；新增客户端也自动纳入。`rewrite/`、`script/`、`source/` 等其他根目录不属于本次同步，自有 `tools/`、`.github/`、`docs/` 不会被上游覆盖。不 merge/reset 整个上游、不执行上游脚本/工作流。Happ 仍只从已同步的全量 `rule/Surge` 构建，不重复合并其他客户端表示。

先运行测试，再用现有 pins 编译两库并逐分类二进制回读。只有全部通过且源码/dat 哈希仍一致才提交规则变更；无变更不造空提交。普通 push 遇到外部推进会直接失败，不 rebase 旧产物、不发布。target 始终是同步后的实际 commit；无变更则是 checkout commit。完整诊断（含逐行报告和 readback）保存在 Actions artifact，保留 14 天；即使构建失败也尝试保留已产生的日志。

Release 标签为 `happ-<UTC YYYYMMDDTHHMMSSZ>-<run_id>-<run_attempt>`。这是**规则数据快照，不是应用语义版本**，同日可有多个 Release；即使没有规则变更，每次成功运行仍创建新快照，数据相同也允许重复，rerun 的 attempt 不同。不会删除旧 Release 或自动清理历史。

发布流程先建 draft，上传全部七个附件后才公开并设置 latest：

- `geosite.dat`、`geoip.dat`：Happ 全量数据库。
- `geosite-chinaonly.dat`、`geoip-chinaonly.dat`：包含 ChinaMax、ChinaMaxNoIP、ChinaMaxNoMedia 的精简数据库。
- `SHA256SUMS`：四个 dat 和以下两个精简元数据文件的 SHA-256。
- `build-manifest.json`、`release-notes.md`：源/checkout/目标 commit、工具 pins/实际元数据、数据变更、转换/跳过数量和限制。mapped IPv6 的历史基线为 116 行，每次发布按报告重新统计，不写死当前数。

任何编译/回读/push 失败不进入发布；上传失败保留未公开 draft，不改变旧 latest，不把半成品公开。**若规则提交已经 push 成功、随后发布失败，请新发起 Run workflow（workflow_dispatch）或等待下次定时运行，不要对旧 run 使用 Re-run**：Re-run 保留旧 `github.sha`，远端推进检查会安全拒绝它。尚未推进远端且默认分支未变化时才可 Re-run；能够进入发布的重试使用不同 attempt 标签。旧 draft 由维护者按需手工处理。完整逐行诊断不作为 Release 默认附件。

首次成功发布后，Happ 可使用以下稳定地址（当前没有替用户创建 Release，不能据此声称地址已可用）：

```text
https://github.com/lay-g/ios_rule_script/releases/latest/download/geosite.dat
https://github.com/lay-g/ios_rule_script/releases/latest/download/geoip.dat
```

### ChinaOnly 精简版

每日流程额外用 `--categories ChinaMax ChinaMaxNoIP ChinaMaxNoMedia` 独立构建、回读，各分类优先读取 `_All.list`，不存在时回退到同名 `.list`。全量版保持不变；任一版本校验失败都不提交或发布。`build-manifest.json` 的 `chinaonly` 字段单独记录精简版统计、跳过原因和校验结果，完整报告在 Actions artifact 的 `chinaonly/` 子目录。

首次包含精简版的 Release 成功发布后，使用：

```text
https://github.com/lay-g/ios_rule_script/releases/latest/download/geosite-chinaonly.dat
https://github.com/lay-g/ios_rule_script/releases/latest/download/geoip-chinaonly.dat
```

域名库包含 `geosite:chinamax`、`geosite:chinamaxnoip`、`geosite:chinamaxnomedia`；IP 库包含 `geoip:chinamax`、`geoip:chinamaxnomedia`。ChinaMaxNoIP 没有 IP 规则，不制造空的 `geoip:chinamaxnoip` 分类。三个分类独立保留，不合并标签，便于选择完整国内、无 IP 或排除国内媒体的规则。

直连动作由客户端配置指定。没有广告、OpenAI、Telegram、private 等其他分类，不可继续引用它们。转换限制与全量版一致，Happ 实机仍待验证。此版本替代原来的 `*-chinamax.dat` 附件，使用者须更新为上述 `*-chinaonly.dat` 下载地址；旧 Release 中的文件不删除。

本地只构建精简版（沿用下文准备的 `TOOLS`）：

```sh
python3 tools/happ/build.py --categories ChinaMax ChinaMaxNoIP ChinaMaxNoMedia \
  --geosite-tool "$TOOLS/bin/domain-list-community" \
  --geoip-tool "$TOOLS/bin/geoip" \
  --geo-reader "$TOOLS/bin/geo-reader" \
  --output build/happ/chinaonly
```

输出目录须不存在或为空。本地文件仍叫 `geosite.dat`、`geoip.dat`，发布元数据步骤校验后复制为带 `-chinaonly` 后缀的附件；不修改数据库内部标签。不要加测试配置 URL 参数，该测试模板要求另外三个分类，不适用于 ChinaOnly 精简版。

Actions 使用官方 go.mod/下载列表核实存在的 **Go 1.27.1**（固定 geoip 要求 1.26+），`GOTOOLCHAIN=local`，复用下述编译器 pins 和本 fork 的 reader，不改转换规则。Actions 固定完整 commit SHA，gh 2.100.0 下载固定 SHA-256 校验；没有第三方发布 action 或额外 Python 包。

辅助 `tools/happ/daily.py snapshot` 会修改并暂存 `rule/`，**仅供干净、可丢弃的 Actions 工作区使用，不要在个人工作树手动运行**。`verify` 校验完整构建报告、文件哈希和路径范围；`manifest` 生成精简发布元数据并复制已校验的 ChinaOnly 附件，不联网。实际流程/失败保护由 `test_daily.py` 的临时 Git 仓库及本地 bare remote 测试覆盖。命令、源码 SHA、真实全量回读结果和远端未验证边界见 [执行计划](../../docs/plans/happ-daily-sync-release.md)。

## 准备工具（显式执行，仓库外）

需要 Python 3.9+、Git、Go 1.26+；本次环境为 Python 3.14.7、Go 1.27.1 linux/amd64。Python 仅用标准库；正常构建不安装任何东西。入口调用 `go version -m` 检查两个编译器的完整 commit、未修改状态，以及回读器的依赖版本，因此构建时也须保留 Go。

固定来源：

- `https://github.com/v2fly/domain-list-community`：`6f3acc3ba95299031cf408232e2e65e2c892fd2d`。
- `https://github.com/Loyalsoldier/geoip`：`1503074d8aee4c623791210e90c04d586c86c8f7`。
- 本仓库 `geo-reader.go`：只调用 `routercommon.GeoSiteList` / `GeoIPList` 和 `proto.Unmarshal` / `protojson.Marshal`，不实现 Protobuf 编解码。复用固定域名工具的 `go.mod` / `go.sum`：v2ray-core `v5.42.0`、protobuf `v1.36.11`。

选择上述域名工具版本是为了完整保留精确域名、后缀和关键词的类型/值集合。上游新版会剪去被后缀覆盖的冗余条目；这不一定改变匹配语义，但不符合本次逐类型审计要求。不改写第三方源码。

在仓库根目录执行（联网下载源码及 Go 依赖；源码里的第三方规则**不作为输入**）：

```sh
REPO="$PWD"
TOOLS="$(mktemp -d /tmp/happ-tools.XXXXXX)"
mkdir -p "$TOOLS/bin"
git clone https://github.com/v2fly/domain-list-community "$TOOLS/domain-list-community"
git -C "$TOOLS/domain-list-community" checkout --detach 6f3acc3ba95299031cf408232e2e65e2c892fd2d
git clone https://github.com/Loyalsoldier/geoip "$TOOLS/geoip"
git -C "$TOOLS/geoip" checkout --detach 1503074d8aee4c623791210e90c04d586c86c8f7
(cd "$TOOLS/domain-list-community" && go build -o "$TOOLS/bin/domain-list-community" .)
(cd "$TOOLS/geoip" && go build -o "$TOOLS/bin/geoip" .)
(cd "$TOOLS/domain-list-community" && go build -o "$TOOLS/bin/geo-reader" "$REPO/tools/happ/geo-reader.go")
git -C "$TOOLS/domain-list-community" rev-parse HEAD
git -C "$TOOLS/geoip" rev-parse HEAD
go version -m "$TOOLS/bin/domain-list-community"
go version -m "$TOOLS/bin/geoip"
go version -m "$TOOLS/bin/geo-reader"
```

不要用 `-buildvcs=false` 或修改工具工作树，否则入口的固定版本检查会失败。工具升级须更新版本约束并重新验证，不自动回退到默认数据库。

## 本地构建和回读

继续在同一 shell、仓库根目录运行；跨 shell 请先设置 `TOOLS` 为已准备目录的绝对路径：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools/happ -p 'test_*.py'
python3 tools/happ/build.py --help
mkdir -p build/happ
OUT="$(mktemp -d "$PWD/build/happ/build.XXXXXX")"
python3 tools/happ/build.py \
  --geosite-tool "$TOOLS/bin/domain-list-community" \
  --geoip-tool "$TOOLS/bin/geoip" \
  --geo-reader "$TOOLS/bin/geo-reader" \
  --output "$OUT"
ls -lh "$OUT/geosite.dat" "$OUT/geoip.dat" "$OUT/conversion-report.json"
# 可独立再次回读，不是编译前文本导出：
"$TOOLS/bin/geo-reader" "$OUT/geosite.dat" "$OUT/geoip.dat" > "$OUT/readback-again.json"
```

成功只在两个工具完成且回读全部一致后打印 `Validated ...`。类别引用用无前缀小写名：`openai`、`telegram`、`advertisinglite`。两个上游工具在数据库内部把分类写为大写；回读按小写核对，配置按 Geo 约定引用小写（Happ 行为仍须实机确认）。

不传 `--categories` 默认递归全量；传入时按大小写敏感的相对目录路径或唯一叶名选择，仍优先 `_All`，例如 `--categories OpenAI Telegram AdvertisingLite` 或 `--categories Cloud/AmazonCloud OpenAI`。先匹配完整相对路径（所以 `Direct` 指顶层），否则叶名必须唯一；歧义、重复选择、路径穿越、未知目录、符号链接和最终标签冲突均失败。即使显式选择，也检查整棵目录树并保留覆盖清单；出现有 `.list` 却没有同名主文件/完整文件的目录时明确失败，不悄悄漏掉。

标签通常取叶名小写，删除名称中的 apostrophe。只有重名的嵌套分类才用相对路径以 `-` 连接消歧：`Direct` → `direct`，`AdGuardSDNSFilter/Direct` → `adguardsdnsfilter-direct`；`Game/Assassin'sCreed-Odyssey` → `game-assassinscreed-odyssey`。这是必要消歧，不给全部标签加统一前缀；无重名的 `Cloud/AmazonCloud` 仍是 `amazoncloud`。最终归一后的标签再次检查碰撞，不能合并来源。

无自身规则的 `Assassin'sCreed`、`Cloud` 是容器，递归纳入其子类。全量时完全无支持规则的分类记为 `status: skipped`，保留逐行原因，不向任何库写空类别；显式选择该分类仍报错。单类可只包含域名或 IP，但**所选集合整体必须同时有支持的域名和 CIDR**，否则在调用工具前失败。原因是 IP 工具在整体空输入时不写文件，而本命令交付两库；这是入口约束，不是 Happ 单库能力的结论。

项目内的 `build/happ/` 已加入 `.gitignore`，用于保存本地数据库、中间文件和日志，不提交到 Git。每次构建创建独立子目录。

输出目录必须不存在或为空，永不覆盖上次产物；重试用新目录。失败返回非零，保留中间数据、日志及失败报告（若已进入编译阶段）；不得使用失败目录中的数据库。输入规则只读。

## 转换与报告

- `DOMAIN` → `full:`，`DOMAIN-SUFFIX` → `domain:`，`DOMAIN-KEYWORD` → `keyword:`。保持匹配类型，域名统一小写。同类型同值只写一次，不合并精确/后缀；数字域名仍是域名。
- 完整域名支持 ASCII DNS 标签或已编码的 punycode；不自动转写 Unicode。关键词允许 `A-Z a-z 0-9 . _ -` 的非空片段，无须满足完整 DNS 名格式。拒绝空白、`#`、`@`、`&`、冒号等编译器语法注入。其他合法但未支持的格式明确报错，不猜测性改写。
- `IP-CIDR` / `IP-CIDR6` 严格检查地址族和主机位，标准化为 CIDR。不能把 `192.0.2.1/24` 扩大为 `/24`。根据 [Surge 官方 IP 规则文档](https://manual.nssurge.com/rules/ip.html)，无掩码的单 IPv4/IPv6 地址分别等于 `/32`、`/128`，本次 STUN 16 条单 IPv6 已纳入并回读通过。不支持带 scope ID 的地址。编译器可能聚合网络；分别折叠 IPv4/IPv6 覆盖集合后比较。
- IPv4-mapped IPv6（完全位于 `::ffff:0:0/96` 的网段）是已知工具限制：固定 GeoIP 编译器会解映射并对 `/128` 产生 `AddPrefix(.../-1)` 错误。只跳过此范围并逐行记录 `IPv4-mapped IPv6 cannot be preserved by pinned GeoIP compiler; not converted to IPv4`，不误跳更大的 IPv6 网络，不把 IPv6 规则改成 IPv4；当前 ChinaMax、ChinaMaxNoMedia、ChinaMedia、TencentVideo 各 29 行，共 116 行。
- 仅 IP 的 `no-resolve` 修饰符可移除，每条转换行记录语义警告。Geo 不能逐条携带 DNS 行为；配置选 `AsIs` 不代表完整保留 Surge 行为。其他参数、未知类型、字段错误明确失败。
- `IP-ASN`、`AND`、`OR`、`USER-AGENT`、`PROCESS-NAME`、`URL-REGEX` 整行跳过，记录路径、行号、原文、原因。OR 内五个 ASN 只算一条跳过；不抽取 AND 内的域名。

输出包含 `geosite-input/`、`geoip-input/`、只引用本地文本的 `geoip-config.json`、两个 `.dat`、`readback.json`、三份工具日志及 `conversion-report.json`。报告中：

- `status: validated` 才是成功；`validation` 显示分类集、域名类型/值和 CIDR 覆盖一致。
- `selection` 区分全量/显式；`inventory` 列出每个相对目录、标签、首选文件、其他 `.list` 变体及 selected/not_selected/container 状态，确保递归覆盖可核查。`summary` 汇总发现/纳入/跳过分类和规则数量，`elapsed_seconds` 为入口开始至校验完成（不含最终报告写盘）的耗时。
- `categories` 记录每个所选源文件路径、SHA-256、included/skipped 状态、`by_rule_type` 读取/转换/跳过的**输入行数**、`skipped` 和 `warnings` 的逐行明细。无支持规则分类没有 `after_compile`，也不会出现在任一数据库。
- `before_compile` 是去重后的输入条目数；`duplicates_removed` 是去重数；`after_compile` 是二进制回读条目数及 IPv4/IPv6 数量。头部 TOTAL 不参与统计。
- `tools` 记录可执行路径、SHA-256、编译器来源/完整 commit、实际 Go build metadata；`commands` 记录实参、退出码、日志路径；`artifacts` 记录两个数据库大小及 SHA-256。

本次实际全量：669 顶层目录、692 总目录（含 2 容器），发现 690 分类、纳入 688、跳过 ChinaASN 和 MOOMusic 两类；19 类选用 `_All`（含仅有 `_All` 的 AdGuardSDNSFilter、EasyPrivacy）。860 个 `.list` 全部在选择/变体清单内。读取 1,434,430 行，转换 1,432,480 行、跳过 1,950 行，64,237 条 `no-resolve` 警告。域名回读 1,340,367 条；CIDR 输入 92,113 条聚合为 65,350 条（IPv4 47,024、IPv6 18,326），覆盖一致。

成功产物位于 `/home/lay/projects/rules/ios_rule_script/build/happ/full.Bu3w6q/`：`geosite.dat` 29,349,986 字节、`geoip.dat` 874,961 字节；完整执行 40.16 秒，峰值 RSS 812,100 KiB。完整覆盖清单见 `conversion-report.json` 的 inventory/categories；本次另保存便于查看的 `coverage.tsv` 和独立再次回读检查记录。规则文件头部 TOTAL 不参与统计。命令、摘要、SHA-256 与诊断证据见 `docs/plans/happ-local-geo-build.md`。

## 可选 Happ 测试配置

只有同时传入两 URL 才生成 `routing.json` 和 `routing.txt`；URL 不会被下载或探测。仅接受无用户名/密码的 HTTP(S) 地址。未传 URL 不生成配置，不放占位下载地址。首批三类必须齐全；其他附加类别不会被猜测性分配动作。

下面的 `example.com` **仅用于本地编码验证，无法用来下载本次数据库**。真正导入前换为你已自行准备、设备可访问的两个文件 URL；本工具不上传、不启动 HTTP 服务。

```sh
mkdir -p build/happ
PROFILE_OUT="$(mktemp -d "$PWD/build/happ/profile.XXXXXX")"
python3 tools/happ/build.py \
  --categories OpenAI Telegram AdvertisingLite \
  --geosite-tool "$TOOLS/bin/domain-list-community" \
  --geoip-tool "$TOOLS/bin/geoip" \
  --geo-reader "$TOOLS/bin/geo-reader" \
  --output "$PROFILE_OUT" \
  --geosite-url https://example.com/geosite.dat \
  --geoip-url https://example.com/geoip.dat
python3 - "$PROFILE_OUT" <<'PY'
import base64, json, pathlib, sys
out = pathlib.Path(sys.argv[1])
link = (out / 'routing.txt').read_text().strip()
assert link.startswith('happ://routing/add/')
data = base64.b64decode(link.removeprefix('happ://routing/add/'), validate=True)
assert data == (out / 'routing.json').read_bytes()
assert json.loads(data)['Geositeurl'] == 'https://example.com/geosite.dat'
print('routing JSON / Base64 roundtrip OK')
PY
```

固定配置名 `ios_rule_script-local-test`：openai、telegram → Proxy，advertisinglite → Block。各 Sites/Ip 引用只对对应库实际存在的类别生成；Direct 为空，不引用默认 `cn` / `private` 等标签，不人为给同一类别设置冲突动作。

按 [Happ 官方路由文档](https://www.happ.su/main/dev-docs/routing.md?displayAgentInstructions=false&markdownSource=page-action) 使用 `Geositeurl`、`Geoipurl`、`happ://routing/add/{base64}`（不是 `onadd`），UTF-8 JSON 和标准 Base64，并在生成时反向解码。显式设置字符串 `GlobalProxy: "true"`、`FakeDNS: "false"`、`DomainStrategy: "AsIs"`、空 `LastUpdated`。DNS 为官方默认示例的 Cloudflare 远程 DoH (`1.1.1.1`) 与 Google 国内字段 DoH (`8.8.8.8`)，含对应 DnsHosts。**这只是测试参数，不是适合中国网络环境的推荐模板。**不承诺更新频率或冲突优先级。

## 实机验收（未完成）

1. 记录设备平台、Happ 版本及订阅类型。选允许手动导入路由的订阅；JSON 订阅不能手动添加，须由提供方随订阅提供。
2. 自行准备能访问真实数据库的 URL，重新生成配置、复制 `routing.txt` 导入。同名会更新；首个配置在两个 Geo 下载完成后才激活。不要把本地 Base64 验证当作下载成功。
3. 确认两个下载成功、分类存在、无错误提示；重连后再验证路由。设置修改只在重连后生效。
4. 分别验证精确域名、后缀、关键词、直接 IPv4/IPv6 访问的代理或拦截结果；确认 DNS 行为。必要时用保留域名 `example.com` / `example.org` 和文档网段 `192.0.2.0/24` / `2001:db8::/32` 配合可控环境隔离匹配语义，勿把保留网段不可达误判为路由结果。
5. 分类之间可能天然重叠；测试模板不重复引用同一分类，但不能据此推断 Happ 的冲突优先级。记录实际表现再决定是否使用。

本次没有可用设备或真实下载地址，未进行导入、下载、重连或流量匹配测试。结论仅为本地编译及回读通过。
