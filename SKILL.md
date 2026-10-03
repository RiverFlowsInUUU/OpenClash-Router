---
name: openclash-router
description: 通过 SSH 操作 OpenWrt/iStoreOS 路由器上的 OpenClash —— 改配置、加节点、调分流、排障、清理。技能聚焦「操作流程」：自动装依赖(paramiko)、自动配置免密连接、以及安全改配置的规程。当用户提到 软路由、路由器、旁路由、OpenClash、加节点、分流、订阅、改配置、内存占用、DNS、代理不通 时使用。
---

# OpenClash 路由器操作技能

用 SSH 管理 **OpenWrt / iStoreOS** 上的 **OpenClash**。

**本技能只负责"怎么操作"**（环境准备、连接配置、改动规程）。
**OpenClash 自身的功能知识**（每个选项含义、防火墙链、覆写语法、错误速查）
请看官方知识库 —— 见下方「领域知识」一节。

---

## 职责边界

| 本技能管 | 不管（查官方） |
|---------|--------------|
| 装依赖、配 SSH 免密 | 某个 UCI 选项是什么意思 |
| 连接测试、环境自检 | 防火墙链怎么建、覆写模块怎么写 |
| **安全修改配置的规程** | Mihomo 各协议参数 |
| 备份/回滚/验证流程 | 错误码逐条解释 |

---

## 第 0 步：环境准备（每次会话第一条命令）

```bash
python "$SKILL/scripts/oc.py" doctor
```

`$SKILL` = 本技能目录（pi 会在系统提示里给出路径，通常是 `~/.pi/agent/skills/openclash-router`）。

**依赖会自动装**：脚本启动时若缺 `paramiko` 会尝试 `pip install`（依次尝试
普通 / `--user` / `--break-system-packages`）。成功则继续，失败才报错并给出命令。
可用 `OC_NO_AUTO_INSTALL=1` 禁用自动安装。

也可显式安装：

```bash
python "$SKILL/scripts/oc.py" bootstrap
```

**根据 doctor 输出分支：**

| 输出 | 含义 | 动作 |
|------|------|------|
| `尚未配置` | 首次使用 | → 走「第 1 步：配置连接」 |
| `自检通过` | 一切就绪 | → 直接干活 |
| `连接失败` | 网络/密钥问题 | → 走「排障」 |

---

## 第 1 步：配置连接（仅首次）

需要向用户索取 **3 个信息**：

1. **路由器 IP**（LAN 地址，如 `192.168.1.1`）
2. **SSH 用户名**（OpenWrt 默认 `root`）
3. **SSH 密码**（仅用于首次部署公钥）

然后执行：

```bash
python "$SKILL/scripts/oc.py" setup --host <IP> --user root --password '<密码>'
```

**setup 会自动完成 4 件事：**

1. 用密码连一次，探测远端环境
2. 生成 ed25519 密钥对 → `~/.config/openclash-mgmt/id_ed25519`
3. 部署公钥到路由器 `/etc/dropbear/authorized_keys`（含 `chmod 600`，dropbear 权限不对会拒绝）
4. **用密钥重新验证登录** —— 失败则中止、不保存配置

**结果**：配置存到 `~/.config/openclash-mgmt/config.json`（权限 600，**不含密码**），
之后永久免密。

### 更安全的做法：让用户自己跑

密码不经过对话记录：

```bash
python "$SKILL/scripts/oc.py" setup      # 交互式，用 getpass 读密码
```

### 其他情形

```bash
# 用户已有私钥，跳过密码
... setup --host <IP> --user root --key ~/.ssh/id_ed25519

# 不想用密钥（明文存密码，不推荐）
... setup --host <IP> --password '<密码>' --no-key

# 密码从环境变量/文件来（避免进 shell 历史）
OC_PASSWORD='xxx' ... setup --host <IP>
... setup --host <IP> --password-file /tmp/pw
```

**⚠️ 绝不要在回复里回显密码。**

---

## 第 2 步：日常操作

```bash
OC="python $SKILL/scripts/oc.py"

$OC probe                      # 总览：系统/内存/运行模式/端口/配置/防火墙/日志
$OC run "<命令>"               # 执行远端命令（可多条，用 ; 分隔）
$OC run "<命令>" --timeout 120 # 长命令
$OC push <本地> <远端>          # 上传
$OC pull <远端> <本地>          # 下载
$OC show-config                # 查看连接配置（密码隐藏）
$OC forget -y                  # 清除配置
```

**路径不用操心**：脚本自动处理 Windows + Git-Bash 的两个坑 ——
MSYS 把远端路径 `/root/x` 改写成 `C:/Program Files/Git/root/x`（自动还原）；
Bash 的 `/tmp` 在 Windows Python 里不存在（自动映射到真实 TEMP）。

---

## 改配置的规程（最重要）

### 铁律 1：改源文件，不改运行配置

| 文件 | 性质 |
|------|------|
| `/etc/openclash/config/<name>.yaml` | ✅ **源文件** —— 改这个 |
| `/etc/openclash/<name>.yaml` | ❌ 每次重启重新生成，改了白改 |

路径用 `uci get openclash.@openclash[0].config_path` 确认。

### 铁律 2：先只读，再动手，等确认

任何修改前先 `probe` + 针对性侦查，给用户一份
**「改什么 / 改成什么 / 怎么回滚」** 的方案，**等用户确认再执行**。

### 铁律 3：改前备份，改后验证

```bash
$OC run "cp -a <文件> <文件>.bak-\$(date +%Y%m%d-%H%M%S)"
```

| 改什么 | 怎么验证 |
|--------|---------|
| YAML | `$OC run "/etc/openclash/clash -t -d /etc/openclash -f /tmp/new.yaml"` 必须通过，再替换、再 restart |
| UCI | `uci commit openclash` → `uci show` 确认 |
| 防火墙 | `/etc/init.d/openclash reload` → `nft list chain` 确认 |

**把备份路径告诉用户。**

### 铁律 4：编辑 YAML 用脚本，不用 sed

```bash
# 1) 下载
$OC pull /etc/openclash/config/proxy.yaml ./work/proxy.yaml
# 2) 本地编辑（Python，按精确字符串匹配，保留原格式风格）
# 3) 上传并校验
$OC push ./work/proxy.yaml /tmp/proxy.yaml
$OC run "/etc/openclash/clash -t -d /etc/openclash -f /tmp/proxy.yaml"
# 4) 校验通过 → 备份 → 替换 → 重启
$OC run "cp -a /etc/openclash/config/proxy.yaml /etc/openclash/config/proxy.yaml.bak-\$(date +%Y%m%d-%H%M%S)"
$OC push ./work/proxy.yaml /etc/openclash/config/proxy.yaml
$OC run "/etc/init.d/openclash restart"
```

**节点命名约定**：`emoji + 半角空格 + 名称`（如 `🇺🇸 RN-01`）。
**重命名节点必须先 `grep -n "旧名"` 找全所有引用再改。**

---

## 排障流程

**顺序**（别跳步，别猜）：

1. `$OC doctor` — 环境是否就绪
2. `$OC probe` — 运行状态总览
3. **要调试日志**（信息最全）：让用户点 LuCI「运行日志 → 生成日志」，
   或 `$OC run "/usr/share/openclash/openclash_debug.sh"` 然后
   `$OC pull /tmp/openclash_debug.log`
4. 日志不够 → 用 `$OC run` 发精确命令
5. 定位后给 LuCI 路径或直接改
6. 仍未解决 → 查 Issues（见下）

**连接类问题先查这几项**：

```bash
$OC run "pidof clash"                                   # 核心是否运行
$OC run "uci get openclash.@openclash[0].enable"         # 插件是否启用
$OC run "tail -30 /tmp/openclash_start.log"              # 启动日志
$OC run "nft list chain inet fw4 openclash | head -20"   # 防火墙规则
$OC run "netstat -tlnp | grep -E '7874|7892|7895|9090'"  # 端口监听
```

---

## 领域知识（OpenClash 自身）

**本技能不重复官方内容。** 需要以下知识时，**直接读官方知识库**：

> ### 📖 https://github.com/vernesong/OpenClash/blob/master/.github/skills/openclash-user-guide/SKILL.md

它涵盖：

- **依赖清单与故障排查** —— 各包作用、缺失症状
- **系统架构与启动流程** —— UCI → 脚本 → YAML 的转换链路
- **防火墙与 DNS 规则详解** —— fw3/fw4 双后端、每条链的规则顺序
- **日志与错误信息速查** —— 16 大类错误关键字 → 原因 → 排查路径
- **各页面选项详解** —— 运行状态 / 插件设置 / 覆写设置 / 订阅 / 配置管理 / 日志
- **诊断命令与 CLI 参考** —— 决策树、LuCI HTTP API、Mihomo 原生 API、脚本速查
- **覆写模块详解** —— INI 三段格式、`[YAML]` 操作符（`!` `+` `-` `*`）、允许的 General key

**取用方式**：

```bash
# 抓取到本地再检索（推荐，避免只读片段）
curl -sL -o /tmp/oc-guide.md \
  https://raw.githubusercontent.com/vernesong/OpenClash/master/.github/skills/openclash-user-guide/SKILL.md
grep -n "关键词" /tmp/oc-guide.md
```

其他权威来源：

| 资源 | 用途 |
|------|------|
| https://wiki.metacubex.one/config/ | Mihomo 配置字段 |
| https://github.com/vernesong/OpenClash/issues | 插件侧已知问题 |
| https://github.com/MetaCubeX/mihomo/issues | 内核侧已知问题 |

**不要编造。** 查不到就明说查不到，并给出上述链接。

---

## 环境相关的坑（真实踩过，动手前先读）

这些是**环境层面**的坑（与 OpenClash 无关），官方知识库不会写：

### 1. iStoreOS 的 `apk` 会卡死

某些包（如 `adb-enablemodem`）的 uninstall 钩子会调用
`adb wait-for-device` 等不存在的硬件 → **`apk del` 永久挂起**，并阻塞后续所有 apk 操作。

```bash
# 卸载前先查是否带 init 脚本
$OC run "apk info -L <包名> | grep -E '/etc/init.d|pre-deinstall'"
# 必要时先中和它的 stop()
$OC run "cat > /etc/init.d/<svc> <<'EOS'
#!/bin/sh /etc/rc.common
START=99
start(){ :; }
stop(){ :; }
restart(){ :; }
EOS
chmod +x /etc/init.d/<svc>"
```

卡死后：`kill -9` apk 及其子进程，再 `apk list -I` 验证数据库完好。

### 2. iStoreOS 组件不能随便关

| 组件 | 作用 | 能否禁 |
|------|------|-------|
| `quickstart` | **可视化首页（QuickStart 仪表盘）** | ❌ 禁了首页消失 |
| `linkease` | 易有云 + **iStore 应用商店后端** | ⚠️ 禁了商店受影响 |
| `startdhns` | 内网穿透 | ✅ 可禁（先问用户是否在用） |
| `wpad`/`hostapd` | WiFi | ✅ 无无线硬件时可禁 |

**禁服务必须连带处理 hotplug**，否则 U 盘插拔/网络变动会自动拉起：

```bash
$OC run "mv /etc/hotplug.d/block/09-quickstart /etc/hotplug.d/block/09-quickstart.disabled"
```

### 3. 旁路由的正常告警

`network.wan.disabled=1`（旁路由）时，启动日志会有：

```
[Warning] Can't Settting Only Intranet Allowed Function, Get IPv4 WAN Interfaces error ...
```

这是**正常现象**，不是故障。

### 4. 别碰这些

- `r8152-firmware` / `kmod-usb-net-rtl8152` —— USB 网卡驱动（很多软路由的第二个网口）
- `dnsmasq-full`、`kmod-nft-tproxy`、`kmod-tun`、`ruby*` —— OpenClash 依赖
- `/etc/dropbear/authorized_keys` —— 登录凭据

### 5. 内存排查的正确姿势

`lsmod` 的 `nf_tables` 大小字段会溢出成天文数字，**统计模块占用要剔除异常值**。
进程内存用 `/proc/*/status` 的 `VmRSS`（BusyBox `ps` 没有 RSS 字段）。

---

## 凭据与安全

```
~/.config/openclash-mgmt/
├── config.json      (600)  连接信息（不含密码）
├── id_ed25519       (600)  私钥
└── id_ed25519.pub   (644)  公钥（已部署到路由器）
```

- 覆盖配置位置：`OC_CONFIG=/path/to/config.json`
- 清除配置：`$OC forget -y`
- 密钥失效（固件升级重置 dropbear）→ 重跑 `setup`

**回复中永不含密码。** 需要密码时让用户自己交互式跑 `setup`。
