# 为 Happ 建立本地 Geo 规则构建流程

本 ExecPlan 是一份持续更新的文档。实施过程中必须始终维护“进度”、“意外与发现”、“决策记录”和“成果与复盘”四个章节。

## 目标与整体说明

把本仓库已有的 Surge 分流规则转换成 Happ 可引用的 `geosite.dat` 和 `geoip.dat`。Geo 文件是带分类标签的域名或 IP 数据库，只描述匹配对象；直连、代理、拦截动作由 Happ 路由配置决定，不写进数据库。

本次只跑通本地转换、编译、回读校验和测试配置生成，不建设 CI、Release、托管服务或自动更新。分类不加前缀，使用现有名称的小写形式，例如 `openai`、`telegram`、`advertisinglite`。不支持 ASN，不混入第三方规则数据，不迁移复写、MITM 或 JavaScript 脚本。

完成后，使用者能从仓库根目录执行一个构建入口，得到两个 Geo 文件、可审查的转换报告，以及在给定文件 URL 时生成的 Happ 测试配置与导入链接。不传 `--categories` 默认递归全分类构建，每类优先 `_All.list`，显式选择仍可用。全量是覆盖全部分类并审计跳过，不代表全部 Surge 行可无损表示；不支持的条件及固定工具不能保留的 IPv4-mapped IPv6 逐行报告。三分类只作为可选测试配置，不为其他类别猜分流动作。Happ 实机加载是独立验收项，不以本地构建成功代替。

## 进度

- [x] (2026-09-17 12:26Z) 完整阅读现有四文件和 ExecPlan/skill，递归调查 669 顶层、692 总目录和 690 分类文件；确认两容器和三组重名。
- [x] (2026-09-17 12:29Z) 默认改为递归全量、优先 `_All`，实现覆盖清单、无支持规则分类跳过、名称消歧和最小格式扩展；17 项单元测试通过。
- [x] (2026-09-17 12:31Z) 真实全量编译/逐分类回读及独立重读源/hash/860 文件覆盖校验通过，纳入 688/690 类；记录大小、耗时、峰值内存和 116 条 mapped IPv6 限制。
- [x] (2026-09-17 12:35Z) README/计划更新完成；17 项测试、CLI help、ExecPlan 格式（0 warning）、diff check 和产物忽略校验通过；显式三分类 `_All` 构建及测试配置/引用/Base64 检查通过。
- [x] (2026-09-17 12:43Z) 本次全量独立 reviewer 审查通过，无 P0/P1/P2 发现；主 agent 复跑17项测试、diff检查通过，并重新计算两个产物大小与 SHA-256，均与 validated 报告一致。

- [x] (2026-09-17 11:39Z) 确认用户要求和官方文档中的 Geo URL、分类引用、导入及订阅限制；确定只实施本地链路。
- [x] (2026-09-17 11:39Z) 检查仓库结构、工作树、Geo 文件和规则样例；未发现现成 Geo 产物或构建入口。
- [x] (2026-09-17 11:54Z) 固定两个上游 commit、实际构建两个工具和只读 helper；保留示例域名及双栈网段原型编译/回读通过。
- [x] (2026-09-17 11:59Z) 实现标准库适配入口、逐行跳过/警告报告和 11 个单元测试，测试通过。
- [x] (2026-09-17 11:59Z) 三分类真实构建/回读通过：244 个域名条目、199 个 CIDR；包含 Telegram 的 4 条 IPv6。
- [x] (2026-09-17 12:02Z) README、可选测试配置及 add 链接完成；真实重建、所有引用存在、URL 原样及 Base64 往返检查通过。
- [x] (2026-09-17 12:02Z) 记录工具、产物绝对路径、真实命令和统计；三次构建语义一致，单侧类别混合的真实编译通过。
- [x] (2026-09-17 12:13Z) 独立 reviewer 审查通过，未发现 P0/P1/P2 问题；主 agent 复跑 11 个测试、计划校验和 diff 检查通过，并独立重建/回读首批三分类成功。
- [x] (2026-09-17 12:17Z) 按用户追加要求创建项目内 `build/happ/` 并加入 `.gitignore`，更新 README 示例；在 `build/happ/build.BSYKUR/` 真实重建及回读通过，`git check-ignore` 确认两个数据库被排除。
- [ ] Happ 实机导入、Geo 下载、重连与路由匹配待验证：本次无可用设备和真实文件下载地址。

## 意外与发现

- 观察：递归有 692 个目录，顶层 669；两目录无自身主文件是容器，不是丢失规则。
  证据：`Assassin'sCreed` 下有两游戏子类，`Cloud` 下有 12 子类；其余嵌套有 AdGuardSDNSFilter/Direct、ChinaIPs/ChinaIPsTest、Game 下 7 类。共 690 个分类（667 顶层、23 嵌套），19 个选择 `_All`，AdGuardSDNSFilter/EasyPrivacy 只有完整文件。860 个 `.list` 均在 inventory 的 selected_file/other_list_files 中。
- 观察：原始叶名有三组碰撞且 apostrophe 需要安全规范化，不能只用目录一级扫描或静默字典覆盖。
  证据：Direct 顶层与 AdGuardSDNSFilter/Direct 的内容不同；两套 Assassin'sCreed 游戏文件的字节也不同，分别保留，来源到标签映射见实际报告与下节。
- 观察：旧版解析器只在全量数据上遇到 3 个下划线关键词、16 个 STUN 单 IPv6。调查官方文档和工具语法后均可无损表示。
  证据：Surge 官方明确单地址掩码语义；独立回读确认 `wb_ad`、两个 `_vmind.qqvideo.tc.qq.com` 关键词和 16 条 STUN `/128` 原样保留。
- 观察：固定 GeoIP 工具对 IPv4-mapped IPv6 失败，必须区分真实 IPv6 和工具内部解映射。
  证据：全量诊断目录 `build/happ/full.aU11mB` 记录 failed；最小单行 `::ffff:113.248.172.245/128` 在 `build/happ/mapped-repro.abqz6l92/mapped.txt` 重现 `AddPrefix(113.248.172.245/-1)`（退出 1）。上游 `lib/entry.go:200-219` 的 `net.ParseCIDR`、`netipx.FromStdIPNet` 与 `Unmap` 导致非法 prefix，`:255` 入 builder 后报错。未修改上游。

以下观察为最初三分类主文件试验的历史证据；不再限制当前 `_All` 优先范围。

- 观察：AdvertisingLite 主文件的头部写有 38,069 条，但实际只有 377 条有效规则；其中 187 个关键词、187 个 CIDR、2 条 URL-REGEX 和 1 条 AND。主文件没有独立 DOMAIN/DOMAIN-SUFFIX。
  证据：首次实际转换报告统计三类合计 458 个输入规则行、转换 443 行、跳过 15 行；保持只读主文件的约定，没有为了追齐头部数混入 `_All`。
- 观察：两个工具的内部分类均转大写，GeoIP 可聚合相邻 CIDR；选定域名版本保留精确/后缀同值的两条规则。
  证据：保留样本回读为 SAMPLE；`192.0.2.0/25` 与 `192.0.2.128/25` 合并为 `/24`；`full:example.org` 与 `domain:example.org` 均保留。真实三分类 CIDR 条目数恰未变化，不能因此假设编译器从不聚合。
- 观察：当前域名工具含冗余剪枝，而选定旧版无回读 CLI；已有 routercommon API 可直接回读两库，无需手写 Protobuf。
  证据：实际检查新版本的 `polishList`、旧版本的 `ParseList` / `toProto`，并构建 `geo-reader.go` 后完成原型和真实数据读取。实际工具路径及命令见“成果与复盘”。

- 观察：当前仓库主要提供多客户端规则成品，并没有可直接扩展的 Geo 构建链路。
  证据：`git ls-files '*.dat' '*.proto' '*.mmdb' '*.srs' '*.mrs'` 无输出；未发现 `tools/`、`docs/` 或已有 `PLANS.md`。`source/README.md` 说明其内容仅用于程序生成规则，不应直接引用。
- 观察：当前规则中的组合条件无需首版实现通用逻辑解析器。
  证据：`rule/Surge/Telegram/Telegram.list` 的 OR 组合全部为 ASN；广告类主文件包含 `AND,((USER-AGENT,Frodo*),(DOMAIN,119.29.29.29))`。前者属于明确排除的 ASN，后者不能去掉 UA 后仅保留域名，否则扩大匹配范围。
- 观察：官方文档没有定义 Surge 式嵌套 AND/OR 字段。
  证据：其 Profile Structure 仅展示 Direct/Proxy/Block 的 Sites、Ip 数组。这不足以证明 Happ 的所有配置入口或内核都不支持逻辑组合，但足以确定本次不能输出这种未被文档定义的语法。
- 观察：执行环境有 Go 和 Python。
  证据：计划编写时 `go version` 为 `go1.27.1 linux/amd64`，`python3 --version` 为 `Python 3.14.7`；此前 PATH 检查未发现 `geoip`、`geoview` 命令。当时工具依赖下载及实际编译尚未执行；现已完成，见“成果与复盘”。

## 决策记录

- 决策：对经最小样本证明无法由固定工具保留的 IPv4-mapped IPv6 逐行跳过，reason 明确写工具限制；不映射到 IPv4、不改第三方源码或 pins。用 `IPv6Network`、`prefixlen >= 96`、`network_address.ipv4_mapped` 识别完全位于 mapped 范围的网段，先严格地址族/主机位校验，不误跳更大 IPv6 网络。
  理由：这是已知格式的编译器限制，不是允许未知规则或宽泛忽略。当前四分类各 29 行，共 116 行；全部在报告中可定位，回读仍严格比较实际支持集合。
  日期/作者：2026-09-17 / supervisor 批准，实施 agent 完成最小重现后落地。

- 决策：用户新请求覆盖旧版“只读主文件/三分类实测”范围；不传 `--categories` 时递归扫描全部目录，每类优先 `<分类>_All.list`，否则 `<分类>.list`；显式选择同样优先完整版本。全量无支持条目的分类逐行记录并标为跳过，不制造空类别；显式选择保留失败行为。
  理由：完整域名主要位于 `_All`，嵌套目录也属于仓库规则，不能静默遗漏。容器和未选变体均在清单可见；未知规则仍失败。
  日期/作者：2026-09-17 / 用户追加要求。
- 决策：标签通常保留叶名小写，仅删除 apostrophe；叶名发生碰撞时，嵌套分类以相对路径用 `-` 连接消歧，顶层保持原名；最终全局冲突仍失败。显式选择支持相对目录路径或唯一叶名，不能静默合并。报告逐目录源路径与标签映射。
  理由：发现顶层 Direct 与 AdGuardSDNSFilter/Direct、Game 与 Assassin'sCreed 下两个游戏分类重名。必要消歧不等于给所有类别添加统一前缀。
  日期/作者：2026-09-17 / supervisor 批准。
- 决策：关键词增加允许 `_`；单 IP 按官方定义转 `/32` 或 `/128`，继续拒绝带主机位网络及 scope ID，不改源文件。
  理由：3 条真实关键词含下划线，现成编译器的 keyword 原样保留；STUN 有 16 条无掩码 IPv6。官方 `https://manual.nssurge.com/rules/ip.html` 明确单 IPv4=/32（Surge Mac 6.0.0 起）、单 IPv6=/128，不需要猜测或有损转换。
  日期/作者：2026-09-17 / 实施 agent 根据官方文档调查。

- 决策：按追加要求使用项目内 `build/happ/` 保存本地编译产物，并以 `/build/happ/` 加入 `.gitignore`；README 改为每次在此目录创建独立输出子目录。第三方工具仍放仓库外。
  理由：用户希望产物保留在项目空间内且不进入 Git；覆盖先前“所有产物放仓库外、不改 .gitignore”的约定。
  日期/作者：2026-09-17 / 用户要求，主 agent 实施。

- 决策：固定 domain-list-community `6f3acc3ba95299031cf408232e2e65e2c892fd2d` 和 geoip `1503074d8aee4c623791210e90c04d586c86c8f7`；新增 `tools/happ/geo-reader.go`，用已有 routercommon 类型和 protobuf API 回读两库，CLI 增加必需的 `--geo-reader`。helper 从固定域名工具的 Go module 构建，依赖复用其 go.mod/go.sum，不新增 Python 包。
  理由：实际检查当前域名工具的 polishList 会删除被后缀覆盖的 full/domain 条目；这是冗余优化，不一定改变匹配语义，但旧版能满足严格类型/值审计。所选旧版已检查无此优化且无回读 CLI；最小 helper 只解码导出 JSON，不编译。
  日期/作者：2026-09-17 / 实施 agent，主 agent 批准。
- 决策：所选分类集合必须整体至少有一条域名和一条 CIDR，否则编译前明确失败；单类仍可仅存在于一个库。
  理由：geoip 的 dat_out.go 在整体空输入时不会输出文件；本命令交付两库，不制造空分类或手写空 Protobuf。这是当前入口/工具约束，不是 Happ 的能力结论。
  日期/作者：2026-09-17 / 实施 agent，主 agent 批准。

- 决策（已被全量追加要求覆盖）：最初读取 `rule/Surge/<分类>/<分类>.list`，不混入 `_All`、`_Resolve` 等变体，也不从 `source/` 自建采集流程。
  理由：复用现有公开规则，格式直接，避免重复输入和扩大维护范围。
  日期/作者：2026-09-17 / 用户约束与主 agent 整理。
- 决策：分类名称小写且不加前缀；不自动构造 `cn`、`private` 等第三方标签。
  理由：用户明确要求不加前缀、不混入第三方数据；配置只能引用实际存在的分类。
  日期/作者：2026-09-17 / 用户。
- 决策：ASN、AND/OR、UA、进程及 URL 条件整条跳过并报告，不展开、不静默丢弃。
  理由：用户排除 ASN；Geo 集合不能原样保存任意跨维度条件。本次不为未来可能出现的可展开 OR 建通用解析器。
  日期/作者：2026-09-17 / 用户约束与主 agent 整理。
- 决策：域名采用 `v2fly/domain-list-community` 编译工具，IP 采用 `Loyalsoldier/geoip`；仅输入自己的数据，不使用默认数据或远程数据配置。
  理由：已有工具支持自定义输入，无需自行编码 Protobuf，也无需新增 Python 依赖。具体版本、CLI 和回读方式必须通过第一里程碑验证，未验证前不视为已确定的可执行命令。
  日期/作者：2026-09-17 / 主 agent。
- 决策：工具安装和构建由使用者显式完成；适配入口接收工具路径，不在正常构建中静默下载安装工具。
  理由：保持一个小入口，避免顺带实现包管理器；版本和来源可以审计。
  日期/作者：2026-09-17 / 主 agent。
- 决策：不发布，不新增常驻 HTTP 服务；Happ 下载地址是配置生成时的显式参数。
  理由：用户要求先跑通本地流程；实机测试和文件传输方式独立处理。
  日期/作者：2026-09-17 / 用户。

## 成果与复盘

### 当前全量追加任务（2026-09-17）

本次仅修改 `tools/happ/build.py`、`tools/happ/test_build.py`、`tools/happ/README.md` 与本计划，复用原样 `geo-reader.go` 和三个固定工具；没有修改 rule/source、第三方工具、依赖、`.gitignore`，无提交、暂存、push、发布或服务。

成功绝对目录为 `/home/lay/projects/rules/ios_rule_script/build/happ/full.Bu3w6q/`。实际入口（仓库根执行，不传分类、不传 URL）：

    /usr/bin/time -v -o /tmp/happ-full-resources.log python3 tools/happ/build.py --geosite-tool /tmp/happ-tools.hzeRY0/bin/domain-list-community --geoip-tool /tmp/happ-tools.hzeRY0/bin/geoip --geo-reader /tmp/happ-tools.hzeRY0/bin/geo-reader --output /home/lay/projects/rules/ios_rule_script/build/happ/full.Bu3w6q

退出 0：`converted 1432480 input lines; skipped 1950; Happ device validation pending`。`status=validated`，三项 validation 均 equal。工具版本元数据及 SHA 在 conversion-report.json；`resources.log` 保存完整执行耗时 40.16 秒、峰值 RSS 812,100 KiB，入口 `elapsed_seconds=39.220`（不含最后报告落盘）。仅把 `json.dumps` 改为直接 `json.dump` 写盘，未引入流式解析库或重写回读器。

发现 690 类，纳入 688 类，跳过 ChinaASN（1009 ASN 行）、MOOMusic（1 UA 行），另有 2 纯容器。GeoSite 有 659 类、GeoIP 有 108 类，允许两库类别不同，无空条目。读取 1,434,430 行，转换 1,432,480 行，跳过 1,950 行；域名 1,340,367 条，CIDR 92,113→65,350 条（IPv4 47,024、IPv6 18,326），类型和值/网络覆盖逐分类完全相等；所有域名类型合计为 DOMAIN 59,599、DOMAIN-SUFFIX 1,279,469、DOMAIN-KEYWORD 1,299。`no-resolve` 警告 64,237 行。

跳过明细为 ASN 1,021、UA 596、进程 173、URL 40、AND 3、OR 1、编译器无法保留的 mapped IPv6 116（ChinaMax、ChinaMaxNoMedia、ChinaMedia、TencentVideo 各 29）。全量覆盖不是规则百分百无损；支持集之外的逐行路径/行号/原文/原因均保留，不将上述内容混入产物。

- `geosite.dat`：29,349,986 字节，SHA-256 `88244a1415ffaae0bdcf175079ff890dea20c5bffa4d48fb65a28f2a23e38e7d`。
- `geoip.dat`：874,961 字节，SHA-256 `a238391189ef75753af3d8ee0b1a409addc2b1d922759d0b87a5b9b7a6165840`。
- 全覆盖清单：同目录 `conversion-report.json` 的 inventory/categories；额外本地审计文件 `coverage.tsv` 有全部 692 目录的来源、标签、状态、选择文件及两库条目数，不把大清单写进上下文。

23 个嵌套类别均已纳入：AdGuardSDNSFilter/Direct；Assassin'sCreed 下 Odyssey/Origins 两类；ChinaIPs/ChinaIPsTest；Cloud 下 360Cloud、AkamaiCloud、AmazonCloud、BaiduCloud、CloudCN、CloudGlobal、HiNet、HuaweiCloud、JingDongCloud、KingsoftCloud、NeteaseCloud、TencentCloud；Game 下 Assassin'sCreed-Odyssey、Assassin'sCreed-Origins、GameDownload、GameDownloadCN、Nikke、Roblox、TencentLoLMobile。只有冲突嵌套标签使用相对路径：`adguardsdnsfilter-direct`、`assassinscreed-assassinscreed-odyssey`、`assassinscreed-assassinscreed-origins`、`game-assassinscreed-odyssey`、`game-assassinscreed-origins`；顶层 `direct` 及其他唯一叶名保持小写。

独立再次从真实二进制读取：

    /tmp/happ-tools.hzeRY0/bin/geo-reader /home/lay/projects/rules/ios_rule_script/build/happ/full.Bu3w6q/geosite.dat /home/lay/projects/rules/ios_rule_script/build/happ/full.Bu3w6q/geoip.dat > /home/lay/projects/rules/ios_rule_script/build/happ/full.Bu3w6q/readback-again.json

退出 0，3.88 秒。随后 Python 重新调用 `category_paths(inventory=...)`、`convert_category(..., allow_empty=True)` 读取全部源与 SHA；加载该独立 JSON 后调用 `verify_readback` 并对比报告每分类 after_compile，检查三条下划线关键词、16 个 STUN /128、无空条目/无 routing.json，以及 inventory 选择+变体路径集合等于全部 860 `.list`。`independent-validation.log` 记录检查成功，验证耗时 22.06 秒；内置校验和再次回读均不是编译前文本检查。

失败诊断也保留：`full.GR5H2u` 是计时器提前写入输出目录，被非空保护正确拒绝（后续计时日志改写 /tmp）；`full.aU11mB` 是 mapped IPv6 全量失败，报告 status=failed；`mapped-repro.abqz6l92` 是单行工具重现。重现命令为：

    /tmp/happ-tools.hzeRY0/bin/geoip convert -c /home/lay/projects/rules/ios_rule_script/build/happ/mapped-repro.abqz6l92/geoip-config.json

显式三分类另在 `/home/lay/projects/rules/ios_rule_script/build/happ/selected.IvQp4Z/` 真实构建并回读通过（同固定工具，加 `--categories OpenAI Telegram AdvertisingLite --geosite-url https://example.com/geosite.dat --geoip-url https://example.com/geoip.dat`）。实际选择 AdvertisingLite_All，转换 38,135 行、跳过 15 行；域名 37,936、CIDR 199，三个标签均在两库中。JSON/Base64 字节往返、六个引用存在、仅三分类测试动作断言均通过，URL 只作编码验证，未下载或发布。

最后执行 `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools/happ -p 'test_*.py' -v`：`Ran 17 tests in 0.128s / OK`；计划 validator：`OK: ExecPlan format is valid (0 warning(s))`；`git diff --check` 无输出，CLI `--help` 退出 0；`git check-ignore` 确认两库被忽略；`git diff --cached --name-only` 无输出。工作树只变更本次四文件。

本次 17 项标准库测试通过，新增/更新覆盖递归与 `_All` 优先、仅完整文件、容器、未归类文件失败、显式相对目录/唯一叶名/歧义、apostrophe/最终碰撞、全量 unsupported-only 跳过与显式失败、默认 CLI、下划线与注入、单 IP、mapped 等价写法/普通 IPv6/更大范围/严格主机位检查。Happ 实机仍未验证。本次独立 reviewer 已验收全量变更，无阻塞发现；workflow `0f981fb8-d606-4be9-b6a9-9f0d47899458` 的 full-build 和 full-review 均已完成。主 agent 实际复跑17项测试（`/tmp/happ-full-parent-tests.log`）、diff检查通过，重新计算全量两个数据库大小与 SHA-256 均与报告一致。本次全量变更尚未提交。

### 历史三分类里程碑（主文件模式，以下数字不代表当前默认构建）

本地里程碑已完成。新增入口、标准库测试、说明及最小只读 Go helper；没有修改 rule/source、全局忽略规则或第三方源码，没有提交、push、tag、发布或启动服务。结论仅为“本地构建与回读通过，Happ 实机待验证”。

旧版最终验收：workflow `9b521666-b924-40b5-8075-f3a5177f598f` 的 implement 与 review 两个子任务均已完成。独立审查无阻塞发现；主 agent 复跑 `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools/happ -p 'test_*.py' -v`，11 项通过；复跑计划格式与 `git diff --check` 通过。主 agent 使用下列相同固定工具重新执行三分类入口，将输出改为 `/tmp/happ-final.8623u1`，退出 0，得到 `converted 443 input lines; skipped 15; Happ device validation pending`，包含实际二进制回读校验。计划初稿已提交为 `21534fb`；实现与本次计划更新尚未提交。

#### 实际工具与原型证据

工具根目录 `/tmp/happ-tools.hzeRY0`，可执行文件为 `/tmp/happ-tools.hzeRY0/bin/domain-list-community`、`/tmp/happ-tools.hzeRY0/bin/geoip`、`/tmp/happ-tools.hzeRY0/bin/geo-reader`。源码分别位于同根目录的 `domain-list-community/`、`geoip/`，Go 依赖缓存也在仓库外。实际准备过程（仓库根执行，子 shell 注明工作目录）：

    git clone --depth=1 https://github.com/v2fly/domain-list-community /tmp/happ-tools.hzeRY0/domain-list-community
    git clone --depth=1 https://github.com/Loyalsoldier/geoip /tmp/happ-tools.hzeRY0/geoip
    git -C /tmp/happ-tools.hzeRY0/domain-list-community fetch --shallow-since=2025-01-01 origin master
    git -C /tmp/happ-tools.hzeRY0/domain-list-community checkout --detach 6f3acc3
    mkdir -p /tmp/happ-tools.hzeRY0/bin
    (cd /tmp/happ-tools.hzeRY0/domain-list-community && go build -o ../bin/domain-list-community .)
    (cd /tmp/happ-tools.hzeRY0/geoip && go build -o ../bin/geoip .)
    (cd /tmp/happ-tools.hzeRY0/domain-list-community && go build -o ../bin/geo-reader /home/lay/projects/rules/ios_rule_script/tools/happ/geo-reader.go)

两个 `git rev-parse HEAD` 的结果分别为 `6f3acc3ba95299031cf408232e2e65e2c892fd2d` 和 `1503074d8aee4c623791210e90c04d586c86c8f7`。`go version -m` 验证两工具 `vcs.modified=false`、相应完整 revision；Go 1.27.1 编译成功。helper 依赖 v2ray-core v5.42.0、protobuf v1.36.11，复用固定域名工具 go.mod/go.sum。可重现的完整 SHA checkout 命令见 README，不依赖此处初次探索时抓到的 HEAD。

`domain-list-community --help` 确认 `--datapath`、`--outputdir`、`--outputname`；`geoip convert --help` 确认 `-c`。GeoIP JSON 的 input 仅为 `text/add` 的本地 uri，output 为 `v2rayGeoIPDat/output`、明确 outputDir/outputName，没有默认配置或远程数据。官方 Happ 文档获取到 `/tmp/happ-tools.hzeRY0/happ-routing.md`，只用于查格式，不作为规则数据。

原型目录 `/tmp/happ-tools.hzeRY0/prototype`，输入 sample 含 `full:example.com`、`domain:example.org`、`keyword:example`，额外用 `full:example.org` 检查类型不合并；IP 输入含两个相邻文档 `/25` 以及 `2001:db8::/32`。实际命令均退出 0：

    /tmp/happ-tools.hzeRY0/bin/domain-list-community --datapath=/tmp/happ-tools.hzeRY0/prototype/geosite-input --outputdir=/tmp/happ-tools.hzeRY0/prototype --outputname=geosite.dat
    /tmp/happ-tools.hzeRY0/bin/geoip convert -c /tmp/happ-tools.hzeRY0/prototype/geoip-config.json
    /tmp/happ-tools.hzeRY0/bin/geo-reader /tmp/happ-tools.hzeRY0/prototype/geosite.dat /tmp/happ-tools.hzeRY0/prototype/geoip.dat > /tmp/happ-tools.hzeRY0/prototype/readback.json

Python 断言实际回读的四个类型/值完全一致；IP 为 `192.0.2.0/24` 和 `2001:db8::/32`。内部分类 SAMPLE 按小写归一核对，配置采用无前缀小写引用。

#### 真实构建、统计与配置证据

首次实际产物目录 `/tmp/happ-build.XfHP6R`。入口完整命令：

    python3 tools/happ/build.py --categories OpenAI Telegram AdvertisingLite --geosite-tool /tmp/happ-tools.hzeRY0/bin/domain-list-community --geoip-tool /tmp/happ-tools.hzeRY0/bin/geoip --geo-reader /tmp/happ-tools.hzeRY0/bin/geo-reader --output /tmp/happ-build.XfHP6R

退出 0，打印 `Validated /tmp/happ-build.XfHP6R: converted 443 input lines; skipped 15; Happ device validation pending`。报告 status=validated，分类集/域名类型和值/CIDR 覆盖全部 equal，没有第三方分类、ASN、组合条件被转换进去。回读前后统计：

- openai：域名 32→32、CIDR 2→2（IPv4 2、IPv6 0），跳过 1 条 ASN，no-resolve 警告 2 条；源 SHA-256 `6f4047cdbf6953cf5d9b38c4ccd6da7bc6f1acb91b7a87134f25d5b8f5d2408b`。
- telegram：域名 25→25、CIDR 10→10（IPv4 6、IPv6 4），跳过 11 条（5 ASN、5 进程、1 OR），no-resolve 警告 10 条；源 SHA-256 `3b375bee8b2ff16d6c955804a5a3638e6e8fdfcc58d209506a928bdd4cc9891a`。
- advertisinglite：域名 187→187、CIDR 187→187（IPv4 186、IPv6 1），跳过 3 条（2 URL-REGEX、1 AND），no-resolve 警告 187 条；源 SHA-256 `4d9a9c809ee52f973228ab35be58f29c7a5e818b3a74cbed820035eb46a0b858`。

`geosite.dat` 4,640 字节，SHA-256 `d643b44ec48f8be64cd47ed3c2e31a4f9efaac78359d2981b704164be999292f`；`geoip.dat` 2,094 字节，SHA-256 `efa0bcdda9d95199dae1087fe6fab41f651b72cc119694f0b6b0ca019b58507f`。报告、readback.json、编译中间文件和三份工具日志均在输出目录。独立再次回读也实际执行：

    /tmp/happ-tools.hzeRY0/bin/geo-reader /tmp/happ-build.XfHP6R/geosite.dat /tmp/happ-build.XfHP6R/geoip.dat > /tmp/happ-build.XfHP6R/readback-again.json

配置目录 `/tmp/happ-profile.BmFXpx`，使用相同三个工具参数和分类，改 `--output /tmp/happ-profile.BmFXpx` 并加 `--geosite-url https://example.com/geosite.dat --geoip-url https://example.com/geoip.dat`；实际再次编译/回读退出 0。URL 仅供本地结构测试，不是可下载本次文件的地址。验证得到 `routing JSON/Base64 byte roundtrip` 成功、两 URL 原样、add 而非 onadd、六个 Geo 引用全都存在，Direct 为空，Proxy 两类、Block 广告类；DNS、AsIs 和字符串布尔值均符合已记录选择。

第三次同参数不带 URL 构建到 `/tmp/happ-repeat.SLVFWy` 退出 0。Python 比较三次 readback、categories（含跳过、警告、源 hash 和数量）、validation 一致，不以字节确定性作为承诺。额外真实测试目录 `/tmp/happ-mixed.m_z4ewik/out`：仅把测试源路径替换为外部的 Domains.list 和 IPs.list，调用真实入口函数/编译器/reader，域名类 3 条、纯 IP 类 2 条通过；两库各只含自己的类别，没有制造空分类。

#### 本地检查与剩余限制

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools/happ -p 'test_*.py' -v` 已通过 11 个标准库测试；覆盖注入、精确/后缀/关键词保留、IPv4/IPv6、重复项、主机位/字段/未知类型错误、路径/缺失/冲突、整行跳过、no-resolve、非空输出、工具缺失/失败、回读差异、URL/配置往返和单侧输入边界。单元测试不依赖网络或 Go 工具；真实工具另行执行，未拿 mock 成功代替真实构建。`python3 tools/happ/build.py --help` 退出 0。最终在 2026-09-17 12:06Z 复跑 11 项测试，`Ran 11 tests in 0.105s / OK`；固定域名模块目录下 `go vet /home/lay/projects/rules/ios_rule_script/tools/happ/geo-reader.go`、`gofmt -l`、`git diff --check` 均无错误，ExecPlan validator 返回 `OK: ExecPlan format is valid (0 warning(s))`。真实 CLI 对非空首次输出目录退出 1，逐文件比较确认未覆盖；实际 reader 对 `/tmp/happ-tools.hzeRY0/prototype/corrupt.dat` 退出 1 并报 `cannot parse invalid wire-format data`。`git diff --cached --name-only` 无输出；工作树只有本计划和四个 tools/happ 文件，未暂存。

旧版限制记录：不支持 ASN/逻辑组合、不会保留每条 no-resolve；当时其他分类/非 ASCII 域名未全部验证；同一类在不同库中的缺席合法但整体两库必须非空。无设备、无真实可下载文件地址，Happ 大小写查找、下载、订阅导入、DNS/重连/路由及冲突优先级均未实机验证。临时目录不是分发存储，可按 README 重建。

## 背景与定位

仓库根目录是 `/home/lay/projects/rules/ios_rule_script`。已有 `rule/Surge/`、`rule/Clash/` 等客户端规则目录，首批输入是：

- `rule/Surge/OpenAI/OpenAI.list`：包含精确域名、域名后缀、关键词、IPv4 和 ASN。
- `rule/Surge/Telegram/Telegram.list`：包含域名、IPv4、IPv6、ASN、进程及 OR。
- `rule/Surge/AdvertisingLite/AdvertisingLite.list`：用于验证拦截分类和 UA/域名 AND 的跳过行为。

规则文件里的 `#` 注释包含统计信息，但统计必须根据实际解析结果重新生成，不依赖文件头的 TOTAL。`geosite.dat` 存储带匹配类型的域名分类，`geoip.dat` 存储 IP 网段分类；一类可以只存在于其中一个文件，不能为配置方便而制造空分类。

官方依据为 `https://www.happ.su/main/dev-docs/routing.md?displayAgentInstructions=false&markdownSource=page-action`。关键约束已收录于此，不要求执行者依赖聊天记录：

- 用 `Geositeurl` 和 `Geoipurl` 指定 Geo 文件，用 `geosite:<分类>` 和 `geoip:<分类>` 在 Direct/Proxy/Block 数组中引用。
- `happ://routing/add/{base64}` 导入 JSON 配置，同名配置更新；首次配置在 Geo 下载成功后激活。`onadd` 会主动激活，首版不用它。
- 路由配置绑定订阅；JSON 订阅不能手动附加配置，必须由提供方随订阅提供。
- 路由设置变更需要重连。文档提到 Geo 更新频率及 `LastUpdated`，但本次不实现或承诺自动更新。
- 官方示例将同一分类放入直连和代理，不能据此推断冲突优先级；测试配置避免人为重复引用，真正的冲突优先级仍须实机验证。

## 工作计划

以下一至四为原有链路，当前增加全量验收并保持固定工具和原有测试配置约束。

### 里程碑一：用现成工具证明格式链路成立

在仓库外的临时目录获取两个工具的源码或官方二进制，固定 tag 或 commit。查阅实际版本的帮助和源代码，确认输入目录、输出文件名和回读/文本导出方式。在本节补充最终命令及版本后，才进入集成。

原型仅使用专门构造的保留示例域名和文档网段：`full:example.com`、`domain:example.org`、`keyword:example`，以及 `192.0.2.0/24`、`2001:db8::/32`。原型的自定义输入必须显式指定，不能沿用工具默认第三方数据。成功标准是编译后通过已有工具或其已有解码 API 回读，能确认分类、域名匹配类型和两种 IP 地址族。若工具确实没有可用回读 CLI，可写最小验证程序调用其现有 Go 类型/API，但不得自行实现 Protobuf 编解码；先在决策记录注明必要性。

这一步必须查明编译器是否会聚合 CIDR 或调整分类大小写；验收比较语义而非盲目要求条目数完全相同。失败时记录命令和错误，修正工具调用，不绕过回读检查。

### 里程碑二：规则适配与报告

新增 `tools/happ/build.py` 和 `tools/happ/test_build.py`，使用 Python 标准库。入口默认递归扫描全部目录，显式类别列表可缩小选择范围；每类优先 `_All.list`，否则主文件。核查所有 `.list` 的归属，记录容器与变体，校验类别不能包含路径穿越或产生规范化名称冲突。跳过空行与注释，支持 UTF-8 输入，按行记录来源。

转换规则为 `DOMAIN` → `full:`、`DOMAIN-SUFFIX` → `domain:`、`DOMAIN-KEYWORD` → `keyword:`；IPv4、IPv6 网段使用 `ipaddress` 校验并以标准 CIDR 输出。不得把精确域名与后缀匹配合并，不得把数字形式的 DOMAIN 擅自转成 IP 规则。对带主机位的 CIDR 使用严格校验并报错，不悄悄扩大网段。只有已确认的 `no-resolve` 修饰符可以移除并记为语义警告；其他未识别参数必须报错。

已知不支持的 `IP-ASN`、`AND`、`OR`、`USER-AGENT`、`PROCESS-NAME`、`URL-REGEX` 整条记录并跳过。未知类型、字段数错误、非法地址和分类缺失应明确失败；全量转换后分类完全为空时记为 skipped，显式选择时仍失败，不能生成假成功产物。域名输入必须防止换行、工具注释/属性/包含语法注入；使用与编译器匹配的校验规则，不强制所有关键词都满足完整 DNS 域名格式。若当前样本暴露额外合法格式，先记录再调整，禁止凭猜测做有损改写。

报告采用 JSON，包含输入路径及 SHA-256、工具版本/commit、各分类按规则类型的读取/转换数量、编译前后数量、跳过条目的路径/行号/原文/原因，以及 `no-resolve` 警告。跳过数量按输入行计数：一个含五个 ASN 的 OR 是一条跳过行，不重复计成五条。无需建立通用规则类层次或插件框架。

### 里程碑三：本地构建和回读集成

在同一个入口中调用两个已准备好的编译器，使用参数数组执行 subprocess，不拼 shell 字符串。域名输入放入独立目录；IP 工具配置只允许本地文本输入，不继承默认配置。调用失败必须返回非零并保留可定位错误。

所有中间文件和正式产物写入指定输出目录，不改原始规则。选择新目录完成本次运行，只有两个数据库编译及校验全部通过才打印成功摘要。入口拒绝非空输出目录，避免覆盖上次成功产物和用户文件。每次运行都显式使用新的输出目录即可重复验证，不需要复杂原子发布或缓存系统。

从二进制回读后核对分类集、域名类型/值和网段覆盖。聚合网段允许条目数量变化，但覆盖范围不可扩大或缩小。首批真实规则必须包含 Telegram IPv6，并确认跳过的 ASN/逻辑条件没有进入 Geo 输出。

### 里程碑四：测试配置与说明

新增 `tools/happ/README.md`，写入固定工具版本的准备命令、本地构建命令、报告含义、限制和实机验证步骤。构建入口支持同时提供 `--geosite-url`、`--geoip-url`，此时才额外生成 `routing.json`、`routing.txt`；不提供 URL 时只构建 Geo 和报告，不插入虚构下载地址。

固定测试配置名称为 `ios_rule_script-local-test`，首批把 `openai`、`telegram` 放入代理，把 `advertisinglite` 放入拦截；IP 引用只对实际存在的对应分类生成。这个配置是首批验证用，不为任意类别猜测分流动作。其他分类构建时可以不生成测试配置。只有首批分类齐全才启用此测试模板，否则带 URL 的调用应明确报错。

DNS、`GlobalProxy`、`DomainStrategy`、`FakeDNS` 等字段需要按官方格式显式填写，并在 README 说明测试选择；不得把文档的字符串 `"true"`/`"false"` 擅自替换为布尔值。DNS 采用官方默认示例的 Cloudflare 远程 DoH 与 Google 国内字段 DoH，明确这只是测试参数、不是适合中国网络环境的推荐模板；域名策略选 `AsIs` 以便分别测试域名和直接 IP 访问，不承诺保留逐条 `no-resolve`。不依赖默认第三方 Geo 标签，也不添加与代理/拦截冲突的直连分类。配置编码使用 UTF-8 JSON 和标准 Base64，生成 `happ://routing/add/` 链接，并通过反向解码验证与 JSON 相同。

暂不启动 HTTP 服务。若用户提供可用设备和文件地址，在允许手动导入的订阅中验证加载、重连和分类路由；若无条件，明确记录待实机验证，不阻塞本地成果交付。

### 里程碑五：递归全量与真实回读

默认不传分类，递归选择首选文件并保留完整目录清单；显式选择沿用同一全局标签映射。按“决策记录”处理安全标签、全量空分类和调查后的格式边缘，不增加其他匹配类型。完整编译后严格比较所有支持类别的类型/值及 CIDR 覆盖；不自动为全部分类生成分流动作。当前结果和复验路径见“成果与复盘”的当前全量任务，文档/格式复核和本次独立 reviewer 已完成，不重复下载工具。

## 具体步骤

以下命令除注明外均在 `/home/lay/projects/rules/ios_rule_script` 执行。构建入口已实现；示例使用本次实际工具路径，若临时目录失效，先按 README 用固定完整 commit 重建工具并替换路径。工具准备放在仓库外，不把第三方源码和数据提交到仓库。

实施前重新检查：

    git status --short
    python3 --version
    go version
    rg -n '^(AND|OR|IP-ASN),' rule/Surge/OpenAI/OpenAI.list rule/Surge/Telegram/Telegram.list rule/Surge/AdvertisingLite/AdvertisingLite.list

工具原型准备目录可用 `mktemp -d /tmp/happ-tools.XXXXXX`。从 `https://github.com/v2fly/domain-list-community`、`https://github.com/Loyalsoldier/geoip` 获取工具后，记录 `git rev-parse HEAD` 和实际构建/帮助命令。域名工具文档已确认 `go run ./ --datapath=<自定义目录>` 入口，其他参数以及 GeoIP 导出配置在第一里程碑验证后补入本计划和 README。不得把未核验的工具参数写成已执行事实。

完成适配后运行：

    python3 -m unittest discover -s tools/happ -p 'test_*.py'
    python3 tools/happ/build.py --help

预期测试通过，帮助中列出下面的参数。工具路径指向第一里程碑得到的可执行文件：

    mkdir -p build/happ
    OUT="$(mktemp -d "$PWD/build/happ/full.XXXXXX")"
    python3 tools/happ/build.py \
      --geosite-tool /tmp/happ-tools.hzeRY0/bin/domain-list-community \
      --geoip-tool /tmp/happ-tools.hzeRY0/bin/geoip \
      --geo-reader /tmp/happ-tools.hzeRY0/bin/geo-reader \
      --output "$OUT"
    ls -lh "$OUT/geosite.dat" "$OUT/geoip.dat" "$OUT/conversion-report.json"

预期两个文件非空，报告含全部所选分类、目录覆盖清单及跳过原因，进程退出码为 0。具体回读命令必须在里程碑一补齐，并在此命令之后实际执行。

另建空目录执行配置生成；把 URL 替换为实机可访问的实际文件地址。URL 参数只生成配置，不代表自动上传或启动服务：

    OUT="$(mktemp -d "$PWD/build/happ/profile.XXXXXX")"
    python3 tools/happ/build.py \
      --categories OpenAI Telegram AdvertisingLite \
      --geosite-tool /tmp/happ-tools.hzeRY0/bin/domain-list-community \
      --geoip-tool /tmp/happ-tools.hzeRY0/bin/geoip \
      --geo-reader /tmp/happ-tools.hzeRY0/bin/geo-reader \
      --output "$OUT" \
      --geosite-url https://example.com/geosite.dat \
      --geoip-url https://example.com/geoip.dat

这里的 `example.com` 仅供验证 JSON/链接生成，不能用于实际下载测试；README 必须区分这两种用途。随后使用测试中的解码断言核对 `routing.txt` 与 `routing.json`。

完成实现后检查工作树，仅允许任务相关新增文件与本计划变化：

    git diff --check
    git status --short
    python3 /home/lay/.agents/skills/exec-plans/scripts/validate_exec_plan.py docs/plans/happ-local-geo-build.md

不执行 commit、push、tag 或发布。

## 验证与验收

最小单元测试使用标准库 `unittest` 和临时目录。覆盖精确域名/后缀/关键词类型保持、IPv4/IPv6、注释空行、重复输入的正确处理、非法 CIDR、未知类型、异常参数、分类路径越界、缺失分类、非空输出目录拒绝、ASN/AND/OR 整条跳过及 `no-resolve` 警告。注入用例应证明输入无法新增工具的 include/属性/额外规则。对不存在的工具或失败的子进程返回非零，不能报告成功。

真实构建验收要求两个现成工具实际运行成功；报告包含输入和工具来源；数据库回读确认预期类别且无第三方类别；域名匹配类型保持；CIDR 覆盖一致。二进制编码可能改变排序、大小写或合并网段，验收以明确核对的语义为准。重复构建要求语义及跳过统计一致，不在未确认工具确定性前承诺文件字节完全一致。

配置验收要求 Geo URL 原样写入对应字段、所有分类引用都存在、JSON 可解析、Base64 往返一致、链接使用 add 而不是 onadd。输出不得夹带真实订阅地址、节点凭证或用户数据。

Happ 实机验收另行记录设备平台和版本、订阅类型、两个文件下载情况、重连后生效情况，以及精确域名/后缀/关键词、直接 IPv4/IPv6 访问的匹配结果。必要时先用里程碑一的可控样本隔离路由语义，避免真实网站的 DNS、节点或广告变化干扰判断。没有完成这一步时最终结论只能写“本地构建与回读通过，Happ 实机待验证”。

## 幂等性与恢复

原始 `rule/`、`source/` 文件只读。工具源码、依赖在仓库外；构建产物置于项目内已忽略的 `build/happ/` 新独立目录。输出目录非空就失败，重试使用新目录，不删除或覆盖旧目录。构建中途失败保留错误日志和中间文件以便定位，但不能把不完整文件标为成功产物。

工具获取或网络失败时报告阻塞，可重试同一固定版本；不自动替换为最新版本、默认第三方数据库或手写编译器。版本升级须先更新决策记录并重新跑样本。若需要变更现有用户文件或新增本计划之外的依赖，先说明原因和影响。撤销本任务只涉及本任务新增的文件，由用户确认后执行，不使用危险清理或 Git 回滚命令。

## 产物与备注

计划文件是 `docs/plans/happ-local-geo-build.md`。实现文件为 `tools/happ/build.py`、`tools/happ/test_build.py`、`tools/happ/README.md` 和最小只读辅助程序 `tools/happ/geo-reader.go`。用户追加要求后，`.gitignore` 新增 `/build/happ/`；推荐产物在项目内此忽略目录保存，第三方工具仍在仓库外。

输出目录包含 `geosite-input/`、`geoip-input/`、`geoip-config.json`、`geosite.dat`、`geoip.dat`、`readback.json`、三份工具日志和 `conversion-report.json`；提供 URL 时另含 `routing.json`、`routing.txt`。不生成发布包、校验和分发文件、CI 配置或滚动 Release。

实施证据在本计划中记录命令、简短输出、工具 commit 和实际产物路径；不得只引用容易丢失的聊天内容或临时日志而没有结果摘要。计划中的绝对工具路径已替换为本次实际位置；真实准备步骤已记录，完整 SHA 的可复现安装命令见 README。

## 接口与依赖

Python 侧只用标准库，包括 `argparse`、`pathlib`、`ipaddress`、`json`、`hashlib`、`base64`、`subprocess`、`tempfile`、`unittest`，不增加 pip 包。运行入口为 `python3 tools/happ/build.py`。

CLI 提供可选 `--categories`（一个或多个大小写敏感相对目录路径或唯一叶名；默认递归全量，优先 `_All`）、`--geosite-tool`、`--geoip-tool`、`--geo-reader`、`--output`，以及成对可选的 `--geosite-url`、`--geoip-url`。工具路径在使用前校验可执行；URL 只接受合法 HTTP/HTTPS 地址且不得包含用户密码，HTTP 可作为受控本地测试候选，其平台可用性由实机确认。失败打印可定位的来源与原因并退出非零，成功打印产物路径和已转换/跳过摘要。

函数以简单解析、分类转换、工具调用和配置生成为边界即可，不要求额外接口层或类。测试需要能直接调用解析与配置生成逻辑，不依赖网络或安装 Go 工具；真实编译与回读单独执行。

外部工具来源和用法依据：`https://github.com/v2fly/domain-list-community` 的自定义 `--datapath`、`full:`/`domain:`/`keyword:` 文本格式，以及 `https://github.com/Loyalsoldier/geoip` 的本地 text 输入与 V2Ray GeoIP 输出。具体工具版本与回读参数已在第一里程碑实测固定，见“成果与复盘”和 README。

修订说明：2026-09-17 创建首版，汇总已确认的用户范围；将工具调用/回读验证列为前置里程碑，并将本地成功与 Happ 实机兼容分开验收。

修订说明：2026-09-17 完成本地实施；经主 agent 批准固定无冗余剪枝的上游版本、新增最小只读 helper/--geo-reader 和整体双库非空边界。补充实际编译、回读、配置、重复构建证据及 AdvertisingLite 头部统计差异；Happ 实机保持待验证。

修订说明：2026-09-17 按用户新请求将默认改为递归全量且优先 `_All`，覆盖旧主文件/三分类范围；经 supervisor 批准最小命名消歧与固定工具 mapped IPv6 限制逐行跳过，补充官方单 IP 语义、17 测试及真实全量/独立回读、覆盖清单与资源证据。
