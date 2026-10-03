# 任务配方

具体任务的逐步做法。**通用动线见 SKILL.md §2**，这里只写各任务的差异点。

---

## 1 · 加节点 / 改分流规则

按 SKILL.md §2 的动线走，差异点：

### 命名与引用

**节点命名**沿用配置里的风格：`emoji + 半角空格 + 名称`（如 `🇺🇸 RN-01`）。

**重命名节点前先找全引用**，否则分组会失效：

```bash
$OC run "grep -n '旧名字' /etc/openclash/config/proxy.yaml"
```

要改的地方：`proxies` 里的定义 + 所有 `proxy-groups` 的 `proxies:` 列表。
注意有些分组用 `filter:` 正则按名字匹配 —— 这类**会自动纳入**，不用手动加
（但改名的节点若原来在列表里，仍需同步改名）。

### 从 vless:// 链接转节点配置

```yaml
- name: "🇺🇸 RN-01"
  type: vless
  server: rn.example.com
  port: 443
  uuid: <uuid>
  network: tcp
  tls: true
  udp: true
  flow: xtls-rprx-vision
  servername: <sni>                     # 对应链接的 sni=
  client-fingerprint: chrome            # 对应 fp=
  reality-opts:
    public-key: "<pbk>"                 # 对应 pbk=
    short-id: "<sid>"                   # 对应 sid=
```

对应关系：`security=reality` → `reality-opts`；`type=tcp` → `network: tcp`；
`encryption=none` 不写；`headerType=none` 不写。

### 验证

```bash
# 确认新节点和分组都进去了
$OC run 'SEC=$(uci get openclash.@openclash[0].dashboard_password)
         PORT=$(uci get openclash.@openclash[0].cn_port)
         curl -s -H "Authorization: Bearer $SEC" http://127.0.0.1:$PORT/proxies | head -c 800'
```

---

## 2 · 排查「某网站走了直连 / 走错代理」

**看实际命中了哪条规则，比读配置快得多。** 用日志做差分：

```bash
BEFORE=$($OC run "wc -l < /tmp/openclash.log" | tail -1 | tr -d ' ')
$OC run "curl -s -o /dev/null --max-time 8 https://目标域名/"
$OC run "tail -n +$BEFORE /tmp/openclash.log | grep -i '目标域名'"
```

日志会显示 `match RuleSet(xxx) using 分组[节点]` —— 一眼看出走了哪条规则、哪个分组。

### Fake-IP 模式的关键差异

Fake-IP 模式下客户端拿到假 IP（`198.18.x.x`），**Mihomo 靠域名匹配规则**：

- **`dig` 看解析结果意义不大**（那是假 IP）
- 要注意的是**规则命中**（上面的日志差分法）
- 判断当前模式：`$OC run "uci get openclash.@openclash[0].en_mode"`

这跟 redir-host 模式行为不同（后者靠 IP 匹配），查官方文档确认细节。

### 常见根因

| 现象 | 可能原因 |
|------|---------|
| 域名走了直连 | 被 `GEOSITE,cn` / `GEOIP,cn` 抓走；或规则顺序问题 |
| 域名没走代理 | `rule-provider` 没加载成功；或规则集没收录该域名 |
| 换了节点但没生效 | 改名后没同步 `proxy-groups` 里的引用 |

---

## 3 · 排查代理不通

按顺序，别跳步：

```bash
$OC probe                                        # 状态总览（先看这个）
$OC run "tail -30 /tmp/openclash_start.log"      # 启动是否成功
$OC run "tail -40 /tmp/openclash.log"            # 有无 error/fatal
```

日志不够时，让用户生成完整调试日志（信息最全，20+ 章节）：

```bash
$OC run "/usr/share/openclash/openclash_debug.sh"
$OC pull /tmp/openclash_debug.log
```

**报错先去官方错误速查表对号入座**（16 大类），比自己猜可靠：

```bash
curl -sL -o /tmp/oc-guide.md https://raw.githubusercontent.com/vernesong/OpenClash/master/.github/skills/openclash-user-guide/SKILL.md
grep -n "报错关键字" /tmp/oc-guide.md
```

### 快速检查清单

```bash
$OC run "pidof clash"                                    # 核心是否运行
$OC run "uci get openclash.@openclash[0].enable"          # 插件是否启用
$OC run "nft list chain inet fw4 openclash | head -20"    # 防火墙规则
$OC run "ip rule show | grep 0x162"                       # TUN 策略路由
```

---

## 4 · 清理内存 / 卸载无用组件

**先出表格给用户看，再动手**（见 `pitfalls.md` §7）：

| 列 | 内容 |
|----|------|
| 服务名 / 包名 | |
| 当前内存占用 | 读 `/proc/*/status` 的 `VmRSS` |
| 作用 | 这个组件干什么的 |
| 能否禁 / 卸 | 以及**风险**（会不会影响首页、商店等） |

用户选定后再执行。**别自作主张卸载东西。**

卸载前**必看 `pitfalls.md` §1**（apk 卡死）—— 尤其带 init 脚本的包。

---

## 5 · 新增自定义规则

规则文件位置与写法见官方文档（`SKILL.md` §1 的抓取命令）。
要点：

- 自定义规则注入需要 `enable_custom_clash_rules=1`
- 规则顺序有意义：先匹配先生效
- 改完跑 `clash -t` 校验

---

## 6 · 升级核心 / 更新订阅

```bash
# 检查当前版本
$OC run "/etc/openclash/clash -v"
$OC run "cat /tmp/clash_last_version 2>/dev/null"
```

升级/更新操作的具体命令见官方文档（`openclash_core.sh` / `openclash.sh` 章节）。
**注意**：这些会替换文件并重启，属高风险操作 —— 先确认用户意图，改完验证。

---

## 通用提醒

- **每个任务结束都跑 `python tests/verify_all.py`**（如果你改了仓库文件）
- **每次改动都留备份**，并把备份路径与回滚命令告诉用户
- **拿不准就去查官方文档**（SKILL.md §1），不要猜
