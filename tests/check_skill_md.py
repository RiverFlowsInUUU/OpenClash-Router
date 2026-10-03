#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""闸门 · SKILL.md 合规性

检查：
  S1  frontmatter 存在，且含 name / description
  S2  name 符合 Agent Skills 规范（小写字母/数字/单连字符，<=64）
  S3  description 非空且 <=1024 字符
  S4  SKILL.md 行数 <= 500（渐进披露原则）
  S5  SKILL.md 引用的 oc.py 子命令真实存在（AST 提取，不依赖 paramiko）
  S6  SKILL.md 索引的 reference/*.md 都存在（防索引漂移）
  S7  SKILL.md 声称的 oc.py 行数与实际一致（防文档漂移）

退出码：0=过 / 1=判负 / 2=环境不达标 / 3=SKIP
"""
import ast
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "SKILL.md")
OC = os.path.join(ROOT, "scripts", "oc.py")

NAME_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
MAX_LINES = 500
MAX_DESC = 1024
LINE_CLAIM_TOLERANCE = 50


def oc_subcommands(path):
    """从 oc.py 源码 AST 提取所有 add_parser("<name>") 的子命令名。

    用 AST 而非运行 --help：避免为了检查语法而引入 paramiko 依赖。
    """
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except Exception:
        return None
    names = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_parser"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            names.add(node.args[0].value)
    return names


def main():
    fails = []
    warns = []

    if not os.path.isfile(SKILL):
        print("ENV   SKILL.md 不存在")
        return 2

    text = open(SKILL, encoding="utf-8").read()

    # S1 frontmatter
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        print("FAIL  S1 缺少 YAML frontmatter（需以 --- 包裹）")
        return 1
    fm = m.group(1)
    name_m = re.search(r"^name:\s*(\S+)\s*$", fm, re.M)
    desc_m = re.search(r"^description:\s*(.+)$", fm, re.M)
    if not name_m or not desc_m:
        print("FAIL  S1 frontmatter 缺 name 或 description")
        return 1
    print("OK    S1 frontmatter 完整")

    # S2 name
    name = name_m.group(1)
    if not NAME_RE.fullmatch(name) or len(name) > 64:
        fails.append("S2 name 违规: %r（只允许小写字母/数字/单连字符，<=64）" % name)
    else:
        print("OK    S2 name=%s（%d 字符）" % (name, len(name)))

    # S3 description
    desc = desc_m.group(1).strip()
    if not desc or len(desc) > MAX_DESC:
        fails.append("S3 description 长度 %d（需 1..%d）" % (len(desc), MAX_DESC))
    else:
        print("OK    S3 description（%d 字符）" % len(desc))

    # S4 行数
    lines = text.count("\n") + 1
    if lines > MAX_LINES:
        fails.append("S4 SKILL.md %d 行 > %d（应外置到 reference/）" % (lines, MAX_LINES))
    else:
        print("OK    S4 SKILL.md %d 行（<= %d）" % (lines, MAX_LINES))

    # S5 子命令引用
    subs = oc_subcommands(OC)
    if subs is None:
        warns.append("S5 无法解析 oc.py（跳过子命令检查）")
    else:
        used = set(re.findall(r'oc\.py"?\s+([a-z][a-z-]+)', text))
        used |= set(re.findall(r'\$OC\s+([a-z][a-z-]+)', text))
        used -= {"scripts"}
        unknown = sorted(c for c in used if c not in subs)
        if unknown:
            fails.append("S5 SKILL.md 引用了不存在的子命令: %s（实际: %s）"
                         % (", ".join(unknown), ", ".join(sorted(subs))))
        else:
            print("OK    S5 引用的 %d 个子命令都存在" % len(used))

    # S6 reference 索引存在
    refs = set(re.findall(r"\((reference/[^)\s#]+\.md)\)", text))
    missing = sorted(r for r in refs if not os.path.isfile(os.path.join(ROOT, r)))
    if missing:
        fails.append("S6 SKILL.md 索引了不存在的文件: %s" % ", ".join(missing))
    else:
        print("OK    S6 索引的 %d 个 reference 文件都存在" % len(refs))

    # S7 行数声称一致
    claim = re.search(r"它有约\s*(\d+)\s*行", text)
    if claim and os.path.isfile(OC):
        actual = sum(1 for _ in open(OC, encoding="utf-8"))
        claimed = int(claim.group(1))
        if abs(claimed - actual) > LINE_CLAIM_TOLERANCE:
            fails.append("S7 SKILL.md 声称 oc.py %d 行，实际 %d 行（偏差 %d）"
                         % (claimed, actual, abs(claimed - actual)))
        else:
            print("OK    S7 行数声称一致（声称 %d / 实际 %d）" % (claimed, actual))
    else:
        warns.append("S7 SKILL.md 未声称 oc.py 行数（跳过）")

    for w in warns:
        print("WARN  " + w)
    if fails:
        for f in fails:
            print("FAIL  " + f)
        print("\n判负：%d 项" % len(fails))
        return 1
    print("\n通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
