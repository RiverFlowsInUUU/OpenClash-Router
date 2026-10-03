#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""闸门 · 可移植性（行尾 / BOM / 编码卫生）

为什么需要：仓库要在 Linux(CI) 与 Windows(用户) 同时工作，
且 oc.py 通过 SSH 把内容推给 Linux 路由器。

  P1  行尾统一 LF（CRLF 会让 shell 脚本在 Linux 上炸）
  P2  无 UTF-8 BOM（BOM 会被 shell/python 当成内容）
  P3  文本文件均为合法 UTF-8
  P4  Python 脚本有 UTF-8 编码声明或纯 ASCII（跨平台安全）
  P5  脚本 print 非 ASCII 时不得裸奔（Windows ACP=936 下会崩溃）
      —— 检测是否调用了 reconfigure(encoding=...) 做保护

退出码：0=过 / 1=判负 / 2=环境不达标 / 3=SKIP
"""
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv"}
TEXT_EXTS = {".py", ".md", ".yml", ".yaml", ".json", ".txt", ".sh", ".cfg", ".ini", ".toml", ""}


def walk():
    for dp, dn, fns in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for fn in fns:
            p = os.path.join(dp, fn)
            if os.path.splitext(fn)[1].lower() in TEXT_EXTS:
                yield p


def rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


def main():
    fails = []
    n = 0
    for path in walk():
        n += 1
        raw = open(path, "rb").read()
        name = rel(path)

        # P2 BOM
        if raw.startswith(b"\xef\xbb\xbf"):
            fails.append("P2 %s 含 UTF-8 BOM" % name)

        # P1 CRLF（仅文本类）
        if b"\r\n" in raw:
            fails.append("P1 %s 含 CRLF 行尾（应为 LF）" % name)

        # P3 UTF-8 合法
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as e:
            fails.append("P3 %s 非合法 UTF-8: %s" % (name, e))
            continue

        # P4/P5 仅 Python
        if name.endswith(".py"):
            has_non_ascii = any(ord(c) > 127 for c in text)
            if has_non_ascii:
                # 有编码声明 或 有 reconfigure 保护
                has_decl = ("# -*- coding: utf-8 -*-" in text
                            or "# coding: utf-8" in text)
                has_reconf = "reconfigure(" in text
                if not (has_decl or has_reconf):
                    fails.append("P4 %s 含非 ASCII 但无编码声明/保护" % name)
            # P5: 若脚本有 print 且无 reconfigure 保护
            if ("print(" in text or "sys.stdout.write" in text) and "reconfigure(" not in text:
                if has_non_ascii:
                    fails.append(
                        "P5 %s 会 print 非 ASCII 但无 reconfigure 保护"
                        "（Windows ACP=936 下 UnicodeEncodeError → 假判负）" % name)

    if fails:
        for f in fails:
            print("FAIL  " + f)
        print("\n判负：%d 项" % len(fails))
        return 1
    print("OK    P1-P5 检查 %d 个文本文件，行尾/BOM/编码均合规" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
