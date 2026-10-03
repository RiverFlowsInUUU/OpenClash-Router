# openclash-router

一个 [pi](https://github.com/badlogic/pi-mono) **Agent Skill**：通过 SSH 操作 OpenWrt / iStoreOS 路由器上的 **OpenClash**。

**它聚焦「操作流程」** —— 环境准备、连接配置、安全改配置的规程。
OpenClash 自身的功能知识（选项含义、防火墙链、覆写语法）**引用官方知识库**，不做会过期的副本。

## 设计原则

| 本技能负责 | 交给官方文档 |
|-----------|------------|
| 自动安装依赖（paramiko / cryptography） | 某个 UCI 选项是什么意思 |
| 自动配置 SSH 免密连接 | 防火墙链怎么建 |
| **安全修改配置的规程**（备份/校验/回滚） | 覆写模块语法 |
| 环境层面的坑（apk 死锁、iStoreOS 组件依赖） | Mihomo 协议参数 |

三条来自优秀 skill 的实践：

1. **脚本当黑盒用** —— `oc.py` 有 600+ 行，`SKILL.md` 明确告诉模型
   “别读源码，用 `--help`”。因此 `--help` 写得自解释（含示例）。
2. **领域知识只引用不复制** —— 官方文档会更新，本地副本会过期。技能里给出
   抓取命令，让模型当场拉最新的。
3. **解释 instead of 命令** —— 说明“为什么要先校验再替换”（因为核心起不来用户就断网），
   比堆一堆大写 MUST 更有效。

> 📖 领域知识请看官方：[OpenClash 用户指南 SKILL.md](https://github.com/vernesong/OpenClash/blob/master/.github/skills/openclash-user-guide/SKILL.md)

## 特性

- **依赖自动安装** —— 缺 `paramiko` 时自动 `pip install`（依次尝试普通 / `--user` / `--break-system-packages`）。
- **首次使用自动引导** —— 检测未配置 → 索取 IP/用户/密码 → 生成密钥、部署公钥、验证 → 之后永久免密。
- **凭据与技能分离** —— 技能通用可分享；连接信息存 `~/.config/openclash-mgmt/`，绝不进仓库。
- **跨平台路径处理** —— 自动兼容 Windows + Git-Bash 的路径转换。
- **CI 把关** —— frontmatter 合规、无凭据泄露、无 CRLF、无过期副本。

## 安装

```bash
git clone https://github.com/RiverFlowsInUUU/openclash-router.git ~/.pi/agent/skills/openclash-router
```

也可放项目级 `.pi/skills/`，或 pi 支持的 `~/.agents/skills/`。

## 使用

### 第一步：环境自检

```bash
SKILL=~/.pi/agent/skills/openclash-router
python $SKILL/scripts/oc.py doctor
```

依赖缺失会自动安装。也可显式执行：

```bash
python $SKILL/scripts/oc.py bootstrap
```

### 第二步：配置连接（仅首次）

```bash
# 交互式（密码不进 shell 历史，推荐）
python $SKILL/scripts/oc.py setup

# 非交互式
python $SKILL/scripts/oc.py setup --host 192.168.1.1 --user root --password 'xxx'
```

`setup` 会自动：用密码连一次 → 生成 ed25519 密钥 → 部署公钥到路由器 →
**用密钥重新验证** → 保存配置（**不含密码**）。之后永久免密。

### 第三步：日常使用

```bash
OC="python ~/.pi/agent/skills/openclash-router/scripts/oc.py"

$OC probe                       # OpenClash 状态总览
$OC run "uci show openclash"    # 执行远端命令
$OC push ./proxy.yaml /tmp/      # 上传
$OC pull /etc/openclash/config/proxy.yaml ./   # 下载
$OC show-config                 # 查看配置（密码隐藏）
$OC forget -y                   # 删除配置
```

在 pi 里说人话也行：

- "帮我给软路由加个节点"
- "为什么这个域名走了直连"
- "路由器内存占用怎么样，有能清的吗"
- "OpenClash 起不来了，帮我看看"

## 命令一览

| 命令 | 作用 |
|------|------|
| `doctor` | 环境自检 + 引导配置 |
| `bootstrap` | 安装/检查本地依赖 |
| `setup` | 配置连接（生成并部署密钥） |
| `probe` | OpenClash 运行状态总览 |
| `run "<cmd>"` | 执行远端命令 |
| `push` / `pull` | 上传 / 下载文件 |
| `show-config` | 显示配置（隐藏密码） |
| `forget` | 删除配置 |

## 目录结构

```
.
├── SKILL.md                     # 技能说明（pi 读取，<500 行）
├── scripts/oc.py                # 管理工具（设计为黑盒调用，用 --help 看用法）
├── .github/workflows/ci.yml     # CI
├── README.md
└── LICENSE
```

> `SKILL.md` 里的每一条命令都可以直接复制执行；`--help` 带完整示例，
> 不需要阅读 `oc.py` 源码。

## 安全

- 仓库**不含任何凭据**；CI 每次扫描敏感文件与令牌模式。
- `setup` 默认生成密钥、部署公钥，**不保存密码**。
- 私钥/配置位于 `~/.config/openclash-mgmt/`，权限 600。
- 明文密码模式（不推荐）：`setup --password 'xxx' --no-key`。

## 环境要求

- Python ≥ 3.8（依赖自动安装）
- 路由器：OpenWrt / iStoreOS，支持 dropbear 或 OpenSSH
- 首次配置需一次 SSH 密码；此后免密

## 已知限制

- 仅支持 OpenWrt 系（其他 Linux 发行版的 SSH 路径可能不同）。
- 首次连接需要密码。

## License

MIT
