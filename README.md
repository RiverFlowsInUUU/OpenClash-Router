<div align="center">

# 🛰️ OpenClash-Router

**让 AI 通过 SSH 管理 OpenWrt / iStoreOS 上的 OpenClash**

轻量 · 判据先行 · 防失联

[![CI](https://github.com/RiverFlowsInUUU/OpenClash-Router/actions/workflows/ci.yml/badge.svg?style=flat-square)](https://github.com/RiverFlowsInUUU/OpenClash-Router/actions/workflows/ci.yml)
[![Agent Skills](https://img.shields.io/badge/Agent_Skills-spec-8250df?style=flat-square)](https://agentskills.io/specification)
[![OpenWrt](https://img.shields.io/badge/OpenWrt-iStoreOS-00b5e2?style=flat-square)](https://istoreos.com/)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776ab?style=flat-square)](#-快速开始)
[![License](https://img.shields.io/badge/License-MIT-dfb317?style=flat-square)](LICENSE)
[![Credentials](https://img.shields.io/badge/Credentials-Zero_In_Repo-2ea043?style=flat-square)](SECURITY.md)

</div>

> 🤖 **AI agent 请从这里开始** → [`SKILL.md`](SKILL.md)：标准流程、五条铁律、领域知识引路、iStoreOS 实测坑。

---

## 💡 这是什么

一个 [Agent Skill](https://agentskills.io/specification)：让 AI 用自然语言帮你管理软路由上的 OpenClash ——
加节点、调分流、配 DNS、排查代理不通、清理内存、管理订阅。

**用起来是这样的：**

```text
你：帮我给软路由加个节点，美国 🇺🇸 的
AI：自动连上路由器 → 侦查现状 → 给你「改什么/怎么回滚」的方案
    你确认 → 完整性检查 → 语法校验 → 备份 → 替换 → 重启 → 等就绪 → 真实链路验证
```

---

## 🎯 设计取向

| | 取向 |
|:--|:--|
| 🚦 **两道闸门** | `deploy-check`（存在/字节数/关键段落）＋ `clash -t`（语法）—— 因为实测 `clash -t` 单独用**不可信**（对不存在的文件、截断的文件都报成功） |
| 🔎 **防失联** | 改 SSH / 防火墙 / DNS 前先想退路；重启后**轮询到就绪**才算完成，不靠"返回了"就宣告成功 |
| 🧭 **领域知识引路** | 按问题层次指向权威源（插件层 / 配置层 / **内核层**，含 Smart 内核），不复制会过期的内容 |
| 🔐 **安全默认** | 生成密钥免密、不存密码、凭据永不进仓库 |
| 🪶 **仓库保持薄** | 只有 1 道凭据闸门；改配置的安全性靠流程（校验＋备份＋验证），不靠堆仓库检查 |

---

## 🧭 领域知识查哪

AI 不会被丢下一个裸链接 —— 它按**问题在哪一层**去对应权威源：

| 层 | 问题类型 | 查哪里 |
|:--|:--|:--|
| **① 插件层** | UCI/LuCI 选项、防火墙链、覆写模块语法、订阅 | [OpenClash 官方知识库](https://github.com/vernesong/OpenClash/blob/master/.github/skills/openclash-user-guide/SKILL.md) |
| **② 配置层** | 字段含义、DNS 策略、分流规则、协议参数 | [Mihomo Wiki](https://wiki.metacubex.one/config/) · [Meta-Docs](https://github.com/MetaCubeX/Meta-Docs/tree/main/docs/config) |
| **③ 内核层** | "为什么这个字段不生效"、行为细节 | 当前内核的源码（见下） |
| **④ 报错/已知问题** | — | [OpenClash Issues](https://github.com/vernesong/OpenClash/issues)（插件侧）· [Mihomo Issues](https://github.com/MetaCubeX/mihomo/issues)（内核侧） |

**内核有两条线**（AI 会先判断用的是哪个）：

| | 上游内核 | **Smart 内核** |
|:--|:--|:--|
| 仓库 | [MetaCubeX/mihomo](https://github.com/MetaCubeX/mihomo/tree/Alpha) | [vernesong/mihomo](https://github.com/vernesong/mihomo/tree/Alpha)（fork，多一个 `smart` 策略组 + LightGBM） |
| 发布 | Releases | [Prerelease-Alpha](https://github.com/vernesong/mihomo/releases)（滚动）+ `LightGBM-Model` |
| 提问 | Issues 可用 | ⚠️ **该仓无 Issues** → 去 OpenClash Issues |

> `smart` 策略组是 OpenClash 作者自制的特性，**上游文档没有** —— 相关字段只能查 Smart 内核源码。

---

## 🚀 快速开始

```bash
# 1. 装进你的 agent 技能目录
git clone https://github.com/RiverFlowsInUUU/OpenClash-Router.git <技能目录>/openclash-router

# 2. 环境自检（依赖缺失会自动安装）
python <技能目录>/scripts/oc.py doctor

# 3. 首次配置连接（交互式，密码不进 shell 历史）
python <技能目录>/scripts/oc.py setup
```

之后对 agent 说人话：

- 「帮我给软路由加个节点」
- 「为什么这个域名走了直连」
- 「OpenClash 起不来了，帮我看看」
- 「路由器内存占用怎么样，有能清的吗」

---

## 📦 安装位置

技能目录名保持 `openclash-router`（与 `SKILL.md` 的 `name` 字段一致）：

| Agent / 约定 | 用户级 | 项目级 |
|:--|:--|:--|
| Agent Skills 标准 | `~/.agents/skills/` | `.agents/skills/` |
| pi | `~/.pi/agent/skills/` | `.pi/skills/` |
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |

> 仓库名 `OpenClash-Router` 是展示用；`name` 字段按规范必须小写。

---

## 🧰 命令一览

```bash
OC="python <技能目录>/scripts/oc.py"

$OC doctor                     # 🩺 环境自检（每次会话第一条）
$OC setup                      # 🔑 配置连接（首次，生成密钥并部署）
$OC probe                      # 📊 OpenClash 状态总览（含内核类型）
$OC safety --config <路径>     # 🛡️ 改前检查：有备份 / 目标是生效配置 / 核心在跑
$OC deploy-check --local <本地> --remote <远端>
                               # ✅ 部署前完整性检查（clash -t 的前置）
$OC run "<cmd>"                # ⚡ 执行远端命令
$OC push / $OC pull            # 📤 上传 / 下载文件
$OC where                      # 📍 打印技能/脚本/配置路径
$OC show-config                # 👁️ 查看配置（密码隐藏）
$OC forget -y                  # 🗑️ 删除配置
```

---

## 🗂️ 结构

```text
.
├── SKILL.md                    # 技能主体（AI 读这个）：流程 / 铁律 / 引路 / 环境坑
├── scripts/
│   └── oc.py                   # 管理工具（黑盒调用，用 --help 看用法）
├── tests/
│   └── check_secrets.py        # 凭据扫描（公开仓红线）
├── .github/workflows/ci.yml    # CI
├── SECURITY.md                 # 凭据纪律
└── LICENSE
```

---

## 🔐 凭据零进仓

工具把连接配置放在**仓库之外**（`~/.config/openclash-mgmt/`，权限 600），
真实 IP / 密码 / token 永不进仓库 —— CI 会扫描。详见 [SECURITY.md](SECURITY.md)。

| 存哪 | 内容 |
|:--|:--|
| `~/.config/openclash-mgmt/config.json` | 连接信息（只记私钥路径，**无密码**） |
| `~/.config/openclash-mgmt/id_ed25519` | 私钥（自动生成） |
| 路由器 `/etc/dropbear/authorized_keys` | 公钥 |

> ⚠️ 本工具会**通过 SSH 修改你的路由器配置**。使用前请确认你有权管理该设备，
> 并知道如何回滚（技能里的流程会自动备份）。

---

## 🌍 环境要求

- Python ≥ 3.8（依赖运行时自动安装：`paramiko`、`cryptography`）
- 路由器：OpenWrt / iStoreOS（dropbear 或 OpenSSH 均可）
- 首次配置需要一次 SSH 密码；此后永久免密

---

<div align="center">

**轻装上阵 · 判据守底**

MIT License © RiverFlowsInUUU

</div>
