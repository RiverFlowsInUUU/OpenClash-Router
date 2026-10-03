# OpenClash-Router

通过 SSH 操作 OpenWrt / iStoreOS 路由器上的 **OpenClash** —— 一个 **AI 驱动的 Agent Skill 仓**。

> 🤖 **AI agent 请从这里开始** → [`SKILL.md`](SKILL.md)：改配置的动线、六条铁律、闸门怎么跑。

---

## 这是什么

一个 [Agent Skills](https://agentskills.io/specification) 技能包：让 AI 用自然语言帮你管理软路由上的 OpenClash
（加节点、调分流、配 DNS、排查代理不通、清理内存、管理订阅）。

**设计取向：AI 驱动 + 判据守底。**

| 原则 | 做法 |
|------|------|
| **文档即知识库** | 全部操作文档整合在 `SKILL.md` + `reference/`，没有面向人类的 docs |
| **领域知识不复制** | OpenClash 功能知识**引用官方文档**（会更新），不在仓内留会过期的副本 |
| **判据先行** | 六条铁律 + 四态退出码协议；改动前后跑闸门 |
| **凭据零容忍** | 公开仓库，`check_secrets.py` 扫描；真实凭据一律占位值 |
| **安全默认** | 生成密钥免密、不存密码、显式指定配置路径不回退 |

---

## 快速开始

```bash
# 1. 放进你的 agent 技能目录
git clone https://github.com/RiverFlowsInUUU/OpenClash-Router.git <技能目录>/openclash-router

# 2. 环境自检（依赖缺失会自动安装）
python <技能目录>/scripts/oc.py doctor

# 3. 首次配置连接（交互式，密码不进 shell 历史）
python <技能目录>/scripts/oc.py setup
```

之后对 agent 说人话即可：

- "帮我给软路由加个节点"
- "为什么这个域名走了直连"
- "路由器内存占用怎么样，有能清的吗"
- "OpenClash 起不来了，帮我看看"

---

## 安装位置

技能目录名保持 `openclash-router`（与 `SKILL.md` 的 `name` 字段一致）。
常见位置：

| Agent / 约定 | 用户级 | 项目级 |
|-------------|--------|--------|
| Agent Skills 标准 | `~/.agents/skills/` | `.agents/skills/` |
| pi | `~/.pi/agent/skills/` | `.pi/skills/` |
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |

> 仓库名是 `OpenClash-Router`（展示用），技能标识是 `openclash-router`（规范要求小写）。
> 两者不同**不是错误**。

---

## 仓库结构

```
.
├── SKILL.md                     # 技能主体（AI 读这个）：动线 / 铁律 / 按需索引
├── reference/                   # 按需加载的细节
│   ├── pitfalls.md              # 环境坑（apk 死锁、组件隐藏依赖、hotplug…）
│   ├── gates.md                 # 闸门与退出码协议
│   └── tasks.md                 # 具体任务配方
├── scripts/oc.py                # 管理工具（黑盒调用，用 --help 看用法）
├── tests/                       # 闸门
│   ├── check_skill_md.py        # S1-S7
│   ├── check_secrets.py         # C1-C3（红线）
│   ├── check_portability.py     # P1-P5
│   └── verify_all.py            # 一键聚合
├── .github/workflows/ci.yml     # CI（与 verify_all 同源）
├── SECURITY.md
└── LICENSE
```

---

## 命令一览

```bash
OC="python <技能目录>/scripts/oc.py"

$OC doctor          # 环境自检 + 引导配置
$OC setup           # 配置连接（生成并部署密钥）
$OC probe           # OpenClash 状态总览
$OC run "<cmd>"     # 执行远端命令
$OC push / $OC pull # 上传 / 下载
$OC where           # 打印技能/脚本/配置路径
$OC show-config     # 查看配置（密码隐藏）
$OC forget -y       # 删除配置
```

完整用法：`$OC --help`

---

## 闸门（改完必跑）

```bash
python tests/verify_all.py
```

四道闸门并行跑，出一张汇总表：

| 闸门 | 查什么 |
|------|--------|
| SKILL.md 合规 | frontmatter / 长度 / 子命令引用 / 索引一致性 |
| **凭据扫描** | 真实 IP、密码、token、私钥 —— **红线** |
| 可移植性 | 行尾 LF / 无 BOM / 编码保护 |
| oc.py 自检 | 依赖可装、CLI 可跑 |

退出码协议：`0` 通过 / `1` 判负 / `2` 环境不达标 / `3` SKIP。
详见 [`reference/gates.md`](reference/gates.md)。

---

## 环境要求

- Python ≥ 3.8（依赖自动安装：`paramiko`、`cryptography`）
- 路由器：OpenWrt / iStoreOS，dropbear 或 OpenSSH 均可
- 首次配置需一次 SSH 密码；此后免密

---

## License

MIT
