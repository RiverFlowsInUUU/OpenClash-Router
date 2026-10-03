# openclash-router

一个 [pi](https://github.com/badlogic/pi-mono) **Agent Skill**：通过 SSH 管理 OpenWrt / iStoreOS 路由器上的 **OpenClash**。

让它帮你加节点、改策略组、调分流规则、切运行模式、配 DNS、排查故障、清理内存、管理订阅 —— 用自然语言就行。

## 特性

- **首次使用自动引导**：自动检测环境，引导你配置连接（生成密钥、部署公钥、验证），之后 **永久免密**。
- **凭据与技能分离**：技能本身通用可分享，你的连接信息存在 `~/.config/openclash-mgmt/`，绝不进仓库。
- **内置避坑知识**：记录了 iStoreOS 上的真实坑（`apk` 死锁、`quickstart` 关掉首页消失、hotplug 拉起服务、旁路由告警等）。
- **完整参考手册**：附 OpenClash 全功能参考（3865 行，涵盖 UCI 选项、防火墙链、覆写模块、错误速查）。

## 安装

```bash
# 用户级（所有项目可用）
git clone https://github.com/<你的用户名>/openclash-router.git ~/.pi/agent/skills/openclash-router
```

或作为项目级技能：

```bash
git clone https://github.com/<你的用户名>/openclash-router.git .pi/skills/openclash-router
```

> pi 也支持 `~/.agents/skills/` 与 `.agents/skills/` 位置。

### 依赖

```bash
python -m pip install paramiko      # 必需
python -m pip install cryptography  # 可选：用于 setup 时生成密钥
```

Python ≥ 3.8。

## 使用

### 首次：配置连接

在 pi 里直接说需求即可，例如：

> 帮我看看软路由的 OpenClash 状态

pi 会自动运行 `doctor`，发现未配置后引导你提供 **路由器 IP / 用户名 / 密码**，然后自动完成密钥部署。

也可以手动配置：

```bash
SKILL=~/.pi/agent/skills/openclash-router

# 交互式（密码不经过 shell 历史）
python $SKILL/scripts/oc.py setup

# 非交互式
python $SKILL/scripts/oc.py setup --host 192.168.1.1 --user root --password 'xxx'
```

配置保存在 `~/.config/openclash-mgmt/config.json`（权限 600，**不含密码**）。

### 日常使用

```bash
OC="python ~/.pi/agent/skills/openclash-router/scripts/oc.py"

$OC doctor                      # 环境自检
$OC probe                       # OpenClash 状态总览
$OC run "uci show openclash"    # 执行远端命令
$OC run "nft list chain inet fw4 openclash"
$OC push ./proxy.yaml /tmp/proxy.yaml    # 上传
$OC pull /etc/openclash/config/proxy.yaml ./proxy.yaml   # 下载
$OC show-config                 # 查看配置（密码隐藏）
$OC forget -y                   # 删除配置
```

在 pi 中说人话也行：

- "帮我加个香港节点"
- "为什么这个域名走了直连"
- "路由器内存占用怎么样，有没有能清的"
- "DNS 泄露了，帮我查"

## 目录结构

```
.
├── SKILL.md                      # 技能说明（pi 读取）
├── scripts/
│   └── oc.py                     # 管理工具（doctor/setup/run/probe/push/pull/...）
├── references/
│   └── openclash-guide.md        # OpenClash 全功能参考
├── LICENSE
└── README.md
```

## 工作原理

```
pi 加载 SKILL.md（只读描述）
        │
        ├─ doctor  → 未配置 → 引导用户提供 IP/用户/密码
        │                    → setup 生成密钥 + 部署公钥 + 验证
        │                    → 保存到 ~/.config/openclash-mgmt/
        │
        └─ 已配置 → oc.py run/probe/push/pull  ← 密钥免密 SSH
```

`oc.py` 会自动处理 Windows + Git-Bash 的路径问题：

- MSYS 会把远端路径 `/root/x` 改写成 `C:/Program Files/Git/root/x` → 自动还原
- Bash 的 `/tmp` 在 Windows Python 中不可访问 → 自动映射到真实 TEMP 目录

## 安全说明

- 仓库**不含任何凭据**。`.gitignore` 排除了 `config.json`、`.oc_creds.json`、私钥等。
- `setup` 默认生成密钥并部署公钥，**不保存密码**。
- 若需明文密码模式（不推荐）：`setup --password 'xxx' --no-key`。
- 私钥位于 `~/.config/openclash-mgmt/id_ed25519`，权限 600。
- 公钥写入路由器 `/etc/dropbear/authorized_keys`（权限 600）。

## 已知限制

- 仅支持 OpenWrt / iStoreOS（`dropbear` 或 OpenSSH 均可）。
- 需要 Python + paramiko 运行环境。
- 首次配置需要一次密码（用于部署公钥）；此后免密。

## License

MIT
