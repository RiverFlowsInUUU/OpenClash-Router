#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""闸门 · 一键聚合（动线收尾用）

把 tests/ 下所有闸门并行跑一遍，只输出一张汇总表；红的才展开尾部。

为什么存在：AI 逐条调用闸门 = 多次工具调用 + 多段输出折进上下文，
且漏跑任何一条都算事故。这里一条命令、一段输出看完结论。

用法：
    python tests/verify_all.py            # 全量，全绿才 exit 0
    python tests/verify_all.py -v         # 无论红绿都展开每个闸门输出
    python tests/verify_all.py --index    # 只列闸门清单，不跑

退出码（全仓统一）：
    0 = 判据全过 ｜ 1 = 有判负 ｜ 2 = 前置环境不达标 ｜ 3 = SKIP（未验证）
    聚合时：任一闸门 1 或 2 → 本脚本 1；全部 0 或 3 → 0（3 以 ⚠️ 明示）

与 CI 同源：.github/workflows/ci.yml 跑同一组闸门。改一侧必须同步另一侧。
"""
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable or "python"

# 闸门清单（与 ci.yml 同源）
GATES = [
    ("SKILL.md 合规", ["tests/check_skill_md.py"]),
    ("凭据扫描", ["tests/check_secrets.py"]),
    ("可移植性", ["tests/check_portability.py"]),
    ("oc.py 自检", ["scripts/oc.py", "bootstrap"]),
]

CODE_LABEL = {0: "通过", 1: "判负", 2: "环境", 3: "跳过"}


def run_one(name, args):
    t0 = time.time()
    cmd = [PY] + [os.path.join(ROOT, a) if a.endswith(".py") else a for a in args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=180, cwd=ROOT)
        out = (r.stdout or "") + (r.stderr or "")
        return name, r.returncode, out, time.time() - t0
    except subprocess.TimeoutExpired:
        return name, 2, "闸门超时（>180s）", time.time() - t0
    except Exception as e:
        return name, 2, "闸门无法执行: %s" % e, time.time() - t0


def main():
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    if "--index" in sys.argv:
        for n, a in GATES:
            print("%-16s %s" % (n, " ".join(a)))
        return 0

    with ThreadPoolExecutor(max_workers=len(GATES)) as ex:
        results = list(ex.map(lambda g: run_one(*g), GATES))

    print("=" * 64)
    print("收尾闸门 · %d 道" % len(GATES))
    print("=" * 64)
    worst = 0
    for name, code, out, secs in results:
        label = CODE_LABEL.get(code, "未知(%d)" % code)
        mark = "OK  " if code == 0 else ("SKIP" if code == 3 else "FAIL")
        print("  %-6s %-16s %-6s %5.1fs" % (mark, name, label, secs))
        if code in (1, 2):
            worst = 1
        if verbose or code not in (0,):
            tail = "\n".join(out.strip().splitlines()[-12:])
            for line in tail.splitlines():
                print("         | " + line)
    print("=" * 64)
    if worst:
        print("结论：有闸门未通过 —— 先修再继续")
    else:
        skipped = [n for n, c, _, _ in results if c == 3]
        if skipped:
            print("结论：全绿，但有跳过项（未验证 ≠ 通过）: %s" % ", ".join(skipped))
        else:
            print("结论：全绿")
    return worst


if __name__ == "__main__":
    sys.exit(main())
