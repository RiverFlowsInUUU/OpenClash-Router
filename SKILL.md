---
name: openclash-router
description: 通过 SSH 操作 OpenWrt/iStoreOS 路由器上的 OpenClash —— 改配置、加节点、调分流规则、切换运行模式、配 DNS、排查代理不通、清理内存、管理订阅。只要用户提到软路由、路由器、旁路由、OpenClash、Clash、Mihomo、机场节点、订阅、分流、DNS 泄露、代理连不上，或让你看/改家里的网络设备配置，就应该使用这个技能——即使用户没有明说"OpenClash"或"路由器"。它负责环境准备（自动装依赖）、建立免密 SSH 连接、以及安全改配置的规程。
---

# OpenClash 路由器操作

通过 SSH 管理装了 **OpenClash** 的 **OpenWrt / iStoreOS** 路由器。

这个技能解决的是**操作**问题：怎么连上去、怎么安全地改配置、怎么验证。
OpenClash 本身的功能（某个选项什么意思、防火墙链怎么建）**不在这个技能里** —— 见下一节。

## 第一原则：两种知识，别混

这个技能**不包含 OpenClash 的领域知识**。如果你要回答"某选项是什么意思"、
"为什么这个规则不生效"、"这个报错啥原因"，**先去查官方知识库**，
不要凭记忆作答 —— 配置字段和选项值编错会直接把用户的网络搞挂。

```bash
# 官方知识库（随时抓取，比本地缓存新）
curl -sL -o /tmp/oc-guide.md \
  https://raw.githubusercontent.com/vernesong/OpenClash/master/.github/skills/openclash-user-guide/SKILL.md

grep -n "关键词" /tmp/oc-guide.md          # 先定位
sed -n '120,160p' /tmp/oc-guide.md        # 再读上下文
```

**该去查的场合**：UCI/LuCI 选项含义 · 防火墙链结构 · 覆写模块语法 ·
DNS 配置（nameserver / fallback / nameserver-policy / fake-ip-filter）·
分流规则与 provider · 报错信息含义 · 订阅处理 · 任何"为什么这个选项不生效"。

官方文档覆盖：依赖清单与故障排查 · 系统架构与启动流程 · 防火墙与 DNS 规则详解 ·
**日志与错误信息速查（16 大类）** · 各页面选项详解 · 诊断命令与 CLI 参考 · 覆写模块详解。

其他权威来源：Mihomo 字段看 https://wiki.metacubex.one/config/ ；
报错先搜 [OpenClash Issues](https://github.com/vernesong/OpenClash/issues) 和
[Mihomo Issues](https://github.com/MetaCubeX/mihomo/issues)。
**查不到就说查不到**，给出链接让用户自己看。

## 工具箱

所有操作通过一个脚本：`$SKILL/scripts/oc.py`（`$SKILL` 是技能目录，pi 会在系统提示里给出）。

> 💡 **把脚本当黑盒用，不要读它的源码。**
> 它有 600+ 行，读进来会挤占你的上下文，而它本来就是设计成直接调用的。
> 想看用法就 `--help`：
> ```bash
> python "$SKILL/scripts/oc.py" --help
> python "$SKILL/scripts/oc.py" setup --help
> ```

| 命令 | 用途 |
|------|------|
| `doctor` | 环境自检。**每次会话第一条命令**，它会告诉你缺什么 |
| `bootstrap` | 显式安装本地依赖（一般不用，缺依赖时会自动装） |
| `setup` | 配置连接（生成密钥、部署公钥、验证） |
| `probe` | OpenClash 状态总览（只读，排查从这开始） |
| `run "<cmd>"` | 在路由器执行命令 |
| `push` / `pull` | 上传 / 下载文件 |
| `show-config` / `forget` | 查看 / 清除连接配置 |

依赖（`paramiko`、`cryptography`）缺失时脚本会**自动 pip install**，
依次尝试普通 / `--user` / `--break-system-packages`。装不上才报错并给命令。
所以通常你不需要为环境操心，`doctor` 一把梭。

## 上手流程

```
python "$SKILL/scripts/oc.py" doctor
        │
        ├─ "尚未配置"  → 首次使用，走 [配置连接]
        ├─ "自检通过"  → 一切就绪，直接干活
        └─ "连接失败"  → 走 [连接排障]
```

### 配置连接（仅首次）

问用户要三样东西：**路由器 IP**、**SSH 用户名**（OpenWrt 通常是 `root`）、**SSH 密码**。

```bash
python "$SKILL/scripts/oc.py" setup --host <IP> --user root --password '<密码>'
```

脚本会自动：密码连一次探路 → 生成 ed25519 密钥 → 部署公钥到路由器
`/etc/dropbear/authorized_keys`（权限 600，权限不对 dropbear 会拒绝）→
**用密钥重新验证** → 验证通过才保存配置。之后永久免密。

**更安全的做法**：让用户自己跑 `setup`（无参数，交互式），密码用 `getpass` 读，
不经过对话记录：

```bash
python "$SKILL/scripts/oc.py" setup
```

**绝不要在回复里回显密码。** 需要密码时，让用户交互式跑，或让他自己填。

其他情形：用户已有私钥 → `setup --key ~/.ssh/id_ed25519`；
不想用密钥 → `setup --password 'xxx' --no-key`（明文存密码，不推荐）。

### 连接排障

```
连不上？
├─ ping <IP> 不通          → 路由器没开机 / IP 变了（让用户查主路由）
├─ ping 通但认证失败        → ls ~/.config/openclash-mgmt/id_ed25519 还在吗？
│                            密钥丢了或固件升级重置了 → 重跑 setup
└─ doctor 说端口不对       → 用户改过 SSH 端口 → setup --port <端口>
```

## 改配置的规程

这是本技能最有价值的部分。改错配置的代价是用户家里断网，
而很多错误是**静默的**（改了没生效、重启后被覆盖），所以流程比手速重要。

### 先搞清楚该改哪个文件

配置有两份，**必须改源文件**：

| 文件 | 说明 |
|------|------|
| `/etc/openclash/config/<name>.yaml` | ✅ **源文件**。人工维护，带注释，重启后据此重新生成 |
| `/etc/openclash/<name>.yaml` | ❌ 每次启动由 Ruby 脚本重新生成，改它等于没改 |

确认路径：`uci get openclash.@openclash[0].config_path`。

### 四步走

**1. 先只读侦查，把方案给用户看**

```bash
OC="python $SKILL/scripts/oc.py"
$OC probe                                        # 状态总览
$OC pull <源文件> ./work/proxy.yaml               # 拿到配置
```

然后告诉用户：**改什么、改成什么、怎么回滚**。等用户确认。别自己闷头改。

**2. 本地编辑，不用 sed**

下载到本地，用 Python 按精确字符串匹配来改（保留原有的空行、缩进、注释风格 ——
用户以后还要手动看这些文件）。sed 容易误伤 YAML 结构，尤其涉及缩进和引号时。

**3. 上传到临时位置，先用内核校验**

```bash
$OC push ./work/proxy_new.yaml /tmp/proxy_new.yaml
$OC run "/etc/openclash/clash -t -d /etc/openclash -f /tmp/proxy_new.yaml"
```

看到 `configuration file ... test is successful` 才能往下走。
这一步能在**不影响线上**的前提下抓住语法错误 —— 直接覆盖再重启的话，
核心起不来，用户就断网了。

**4. 备份 → 替换 → 重启 → 验证**

```bash
$OC run "cp -a <源文件> <源文件>.bak-\$(date +%Y%m%d-%H%M%S)"
$OC push ./work/proxy_new.yaml <源文件>
$OC run "/etc/init.d/openclash restart"
# 验证：新节点/新规则真的进去了吗
$OC run 'SEC=$(uci get openclash.@openclash[0].dashboard_password); \
         curl -s -H "Authorization: Bearer $SEC" http://127.0.0.1:9090/proxies | head -c 500'
```

**把备份路径告诉用户**，并给出回滚命令。这样他随时能自己退回去。

### 改其他类型的东西

| 改什么 | 生效方式 | 验证 |
|--------|---------|------|
| YAML 配置 | `/etc/init.d/openclash restart` | `clash -t` + 核心 API |
| UCI 选项 | `uci commit openclash` | `uci show openclash` |
| 防火墙规则 | `/etc/init.d/openclash reload` | `nft list chain inet fw4 openclash` |
| 覆写模块 | 重启核心 | `grep -c 'Overwrite Module' /tmp/openclash.log` 应 > 0 |

### 编辑 YAML 的两个注意点

**节点命名**沿用配置里的风格：`emoji + 半角空格 + 名称`（如 `🇺🇸 RN-01`）。

**重命名节点前先找全引用**，否则分组会失效：

```bash
$OC run "grep -n '旧名字' <源文件>"
```
`proxies` 里的定义、`proxy-groups` 里的 `proxies:` 列表都要同步改。
注意有些分组用 `filter:` 正则按名字匹配，改名后会自动纳入 —— 这类不用手动加。

## 常见任务

### 加节点 / 改分流

走上面的「四步走」。新节点如果属于某个 `url-test` 分组的手动列表，
记得同时把新名字加进该组的 `proxies:` 数组。

### 排查"某个网站走了直连 / 走错代理"

先看实际命中了哪条规则（比读配置快）：

```bash
BEFORE=$($OC run "wc -l < /tmp/openclash.log" | tail -1 | tr -d ' ')
$OC run "curl -s -o /dev/null --max-time 8 https://目标域名/"
$OC run "tail -n +$BEFORE /tmp/openclash.log | grep -i '目标域名'"
```
日志会显示 `match RuleSet(xxx) using 分组[节点]`。

Fake-IP 模式下要特别注意：客户端拿到的是假 IP（`198.18.x.x`），
**Mihomo 靠域名匹配规则**。所以直接 `dig` 看解析结果意义不大，
要看规则命中。这点和 redir-host 模式的行为不同，查官方文档确认。

### 排查代理不通

按顺序，别跳步：

```bash
$OC probe                                              # 状态总览
$OC run "tail -30 /tmp/openclash_start.log"            # 启动是否成功
$OC run "tail -40 /tmp/openclash.log"                  # 有无 error/fatal
```

日志不够时，让用户生成完整调试日志（信息最全）：

```bash
$OC run "/usr/share/openclash/openclash_debug.sh"
$OC pull /tmp/openclash_debug.log
```

**报错先去官方错误速查表对号入座**（16 大类），比自己猜可靠：

```bash
curl -sL -o /tmp/oc-guide.md https://raw.githubusercontent.com/vernesong/OpenClash/master/.github/skills/openclash-user-guide/SKILL.md
grep -n "报错关键字" /tmp/oc-guide.md
```

### 清理内存 / 卸载无用组件

**先出表格给用户看，再动手。** 列出：服务名 / 占用 / 作用 / 能否禁 / 风险。
用户选定后再执行。别自作主张卸载东西。

侦查用：

```bash
$OC run 'for d in /proc/[0-9]*; do p=${d#/proc/}; n=$(sed -n "s/^Name:[ \t]*//p" $d/status|head -1); r=$(awk "/^VmRSS:/{print \$2}" $d/status); [ -n "$r" ] && echo "$r $p $n"; done | sort -rn | head -15'
```

## 环境坑（官方文档不会写，但你会踩）

这些是 iStoreOS / OpenWrt 特有的，和 OpenClash 功能无关，所以官方知识库没有。
**动手前先扫一眼**：

### `apk` 可能永久卡死

iStoreOS 用 `apk`。某些包的卸载钩子会调用等待硬件的东西
（例：`adb-enablemodem` 会跑 `adb wait-for-device`，没接 4G 模块就永远等下去）。
结果：`apk del` 挂起，**并阻塞之后所有 apk 操作**。

卸载前先看这个包带不带 init 脚本：

```bash
$OC run "apk info -L <包名> | grep -E '/etc/init.d|pre-deinstall'"
```

带的话，先把它的 `stop()` 中和掉再卸：

```bash
$OC run "cat > /etc/init.d/<svc> <<'EOS'
#!/bin/sh /etc/rc.common
START=99
start(){ :; }
stop(){ :; }
restart(){ :; }
EOS
chmod +x /etc/init.d/<svc>"
```

已经卡了：`kill -9` 掉 apk 及其子进程，然后 `apk list -I` 确认数据库没坏。

### iStoreOS 的组件有隐藏依赖

关服务前想清楚它是干什么的 —— 有些名字看着无关，其实是关键组件：

| 组件 | 实际作用 | 关了会怎样 |
|------|---------|-----------|
| `quickstart` | **可视化首页（QuickStart 仪表盘）** | 首页消失，退化成普通 LuCI 页 |
| `linkease` | 易有云 + **iStore 应用商店后端** | 商店可能不可用 |
| `startdhns` | 内网穿透 | 穿透失效（先问用户用不用） |
| `wpad` / `hostapd` | WiFi | 无无线硬件时才可关 |

**禁服务要连 hotplug 一起处理**，否则 U 盘插拔或网络变动会自动把它拉起来：

```bash
$OC run "mv /etc/hotplug.d/block/09-quickstart /etc/hotplug.d/block/09-quickstart.disabled"
```

改完建议重启一次验证服务真的没被拉起。

### 旁路由的 WAN 告警是正常的

`network.wan.disabled=1`（旁路由）时，启动日志必然出现：

```
[Warning] Can't Settting Only Intranet Allowed Function, Get IPv4 WAN Interfaces error ...
```

这不是故障，别去"修"它。

### 统计这类数据有坑

- `lsmod` 的 `nf_tables` 大小字段会溢出成天文数字，**算模块占用要剔除异常值**。
- BusyBox 的 `ps` 没有 RSS 字段，进程内存读 `/proc/*/status` 的 `VmRSS`。

### 别碰这些

- `r8152-firmware` / `kmod-usb-net-rtl8152` —— USB 网卡驱动（软路由常见的第二个网口）
- `dnsmasq-full`、`kmod-nft-tproxy`、`kmod-tun`、`ruby*` —— OpenClash 的依赖
- `/etc/dropbear/authorized_keys` —— 登录凭据，改错会把自己锁在外面

## 工具出问题时

```
oc.py 报错？
├─ "缺少 paramiko"  → 自动装失败。让用户跑：python -m pip install paramiko
├─ "认证失败"        → 密钥没了/密码变了 → 重跑 setup
├─ "连接失败"        → 网络不通 或 IP 变了 → ping 一下确认
└─ 命令返回 exit≠0   → 那多半是远端命令本身的问题，不是工具的问题
```

路径问题已被脚本处理（Windows + Git-Bash 的 MSYS 转换、`/tmp` 映射），
你不用手动处理反斜杠或 `C:/Program Files/Git/` 前缀。

## 凭据

```
~/.config/openclash-mgmt/
├── config.json      (600)  连接信息，不含密码
├── id_ed25519       (600)  私钥
└── id_ed25519.pub   (644)  公钥（已部署到路由器）
```

- 换位置：`OC_CONFIG=/path/to/config.json`
- 清除：`python "$SKILL/scripts/oc.py" forget -y`
- 密钥失效（固件升级常会重置 dropbear）→ 重跑 `setup`

回复里**永远不要出现密码**。
