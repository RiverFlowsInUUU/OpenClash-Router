---
name: openclash-router
description: 通过 SSH 操作 OpenWrt/iStoreOS 路由器上的 OpenClash —— 改配置、加节点、调分流规则、切换运行模式、配 DNS、排查代理不通、清理内存、管理订阅。只要用户提到软路由、路由器、旁路由、OpenClash、Clash、Mihomo、机场节点、订阅、分流、DNS 泄露、代理连不上，或让你看/改家里的网络设备配置，就应该使用这个技能——即使用户没有明说"OpenClash"或"路由器"。它负责环境准备（自动装依赖）、建立免密 SSH 连接、安全改配置的规程，以及防失联与回滚。
---

# OpenClash 路由器操作

通过 SSH 管理装了 **OpenClash** 的 **OpenWrt / iStoreOS** 路由器。

本仓是 **AI 驱动的操作技能仓**：全部操作文档整合在本 skill 与 `reference/` 里，
没有面向人类的 docs。AI 按用户需求操作**用户的设备**，判据与纪律守底线。

---

## 0 · 先说最重要的一件事：改的是**设备**，不是这个仓库

本技能和「配置模板仓」（改了仓库就等于改了成品）**根本不同**：

```
第一层  本仓库（工具 + 知识 + 闸门）    ← 闸门守这里，git 管这里
   │
   │ oc.py 通过 SSH
   ▼
第二层  用户的路由器（真正要改的目标）   ← ⚠️ 闸门守不到，git 管不到
```

**由此推出的三条铁律**：

1. **用户说「改配置」几乎总是指第二层**（他的路由器），不是改本仓库。
2. **闸门全绿 ≠ 用户的路由器改对了。** 它只证明"工具没问题"。
3. **`git revert` 救不了路由器。** 回滚只能靠路由器上的备份文件。

> 完整的差异分析与推论见 [`reference/two-layers.md`](reference/two-layers.md) ——
> **每个任务开始前都应该先读它**，尤其当你同时要改仓库和设备时。

---

## 1 · 阅读协议（按序执行）

1. **先读本文件**，用 §0 判断这次改动落在哪一层。
2. 需要细节时按 §5 索引跳转 `reference/`；**没命中索引就不读**。
3. **权威归属**（重复时以专项文件为准）：
   - 两层关系 / 回滚 / 防失联 → `two-layers.md`
   - 环境坑 → `pitfalls.md`
   - 任务配方 → `tasks.md`
   - 闸门与退出码 → `gates.md`
   - 已论定的事 → `boundaries.md`
   - **OpenClash 领域知识 → 官方文档（§2），不在仓内**
4. 行文原则：**判据先行、表格优先**；凡标「实测」的皆为经验值教训。

---

## 2 · 领域知识查官方，禁止凭记忆

配置字段和选项值编错会**直接把用户的网络搞挂**。凡涉及「某选项什么意思」
「为什么这个规则不生效」「这个报错啥原因」，**先去查官方知识库**：

```bash
# 官方知识库（随时抓，比任何本地副本新）
curl -sL -o /tmp/oc-guide.md \
  https://raw.githubusercontent.com/vernesong/OpenClash/master/.github/skills/openclash-user-guide/SKILL.md

grep -n "关键词" /tmp/oc-guide.md          # 先定位
sed -n '120,160p' /tmp/oc-guide.md        # 再读上下文
```

**必须去查**：UCI/LuCI 选项含义 · 防火墙链结构 · 覆写模块语法 ·
DNS 配置（nameserver / fallback / nameserver-policy / fake-ip-filter）·
分流规则与 provider · 报错信息含义 · 订阅处理 · 任何「为什么这个选项不生效」。

其他权威来源：Mihomo 字段 → https://wiki.metacubex.one/config/ ；
报错先搜 [OpenClash Issues](https://github.com/vernesong/OpenClash/issues) 与
[Mihomo Issues](https://github.com/MetaCubeX/mihomo/issues)。
**查不到就说查不到** —— 禁止编造字段名、选项值、错误解释。

---

## 3 · 动线

### 动线 A · 改设备（最常见的任务）

```
① 只读侦查 → ② 拉源文件 → ③ 本地改 → ④ 内核校验
→ ⑤ 备份 → ⑥ 替换 → ⑦ 重启 → ⑧ 验证生效 → ⑨ 汇报(含回滚)
```

```bash
OC="python $SKILL/scripts/oc.py"

# ① 侦查（随时可做，只读）
$OC doctor && $OC probe
#    拿到现状后，给用户「改什么/改成什么/怎么回滚」的表格，等他确认

# ② 拉源文件（一定要改源文件，不是运行配置 —— 铁律 1）
$OC pull /etc/openclash/config/proxy.yaml ./work/proxy.yaml

# ③ 本地编辑（Python 精确匹配，保留缩进/注释；不要用 sed）

# ④ 设备安全检查 + 内核校验（不影响线上就能发现语法错）
$OC safety --config /etc/openclash/config/proxy.yaml   # D1 备份/D2 目标对不对/D3 核心
$OC push ./work/proxy.yaml /tmp/proxy.yaml
$OC run "/etc/openclash/clash -t -d /etc/openclash -f /tmp/proxy.yaml"
#    看到 "test is successful" 才继续

# ⑤ 备份（git 救不了路由器，这是唯一回滚依据）
$OC run "cp -a /etc/openclash/config/proxy.yaml \
         /etc/openclash/config/proxy.yaml.bak-\$(date +%Y%m%d-%H%M%S)"

# ⑥ 替换  ⑦ 重启
$OC push ./work/proxy.yaml /etc/openclash/config/proxy.yaml
$OC run "/etc/init.d/openclash restart"

# ⑧ 验证生效（文件改了 ≠ 生效了）
$OC run 'SEC=$(uci get openclash.@openclash[0].dashboard_password)
         PORT=$(uci get openclash.@openclash[0].cn_port)
         curl -s -H "Authorization: Bearer $SEC" http://127.0.0.1:$PORT/proxies | head -c 500'

# ⑨ 汇报：改了什么 + 备份路径 + 回滚命令
```

**为什么这个顺序**：④ 在 ⑥ 前 → 语法错不会导致断网；⑤ 在 ⑥ 前 → 有退路；
⑧ 单独一步 → 因为**文件写对只是前提，运行时真变了才算成**。

### 动线 B · 改仓库（修工具 / 沉淀知识）

```
① 明确改什么、为什么 → ② 改文件 → ③ python tests/verify_all.py
→ ④ 本地 commit → ⑤ 停在推送前（push 是独立确认项）
```

**闸门只在这条动线上有意义。**

### 只读操作（不需授权，随时可做）

`probe`、`run "cat ..."`、`run "grep ..."`、`doctor`、
`safety`（只读检查，不修改）—— 这些不改任何东西。

---

## 4 · 纪律

### 4.1 执行授权

> 🚨 **铁律**：
> 1. **没有用户的命令，不改任何文件、不改设备。** 用户对方案的**澄清、补充、范围确认**
>    （「我说的是这两项」「可以改」「没说后头的」）**一概不是执行授权**，
>    只说明讨论还在继续。
> 2. **没有用户的命令，不 push。** 改和推是两道独立的门。
> 3. 只有**命令词**（「干 / 改吧 / 动手 / 按这个来」）才开启动线。
>    语义有歧义时**退回只读并问一句** —— 猜错的代价远大于多问一句。

### 4.2 五条操作铁律

1. **改源文件，不改运行配置。**
   `/etc/openclash/config/<name>.yaml` 是源文件（人工维护、带注释）；
   `/etc/openclash/<name>.yaml` 每次启动由 Ruby 重新生成，改它等于没改。
   路径用 `uci get openclash.@openclash[0].config_path` 确认。

2. **改前备份，并把回滚方式告诉用户。** git 救不了路由器 ——
   备份文件是唯一退路。用户要能自己退回去，不必依赖你。

3. **先校验再替换。** `clash -t` 不通过绝不覆盖。直接覆盖再重启的话，
   核心起不来用户就断网了。

4. **回显零密码。** 回复里**永远不要出现密码**。需要时让用户交互式跑 `setup`
   （`getpass` 读，不进对话记录）。

5. **凭据不进仓库。** 这是公开仓库。真实 IP / 密码 / token 一律占位值
   （`192.0.2.x`、`REPLACE_WITH_*`、`<你的密码>`）。`check_secrets.py` 会拦。

### 4.3 防失联（我们独有的纪律）

改**可能影响远程访问**的东西之前，先想清楚「改坏了怎么救回来」：

| 风险操作 | 措施 |
|---------|------|
| 改防火墙 / 访问控制 | 先确认还有一条不经代理的路径（直连 LAN） |
| 改 DNS 劫持 | 想好「DNS 挂了怎么用 IP 连回来」 |
| 改 SSH / dropbear | **最后做**，且别弄断当前会话 |
| 重启核心 | 用 `restart` 而非 `stop`（避免停在那起不来） |

### 4.4 操作不幂等

重试前先想「重跑一次会怎样」：

| 操作 | 幂等 | 注意 |
|------|------|------|
| `pull` / `push` / `probe` / `run "cat"` | ✅ | 安全重试 |
| `restart` | ⚠️ | 每次断流数秒 |
| 清缓存 / 断连接 | ⚠️ | 影响正在用的连接 |
| `kill` 进程 / `apk del` | ❌ | 重跑可能杀错 / 卡死（见 `pitfalls.md`） |

---

## 5 · 按需读取

| 文件 | 何时读 |
|:-----|:-------|
| [`reference/two-layers.md`](reference/two-layers.md) | **每个任务开始前** —— 两层关系、四条动线差异、防失联、不幂等操作。同时改仓库+设备时**必读** |
| [`reference/tasks.md`](reference/tasks.md) | 做具体任务时（加节点 / 排查走错代理 / 代理不通 / 清理内存）—— 逐步配方 |
| [`reference/pitfalls.md`](reference/pitfalls.md) | 改配置 / 卸载软件包 / 开关服务**之前** —— 环境坑（apk 死锁、iStoreOS 组件隐藏依赖、hotplug 复活、旁路由告警…） |
| [`reference/gates.md`](reference/gates.md) | 跑闸门、或要改判据时 —— 四态退出码协议、各闸门判据。**注意它只守仓库** |
| [`reference/boundaries.md`](reference/boundaries.md) | 想改某处却被判「不做 / 不适用」，或要确认算不算例外时 —— 已论定清单（每行带重议条件） |

---

## 6 · 工具箱

所有操作通过技能自带的脚本：`scripts/oc.py`（在**本技能目录**下）。
下文用 `$SKILL` 指代技能目录；不确定时让脚本自己报：

```bash
python <技能目录>/scripts/oc.py where      # 打印技能/脚本/配置的绝对路径
```

> 💡 **把脚本当黑盒用，不要读它的源码。**
> 它有约 900 行，读进来会挤占上下文，而它本来就是设计成直接调用的。
> 想看用法就 `--help`。

| 命令 | 用途 |
|------|------|
| `doctor` | 环境自检。**每次会话第一条命令** |
| `bootstrap` | 显式安装本地依赖（一般不用，缺依赖会自动装） |
| `where` | 打印技能/脚本/配置的绝对路径 |
| `setup` | 配置连接（生成密钥、部署公钥、验证） |
| `probe` | OpenClash 状态总览（只读，排查从这开始） |
| `run "<cmd>"` | 在路由器执行命令（多个词自动拼一条；多命令用 `;`） |
| `safety --config <路径>` | **设备侧安全检查**：备份存在 / 目标是生效配置 / 核心在跑 |
| `push` / `pull` | 上传 / 下载文件 |
| `show-config` / `forget` | 查看 / 清除连接配置 |

依赖（`paramiko`、`cryptography`）缺失时**自动 pip install**，
依次尝试普通 / `--user` / `--break-system-packages`。装不上才报错。

---

## 7 · 上手：配置连接（仅首次）

`doctor` 报「尚未配置」时，问用户要：**路由器 IP**、**SSH 用户名**（通常 `root`）、**SSH 密码**。

```bash
python "$SKILL/scripts/oc.py" setup --host <IP> --user root --password '<密码>'
```

脚本自动：密码连一次探路 → 生成 ed25519 密钥 → 部署公钥到
`/etc/dropbear/authorized_keys`（权限 600，不对 dropbear 会拒绝）→
**用密钥重新验证** → 通过才保存。之后永久免密。

**更安全的做法**：让用户自己跑无参数的 `setup`（交互式，密码经 `getpass`）。

其他情形：已有私钥 → `setup --key <路径>`；不想用密钥 → `setup --password 'xxx' --no-key`。

### 连接排障

```
连不上？
├─ exit 7 (连不上)     → ping <IP> 确认在线、IP 未变
├─ exit 6 (认证失败)   → ls ~/.config/openclash-mgmt/id_ed25519 还在吗？
│                         密钥丢了 / 固件升级重置了 → 重跑 setup
└─ 改过 SSH 端口       → setup --port <端口>
```

---

## 8 · 退出码协议

脚本/CI 依赖退出码判断成败。**改任何脚本的退出码前先读 `gates.md`**。

| 码 | 含义 | 怎么办 |
|----|------|--------|
| `0` | 成功 | — |
| `1` | 判负（闸门不过，或 `run` 透传的远端失败码） | 看输出定位 |
| `2` | 环境/参数不达标 | 先修环境 |
| `3` | SKIP（未验证） | **未验证 ≠ 通过**，需明示 |
| `4` | 尚未配置 | 跑 `setup` |
| `5` | `OC_CONFIG` 指定的文件不存在 | 检查环境变量 |
| `6` | 认证失败 | 重跑 `setup` |
| `7` | 连不上 | `ping` 确认 |
| `9` / `10` | push / pull 的文件不存在 | 确认路径 |
| `124` | 命令超时 | 加 `--timeout <秒>` |

---

## 9 · 凭据位置

```
~/.config/openclash-mgmt/
├── config.json      (600)  连接信息，不含密码
├── id_ed25519       (600)  私钥
└── id_ed25519.pub   (644)  公钥（已部署到路由器）
```

- 换位置：`OC_CONFIG=/path/to/config.json`（**显式指定后只认它**，不存在则报 5）
- 清除：`python "$SKILL/scripts/oc.py" forget -y`
- 密钥失效（固件升级常重置 dropbear）→ 重跑 `setup`

**回复里永远不要出现密码。**

---

## 10 · 一句话记住

> **闸门守仓库，校验守配置，验证守效果，备份守退路。**
> 四件事，四个不同的东西，缺一不可。
