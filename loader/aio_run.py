#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aio_run.py — all-in-one 单会话挂载器（CTF 沙箱版）

用法:
    python aio_run.py [script.js]          # 默认 hooks/sunrun_inject.js

做什么:
    1. 自动发现支付宝主进程 pid，attach 并加载注入脚本；
    2. 自动发现 sandboxed_privilege_process 子进程 —— 小程序容器可能跑在
       这个进程里（冷启动后尤其常见）。症状是"计时在走但轨迹不动"，
       所以这里对子进程再挂一次同样的脚本（hooks 类不存在时会安静跳过）。

注意:
    - 仅用于 CTF / 授权沙箱环境，详见 README 免责声明。
    - 失败不重连（attach 后多次重复注入容易触发目标自毁）。
"""
import frida
import subprocess
import sys
import time

SERIAL = "127.0.0.1:16384"          # MuMu 模拟器 adb 地址，按需修改
FRIDA_PORT = 39571                   # Florida frida-server 监听端口


def adb(*args):
    return subprocess.run(["adb", "-s", SERIAL, *args],
                          capture_output=True, text=True).stdout


def alipay_pids():
    """返回 (主进程pid, [子进程pid列表])"""
    out = adb("shell", "ps -A")
    main, children = None, []
    for line in out.splitlines():
        if "AlipayGphone" not in line:
            continue
        parts = line.split()
        pid, name = int(parts[1]), parts[-1]
        if name == "com.eg.android.AlipayGphone":
            main = pid
        elif "sandboxed" in name or "gpu" in name:
            children.append(pid)
    return main, children


def on_msg(tag):
    def handler(m, d):
        if m["type"] == "send":
            print(m["payload"], flush=True)
        elif m["type"] == "error":
            print("[%s][script-error] %s" % (tag, str(m.get("description"))[:300]), flush=True)
    return handler


def attach_and_load(dev, pid, src, tag):
    try:
        session = dev.attach(pid)
    except Exception as e:
        print("[%s] attach %d failed: %s" % (tag, pid, e), flush=True)
        return None
    script = session.create_script(src)
    script.on("message", on_msg(tag))
    try:
        script.load()
    except Exception as e:
        print("[%s] load %d failed: %s" % (tag, pid, e), flush=True)
        return None
    print("[%s] loaded into pid=%d" % (tag, pid), flush=True)
    return script


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "hooks/sunrun_inject.js"
    with open(path, encoding="utf-8") as f:
        src = f.read()

    main_pid, children = alipay_pids()
    if not main_pid:
        print("[!] AlipayGphone 主进程未找到"); sys.exit(1)
    print("[*] main=%d children=%s" % (main_pid, children), flush=True)

    dev = frida.get_device_manager().add_remote_device("127.0.0.1:%d" % FRIDA_PORT)

    scripts = []
    s = attach_and_load(dev, main_pid, src, "main")
    if s:
        scripts.append(s)
    for cpid in children:                    # sandboxed 子进程：加载失败=容器不在该进程，属正常
        s = attach_and_load(dev, cpid, src, "sbx%d" % cpid)
        if s:
            scripts.append(s)

    if not scripts:
        print("[!] 没有任何一次挂载成功"); sys.exit(1)
    print("[*] active sessions: %d — 单会话原则：之后不要再 attach" % len(scripts), flush=True)

    probe = scripts[0]
    while True:
        time.sleep(20)
        alive = 0
        for s in scripts:
            try:
                print("[status]", s.exports_sync.status(), flush=True)
                alive += 1
            except Exception:
                pass
        if alive == 0:
            print("[!] 全部会话失效 — 不重试，检查目标是否自毁", flush=True)
            break


if __name__ == "__main__":
    main()
