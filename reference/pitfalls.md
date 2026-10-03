# 环境坑（官方文档不会写，动手前必读）

这些是 **iStoreOS / OpenWrt 环境层面**的坑，与 OpenClash 功能无关，
所以官方知识库没有。**每一项都是实测踩过的**，代价是断网 / 卡死 / 首页消失。

> 改配置、卸载软件包、开关服务**之前**先读本文件。

---

## 1 · `apk` 可能永久卡死 ⚠️

iStoreOS 用 `apk`（不是 opkg）。某些软件包的卸载钩子会调用**等待硬件**的命令 ——
典型是 `adb-enablemodem` 会跑 `adb wait-for-device`，没接 4G 模块就**永远等下去**。

**后果**：`apk del` 挂起，**并阻塞之后所有 apk 操作**（含安装）。实测卡了 16 小时。

### 预防：卸载前先看这个包带不带 init 脚本

```bash
$OC run "apk info -L <包名> | grep -E '/etc/init.d|pre-deinstall'"
```

带了的话，**先把它的 `stop()` 中和掉**再卸：

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

### 已经卡了：怎么救

```bash
$OC run "ps w | grep -E 'apk|adb'"          # 找到 apk 及其子进程
$OC run "kill -9 <apk_pid> <子进程...>"      # 全部杀掉
$OC run "apk list -I | wc -l"                # 验证数据库完好（能列出包数）
$OC run "apk update"                         # 验证还能正常工作
```

杀掉后 apk 锁会变成已删除状态，但那不影响后续使用（实测）。

### 注意

- 卸载前**先中和 init 脚本**，否则重跑还会卡
- 卸载命令放**后台执行**并观察日志，不要前台阻塞
- `timeout` 命令在 iStoreOS 上**不存在**（BusyBox 精简掉了），别指望用它兜底

---

## 2 · iStoreOS 组件有隐藏依赖 ⚠️

关服务前想清楚它是干什么的 —— 有些名字看着无关，其实是关键组件：

| 组件 | 实际作用 | 关了会怎样 |
|------|---------|-----------|
| `quickstart` | **可视化首页（QuickStart 仪表盘）** | 首页消失，退化成普通 LuCI 页 |
| `linkease` | 易有云 + **iStore 应用商店后端** | 商店可能不可用 |
| `startdhns` | 内网穿透 | 穿透失效（先问用户用不用） |
| `wpad` / `hostapd` | WiFi | 无无线硬件时才可关 |

**实测教训**：优化内存时关了 `quickstart`，用户发现"可视化首页不见了"。
它的 LuCI controller 逻辑是：

```lua
if luci.sys.call("pgrep quickstart >/dev/null") == 0 then
    entry({"admin","quickstart"}, template("quickstart/home"), ...)   -- 正常
else
    entry({"admin","quickstart"}, call("redirect_fallback"))          -- 退化
end
```

服务不运行 → 首页被 `redirect_fallback` 替换。

---

## 3 · 禁服务必须连带处理 hotplug ⚠️

很多 iStoreOS 服务在 `/etc/hotplug.d/` 里有触发器。单纯 `disable` + `stop`
**仍会在 U 盘插拔或网络变动时被自动拉起**。

实测：`quickstart` 与 `startdhns` 各有 hotplug：

```bash
$OC run "cat /etc/hotplug.d/block/09-quickstart"    # 调 quickstart blockChange
$OC run "cat /etc/hotplug.d/iface/21-startdhns"     # 调 quickstart ifaceEvent
```

禁用时要一并改名：

```bash
$OC run "mv /etc/hotplug.d/block/09-quickstart /etc/hotplug.d/block/09-quickstart.disabled"
$OC run "mv /etc/hotplug.d/iface/21-startdhns /etc/hotplug.d/iface/21-startdhns.disabled"
```

**改完重启一次验证**服务真的没被拉起。

---

## 4 · 旁路由的 WAN 告警是正常的

`network.wan.disabled=1`（旁路由）时，启动日志必然出现：

```
[Warning] Can't Settting Only Intranet Allowed Function,
          Get IPv4 WAN Interfaces error, Please Verify The Firewall's WAN Zone Name is wan, ...
```

**这不是故障**，别去"修"它。判断依据：

```bash
$OC run "uci get network.wan.disabled"     # 1 = 旁路由，告警属预期
```

---

## 5 · 统计这类数据有坑

- **`lsmod` 的 `nf_tables` 大小字段会溢出**成天文数字（实测 `208896767`，
  实际约 204KB）。算模块占用必须**剔除异常值**（如 `$2 < 2000000`）。
- **BusyBox 的 `ps` 没有 RSS 字段**，进程内存要读 `/proc/*/status` 的 `VmRSS`。
- BusyBox 的 `ls`/`cat` 等缺常用参数（`cat -A`、`ps -eo`、`diff`、`comm` 都没有）。
  复杂文本处理放本地做，别在路由器上折腾。

---

## 6 · 别碰这些

| 项目 | 为什么 |
|------|--------|
| `r8152-firmware` / `kmod-usb-net-rtl8152` | USB 网卡驱动 —— 很多软路由的第二个网口靠它 |
| `dnsmasq-full`、`kmod-nft-tproxy`、`kmod-tun`、`ruby*` | OpenClash 的依赖，删了插件跑不起来 |
| `/etc/dropbear/authorized_keys` | 登录凭据，改错会把自己锁在外面 |

判断网卡驱动：`ls -l /sys/class/net/eth1/device/driver`（指向 `r8152` 就是它）。

---

## 7 · 内存优化的正确姿势

**先出表格给用户看，再动手。** 列出：服务名 / 占用 / 作用 / 能否禁 / 风险。
用户选定后再执行 —— 别自作主张卸载东西（见 §2 的教训）。

侦查命令：

```bash
$OC run 'for d in /proc/[0-9]*; do p=${d#/proc/}; n=$(sed -n "s/^Name:[ \t]*//p" $d/status|head -1); r=$(awk "/^VmRSS:/{print \$2}" $d/status); [ -n "$r" ] && echo "$r $p $n"; done | sort -rn | head -15'
```

**通用收益排序**（实测这台机器）：卡死进程 → 无用硬件包（modem/adb/iOS 系列，约 23MB）
→ iStoreOS 三件套（quickstart 27MB / linkease 47MB / startdhns 20MB）→ wifi 服务（8MB）。

`clash` 自身占约 200MB 属正常（Smart 内核 + 规则多），别去动它。
