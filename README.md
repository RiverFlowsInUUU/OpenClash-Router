# OpenClash-Router

通过 SSH 操作 OpenWrt / iStoreOS 路由器上的 **OpenClash** —— 一个轻量的 **Agent Skill**。

> 🤖 **AI agent 请从这里开始** → [`SKILL.md`](SKILL.md)：标准流程、铁律、环境坑。

---

## 这是什么

让 AI 用自然语言帮你管理软路由上的 OpenClash（加节点、调分流、配 DNS、
排查代理不通、清理内存）。设计取向是**轻量实用**：

- **一条流程走天下**：侦查 → 改 → 校验 → 备份替换 → 验证
- **领域知识不复制**：OpenClash 选项含义引用[官方文档](https://github.com/vernesong/OpenClash/blob/master/.github/skills/openclash-user-guide/SKILL.md)
- **防失联**：改 SSH/防火墙/DNS 前先想退路；回滚靠路由器上的备份文件
- **安全默认**：生成密钥免密、不存密码、凭据不进仓库

仓库刻意保持**薄**：改配置靠 `clash -t` 校验和备份回滚，不靠仓库闸门。

---

## 快速开始

```bash
git clone https://github.com/RiverFlowsInUUU/OpenClash-Router.git <技能目录>/openclash-router

python <技能目录>/scripts/oc.py doctor     # 依赖缺失会自动装
python <技能目录>/scripts/oc.py setup      # 首次配置（交互式）
```

之后对 agent 说人话：

- "帮我给软路由加个节点"
- "为什么这个域名走了直连"
- "OpenClash 起不来了，帮我看看"

---

## 安装位置

技能目录名保持 `openclash-router`（与 `SKILL.md` 的 `name` 一致）：

| Agent / 约定 | 用户级 | 项目级 |
|-------------|--------|--------|
| Agent Skills 标准 | `~/.agents/skills/` | `.agents/skills/` |
| pi | `~/.pi/agent/skills/` | `.pi/skills/` |
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |

> 仓库名 `OpenClash-Router` 是展示用；`name` 字段规范要求小写。

---

## 命令

```bash
OC="python <技能目录>/scripts/oc.py"

$OC doctor          # 环境自检
$OC setup           # 配置连接（首次）
$OC probe           # OpenClash 状态总览
$OC safety --config <路径>   # 改前检查：备份/目标/核心
$OC run "<cmd>"     # 执行远端命令
$OC push / pull     # 上传 / 下载
$OC where           # 打印路径
$OC show-config     # 查看配置（密码隐藏）
$OC forget -y       # 删除配置
```

---

## 结构

```
.
├── SKILL.md            # 技能主体（AI 读这个）
├── scripts/oc.py       # 管理工具（黑盒调用，用 --help）
├── tests/check_secrets.py   # 凭据扫描（公开仓红线）
├── .github/workflows/ci.yml
├── SECURITY.md
└── LICENSE
```

---

## 凭据存放

工具把配置放在**仓库之外**（`~/.config/openclash-mgmt/`，权限 600），
真实凭据永不进仓库。详见 [SECURITY.md](SECURITY.md)。

---

## 环境要求

- Python ≥ 3.8（依赖自动安装：`paramiko`、`cryptography`）
- 路由器：OpenWrt / iStoreOS（dropbear 或 OpenSSH）
- 首次配置需一次 SSH 密码；此后免密

---

## License

MIT
