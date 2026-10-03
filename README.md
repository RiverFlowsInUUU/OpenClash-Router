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

> 🤖 **AI agent 请从这里开始** → [`SKILL.md`](SKILL.md)：一条标准流程、五条铁律、iStoreOS 实测坑。

---

## 💡 这是什么

一个 [Agent Skill](https://agentskills.io/specification)：让 AI 用自然语言帮你管理软路由上的 OpenClash ——
加节点、调分流、配 DNS、排查代理不通、清理内存、管理订阅。

**用起来是这样的：**

```text
你：帮我给软路由加个节点，美国 🇺🇸 的
AI：（自动连上路由器 → 侦查现状 → 给方案 → 你确认 → 校验 → 替换 → 验证 → 汇报回滚方式）
```

**设计取向：轻量实用。**

| | 取向 |
|:--|:--|
| 🎯 **一条流程** | 侦查 → 改 → 校验 → 备份替换 → 验证 —— 不会让你在文档里迷路 |
| 📖 **知识不复制** | OpenClash 选项含义[引用官方文档](https://github.com/vernesong/OpenClash/blob/master/.github/skills/openclash-user-guide/SKILL.md)，不留会过期的副本 |
| 🛡️ **防失联** | 改 SSH / 防火墙 / DNS 前先想退路；回滚靠路由器上的备份文件，不是 git |
| 🔐 **安全默认** | 生成密钥免密、不存密码、凭据永不进仓库 |

> 仓库刻意保持**薄**：改配置的安全性靠 `clash -t` 校验 + 备份回滚，不靠一堆仓库闸门。

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
$OC probe                      # 📊 OpenClash 状态总览
$OC safety --config <路径>     # 🛡️ 改前检查：有备份 / 目标对 / 核心在跑
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
├── SKILL.md                    # 技能主体（AI 读这个）：流程 / 铁律 / 环境坑 / 退出码
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
