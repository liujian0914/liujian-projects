# -*- coding: utf-8 -*-
"""
题库系统 - 桌面启动器
双击后在本机起一个只监听 127.0.0.1 的小服务，再用 Edge/Chrome 的应用窗口模式打开，
看起来就是一个独立 App，没有地址栏。

数据保存在浏览器该地址下的 localStorage 里（地址固定 = 数据不会丢）。
换设备用界面里的「导出进度 / 导入进度」。
"""
import os
import sys
import time
import socket
import threading
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

PORT = 8766
HOST = "127.0.0.1"

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=base_dir(), **kw)

    def log_message(self, *a):
        pass

    def end_headers(self):
        # 允许 PWA / 离线缓存
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def port_open(port):
    s = socket.socket()
    s.settimeout(0.25)
    try:
        return s.connect_ex((HOST, port)) == 0
    finally:
        s.close()


def open_app_window(url):
    for exe in BROWSERS:
        if os.path.exists(exe):
            try:
                os.spawnv(os.P_NOWAIT, exe, [exe, "--app=" + url,
                                             "--window-size=1240,880",
                                             "--no-first-run",
                                             "--no-default-browser-check"])
                return True
            except Exception:
                pass
    return False


def main():
    url = "http://%s:%d/index.html" % (HOST, PORT)

    if port_open(PORT):
        # 已经在跑，直接开窗口
        if not open_app_window(url):
            webbrowser.open(url)
        return

    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()

    time.sleep(0.35)
    if not open_app_window(url):
        webbrowser.open(url)

    # 保持进程存活（关掉网页后再点一次图标即可重开）
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, str(e), "题库系统 启动失败", 0x10)
