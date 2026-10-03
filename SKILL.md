---
name: openclash-router
description: 通过 SSH 操作 OpenWrt/iStoreOS 路由器上的 OpenClash —— 改配置、加节点、调分流规则、切换运行模式、配 DNS、排查代理不通、清理内存、管理订阅。只要用户提到软路由、路由器、旁路由、OpenClash、Clash、Mihomo、机场节点、订阅、分流、DNS 泄露、代理连不上，或让你看/改家里的网络设备配置，就应该使用这个技能——即使用户没有明说"OpenClash"或"路由器"。它负责环境准备（自动装依赖）、建立免密 SSH 连接、以及安全改配置的规程。
---

# OpenClash 路由器操作

通过 SSH 管理装了 **OpenClash** 的 **OpenWrt / iStoreOS** 路由器。

本仓库是 **AI 驱动的操作技能仓**：全部操作文档整合在本 skill 与 `reference/` 里，
没有面向人类的 docs。AI 按用户需求改配置，**闸门守底线**。

---

## 阅读协议（按序执行）

1. **先读本文件**，按「动线」判断当前该做什么，**不要跳步**。
2. 需要某个主题的细节时，按 §4 索引表的「何时读」跳转 `reference/`；**没命中索引就不读**。
3. **权威归属**（重复时以专项文件为准）：领域知识 = 官方文档（§1）·
   操作流程与铁律 = 本文件 · 环境坑 = `reference/pitfalls.md` · 闸门判据 = `reference/gates.md`。
4. 行文原则：**判据先行、表格优先**；凡标「实测」的皆为经验值教训。

---

## 0 · 边界：这个技能管什么

| 本技能管（操作流程） | 交给官方文档（领域知识） |
|---------------------|------------------------|
| 装依赖、配 SSH 免密连接 | 某个 UCI 选项是什么意思 |
| **安全修改配置的规程**（备份/校验/回滚） | 防火墙链怎么建、覆写模块怎么写 |
| 环境层面的坑（iStoreOS 专有） | Mihomo 各协议参数、错误码含义 |
| 闸门与退出码协议 | OpenClash 自身的行为 |

**不要在本技能里找 OpenClash 功能知识** —— 见 §1。

---

## 1 · 第一原则：领域知识查官方，不许凭记忆

配置字段和选项值编错会**直接把用户的网络搞挂**。所以凡涉及「某选项什么意思」
「为什么这个规则不生效」「这个报错啥原因」，**先去查官方知识库**：

```bash
# 官方知识库（随时抓，比任何本地副本新）
curl -sL -o /tmp/oc-guide.md \
  https://raw.githubusercontent.com/vernesong/OpenClash/master/.github/skills/openclash-user-guide/SKILL.md

grep -n "关键词" /tmp/oc-guide.md          # 先定位
sed -n '120,160p' /tmp/oc-guide.md        # 再读上下文
```

**必须去查的场合**：UCI/LuCI 选项含义 · 防火墙链结构 · 覆写模块语法 ·
DNS 配置（nameserver / fallback / nameserver-policy / fake-ip-filter）·
分流规则与 provider · 报错信息含义 · 订阅处理 · 任何「为什么这个选项不生效」。

官方文档覆盖：依赖清单与故障排查 · 系统架构与启动流程 · 防火墙与 DNS 规则详解 ·
**日志与错误信息速查（16 大类）** · 各页面选项详解 · 诊断命令与 CLI 参考 · 覆写模块详解。

其他权威来源：Mihomo 字段 → https://wiki.metacubex.one/config/ ；
报错先搜 [OpenClash Issues](https://github.com/vernesong/OpenClash/issues) 与
[Mihomo Issues](https://github.com/MetaCubeX/mihomo/issues)。
**查不到就说查不到**，给链接让用户自己看 —— **禁止编造字段名、选项值、错误解释**。

---

## 2 · 动线（AI 改配置的标准流程）

```
① 只读侦查  → 列出现状与可改项，等用户确认
② 改配置    → 本地编辑 → 上传临时位置 → 内核校验
③ 落盘      → 备份 → 替换 → 重启 → 验证
④ 收尾闸门  → python tests/verify_all.py
⑤ 停在推送前 → git push 是独立确认项
```

> 🚨 **执行授权铁律**
> 1. **没有用户的命令，不改任何文件。** 用户对方案的**澄清、补充、范围确认**
>    （「我说的是这两项」「可以改」「没说后头的」）**一概不是执行授权**，
>    只说明讨论还在继续。
> 2. **没有用户的命令，不 push。** 改和推是两道独立的门，各要一次明确指令。
> 3. 只有**命令词**（「干 / 改吧 / 动手 / 按这个来」）才开启②。
>    语义有歧义时，**退回只读并问一句** —— 猜错方向的代价远大于多问一句。

**每一步的细节**：

### ① 只读侦查（随时可做，不需要授权）

```bash
OC="python $SKILL/scripts/oc.py"
$OC doctor          # 环境是否就绪（首次还会引导配置）
$OC probe           # 状态总览：系统/内存/模式/端口/配置/覆写/防火墙/日志
```

拿到现状后，**给用户一份「改什么 / 改成什么 / 怎么回滚」的表格，然后等**。

### ② 改配置

```bash
# 1) 拿到源文件（一定改源文件，不是运行配置 —— 见 §3 铁律 1）
$OC pull /etc/openclash/config/proxy.yaml ./work/proxy.yaml

# 2) 本地编辑（Python 精确匹配，保留缩进/注释风格；不要用 sed）

# 3) 上传到临时位置，先用内核校验（不影响线上）
$OC push ./work/proxy.yaml /tmp/proxy.yaml
$OC run "/etc/openclash/clash -t -d /etc/openclash -f /tmp/proxy.yaml"
```

看到 `configuration file ... test is successful` 才能往下。

### ③ 落盘

```bash
# 备份（把路径告诉用户，并给回滚命令）
$OC run "cp -a <源文件> <源文件>.bak-\$(date +%Y%m%d-%H%M%S)"
$OC push ./work/proxy.yaml <源文件>
$OC run "/etc/init.d/openclash restart"
# 验证：改动真的生效了吗（端口从配置读，别写死）
$OC run 'SEC=$(uci get openclash.@openclash[0].dashboard_password)
         PORT=$(uci get openclash.@openclash[0].cn_port)
         curl -s -H "Authorization: Bearer $SEC" http://127.0.0.1:$PORT/proxies | head -c 500'
```

### ④ 收尾闸门（改完必跑）

```bash
python "$SKILL/tests/verify_all.py"
```

全绿才算完。红的先修 —— 尤其**凭据扫描**是红线（这是公开仓库）。

### ⑤ 推送

**`git push` 永远是独立确认项。** 用户说「改吧 / 按这个来」只授权本地改动；
要用户明确说「推」才 push。

---

## 3 · 六条铁律

1. **改源文件，不改运行配置。**
   `/etc/openclash/config/<name>.yaml` 是源文件（人工维护、带注释）；
   `/etc/openclash/<name>.yaml` 每次启动由 Ruby 重新生成，改它等于没改。
   路径用 `uci get openclash.@openclash[0].config_path` 确认。

2. **改前备份，改后验证。** 备份路径必须告诉用户，并给回滚命令 ——
   这样他随时能自己退回去，不必依赖你。

3. **先校验再替换。** 用 `clash -t` 在临时位置验证，不通过绝不覆盖。
   直接覆盖再重启的话，核心起不来用户就断网了。

4. **回显零密码。** 回复里**永远不要出现密码**。需要密码时让用户交互式跑
   `setup`（用 `getpass` 读，不进对话记录）。

5. **凭据不进仓库。** 这是公开仓库。真实 IP / 密码 / token 一律用占位值
   （`192.0.2.x`、`REPLACE_WITH_*`、`<你的密码>`）。闸门 `check_secrets.py` 会拦。

6. **只连接用户授权的设备。** 没有明确指令，不碰任何网络设备。
   验证配置优先用本地脚本。

---

## 4 · 按需读取

| 文件 | 何时读 |
|:-----|:-------|
| [`reference/pitfalls.md`](reference/pitfalls.md) | **改配置 / 卸载软件包 / 开关服务之前** —— 环境坑全文（apk 死锁、iStoreOS 组件依赖、hotplug 复活、旁路由告警等） |
| [`reference/gates.md`](reference/gates.md) | 跑闸门、或要改闸门判据时 —— 四态退出码协议、各闸门判据说明 |
| [`reference/tasks.md`](reference/tasks.md) | 做具体任务时（加节点 / 排查走错代理 / 代理不通 / 清理内存）—— 逐步配方 |
| [`reference/boundaries.md`](reference/boundaries.md) | 想改某处却被判「不做 / 不适用」、或要确认某处算不算例外时 —— **例外清单 + 已论定清单**（每行带重议条件，防已定裁定被当新缺陷重报） |
| `SKILL.md` §1 的官方链接 | OpenClash 领域知识 —— **不读本地副本，读官方** |

---

## 5 · 工具箱

所有操作通过技能自带的脚本：`scripts/oc.py`（在**本技能目录**下）。

下文用 `$SKILL` 指代技能目录。你的 agent 加载技能时通常会告知其绝对路径；
不确定时让脚本自己报：

```bash
python <技能目录>/scripts/oc.py where      # 打印技能/脚本/配置的绝对路径
```

> 💡 **把脚本当黑盒用，不要读它的源码。**
> 它有约 800 行，读进来会挤占上下文，而它本来就是设计成直接调用的。
> 想看用法就 `--help`：
> ```bash
> python "$SKILL/scripts/oc.py" --help
> python "$SKILL/scripts/oc.py" setup --help
> ```

| 命令 | 用途 |
|------|------|
| `doctor` | 环境自检。**每次会话第一条命令**，会告诉你缺什么 |
| `bootstrap` | 显式安装本地依赖（一般不用，缺依赖会自动装） |
| `where` | 打印技能/脚本/配置的绝对路径 |
| `setup` | 配置连接（生成密钥、部署公钥、验证） |
| `probe` | OpenClash 状态总览（只读，排查从这开始） |
| `run "<cmd>"` | 在路由器执行命令（多个词自动拼一条；多命令用 `;`） |
| `push` / `pull` | 上传 / 下载文件 |
| `show-config` / `forget` | 查看 / 清除连接配置 |

依赖（`paramiko`、`cryptography`）缺失时脚本会**自动 pip install**，
依次尝试普通 / `--user` / `--break-system-packages`。装不上才报错并给命令。
所以通常你不需要为环境操心。

---

## 6 · 上手：配置连接（仅首次）

`doctor` 报「尚未配置」时，问用户要三样：**路由器 IP**、**SSH 用户名**（OpenWrt 通常 `root`）、**SSH 密码**。

```bash
python "$SKILL/scripts/oc.py" setup --host <IP> --user root --password '<密码>'
```

脚本自动：密码连一次探路 → 生成 ed25519 密钥 → 部署公钥到
`/etc/dropbear/authorized_keys`（权限 600，不对 dropbear 会拒绝）→
**用密钥重新验证** → 通过才保存配置。之后永久免密。

**更安全的做法**：让用户自己跑无参数的 `setup`（交互式，密码经 `getpass`，不进对话）。

其他情形：已有私钥 → `setup --key ~/.ssh/id_ed25519`；
不想用密钥 → `setup --password 'xxx' --no-key`（明文存密码，不推荐）。

### 连接排障

```
连不上？
├─ exit 7 (连不上)      → ping <IP> 确认在线、IP 未变
├─ exit 6 (认证失败)    → ls ~/.config/openclash-mgmt/id_ed25519 还在吗？
│                          密钥丢了 / 固件升级重置了 → 重跑 setup
└─ 用户改过 SSH 端口    → setup --port <端口>
```

---

## 7 · 退出码是协议（跨脚本统一）

脚本/CI 依赖退出码判断成败。**新增或修改任何脚本的退出码前，先读 `reference/gates.md`**。

| 码 | 含义 | 怎么办 |
|----|------|--------|
| `0` | 成功 | — |
| `1` | 判负（闸门不过，或 `run` 透传的远端失败码） | 看输出定位 |
| `2` | 环境/参数不达标 | 先修环境（缺依赖、参数错） |
| `3` | SKIP（未验证） | **未验证 ≠ 通过**，需明示 |
| `4` | 尚未配置 | 跑 `setup` |
| `5` | `OC_CONFIG` 指定的文件不存在 | 检查环境变量 |
| `6` | 认证失败 | 重跑 `setup` |
| `7` | 连不上 | `ping` 确认 |
| `9` / `10` | push / pull 的文件不存在 | 确认路径 |
| `124` | 命令超时 | 加 `--timeout <秒>` |

```bash
$OC run "..." --timeout 120     # 慢命令显式给超时
```

路径问题已被脚本处理（Windows + Git-Bash 的 MSYS 转换、`/tmp` 映射），
你不用手动处理反斜杠或 `C:/Program Files/Git/` 前缀。

---

## 8 · 凭据位置

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
