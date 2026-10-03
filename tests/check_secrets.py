#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""闸门 · 凭据泄露扫描

这是**公开仓库**。AI 在改配置 / 调试时最容易把真实凭据粘进仓库：
路由器 IP、SSH 密码、API secret、订阅 token、私钥……

一旦推送就不可回收（git 历史改写代价极高）。所以这道闸门是红线。

扫描三类：
  C1  禁止出现的文件名（本地配置 / 私钥）
  C2  熵与模式扫描：token / 私钥 / 已知凭据格式
  C3  上下文扫描：本仓库特有的敏感字段被赋了非占位值

允许的占位写法（白名单）：
  192.0.2.x / 198.51.100.x / 203.0.113.x   §RFC 5737 文档用 IP
  example.com / *.example / localhost       §RFC 2606 保留域名
  REPLACE_WITH_*  / <你的密码> / xxx        §显式占位
  127.0.0.1                                  §本机回环

退出码：0=过 / 1=判负 / 2=环境不达标 / 3=SKIP
"""
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules"}
SKIP_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz", ".woff", ".woff2"}

# C1: 这些文件名不允许出现在仓库里
BANNED_FILES = {
    "config.json",          # 本工具的连接配置
    "id_ed25519",           # 私钥
    "id_rsa",
    ".oc_creds.json",
    "known_hosts",
}

# C2: 高置信度凭据模式（不看上下文也不会误报的）
SECRET_PATTERNS = [
    (r"ghp_[A-Za-z0-9]{30,}", "GitHub personal token"),
    (r"github_pat_[A-Za-z0-9_]{30,}", "GitHub PAT"),
    (r"gho_[A-Za-z0-9]{30,}", "GitHub OAuth token"),
    (r"sk-[A-Za-z0-9]{32,}", "OpenAI-style API key"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "Slack token"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key id"),
    (r"AGE-SECRET-KEY-1[A-Z0-9]{50,}", "age 私钥"),
    (r"-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----", "私钥文件内容"),
    (r"ssh-rsa AAAA[0-9A-Za-z+/]{100,}", "SSH 公钥（可能是真实主机的，慎入）"),
]

# C3: 本仓库特有的敏感上下文 —— 必须有占位/示例特征
#     (字段/键名正则, 说明)
CONTEXT_KEYS = [
    (r"OC_PASS(?:WORD)?\s*[=:]\s*['\"]?([^\s'\"]{6,})", "SSH 密码"),
    (r"password\s*[=:]\s*['\"]([A-Za-z0-9!@#$%^&*_-]{6,})['\"]", "明文密码"),
    (r"secret\s*[=:]\s*['\"]([A-Za-z0-9_-]{8,})['\"]", "API secret"),
    (r"OC_HOST\s*[=:]\s*['\"]?(\d{1,3}(?:\.\d{1,3}){3})", "路由器 IP"),
    (r"\"key\"\s*:\s*\"([^\"]+)\"", "私钥路径（可能含真实用户名）"),
]

# 安全的占位特征：命中任一即视为占位、不判负
PLACEHOLDER_HINTS = [
    "replace", "your_", "your-", "example", "placeholder", "dummy",
    "<", ">", "xxx", "****", "...", "redacted", "fake", "sample",
    "test", "foo", "bar", "changeme", "todo", "占位", "示例", "你的",
]

SAFE_IP = re.compile(r"^(127\.|192\.0\.2\.|198\.51\.100\.|203\.0\.113\.|0\.0\.0\.0|255\.255\.255\.255)")
SAFE_HOST = re.compile(r"^(localhost|.*\.example(\.com)?|example\.(com|org|net))$", re.I)


def is_placeholder(value):
    low = value.lower()
    return any(h in low for h in PLACEHOLDER_HINTS)


def walk_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in SKIP_EXTS:
                continue
            yield os.path.join(dirpath, fn)


def rel(path):
    return os.path.relpath(path, ROOT).replace("\\", "/")


def main():
    fails = []

    # C1 文件名
    for path in walk_files():
        if os.path.basename(path) in BANNED_FILES:
            fails.append("C1 禁止的文件: %s" % rel(path))

    # C2 / C3 内容
    for path in walk_files():
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        name = rel(path)

        # C2 高置信度模式
        for pat, label in SECRET_PATTERNS:
            for m in re.finditer(pat, text):
                val = m.group(0)
                if is_placeholder(val):
                    continue
                line_no = text[:m.start()].count("\n") + 1
                fails.append("C2 %s:%d 疑似 %s" % (name, line_no, label))

        # C3 上下文键
        for pat, label in CONTEXT_KEYS:
            for m in re.finditer(pat, text, re.I):
                val = m.group(1)
                if is_placeholder(val):
                    continue
                # IP 类做 RFC 5737 / 保留地址白名单
                if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", val):
                    if SAFE_IP.match(val):
                        continue
                if SAFE_HOST.match(val):
                    continue
                line_no = text[:m.start()].count("\n") + 1
                fails.append("C3 %s:%d 疑似 %s（值: %s）" % (name, line_no, label, val[:20]))

    if fails:
        for f in fails:
            print("FAIL  " + f)
        print("\n判负：发现 %d 处疑似凭据 —— 公开仓库不可推送" % len(fails))
        print("修法：替换为占位值（REPLACE_WITH_*、192.0.2.x、example.com、<你的密码>）")
        return 1

    n = sum(1 for _ in walk_files())
    print("OK    扫描 %d 个文件，无凭据泄露" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
