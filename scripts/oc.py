#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
oc.py — OpenWrt / OpenClash 管理入口 (通用技能)

子命令:
  doctor              检查环境与配置状态，告诉你还缺什么
  bootstrap           安装/检查本地依赖 (paramiko / cryptography)
  where               打印技能/脚本/配置的绝对路径
  setup               配置连接 (生成密钥 -> 部署公钥 -> 验证 -> 保存)
  run "<cmd>"         在路由器执行命令 (多条用 ; 或换行)
  probe               一览 OpenClash 运行状态 (只读)
  push <本地> <远端>   上传文件
  pull <远端> <本地>   下载文件
  show-config         显示当前配置 (隐藏密码)
  forget              删除已保存的配置

配置位置 (按优先级):
  $OC_CONFIG -> ~/.config/openclash-mgmt/config.json -> <技能目录>/config.json

setup 用法:
  # 交互式 (推荐人工执行)
  python oc.py setup

  # 非交互式
  python oc.py setup --host 192.168.1.1 --user root --password 'xxx'
  python oc.py setup --host 192.168.1.1 --user root --password-file /tmp/pw
  OC_PASSWORD=xxx python oc.py setup --host 192.168.1.1
  python oc.py setup --host 192.168.1.1 --key ~/.ssh/id_ed25519   # 已有私钥

  # 不生成密钥，直接用密码保存 (最省事，但存明文)
  python oc.py setup --host 192.168.1.1 --password 'xxx' --no-key
"""
import argparse
import getpass
import json
import os
import posixpath
import shlex
import subprocess
import sys
import stat


# ---------------------------------------------------------------- 依赖自举
# 本脚本只需要 paramiko。缺失时尝试自动安装；失败则给出可复制的安装命令。
_AUTO_INSTALLED = {}


def _ensure_dep(module, package=None):
    package = package or module
    try:
        return __import__(module)
    except ImportError:
        pass
    if os.environ.get("OC_NO_AUTO_INSTALL"):
        return None
    cmds = [
        [sys.executable, "-m", "pip", "install", "--quiet", package],
        [sys.executable, "-m", "pip", "install", "--user", "--quiet", package],
        [sys.executable, "-m", "pip", "install", "--break-system-packages", "--quiet", package],
    ]
    for c in cmds:
        try:
            r = subprocess.run(c, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
        except Exception:
            continue
        if r.returncode != 0:
            continue
        try:
            import importlib
            importlib.invalidate_caches()
            mod = __import__(module)
            _AUTO_INSTALLED[module] = True
            return mod
        except ImportError:
            continue
    return None


paramiko = _ensure_dep("paramiko")
if paramiko is None:
    sys.stderr.write(
        "缺少 paramiko（自动安装失败）。请手动执行以下任一命令后重试：\n"
        "  python -m pip install paramiko\n"
        "  python -m pip install --user paramiko\n"
        "  python -m pip install --break-system-packages paramiko   # 系统 Python (PEP 668)\n"
    )
    sys.exit(3)

# Windows 控制台默认 GBK，强制 UTF-8 以正确显示中文/emoji
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------- 常量
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_CANDIDATES = []
if os.environ.get("OC_CONFIG"):
    CONFIG_CANDIDATES.append(os.environ["OC_CONFIG"])
CONFIG_CANDIDATES.append(os.path.join(os.path.expanduser("~"), ".config", "openclash-mgmt", "config.json"))
CONFIG_CANDIDATES.append(os.path.join(SKILL_DIR, "config.json"))

KEY_DIR = os.path.join(os.path.expanduser("~"), ".config", "openclash-mgmt")
KEY_PATH = os.environ.get("OC_KEY_PATH") or os.path.join(KEY_DIR, "id_ed25519")

REMOTE_AUTHORIZED = "/etc/dropbear/authorized_keys"


def out(msg=""):
    sys.stdout.write(str(msg) + "\n")
    sys.stdout.flush()


def die(msg, code=2):
    sys.stderr.write("ERROR: " + str(msg) + "\n")
    sys.exit(code)


# ---------------------------------------------------------------- 配置读写
def config_path_for_write():
    """优先级最高且可写的位置"""
    if os.environ.get("OC_CONFIG"):
        return os.environ["OC_CONFIG"]
    return CONFIG_CANDIDATES[1]


def config_path_existing():
    for p in CONFIG_CANDIDATES:
        if p and os.path.isfile(p):
            return p
    return None


def load_config(required=True):
    p = config_path_existing()
    if not p:
        if required:
            die("尚未配置。请先运行:  python oc.py setup\n或先运行 python oc.py doctor 查看状态", 4)
        return {}, None
    try:
        with open(p, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        die("配置文件损坏 %s: %s" % (p, e), 5)
    return cfg, p


def save_config(cfg):
    p = config_path_for_write()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    try:
        os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)   # 600
    except Exception:
        pass
    return p


# ---------------------------------------------------------------- 密钥
def generate_key(path=KEY_PATH):
    """生成 ed25519 密钥对，返回 (私钥路径, 公钥字符串)。

    cryptography 缺失时先尝试自动安装；仍不可用则返回 (None, None)，
    调用方会回退到密码模式。
    """
    _ensure_dep("cryptography")
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        return None, None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    k = ed25519.Ed25519PrivateKey.generate()
    priv = k.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.OpenSSH,
        serialization.NoEncryption(),
    )
    with open(path, "wb") as f:
        f.write(priv)
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass
    pub = k.public_key().public_bytes(
        serialization.Encoding.OpenSSH,
        serialization.PublicFormat.OpenSSH,
    ).decode()
    return path, pub + " openclash-mgmt"


# ---------------------------------------------------------------- SSH
def connect(cfg, prefer_key=None, timeout=20):
    host = cfg.get("host")
    if not host:
        die("配置缺少 host", 4)
    port = int(cfg.get("port") or 22)
    user = cfg.get("user") or "root"

    keyfile = prefer_key if prefer_key is not None else cfg.get("key")
    password = cfg.get("password") or None

    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kw = dict(hostname=host, port=port, username=user, timeout=timeout,
              banner_timeout=timeout, auth_timeout=timeout,
              allow_agent=False, look_for_keys=False)
    if keyfile and os.path.isfile(os.path.expanduser(keyfile)):
        kw["key_filename"] = os.path.expanduser(keyfile)
        if cfg.get("key_passphrase"):
            kw["passphrase"] = cfg["key_passphrase"]
    elif password:
        kw["password"] = password
    else:
        die("配置里既没有可用私钥也没有密码", 4)
    try:
        cli.connect(**kw)
    except paramiko.AuthenticationException:
        die("认证失败：用户名/密码/密钥 不正确", 6)
    except Exception as e:
        die("连接 %s:%s 失败: %s" % (host, port, e), 7)
    return cli


def run_remote(cli, command, timeout=None):
    stdin, stdout, stderr = cli.exec_command(command, timeout=timeout)
    o = stdout.read().decode("utf-8", "replace")
    e = stderr.read().decode("utf-8", "replace")
    rc = stdout.channel.recv_exit_status()
    return rc, o, e


# ---------------------------------------------------------------- doctor
# (名称, 检查命令, 提示文字)  —— 检查命令退出码 0 且输出非空视为通过
PREREQS_REMOTE = [
    ("OpenClash 插件", "ls /etc/init.d/openclash 2>/dev/null", ""),
    ("UCI 配置", "uci show openclash 2>/dev/null | head -1", ""),
    ("核心二进制", "ls /etc/openclash/core/ 2>/dev/null | head -1", ""),
    ("ruby", "command -v ruby", "YAML 生成依赖"),
    ("ruby-yaml", "ruby -ryaml -e 'puts 1' 2>/dev/null", "YAML 解析（Psych）"),
    ("dnsmasq-full", "dnsmasq --version 2>/dev/null | grep -o 'ipset\\|nftset' | head -1",
     "需 full 版（带 ipset/nftset）"),
    ("ip-full", "command -v ip", "策略路由/地址集"),
    ("kmod-tun", "ls /lib/modules/*/tun.ko* 2>/dev/null || grep -qw tun /proc/modules && echo ok",
     "TUN 模式需要"),
]

# 按 fw4/fw3 区分的内核模块
KMOD_NFT = "kmod-nft-tproxy"
KMOD_IPT = "kmod-ipt-tproxy"


def cmd_bootstrap(args):
    """显式安装/检查本地依赖，并报告结果。"""
    out("=" * 62)
    out("OpenClash 管理技能 — 本地依赖")
    out("=" * 62)
    ok = True
    for mod, pkg in (("paramiko", "paramiko"), ("cryptography", "cryptography")):
        m = _ensure_dep(mod, pkg)
        if m is None:
            out("  [x] %-14s 安装失败" % mod)
            ok = False
        else:
            ver = getattr(m, "__version__", "?")
            tag = "本次安装" if _AUTO_INSTALLED.get(mod) else "已可用"
            out("  [v] %-14s %s  (%s)" % (mod, ver, tag))
    out()
    if ok:
        out("依赖就绪。下一步:  python %s setup" % os.path.basename(__file__))
    else:
        out("部分依赖缺失，请手动安装：")
        out("  python -m pip install paramiko cryptography")
    return 0 if ok else 3


def cmd_doctor(args):
    out("=" * 62)
    out("OpenClash 管理技能 — 环境自检")
    out("=" * 62)

    # 1. 本地依赖
    out("\n[1/3] 本地依赖")
    out("  python      : %s" % sys.version.split()[0])
    out("  paramiko    : %s%s" % (paramiko.__version__, "  (已自动安装)" if _AUTO_INSTALLED.get("paramiko") else ""))
    try:
        import cryptography
        out("  cryptography: %s%s" % (cryptography.__version__, "  (已自动安装)" if _AUTO_INSTALLED.get("cryptography") else ""))
        _has_crypto = True
    except ImportError:
        out("  cryptography: 缺失  (仅 setup 生成密钥时需要；可 pip install cryptography)")
        _has_crypto = False

    # 2. 配置
    out("\n[2/3] 连接配置")
    cfg, path = load_config(required=False)
    if not path:
        out("  状态: 尚未配置  ← 需要运行 setup")
        out("  运行:  python %s setup" % os.path.basename(__file__))
        out("\n  需要准备:")
        out("    - 路由器 IP (LAN 地址)")
        out("    - SSH 用户名 (OpenWrt 通常是 root)")
        out("    - SSH 密码 (或现有私钥路径)")
        return 4
    out("  配置文件: %s" % path)
    out("  主机    : %s:%s" % (cfg.get("host"), cfg.get("port") or 22))
    out("  用户    : %s" % (cfg.get("user") or "root"))
    out("  认证    : %s" % ("密钥" if cfg.get("key") else ("密码" if cfg.get("password") else "无!")))

    # 3. 连通性 + 远端环境
    out("\n[3/3] 连通性与远端环境")
    try:
        cli = connect(cfg)
    except SystemExit as e:
        out("  连接失败 (见上方错误)")
        return e.code if isinstance(e.code, int) else 7
    try:
        rc, o, e = run_remote(cli, "cat /proc/sys/kernel/hostname; "
                                   "cat /etc/openwrt_release 2>/dev/null | grep DISTRIB_ID; "
                                   "uname -m; command -v fw4 >/dev/null && echo fw4 || echo fw3")
        out("  主机名  : %s" % o.strip().replace("\n", " | "))
        for name, c, hint in PREREQS_REMOTE:
            rc, o2, _ = run_remote(cli, c)
            passed = rc == 0 and o2.strip()
            mark = "OK " if passed else "!! "
            extra = "" if passed or not hint else "   <- " + hint
            out("  %s %s%s" % (mark, name, extra))

        # 透明代理内核模块（按防火墙后端区分）
        rc, o, _ = run_remote(cli, "command -v fw4 >/dev/null && echo nft || echo ipt")
        kmod_name = KMOD_NFT if o.strip() == "nft" else KMOD_IPT
        rc, o2, _ = run_remote(
            cli, "apk info -e %s 2>/dev/null || opkg list-installed 2>/dev/null | grep -q %s && echo ok" % (kmod_name, kmod_name))
        out("  %s %s%s" % ("OK " if o2.strip() else "!! ", kmod_name, "" if o2.strip() else "   <- UDP 透明代理需要"))

        rc, o3, _ = run_remote(cli, "pidof clash")
        out("  clash 进程: %s" % ("运行中 PID " + o3.strip() if o3.strip() else "未运行"))
    finally:
        cli.close()

    out("\n" + "-" * 62)
    out("自检通过，可以开始使用。")
    out('示例:  python %s run "uci show openclash | head"' % os.path.basename(__file__))
    return 0


# ---------------------------------------------------------------- setup
def _parse_authorized_keys(content, pubkey):
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    if any(pubkey.split()[1] in l for l in lines):
        return None  # 已存在
    lines.append(pubkey)
    return "\n".join(lines) + "\n"


def cmd_setup(args):
    out("=" * 62)
    out("OpenClash 管理技能 — 配置连接")
    out("=" * 62)

    # ---- 收集参数 ----
    host = args.host
    user = args.user
    password = args.password or os.environ.get("OC_PASSWORD")
    if args.password_file:
        with open(args.password_file, encoding="utf-8") as f:
            password = f.read().strip()
    keyfile = os.path.expanduser(args.key) if args.key else None
    port = int(args.port or 22)

    interactive = sys.stdin.isatty() and not host and not keyfile
    if interactive:
        out("\n需要以下信息 (直接回车使用括号内默认值):\n")
        host = input("  路由器 IP [192.168.1.1]: ").strip() or "192.168.1.1"
        user = input("  SSH 用户名 [root]: ").strip() or "root"
        port = int(input("  SSH 端口 [22]: ").strip() or "22")
        use_key = input("  已有私钥? 输入私钥路径 (留空则用密码): ").strip()
        if use_key:
            keyfile = os.path.expanduser(use_key)
        else:
            password = getpass.getpass("  SSH 密码: ")

    if not host:
        die("缺少 --host")
    user = user or "root"

    if keyfile:
        if not os.path.isfile(keyfile):
            die("私钥不存在: %s" % keyfile)
        cfg = {"host": host, "port": port, "user": user, "key": keyfile}
        out("\n[1/2] 用现有私钥测试连接 ...")
        cli = connect(cfg)
        cli.close()
        out("  成功")
        p = save_config(cfg)
        out("\n[2/2] 已保存: %s" % p)
        out("完成，可以直接使用。")
        return 0

    if not password:
        die("缺少密码。用 --password / --password-file / OC_PASSWORD，或交互式运行")

    # ---- 步骤 1: 密码连接 ----
    out("\n[1/4] 用密码连接 %s ..." % host)
    tmp = {"host": host, "port": port, "user": user, "password": password}
    cli = connect(tmp)
    rc, o, _ = run_remote(cli, "cat /etc/openwrt_release 2>/dev/null | grep -E 'DISTRIB_(ID|RELEASE)'; uname -m")
    out("  成功. 远端: %s" % " | ".join(x for x in o.strip().splitlines() if x))
    rc, o, _ = run_remote(cli, "pidof clash >/dev/null && echo yes || echo no")
    out("  OpenClash 运行中: %s" % o.strip())

    if args.no_key:
        cli.close()
        p = save_config(tmp)
        out("\n[2/4] --no-key 已指定，跳过密钥配置")
        out("已保存(密码明文): %s" % p)
        out("完成。")
        return 0

    # ---- 步骤 2: 生成密钥 ----
    out("\n[2/4] 生成 SSH 密钥 ...")
    keypath, pubkey = generate_key(KEY_PATH)
    if not keypath:
        out("  cryptography 不可用，回退到密码模式")
        cli.close()
        p = save_config(tmp)
        out("已保存(密码明文): %s" % p)
        return 0
    out("  私钥: %s" % keypath)
    out("  公钥: %s" % pubkey)

    # ---- 步骤 3: 部署公钥 ----
    out("\n[3/4] 部署公钥到路由器 ...")
    rc, existing, _ = run_remote(cli, "cat %s 2>/dev/null" % REMOTE_AUTHORIZED)
    merged = _parse_authorized_keys(existing, pubkey)
    if merged is None:
        out("  公钥已存在，跳过")
    else:
        sftp = cli.open_sftp()
        with sftp.open(REMOTE_AUTHORIZED, "w") as f:
            f.write(merged)
        sftp.close()
        out("  已写入 %s" % REMOTE_AUTHORIZED)
    run_remote(cli, "chmod 700 /etc/dropbear 2>/dev/null; chmod 600 %s" % REMOTE_AUTHORIZED)
    out("  权限已设为 600")

    # 确认 dropbear 允许公钥认证
    rc, o, _ = run_remote(cli, "uci -q get dropbear.main.PasswordAuth; "
                               "uci -q get dropbear.main.RootPasswordAuth; "
                               "ls /etc/init.d/dropbear >/dev/null && echo has_dropbear")
    if "has_dropbear" not in o:
        out("  提示: 未发现 dropbear 服务，若用 OpenSSH 请确认 ~/.ssh/authorized_keys")
    cli.close()

    # ---- 步骤 4: 验证密钥登录 ----
    out("\n[4/4] 验证密钥登录 ...")
    cfg = {"host": host, "port": port, "user": user, "key": keypath}
    cli2 = connect(cfg)
    rc, o, _ = run_remote(cli2, "echo KEY_OK; uname -n 2>/dev/null || cat /proc/sys/kernel/hostname")
    cli2.close()
    if "KEY_OK" not in o:
        die("密钥登录验证失败，未保存配置。公钥可能未被接受。", 8)
    out("  成功 (免密)")

    p = save_config(cfg)
    out("\n" + "=" * 62)
    out("配置完成! 配置已保存到: %s" % p)
    out("(不包含密码，只记录私钥路径)")
    out("=" * 62)
    out("\n验证:  python %s probe" % os.path.basename(__file__))
    return 0


# ---------------------------------------------------------------- run
def cmd_run(args):
    cfg, _ = load_config()
    cmds = args.command if isinstance(args.command, list) else [args.command]
    cli = connect(cfg)
    try:
        for c in cmds:
            c = _remote_path(c)
            out("$ " + c)
            rc, o, e = run_remote(cli, c, timeout=args.timeout)
            if o:
                sys.stdout.write(o if o.endswith("\n") else o + "\n")
            if e.strip():
                sys.stderr.write("[stderr] " + (e if e.endswith("\n") else e + "\n"))
            if rc != 0:
                out("[exit=%d]" % rc)
            out()
    finally:
        cli.close()
    return 0


# ---------------------------------------------------------------- probe
PROBE_SCRIPT = r'''
echo "### 系统"
cat /etc/openwrt_release 2>/dev/null | grep -E 'DISTRIB_(ID|RELEASE|TARGET|ARCH)'
uname -r
command -v fw4 >/dev/null && echo "firewall: fw4 (nftables)" || echo "firewall: fw3 (iptables)"
printf 'network role: '; [ "$(uci -q get network.wan.disabled)" = "1" ] && echo "旁路由 (WAN disabled)" || echo "主路由"

 echo
echo "### 内存"
free -m | head -2

echo
echo "### OpenClash 运行状态"
printf 'clash PID   : '; pidof clash || echo "(未运行)"
printf '插件启用    : '; uci -q get openclash.@openclash[0].enable
printf '运行模式    : '; uci -q get openclash.@openclash[0].en_mode
printf '代理模式    : '; uci -q get openclash.@openclash[0].proxy_mode
printf '核心类型    : '; uci -q get openclash.@openclash[0].core_type
printf '内核版本    : '; /etc/openclash/clash -v 2>&1 | head -1
printf '配置文件    : '; uci -q get openclash.@openclash[0].config_path
printf 'API 端口    : '; uci -q get openclash.@openclash[0].cn_port

echo
echo "### 端口监听（读实际配置，非默认值）"
D=$(uci -q get openclash.@openclash[0].dns_port); D=${D:-7874}
P=$(uci -q get openclash.@openclash[0].proxy_port); P=${P:-7892}
T=$(uci -q get openclash.@openclash[0].tproxy_port); T=${T:-7895}
H=$(uci -q get openclash.@openclash[0].http_port); H=${H:-7890}
S=$(uci -q get openclash.@openclash[0].socks_port); S=${S:-7891}
M=$(uci -q get openclash.@openclash[0].mixed_port); M=${M:-7893}
C=$(uci -q get openclash.@openclash[0].cn_port); C=${C:-9090}
for port in "$D" "$P" "$T" "$H" "$S" "$M" "$C"; do
  line=$(netstat -tlnp 2>/dev/null | awk -v p="$port" '$4 ~ (":" p "$") {print $4"  "$7; exit}')
  printf '  %-6s %s\n' "$port" "${line:-（未监听）}"
done

echo
echo "### 配置文件（源文件与运行配置）"
CFG=$(uci -q get openclash.@openclash[0].config_path)
[ -n "$CFG" ] && ls -la "$CFG" 2>/dev/null | awk '{print "  源文件: "$5" "$9}'
NAME=$(basename "$CFG" 2>/dev/null)
[ -n "$NAME" ] && ls -la "/etc/openclash/$NAME" 2>/dev/null | awk '{print "  运行:   "$5" "$9}'
ls -la /etc/openclash/config/*.yaml 2>/dev/null | sed 's/^/  /'

echo
echo "### 覆写模块（三关：文件 + UCI 条目 + enable=1）"
ls /etc/openclash/overwrite/ 2>/dev/null | sed 's/^/  文件: /'
uci show openclash 2>/dev/null | grep -E 'config_overwrite\[[0-9]+\]\.(name|enable|config)' | sed 's/^/  UCI:  /'
printf '  日志中处理过的模块数: '; n=$(grep -c 'Overwrite Module' /tmp/openclash.log 2>/dev/null); echo "${n:-0}"

echo
echo "### 防火墙"
if command -v fw4 >/dev/null 2>&1; then
  nft list chain inet fw4 openclash 2>/dev/null | head -3
  printf '  DNS 劫持规则数: '; nft list chain inet fw4 dstnat 2>/dev/null | grep -c 'OpenClash DNS'
  ip rule show 2>/dev/null | grep 0x162 | sed 's/^/  策略路由: /'
else
  iptables -t nat -L openclash -n 2>/dev/null | head -3
  iptables -t nat -L PREROUTING -n 2>/dev/null | grep -c 'OpenClash DNS' | sed 's/^/  DNS 劫持规则数: /'
fi

echo
echo "### 最近启动日志"
tail -6 /tmp/openclash_start.log 2>/dev/null | sed 's/^/  /'

echo
echo "### 最近错误"
tail -80 /tmp/openclash.log 2>/dev/null | grep -E 'level=(error|fatal)' | tail -5 | sed 's/^/  /'
[ -z "$(tail -80 /tmp/openclash.log 2>/dev/null | grep -E 'level=(error|fatal)')" ] && echo "  (无)"
'''


def cmd_probe(args):
    cfg, _ = load_config()
    cli = connect(cfg)
    try:
        rc, o, e = run_remote(cli, PROBE_SCRIPT, timeout=60)
        sys.stdout.write(o)
        if e.strip():
            sys.stderr.write("[stderr] " + e + "\n")
    finally:
        cli.close()
    return 0


# ---------------------------------------------------------------- transfer
def _local_path(p):
    """把 Git-Bash/MSYS 风格的本地路径转成 Windows 可识别路径。

    Windows 上 Python 无法打开字面量 '/tmp/x' 或 '/c/Users/x'。
    这里按模式转换（不依赖路径是否存在），因为目标文件可能尚未创建。
    """
    if os.name != "nt" or not p:
        return p

    q = p.replace("/", os.sep)
    # /tmp/... -> 真正的 Windows 临时目录（MSYS 的 /tmp 是个虚拟挂载）
    for root in (os.environ.get("TEMP"), os.environ.get("TMP"),
                 os.path.expanduser("~/AppData/Local/Temp")):
        if root and (q == os.sep + "tmp" or q.startswith(os.sep + "tmp" + os.sep)):
            rest = q[len(os.sep + "tmp"):].lstrip(os.sep)
            return os.path.join(root, rest) if rest else root
    # /c/Users/... -> C:/Users/...
    if len(q) >= 2 and q[0] == os.sep and q[1].isalpha() and (len(q) == 2 or q[2] == os.sep):
        return q[1].upper() + ":" + q[2:]
    return q if os.sep in q or os.sep in p else p


def _remote_path(p):
    """还原 Git-Bash/MSYS 对远端路径的自动转换。
    MSYS 会把 '/root/x' 改成 'C:/Program Files/Git/root/x'，需逆转回 '/root/x'。
    只对纯路径生效，含空格的命令不做改写。
    """
    if not p:
        return p
    q = p.replace("\\", "/")
    low = q.lower()
    for prefix in ("c:/program files/git/", "c:/program files (x86)/git/",
                   "c:/msys64/", "c:/cygwin64/", "c:/cygwin/"):
        if low.startswith(prefix):
            tail = q[len(prefix):]
            # 只有看起来像远端路径时才还原（避免吞掉真实命令）
            if tail.startswith(("root/", "etc/", "tmp/", "usr/", "var/", "opt/",
                                "home/", "mnt/", "www/", "lib/", "bin/", "sbin/",
                                "proc/", "sys/", "dev/")):
                return "/" + tail
    return p


def cmd_push(args):
    cfg, _ = load_config()
    local = _local_path(args.local)
    remote = _remote_path(args.remote)
    if not os.path.isfile(local):
        die("本地文件不存在: %s" % args.local, 9)
    cli = connect(cfg)
    try:
        sftp = cli.open_sftp()
        sftp.put(local, remote)
        sftp.close()
        out("已上传: %s -> %s" % (local, remote))
        rc, o, _ = run_remote(cli, "ls -la %s" % shlex.quote(remote))
        out(o.rstrip())
    finally:
        cli.close()
    return 0


def cmd_pull(args):
    cfg, _ = load_config()
    remote = _remote_path(args.remote)
    cli = connect(cfg)
    try:
        local = _local_path(args.local)
        if local.endswith(("/", os.sep)):
            os.makedirs(local, exist_ok=True)
            local = os.path.join(local, posixpath.basename(remote))
        d = os.path.dirname(os.path.abspath(local))
        if d:
            os.makedirs(d, exist_ok=True)
        sftp = cli.open_sftp()
        sftp.get(remote, local)
        sftp.close()
        out("已下载: %s -> %s (%d 字节)" % (remote, local, os.path.getsize(local)))
    finally:
        cli.close()
    return 0


# ---------------------------------------------------------------- misc
def cmd_where(args):
    """打印本脚本与技能目录的绝对路径（供 agent 定位用）。"""
    out("技能目录 : %s" % SKILL_DIR)
    out("脚本     : %s" % os.path.abspath(__file__))
    cp = config_path_existing()
    out("配置文件 : %s" % (cp or "(尚未配置)"))
    return 0


def cmd_show_config(args):
    cfg, p = load_config()
    safe = dict(cfg)
    if safe.get("password"):
        safe["password"] = "<已设置，%d 字符>" % len(safe["password"])
    out("配置文件: %s" % p)
    out(json.dumps(safe, indent=2, ensure_ascii=False))
    return 0


def cmd_forget(args):
    p = config_path_existing()
    if not p:
        out("没有已保存的配置")
        return 0
    if not args.yes:
        ans = input("确定删除 %s ? [y/N] " % p).strip().lower()
        if ans not in ("y", "yes"):
            out("已取消")
            return 1
    os.remove(p)
    out("已删除: %s" % p)
    return 0


# ---------------------------------------------------------------- main
def main():
    epilog = """\
示例:
  # 环境自检（第一条命令总是它）
  python oc.py doctor

  # 首次配置连接（交互式，密码不经过 shell 历史）
  python oc.py setup
  # 非交互式
  python oc.py setup --host 192.168.1.1 --user root --password 'xxx'
  # 用已有私钥
  python oc.py setup --host 192.168.1.1 --key ~/.ssh/id_ed25519

  # 看 OpenClash 状态
  python oc.py probe

  # 执行远端命令（可多条，用 ; 分隔）
  python oc.py run "uci show openclash | head"
  python oc.py run "pidof clash; uptime"

  # 上传 / 下载
  python oc.py push ./proxy.yaml /tmp/proxy.yaml
  python oc.py pull /etc/openclash/config/proxy.yaml ./proxy.yaml

  改配置流程（重要）: 先用 clash -t 校验再替换，详见 SKILL.md
  python oc.py run "/etc/openclash/clash -t -d /etc/openclash -f /tmp/new.yaml"

路径无需处理: 脚本自动兼容 Windows + Git-Bash 的路径转换。
环境变量: OC_CONFIG 指定配置文件; OC_NO_AUTO_INSTALL=1 禁用依赖自动安装。
"""
    ap = argparse.ArgumentParser(
        prog="oc.py",
        description="OpenWrt / OpenClash 管理入口（通过 SSH）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )
    sub = ap.add_subparsers(dest="cmd", metavar="<命令>")

    sub.add_parser("doctor", help="环境自检（依赖 + 连接 + 远端环境）——每次会话第一条命令")
    sub.add_parser("bootstrap", help="安装/检查本地依赖 (paramiko, cryptography)")
    sub.add_parser("where", help="打印技能/脚本/配置的绝对路径")
    sub.add_parser("probe", help="一览 OpenClash 运行状态（系统/内存/模式/端口/配置/防火墙/日志）")

    s = sub.add_parser("setup", help="配置连接（生成并部署密钥，之后免密）")
    s.add_argument("--host", help="路由器 IP，如 192.168.1.1")
    s.add_argument("--port", help="SSH 端口，默认 22")
    s.add_argument("--user", help="SSH 用户名，OpenWrt 通常为 root")
    s.add_argument("--password", help="SSH 密码（仅首次部署公钥用；建议改用交互式）")
    s.add_argument("--password-file", help="从文件读密码（避免进 shell 历史）")
    s.add_argument("--key", help="使用已有私钥，跳过密码流程")
    s.add_argument("--no-key", action="store_true", help="不生成密钥，保存明文密码（不推荐）")

    r = sub.add_parser("run", help="在路由器执行命令（多条用 ; 分隔）")
    r.add_argument("command", nargs="+", help="要执行的命令")
    r.add_argument("--timeout", type=int, default=None, help="超时秒数（默认不限）")

    pu = sub.add_parser("push", help="上传本地文件到路由器")
    pu.add_argument("local", help="本地文件路径")
    pu.add_argument("remote", help="远端目标路径")

    pl = sub.add_parser("pull", help="从路由器下载文件到本地")
    pl.add_argument("remote", help="远端文件路径")
    pl.add_argument("local", help="本地目标路径")

    sub.add_parser("show-config", help="显示当前连接配置（密码已隐藏）")

    f = sub.add_parser("forget", help="删除已保存的连接配置")
    f.add_argument("-y", "--yes", action="store_true", help="不询问直接删除")

    args = ap.parse_args()
    if not args.cmd:
        ap.print_help()
        return 1

    handlers = {
        "doctor": cmd_doctor,
        "bootstrap": cmd_bootstrap,
        "where": cmd_where,
        "setup": cmd_setup,
        "run": cmd_run,
        "probe": cmd_probe,
        "push": cmd_push,
        "pull": cmd_pull,
        "show-config": cmd_show_config,
        "forget": cmd_forget,
    }
    return handlers[args.cmd](args) or 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
