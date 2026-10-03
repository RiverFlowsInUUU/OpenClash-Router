---
name: openclash-router
description: 通过 SSH 管理 OpenWrt/iStoreOS 路由器上的 OpenClash —— 加节点、改策略组/分流规则、切模式、调 DNS、排障、内存清理、订阅管理。首次使用会自动检测并引导配置连接（免密密钥）。触发词：软路由、路由器、旁路由、OpenClash、加节点、分流、订阅、改配置、内存占用、DNS、代理不通。
---

# OpenClash 路由器管理

一个通用技能，用于通过 SSH 管理 **OpenWrt / iStoreOS** 上的 **OpenClash**。

## 第零步（每次任务开始前必做）

**先跑 `doctor`**。它会告诉你环境是否就绪；未配置时会给出引导。

```bash
python "$SKILL/scripts/oc.py" doctor
```

其中 `$SKILL` = 本技能目录（pi 会在系统提示里给出技能路径，通常为
`~/.pi/agent/skills/openclash-router`）。

**根据 doctor 结果分支：**

### 情形 A — 输出「尚未配置」

说明这是**首次使用**（或配置被删）。此时**必须向用户索取**以下信息，然后用 `setup` 自动配置：

| 需要什么 | 说明 |
|---------|------|
| **路由器 IP** | 局域网地址，如 `192.168.1.1` |
| **SSH 用户名** | OpenWrt 默认 `root` |
| **SSH 密码** | root 登录密码（用于首次部署公钥） |
| **SSH 端口** | 默认 `22`，可选 |

拿到后执行（**推荐方式**，生成密钥并部署，之后免密）：

```bash
python "$SKILL/scripts/oc.py" setup --host <IP> --user root --password '<密码>'
```

或者让用户**自己在终端交互式运行**（密码不经过对话，更安全）：

```bash
python "$SKILL/scripts/oc.py" setup
```

设置完成后会打印保存路径（`~/.config/openclash-mgmt/config.json`），**配置里不含密码**，只记录私钥路径。

> **若用户已有私钥**，可跳过密码：
> `python "$SKILL/scripts/oc.py" setup --host <IP> --user root --key ~/.ssh/id_ed25519`
>
> **若用户不想用密钥**：
> `... setup --host <IP> --password '<密码>' --no-key`（明文保存密码）

### 情形 B — 输出「自检通过」

配置已就绪，**直接开始干活**，不要再问连接信息。

### 情形 C — 连接失败

按顺序排查并告知用户：

1. 路由器是否在线：`ping <IP>`
2. 私钥是否还在：`ls ~/.config/openclash-mgmt/id_ed25519`
3. IP 是否变了（DHCP 重新分配）→ 让用户查主路由或 LuCI
4. 密钥被重置（固件升级）→ 重新跑 `setup`

## 命令速查

```bash
SKILL=~/.pi/agent/skills/openclash-router     # 或 pi 给出的技能路径
OC="python $SKILL/scripts/oc.py"

$OC doctor                    # 环境自检 / 引导配置
$OC setup --host ...          # 配置连接
$OC probe                     # OpenClash 状态总览（只读，先跑这个）
$OC run "uci show openclash"  # 执行任意命令（可多条，用 ; 分隔）
$OC push 本地文件 /root/target # 上传
$OC pull /etc/config/openclash ./local.yaml   # 下载
$OC show-config               # 查看当前配置（密码已隐藏）
$OC forget -y                 # 删除配置
```

**路径注意（Git-Bash on Windows）**：脚本已自动处理 MSYS 路径转换（`/root/x` ↔ `C:/Program Files/Git/root/x`）和本地 `/tmp` 映射，直接写 Unix 风格路径即可。

## 工作流铁律

### 1. 先只读，再动手

任何修改前，先 `probe` + 针对性侦查。把现状和目标对齐，给用户一份
**「改什么 / 改成什么 / 怎么回滚」**的方案，**等用户确认再执行**。

### 2. 改源文件，不改运行配置

| 文件 | 性质 |
|------|------|
| `/etc/openclash/config/<name>.yaml` | ✅ **权威源文件**（改这个） |
| `/etc/openclash/<name>.yaml` | ❌ 每次重启由 Ruby 重新生成，改了白改 |

配置路径：`uci get openclash.@openclash[0].config_path`

### 3. 改前备份，改后验证

```bash
$OC run "cp -a <文件> <文件>.bak-\$(date +%Y%m%d-%H%M%S)"
```
- 改 YAML → 先 `clash -t -d /etc/openclash -f /tmp/new.yaml` 校验，再替换，再 `/etc/init.d/openclash restart`
- 改 UCI → `uci commit openclash`，再 `uci show` 确认
- 改防火墙 → `/etc/init.d/openclash reload`，再 `nft list chain`

**明确告诉用户备份文件路径。**

### 4. 编辑 YAML 的正确姿势

**不要用 sed**。流程：

```bash
# 下载到本地编辑
$OC pull /etc/openclash/config/proxy.yaml ./work/proxy.yaml
# 本地用 Python 按精确字符串/行号修改（保留原格式风格）
# 上传并校验
$OC push ./work/proxy_new.yaml /tmp/proxy_new.yaml
$OC run "/etc/openclash/clash -t -d /etc/openclash -f /tmp/proxy_new.yaml"
# 校验通过后备份+替换+重启
```

**节点命名约定**：`emoji + 半角空格 + 名称`，例如 `🇺🇸 RN-01`。
**重命名节点必须同步改所有引用** —— 先 `grep -n "旧名"` 找全。

### 5. apk 可能卡死（iStoreOS 特有坑）

iStoreOS 用 `apk`（非 opkg）。某些包（如 `adb-enablemodem`）的 init 脚本在 uninstall 时调用
`adb wait-for-device` 等不存在的硬件，导致 **`apk del` 永久挂起**，并阻塞后续所有 apk 操作。

**卸载前先查**：
```bash
$OC run "apk info -L <包名> | grep -E '/etc/init.d|\.pre-deinstall'"
```
如带 init 脚本且涉及硬件等待，先**中和**该脚本的 `stop()` 再卸载：
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
**遇到卡死**：`kill -9` 掉 apk 及其子进程，然后 `apk list -I` 验证数据库完好。

### 6. iStoreOS 组件不可随意关停

| 组件 | 作用 | 可否禁用 |
|------|------|---------|
| `quickstart` | **可视化首页（QuickStart 仪表盘）** | ❌ 禁用后首页消失 |
| `linkease` | 易有云 + **iStore 应用商店后端** | ⚠️ 禁用后商店受影响 |
| `startdhns` | 内网穿透 | ✅ 可禁（用户可能在用） |
| `wpad`/`hostapd` | WiFi（无无线硬件时可禁） | ✅ 视硬件 |

**禁用服务必须连带处理 hotplug 触发器**，否则 U 盘插拔/网络变动时会自动拉起：
```bash
$OC run "mv /etc/hotplug.d/block/09-quickstart /etc/hotplug.d/block/09-quickstart.disabled"
```

### 7. 旁路由特征（避免误判为故障）

`network.wan.disabled=1` 时，启动日志会报：
```
[Warning] Can't Settting Only Intranet Allowed Function, Get IPv4 WAN Interfaces error ...
```
这是**正常告警**，不是故障。

### 8. 别碰这些

- `r8152-firmware` / `kmod-usb-net-rtl8152`（USB 网卡驱动）
- `dnsmasq-full`、`kmod-nft-tproxy`、`kmod-tun`、`ruby*`（OpenClash 依赖）
- `/etc/dropbear/authorized_keys`（登录凭据）

## 侦查命令库

脚本内 `probe` 已覆盖大部分。补充：

```bash
# 覆写模块是否真正生效（三道关）
$OC run "uci show openclash | grep -A6 config_overwrite; grep -c 'Overwrite Module' /tmp/openclash.log"

# 防火墙
$OC run "nft list chain inet fw4 openclash; nft list chain inet fw4 openclash_mangle"
$OC run "nft list chain inet fw4 dstnat | grep 'OpenClash DNS'"
$OC run "ip rule show | grep 0x162"     # TUN 模式策略路由

# 核心 API
$OC run 'SEC=$(uci get openclash.@openclash[0].dashboard_password); curl -s -H "Authorization: Bearer $SEC" http://127.0.0.1:9090/proxies | head -c 800'

# 进程内存排行
$OC run 'for d in /proc/[0-9]*; do p=${d#/proc/}; n=$(sed -n "s/^Name:[ \t]*//p" $d/status|head -1); r=$(awk "/^VmRSS:/{print \$2}" $d/status); [ -n "$r" ] && echo "$r $p $n"; done | sort -rn | head -15'

# 启动日志
$OC run "tail -20 /tmp/openclash_start.log"
$OC run "tail -40 /tmp/openclash.log"
```

## 任务配方

### 加节点 / 改策略组

1. `$OC pull /etc/openclash/config/proxy.yaml ./work/proxy.yaml`
2. 本地编辑（emoji + 空格命名；改完 grep 确认所有引用同步）
3. `$OC push ./work/proxy_new.yaml /tmp/proxy_new.yaml`
4. `$OC run "/etc/openclash/clash -t -d /etc/openclash -f /tmp/proxy_new.yaml"` ← 必须通过
5. 备份源文件 → `cp /tmp/proxy_new.yaml /etc/openclash/config/proxy.yaml`
6. `$OC run "/etc/init.d/openclash restart"`
7. 验证：`$OC run 'SEC=...; curl ... /proxies'` 确认新节点和分组存在

### 诊断故障

优先级（**先要日志，别猜**）：
1. 让用户生成调试日志：LuCI「运行日志」→「生成日志」，或 `$OC run "/usr/share/openclash/openclash_debug.sh"` 然后 `$OC pull /tmp/openclash_debug.log`
2. 日志不够 → 给精确 CLI 命令
3. 定位根因 → 给 LuCI 路径（服务 → OpenClash → ...）或直接改
4. 仍未解决 → 查 [OpenClash Issues](https://github.com/vernesong/OpenClash/issues) / [Mihomo Issues](https://github.com/MetaCubeX/mihomo/issues)

**高频根因**（来自 OpenClash 官方排查表）：
| 现象 | 常见原因 |
|------|---------|
| 某域名不走代理/走错组 | 规则顺序、rule-provider 未加载、Fake-IP 下靠域名匹配 |
| Google Play 下载失败 | 需 `nameserver-policy` 强制境外 DNS + 规则走代理（**双管齐下**） |
| Hysteria/TUIC 连不上 | Linux ≥6.6 的 quic-go GSO 问题 → 开 `disable_quic_go_gso` |
| DNS 泄露 | fallback 与 nameserver 并发抢答 → 弃用 fallback 改用 `nameserver-policy` |
| 覆写模块不生效 | 三关：UCI 条目存在 + `enable=1` + `config` 非空且匹配 |

### 内存 / 清理

**先出表格给用户看，再动手**。表格维度：服务名 / 当前内存 / 用途 / 是否可禁 / 风险。

通用收益排序：卡死进程 → 无用硬件包（modem/adb/iOS）→ iStoreOS 三件套 → wifi 服务。

## 参考资料

需要 OpenClash 功能的**完整**参考（每个 UCI 选项对应的 YAML 段、防火墙链结构、
覆写模块语法、错误速查表），读：

```
references/openclash-guide.md
```

它涵盖：依赖清单、系统架构、启动流程、防火墙/DNS 规则详解（fw3+fw4 双后端）、
错误信息速查、各页面选项详解（运行状态 / 插件设置 / 覆写设置 / 订阅 / 配置管理 / 日志）、
诊断命令与 CLI、覆写模块详解。

> 本文档未覆盖的内容（特定协议的详细参数、新版特性、插件开发），
> **不要编造** —— 主动查 Mihomo Wiki (https://wiki.metacubex.one/config/)、
> Meta-Docs、或 OpenClash/Mihomo 源码与 Issues。

## 凭据与安全

- 配置：`~/.config/openclash-mgmt/config.json`（权限 600，**无密码**）
- 私钥：`~/.config/openclash-mgmt/id_ed25519`（自动生成）
- 覆盖位置：设 `OC_CONFIG` 环境变量
- 公钥部署在路由器 `/etc/dropbear/authorized_keys`
- 删除配置：`$OC forget -y`

**永远不要在对话中回显密码。** 需要密码时优先让用户自己交互式运行 `setup`。
