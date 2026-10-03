---
name: openclash-router
description: 通过 SSH 操作 OpenWrt/iStoreOS 路由器上的 OpenClash —— 改配置、加节点、调分流规则、切换运行模式、配 DNS、排查代理不通、清理内存、管理订阅。只要用户提到软路由、路由器、旁路由、OpenClash、Clash、Mihomo、机场节点、订阅、分流、DNS 泄露、代理连不上，或让你看/改家里的网络设备配置，就应该使用这个技能——即使用户没有明说"OpenClash"或"路由器"。它负责环境准备（自动装依赖）、建立免密 SSH 连接、安全改配置与回滚。
---

# OpenClash 路由器操作

通过 SSH 管理装了 **OpenClash** 的 **OpenWrt / iStoreOS** 路由器。

---

## 0 · 三条底线（先记住这个）

1. **改的是用户的路由器，不是这个仓库。** 改错了用户全家断网，
   且 `git revert` 救不了路由器 —— 回滚只能靠路由器上的备份文件。
2. **没有用户的明确命令，不改任何东西。** 用户的澄清、补充、"可以改 false"
   都**不是执行授权**；只有「干 / 改吧 / 按这个来」才算。歧义就问，别猜。
3. **回复里永远不要出现密码。**

> 深层原因：本仓库只是**工具**，真正要改的是路由器上的运行状态。
> 仓库的 CI 全绿不代表路由器改对了；`git revert` 也回滚不了路由器。

---

## 1 · 标准流程（改配置就这么几步）

```bash
OC="python $SKILL/scripts/oc.py"     # $SKILL = 本技能目录

# ① 只读侦查（随时可做，不需授权）
$OC doctor          # 环境自检（首次会引导配置连接）
$OC probe           # 状态总览：系统/内存/模式/端口/配置/防火墙/日志

#    拿到现状后，给用户「改什么 / 改成什么 / 怎么回滚」的表格，等确认

# ② 改前检查 + 拉源文件（一定改源文件，不是运行配置 —— 见 §2 铁律 1）
$OC safety --config /etc/openclash/config/proxy.yaml   # 有备份? 目标对? 核心在跑?
$OC pull /etc/openclash/config/proxy.yaml ./work/proxy.yaml

# ③ 本地编辑（Python 精确匹配，保留缩进/注释；不要用 sed）

# ④ 部署前检查 + 内核校验（两个闸门，都要过）
#    为什么两个：实测 clash -t 只抓 YAML 语法错，**不查存在性/完整性**：
#      · 文件不存在  → 照样报 "test is successful"
#      · 50638 字节截断到 1000 字节 → 照样报 successful
#    所以先 deploy-check 自己查，再用 clash -t 补语法检查。
$OC push ./work/proxy.yaml /tmp/proxy.yaml     # push 会自动核字节数
$OC deploy-check --local ./work/proxy.yaml --remote /tmp/proxy.yaml
#    D1 远端存在非空 / D2 字节数一致 / D3 关键段落齐全 —— 全过才继续
$OC run "/etc/openclash/clash -t -d /etc/openclash -f /tmp/proxy.yaml"
#    “test is successful” 且退出码0 才继续；不过就查官方文档（§3）
#    注：这里验的是**待部署的新文件**（部署前闸门）。OpenClash 官方
#        文档里的同款命令验的是当前 config_path（诊断用），两者互补。

# ⑤ 备份 → 替换 → 重启
$OC run "cp -a /etc/openclash/config/proxy.yaml \
         /etc/openclash/config/proxy.yaml.bak-\$(date +%Y%m%d-%H%M%S)"
$OC push ./work/proxy.yaml /etc/openclash/config/proxy.yaml
$OC run "/etc/init.d/openclash restart"
#    restart 没有「前台」选项，它内部是同步+异步混合（实测 init 源码）：
#      同步完成：Step 1-3 —— 含 yml_change.sh 重新生成运行配置（返回时已完成）
#      后台进行：Step 4 注册核心（procd，不等进程）+ Step 6 等就绪/建防火墙（带 &）
#    ⇒ restart 返回时「配置已写到文件层面」，但「运行时未就绪」→ 必须自己轮询（⑥）

# ⑥ 二级闸门：等就绪 + 三查（restart 返回 ≠ 核心可用）
#    6a 等就绪：就绪判据 = 核心 API 的 /group 返回 200（与 init 脚本同标准）
$OC run 'SEC=$(uci get openclash.@openclash[0].dashboard_password)
         PORT=$(uci get openclash.@openclash[0].cn_port)
         for i in $(seq 1 30); do
           code=$(curl -m 5 -s -o /dev/null -w "%{http_code}" \
                  -H "Authorization: Bearer $SEC" \
                  http://127.0.0.1:$PORT/group)
           [ "$code" = "200" ] && echo "就绪（${i}s）" && break
           sleep 1
         done; [ "$code" = "200" ] || echo "⚠️ 30s 未就绪（HTTP $code）"'

#    6b 查错误日志（重启失败会在这暴露）
$OC run "tail -30 /tmp/openclash.log | grep -E 'level=(error|fatal)' || echo '无 error/fatal'"

#    6c 真实链路（最关键：核心活着 ≠ 流量能出去）
#        前提：router_self_proxy=1（路由器自身流量走代理）。若为 0，此测试只验直连。
$OC run "curl -s -o /dev/null -w '真实链路 HTTP %{http_code} 耗时 %{time_total}s\n' \
         --max-time 10 https://www.gstatic.com/generate_204"
#    6c 期望 204；返回 000/超时 = 代理不通（节点/订阅/规则问题）

# ⑦ 清理临时文件（/tmp 是内存盘，别堆垃圾）
$OC run "rm -f /tmp/proxy.yaml"

# ⑧ 汇报：改了什么 + 备份路径 + 回滚命令
```

**为什么这个顺序**：④ 在 ⑤ 前面 → 语法错不会导致断网；备份在替换前 → 有退路；
⑥ 单独一步 → **restart 返回 ≠ 核心就绪**（它只保证配置已重新生成，
就绪是后台在做的）——文件写对只是前提，运行时真就绪才算成。

**重载方式的选择**（改了什么决定用哪个 —— 依据 OpenClash 官方「热生效 vs 需重启」表）：

| 改了什么 | 用什么重载 | 会重新生成运行配置吗 | 延迟 |
|---------|-----------|------------------|------|
| 源配置 `config/<name>.yaml` | `/etc/init.d/openclash restart` | ✅ 是（跑 `yml_change.sh`） | ~3-5s |
| 端口 / TUN / DNS / 覆写 | 同上（需重启核心） | ✅ | ~3-5s |
| 防火墙规则 | `/etc/init.d/openclash reload` | ❌ 只重建防火墙链 | 即时 |
| **访问控制（黑白名单）** | **需 restart**（重建防火墙链）⚠️ | — | ~5s |
| 代理模式 / 日志级别 / Sniffer / 规则 | 内核 API `PATCH /configs` | ❌ 热改 | 即时 |
| 策略组选择 | 内核 API `PUT /configs` | ❌ 热改 | 即时 |

⚠️ **OpenClash 的 `reload` 只重建防火墙链，不重载配置文件。**
OpenWrt 官方对 `reload` 的通用语义是「重载配置（通常发 SIGHUP）」，
但 OpenClash 的实现是防火墙专用 —— 所以改了源配置**必须用 `restart`**，
否则改动进不去运行配置。

```
改了什么              → 重载方式
─────────────────────────────────────────
源配置 yaml           → restart（必须）
端口/TUN/DNS/覆写     → restart
访问控制黑白名单       → restart
防火墙规则            → reload（即时）
代理模式/日志/Sniffer → API PATCH /configs
策略组选择            → API PUT /configs
```

**push 是独立确认项**：用户说「改吧」只授权本地/设备改动；说「推」才 `git push`。

---

## 2 · 五条铁律

1. **改源文件，不改运行配置。**
   `/etc/openclash/config/<name>.yaml` 是源文件（人工维护、带注释）；
   `/etc/openclash/<name>.yaml` 每次启动由 Ruby 重新生成，改它等于没改。
   路径用 `uci get openclash.@openclash[0].config_path` 确认。

2. **改前备份，把回滚方式告诉用户。** 路由器没有 git ——
   `cp -a` 的备份是唯一退路，用户要能自己退回去。

3. **先校验再替换，改后用二级闸门确认就绪。** 校验有两道，缺一不可：
   `deploy-check`（存在/字节数/关键段落）+ `clash -t`（语法）。
   ⚠️ **`clash -t` 单独用不可信** —— 实测它对**不存在的文件**和**截断的文件**
   都报 `test is successful`（只抓 YAML 语法错）。不通过绝不覆盖；
   `restart` 会立即返回（内部是后台的），必须用 §1 ⑥ 等就绪
   （`/group` 返回 200）+ 查日志 + 真实链路测试才算成功。

4. **防失联。** 改防火墙/DNS/SSH 前想清楚「改坏了怎么连回来」：
   - 改 SSH/dropbear 最后做，别弄断当前会话
   - 重启用 `restart` 别用 `stop`
   - 改防火墙前确认还有一条不经代理的路径

5. **公开仓库，凭据零容忍。** 真实 IP/密码/token 一律占位值
   （`192.0.2.x`、`REPLACE_WITH_*`、`<你的密码>`）。

---

## 3 · 领域知识查官方，禁止凭记忆

配置字段编错会**直接把用户的网络搞挂**。凡涉及「某选项什么意思」「为什么这个
规则不生效」「这个报错啥原因」，**先查官方，不要凭记忆作答**。

**按问题层次选源**（越靠后越底层、越权威，也越难读）：

| 问题属哪个层 | 查哪里 | 为什么是这个 |
|------------|--------|------------|
| **① OpenClash 插件层**<br>UCI/LuCI 选项、防火墙链、覆写模块语法、订阅处理 | [OpenClash 官方知识库](https://github.com/vernesong/OpenClash/blob/master/.github/skills/openclash-user-guide/SKILL.md) | 它讲的是「插件怎么把 UI 选项变成 Mihomo 配置」 |
| **② Mihomo 配置层**<br>字段含义/取值、DNS 策略、分流规则、各代理协议参数 | [Mihomo Wiki](https://wiki.metacubex.one/config/) · [Meta-Docs 仓库](https://github.com/MetaCubeX/Meta-Docs/tree/main/docs/config) | 配置字段的**权威定义**（Meta-Docs 按 config/dns、config/proxies、config/rules… 分类） |
| **③ 内核实底层**<br>「为什么这个字段不生效」、行为细节、边界 | 看当前用的是哪个内核（见下方「先分内核」） | 文档没写清的，源码是唯一真相（见下方定位表） |
| **④ 已知问题/报错** | [OpenClash Issues](https://github.com/vernesong/OpenClash/issues)（插件侧）· [Mihomo Issues](https://github.com/MetaCubeX/mihomo/issues)（内核侧） | 先搜再问；优先看作者/维护者回复与高赞方案 |

> ⚠️ 先判断问题在哪一层 —— 把「插件层」的问题拿去查内核文档、
> 或把「内核行为」问题当成插件 bug，都会绕远路。

### ⚠️ 先分内核：Smart 内核 ≠ 上游内核

OpenClash 自带一个**改装过的 Mihomo 内核**（作者 vernesong），多了一个上游没有的
`smart` 策略组（LightGBM 模型预测节点质量）。**查文档前先确认用的是哪个**：

```bash
$OC run "uci get openclash.@openclash[0].core_type"   # Smart 或 Meta
$OC run "/etc/openclash/clash -v | head -1"           # 看版本串里有无 alpha-smart
```

用户机器上实测：`core_type=Smart`，版本串含 `alpha-smart`。

| | 上游内核 | Smart 内核 |
|---|---|---|
| 仓库 | [MetaCubeX/mihomo](https://github.com/MetaCubeX/mihomo/tree/Alpha) | [vernesong/mihomo](https://github.com/vernesong/mihomo/tree/Alpha)（**fork** 自上游，加 Smart） |
| 特性 | 官方全部功能 | 上游全部 + `smart` 策略组 + LightGBM 模型 |
| 发布 | Releases | [Releases: `Prerelease-Alpha`](https://github.com/vernesong/mihomo/releases)（`mihomo-<arch>-alpha-smart-<sha>.gz`）+ `LightGBM-Model` |
| 源码关键路径 | — | `component/smart/`（weight/store/lightgbm）· `adapter/outboundgroup/smart.go` |
| Issues | 有（活跃） | ❌ **无 Issues 通道**（`has_issues=false`）—— 别去那里提问 |

**所以遇到 smart 相关问题的查法**：

1. **配置层**：`type: smart` 的字段 —— 上游文档没有，只能看
   [`adapter/outboundgroup/smart.go`](https://github.com/vernesong/mihomo/tree/Alpha/adapter/outboundgroup) 与 [`component/smart/`](https://github.com/vernesong/mihomo/tree/Alpha/component/smart)
2. **下载/版本**：看 [Releases](https://github.com/vernesong/mihomo/releases)（只有 `Prerelease-Alpha` 一个 tag，滚动更新）
3. **LightGBM 模型**：独立 release `LightGBM-Model`（`Model.bin`）
4. **提问**：Smart 无 Issues ⇒ 去 [OpenClash Issues](https://github.com/vernesong/OpenClash/issues)（同一作者）
5. **共性行为**：smart 以外的内核行为，仍以上游文档/源码为准

### 怎么取用（可照抄）

```bash
# ① 插件层：整份抓下来 grep（比网页里翻快）
curl -sL -o /tmp/oc-guide.md \
  https://raw.githubusercontent.com/vernesong/OpenClash/master/.github/skills/openclash-user-guide/SKILL.md
grep -n "关键词" /tmp/oc-guide.md && sed -n '120,160p' /tmp/oc-guide.md

# ② 配置层：Meta-Docs 是纯 markdown，可直接抓单个字段页
curl -sL -o /tmp/md.md \
  https://raw.githubusercontent.com/MetaCubeX/Meta-Docs/main/docs/config/dns/index.md
grep -n "fake-ip\|nameserver-policy" /tmp/md.md

# ② 配置层：完整配置示例（不知道某段该怎么写时，看这个比看字段表快）
curl -sL -o /tmp/mihomo-config.yaml \
  https://raw.githubusercontent.com/MetaCubeX/mihomo/Alpha/docs/config.yaml

# ③ 内核层：在源码里定位实现（比读全仓快）
#    上游： https://github.com/search?q=repo%3AMetaCubeX%2Fmihomo+关键词&type=code
#    Smart：https://github.com/search?q=repo%3Avernesong%2Fmihomo+关键词&type=code
```

### ③ 内核实底层 · 关键词 → 源码位置

问题渗到「文档没说清、字段不生效」时，去源码找答案。
**先确认内核**（上方）—— Smart 问题去 `vernesong/mihomo`，其余去上游。
常见入口（两边目录结构同源）：

| 想查什么 | 去哪个目录 |
|---------|-----------|
| 配置解析/校验（字段为何报错） | `config/` |
| 规则引擎（DOMAIN/GEOIP/RULE-SET 如何匹配） | `rules/` · `adapter/` |
| DNS（fake-ip、nameserver-policy、fallback 行为） | `dns/` · `component/resolver/` |
| 入口/TUN/透明代理 | `listener/`（含 `sing_tun/`） |
| 代理协议实现（vless/hysteria/tuic…） | `adapter/outbound/` |
| **Smart 策略组 / LightGBM**（仅 Smart 内核） | `adapter/outboundgroup/smart.go` · `component/smart/` |
| 完整配置示例 | [`docs/config.yaml`](https://github.com/MetaCubeX/mihomo/blob/Alpha/docs/config.yaml) |

> 注：`MetaCubeX/mihomo` 的仓库 description 字面显示成别的东西（实测是无关内容），
> **但仓库本体就是内核**（分支用 `Alpha`/`Meta`，主题是 Go）。别被 description 劝退。

**查不到就说查不到**，把链接给用户自己看 —— 禁止编造字段名、选项值、错误解释。

---

## 4 · 环境坑（iStoreOS 实测，动手前扫一眼）

### `apk` 可能永久卡死

某些包的卸载钩子会等不存在的硬件（如 `adb-enablemodem` 跑
`adb wait-for-device`）→ `apk del` 挂起并**阻塞所有 apk 操作**。实测卡 16 小时。

卸载前先看包带不带 init 脚本：

```bash
$OC run "apk info -L <包名> | grep -E '/etc/init.d|pre-deinstall'"
```

带了就先中和 `stop()` 再卸（写个空操作脚本覆盖它）。
卡了就 `kill -9` 掉 apk 及子进程，再 `apk list -I` 验证数据库没坏。
注意 iStoreOS **没有 `timeout` 命令**，卸载放后台跑。

### iStoreOS 组件有隐藏依赖，别乱关

| 组件 | 实际作用 | 关了会怎样 |
|------|---------|-----------|
| `quickstart` | **可视化首页（QuickStart 仪表盘）** | 首页消失 |
| `linkease` | 易有云 + **iStore 应用商店后端** | 商店可能不可用 |
| `startdhns` | 内网穿透 | 穿透失效（先问用户） |
| `wpad`/`hostapd` | WiFi | 无无线硬件时才可关 |

**禁服务要连带处理 hotplug**（否则插拔 U 盘/网络变动会拉起来）：

```bash
$OC run "mv /etc/hotplug.d/block/09-quickstart /etc/hotplug.d/block/09-quickstart.disabled"
```

### 旁路由的 WAN 告警是正常的

`network.wan.disabled=1` 时启动日志必有
`Can't Settting Only Intranet Allowed Function ... Get IPv4 WAN Interfaces error`
—— **不是故障**，别去修。

### 统计的坑

- `lsmod` 的 `nf_tables` 大小会溢出成天文数字，算模块占用要剔除异常值
- BusyBox `ps` 没有 RSS 字段，读 `/proc/*/status` 的 `VmRSS`
- BusyBox 缺 `diff`/`comm`/`timeout`/`cat -A`，复杂文本处理放本地做

### 别碰这些

`r8152-firmware` / `kmod-usb-net-rtl8152`（USB 网卡驱动）·
`dnsmasq-full`、`kmod-nft-tproxy`、`kmod-tun`、`ruby*`（OpenClash 依赖）·
`/etc/dropbear/authorized_keys`（登录凭据）

判断网卡驱动：`ls -l /sys/class/net/eth1/device/driver`

---

## 5 · 常见任务要点

**加节点**：命名用 `emoji + 空格 + 名称`（如 `🇺🇸 RN-01`）；
重命名前先 `$OC run "grep -n '旧名' <源文件>"` 找全所有引用
（定义 + 各分组的 `proxies:` 列表）同步改；用 `filter:` 正则的分组会自动纳入。

**vless 链接转 YAML**：`security=reality` → `reality-opts{public-key,short-id}`；
`sni=` → `servername`；`fp=` → `client-fingerprint`；`type=tcp` → `network: tcp`。

**排查走错代理**：看日志差分，比读配置快 ——
```bash
BEFORE=$($OC run "wc -l < /tmp/openclash.log" | tail -1 | tr -d ' ')
$OC run "curl -s -o /dev/null --max-time 8 https://目标域名/"
$OC run "tail -n +$BEFORE /tmp/openclash.log | grep -i '目标域名'"
```
Fake-IP 模式下 `dig` 无意义（返回假 IP），要看规则命中。

**清理内存**：先出表格（服务/占用/作用/风险）给用户选，别自作主张卸。
`clash` 占 200MB 属正常，别动。

**Smart 策略组相关**（`type: smart` / LightGBM 模型 / `uselightgbm`）：
这是 OpenClash 作者自制的内核特性，**上游文档里没有** ——
字段含义与行为去 [vernesong/mihomo](https://github.com/vernesong/mihomo/tree/Alpha)
（`adapter/outboundgroup/smart.go` · `component/smart/`），
版本/模型去 [Releases](https://github.com/vernesong/mihomo/releases)。
注意：**该仓无 Issues 通道**，提问去 OpenClash Issues（同一作者）。

---

## 6 · 工具箱

所有操作通过 `scripts/oc.py`（黑盒调用，用 `--help` 看用法，**别读源码** ——
约 1020 行会挤占上下文）。

```bash
python <技能目录>/scripts/oc.py where      # 打印技能/脚本/配置绝对路径
```

| 命令 | 用途 |
|------|------|
| `doctor` | 环境自检。**每次会话第一条命令** |
| `setup` | 配置连接（生成密钥、部署公钥、验证） |
| `probe` | OpenClash 状态总览（只读） |
| `safety --config <路径>` | 改前检查：有备份 / 目标是生效配置 / 核心在跑 |
| `deploy-check --local <本地> --remote <远端>` | 部署前完整性检查（`clash -t` 的前置） |
| `run "<cmd>"` | 在路由器执行命令（多个词自动拼一条；多命令用 `;`） |
| `push` / `pull` | 上传 / 下载文件 |
| `where` | 打印技能/脚本/配置绝对路径 |
| `show-config` / `forget` | 查看 / 清除连接配置 |

依赖缺失会自动 `pip install`（依次尝试普通 / `--user` / `--break-system-packages`）。

---

## 7 · 配置连接（仅首次）

`doctor` 报「尚未配置」时，问用户要：**路由器 IP**、**SSH 用户名**（通常 `root`）、**SSH 密码**。

```bash
python "$SKILL/scripts/oc.py" setup --host <IP> --user root --password '<密码>'
```

脚本自动：密码连一次 → 生成 ed25519 密钥 → 部署公钥到
`/etc/dropbear/authorized_keys`（权限 600）→ **用密钥重新验证** → 通过才保存。
之后永久免密。更安全的做法：让用户自己跑无参数的 `setup`（交互式）。

排障：连不上 → `ping <IP>`；认证失败 → 密钥丢了，重跑 `setup`；改过端口 → `--port`。

---

## 8 · 退出码（脚本可依赖）

| 码 | 含义 |
|----|------|
| `0` | 成功 |
| `1` / 远端原值 | `run` 透传的远端失败码 |
| `2` | 参数/环境错 |
| `3` | 缺依赖且自动装失败 |
| `4` | 尚未配置 → 跑 `setup` |
| `5` | `OC_CONFIG` 指定的文件不存在 |
| `6` | 认证失败 → 重跑 `setup` |
| `7` | 连不上 → `ping` |
| `8` | `setup` 密钥验证失败（未保存配置） |
| `9` / `10` | push / pull 的文件不存在 |
| `11` | push 后字节数不符（传输被截断） |
| `12` | push 的远端目录不存在 |
| `13` | push 上传本身失败 |
| `124` | 超时 → 加 `--timeout <秒>` |
| `130` | 被 Ctrl+C 中断 |

---

## 9 · 凭据与仓库

```
~/.config/openclash-mgmt/
├── config.json      (600)  连接信息，不含密码
├── id_ed25519       (600)  私钥
└── id_ed25519.pub   (644)  公钥（已部署到路由器）
```

- 换位置：`OC_CONFIG=...`（显式指定后只认它，不存在报 5）
- 清除：`python "$SKILL/scripts/oc.py" forget -y`
- 本仓库是公开的，真实凭据不进仓库（`OC_CONFIG` 默认在仓库外）
- 修改本仓库文件后：跑 `python tests/check_secrets.py` 再提交；
  **`git push` 需用户单独确认**
