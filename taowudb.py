#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
taowuDB — 一键启动程序。

直接运行即可启动 GUI 管理界面，后端引擎自动启动：

    python taowudb.py                   启动 GUI（默认）
    python taowudb.py --server-only     仅启动后端服务（无 GUI）
    python taowudb.py --cli             启动命令行客户端
    python taowudb.py --init            初始化数据库
    python taowudb.py --check           检查环境
    python taowudb.py --status          查看状态
    python taowudb.py --stop            停止服务
    python taowudb.py --help            查看帮助

架构:
    python taowudb.py
        │
        ├── 1. 启动后端引擎 (Engine)
        ├── 2. 启动 MySQL 协议服务 (后台线程)
        ├── 3. 启动 PyQt GUI (主线程，阻塞)
        └── 4. 关闭 GUI 时自动停止所有服务
"""

import argparse
import os
import sys
import time
import threading
from pathlib import Path

# ── Win32 UTF-8 ──────────────────────────────────────────────
# 使用 backslashreplace 策略: 非法字符显示为 \xNN 而非崩溃或静默替换
# 这样用户可以看清楚是什么字节出了问题，方便诊断
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

# ── 项目路径 ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
# 确保 xuanwu_firewall 的 xwf 包可被导入
_XUANWU_ROOT = PROJECT_ROOT / "xuanwu_firewall"
if _XUANWU_ROOT.exists() and str(_XUANWU_ROOT) not in sys.path:
    sys.path.insert(0, str(_XUANWU_ROOT))

import logging
_log = logging.getLogger("taowudb")
sys.path.insert(0, str(PROJECT_ROOT))


# ==========================================================================
# 统一控制器
# ==========================================================================


class TaowuController:
    """掌管 Engine + Server + GUI 生命周期。

    后端在后台线程运行，GUI 在主线程运行。
    关闭 GUI 时自动停止后端。
    """

    def __init__(self, host="127.0.0.1", port=3306, data_dir="taowu_data", config_path=None):
        self.host = host
        self.port = port
        self.data_dir = data_dir
        self.config_path = config_path
        self.engine = None
        self.server = None
        self._server_thread = None
        self._running = False
        self._lock = threading.RLock()

    # ═══════════════════════════════════════════════════════════
    # 启动 / 停止
    # ═══════════════════════════════════════════════════════════

    def boot(self) -> bool:
        """启动后端引擎."""
        with self._lock:
            if self._running:
                return True
            try:
                from taowu.engine import Engine
                self.engine = Engine(
                    data_dir=self.data_dir,
                    config_path=self.config_path,
                    host=self.host,
                    port=self.port,
                )
                self.engine.boot()
                self._running = True
                return True
            except Exception as e:
                print(f"[taowuDB] 引擎启动失败: {e}")
                return False

    def start_server(self) -> bool:
        """在后台线程启动 MySQL 协议服务."""
        with self._lock:
            if not self._running:
                return False
            if self.server is not None:
                return True
            try:
                from taowu.server import TaowuServer
                self.server = TaowuServer(self.engine)
                self.server.start()
                self._server_thread = threading.Thread(
                    target=self._safe_serve, name="taowu-server", daemon=True
                )
                self._server_thread.start()
                return True
            except Exception as e:
                print(f"[taowuDB] 服务启动失败: {e}")
                return False

    def _safe_serve(self):
        try:
            self.server.serve_forever()
        except Exception as e:
            _log.warning("Server stopped: %s", e)

    def shutdown(self):
        """停止所有服务."""
        with self._lock:
            if self.server:
                try:
                    self.server.shutdown()
                except Exception as e:
                    _log.warning("Error shutting down server: %s", e)
                self.server = None
            if self._server_thread and self._server_thread.is_alive():
                self._server_thread.join(timeout=3)
            if self.engine:
                try:
                    self.engine.shutdown()
                except Exception as e:
                    _log.warning("Error shutting down engine: %s", e)
                self.engine = None
            self._running = False

    @property
    def is_running(self):
        return self._running

    def status_dict(self):
        s = {"running": self._running, "host": self.host, "port": self.port}
        if self.engine and self._running:
            try:
                s["databases"] = self.engine.catalog.database_names
                s["users"] = self.engine.user_manager.user_count
                s["config_sections"] = len(self.engine.config_manager.sections)
                s["config_count"] = len(self.engine.config_manager.list())
                s["version"] = "0.1.0"
                # 防火墙状态
                fw = getattr(self.engine, 'firewall', None)
                if fw is not None:
                    s["firewall"] = fw.stats()
            except Exception as e:
                _log.warning("Error collecting status info: %s", e)
        return s


# ==========================================================================
# GUI 启动器（核心 — 一个入口拉起一切）
# ==========================================================================


def launch_gui(ctrl: TaowuController):
    """启动 PyQt GUI，后端由 ctrl 管理。

    GUI 关闭时自动停止后端。
    """
    try:
        from PySide6.QtWidgets import QApplication, QSplashScreen
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QPixmap, QColor, QFont
    except ImportError:
        print("\n[taowuDB] PySide6 未安装，正在尝试安装...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PySide6", "-q"])
        print("[taowuDB] 安装完成，请重新运行: python taowudb.py")
        return

    # ── Qt Application ──────────────────────────────────────
    app = QApplication(sys.argv)
    app.setApplicationName("taowuDB")
    app.setApplicationVersion("0.1.0")

    # ── 启动画面 ────────────────────────────────────────────
    splash = QSplashScreen()
    splash.setMinimumSize(500, 300)

    from config_gui.utils.theme import LIGHT_THEME
    bg = LIGHT_THEME["background"]
    primary = LIGHT_THEME["primary"]

    splash.setStyleSheet(f"""
        QSplashScreen {{
            background-color: {bg};
            border: 2px solid {primary};
            border-radius: 12px;
        }}
    """)
    splash.showMessage(
        "\n\n  taowuDB v0.1.0\n\n"
        "  正在启动数据库引擎...\n\n"
        f"  数据目录: {ctrl.data_dir}\n"
        f"  监听地址: {ctrl.host}:{ctrl.port}",
        Qt.AlignCenter,
        QColor(primary),
    )
    splash.show()
    app.processEvents()

    # ── 启动后端 ────────────────────────────────────────────
    splash.showMessage(
        "\n\n  taowuDB v0.1.0\n\n"
        "  正在启动存储引擎...",
        Qt.AlignCenter,
        QColor(primary),
    )
    app.processEvents()

    if not ctrl.boot():
        splash.close()
        print("[taowuDB] 后端启动失败")
        return

    splash.showMessage(
        "\n\n  taowuDB v0.1.0\n\n"
        "  正在启动 MySQL 协议服务...",
        Qt.AlignCenter,
        QColor(primary),
    )
    app.processEvents()

    ctrl.start_server()

    splash.showMessage(
        "\n\n  taowuDB v0.1.0\n\n"
        "  正在加载 GUI 界面...",
        Qt.AlignCenter,
        QColor(primary),
    )
    app.processEvents()

    # ── 加载 GUI ────────────────────────────────────────────
    from config_gui.utils.theme import apply_theme
    apply_theme(app, "light")

    from config_gui.ui.main_window import MainWindow
    window = MainWindow(ctrl.engine)
    window.setWindowTitle(f"taowuDB — {ctrl.host}:{ctrl.port}")

    # 关闭窗口时自动停止后端
    def on_close(event):
        splash.show()
        splash.showMessage("\n\n  正在停止服务...", Qt.AlignCenter, QColor(primary))
        app.processEvents()
        ctrl.shutdown()
        splash.close()
        event.accept()

    window.closeEvent = on_close

    splash.close()
    window.show()

    info = ctrl.status_dict()
    print(f"\n  [taowuDB] GUI 已启动")
    print(f"  [taowuDB] 后端: {ctrl.host}:{ctrl.port}")
    print(f"  [taowuDB] 数据库: {len(info.get('databases', []))} 个")
    print(f"  [taowuDB] 用户: {info.get('users', 0)} 个")

    # 防火墙状态
    fw_info = info.get("firewall", {})
    if fw_info:
        fw_mode = fw_info.get("mode", "?")
        fw_rules = fw_info.get("rule_count", 0)
        fw_layers = [k for k, v in fw_info.get("layers", {}).items() if v]
        print(f"  [taowuDB] 🛡️ 玄武防火墙: {fw_mode}模式 | {fw_rules}条规则 | "
              f"层级: {', '.join(fw_layers) if fw_layers else '检测'}")
        print(f"  [taowuDB] 💡 按 Ctrl+Shift+F 或点击工具栏 🏯 打开防火墙控制台")
    else:
        print(f"  [taowuDB] 玄武防火墙: 未安装（透传模式）")

    print(f"  [taowuDB] 关闭 GUI 窗口即可停止所有服务\n")

    sys.exit(app.exec())


# ==========================================================================
# 命令行界面（无 GUI 时用）
# ==========================================================================


def launch_cli(ctrl: TaowuController):
    """启动内置 CLI（无 GUI 时的备选）。"""
    if not ctrl.boot():
        return
    ctrl.start_server()

    from scripts.taowu_cli import TaowuCLI
    cli = TaowuCLI(local=True, host=ctrl.host, port=ctrl.port)
    cli._engine = ctrl.engine
    cli._db = ctrl.engine.current_database or ""
    cli._update_prompt()
    cli.run()
    ctrl.shutdown()


def launch_server_only(ctrl: TaowuController):
    """仅启动后端服务（无 GUI / 无 CLI）。"""
    if not ctrl.boot():
        sys.exit(1)
    ctrl.start_server()

    print(f"\n  [taowuDB] 服务运行中: {ctrl.host}:{ctrl.port}")
    print(f"  [taowuDB] 连接: mysql -h {ctrl.host} -P {ctrl.port} -u root")
    print(f"  [taowuDB] 按 Ctrl+C 停止\n")

    try:
        while ctrl.is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[taowuDB] 收到停止信号...")
    finally:
        ctrl.shutdown()
        print("[taowuDB] 已停止")


def cmd_init(args):
    """初始化数据库."""
    from scripts.init_db import main as init_main
    save_argv = sys.argv
    sys.argv = ["init_db.py"]
    if getattr(args, 'force', False):
        sys.argv.append("--force")
    data_dir = getattr(args, 'data_dir', 'taowu_data')
    sys.argv.extend(["--data-dir", data_dir])
    try:
        init_main()
    finally:
        sys.argv = save_argv


def cmd_check(args):
    """检查环境."""
    print("taowuDB 环境检查")
    print("=" * 55)
    print(f"Python:   {sys.version.split()[0]}")

    for name, mod in [("taowu 引擎", "taowu"), ("config_gui GUI", "config_gui")]:
        try:
            __import__(mod)
            print(f"  {name:20s} [OK]")
        except ImportError:
            print(f"  {name:20s} [MISS]")

    for name, mod in [("PySide6 (GUI)", "PySide6"), ("pyqtgraph", "pyqtgraph"), ("Pygments", "pygments")]:
        try:
            __import__(mod.split()[0] if "(" in mod else mod)
            print(f"  {name:20s} [OK]")
        except ImportError:
            print(f"  {name:20s} [--] (可选)")

    dp = Path(getattr(args, 'data_dir', 'taowu_data'))
    print(f"\n数据目录: {dp.absolute()}")
    if dp.exists():
        for f in sorted(dp.glob("*")):
            tag = "[D]" if f.is_dir() else "[F]"
            print(f"  {tag} {f.name}")
    else:
        print("  (不存在)")
    print("=" * 55)


def cmd_status(args):
    """查看状态."""
    ctrl = TaowuController(
        host=getattr(args, 'host', '127.0.0.1'),
        port=getattr(args, 'port', 3306),
        data_dir=getattr(args, 'data_dir', 'taowu_data'),
    )
    info = ctrl.status_dict()
    state_str = "[RUNNING]" if info["running"] else "[STOPPED]"
    print(f"\n  taowuDB {state_str}")
    print(f"  {'监听:':10s} {info.get('host','-')}:{info.get('port','-')}")
    if info["running"]:
        print(f"  {'数据库:':10s} {len(info.get('databases',[]))} 个 — {', '.join(info.get('databases',[])) or '(无)'}")
        print(f"  {'用户:':10s} {info.get('users',0)} 个")
        print(f"  {'配置:':10s} {info.get('config_count',0)} 个参数 / {info.get('config_sections',0)} 个分类")
        fw = info.get("firewall")
        if fw:
            fw_status = "🟢 已启用" if fw.get("enabled") else "⚪ 已禁用"
            if not fw.get("available"):
                fw_status = "🔴 不可用（xwf 未安装）"
            print(f"  {'防火墙:':10s} {fw_status}  mode={fw.get('mode','?')}  rules={fw.get('rule_count',0)}")
            print(f"  {'':10s} checked={fw.get('total_checked',0)}  blocked={fw.get('total_blocked',0)}  alerted={fw.get('total_alerted',0)}")


# ==========================================================================
# 主入口
# ==========================================================================


def build_parser():
    p = argparse.ArgumentParser(
        description="taowuDB — 一键启动数据库管理系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python taowudb.py                    启动 GUI 管理界面（默认）
  python taowudb.py --server-only      仅启动后端服务
  python taowudb.py --cli              启动命令行客户端
  python taowudb.py --init --force     初始化数据库
  python taowudb.py --check            检查环境依赖
  python taowudb.py --status           查看运行状态
        """,
    )
    p.add_argument("--server-only", action="store_true", help="仅启动后端服务（无 GUI）")
    p.add_argument("--cli", action="store_true", help="启动命令行客户端")
    p.add_argument("--init", action="store_true", help="初始化数据库")
    p.add_argument("--force", action="store_true", help="强制初始化（覆盖已有数据）")
    p.add_argument("--check", action="store_true", help="检查环境依赖")
    p.add_argument("--status", action="store_true", help="查看运行状态")
    p.add_argument("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1）")
    p.add_argument("--port", type=int, default=3306, help="监听端口（默认 3306）")
    p.add_argument("--data-dir", default="taowu_data", help="数据目录（默认 taowu_data）")
    p.add_argument("--firewall-data-dir", default=None,
                   help="玄武防火墙数据目录（默认 xuanwu_firewall/data）")
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    ctrl = TaowuController(
        host=args.host,
        port=args.port,
        data_dir=args.data_dir,
    )

    # ── 处理独立命令 ──────────────────────────────────────
    if args.init:
        return cmd_init(args)
    if args.check:
        return cmd_check(args)
    if args.status:
        return cmd_status(args)

    # ── 选择启动模式 ──────────────────────────────────────
    if args.server_only:
        launch_server_only(ctrl)
    elif args.cli:
        launch_cli(ctrl)
    else:
        # 默认：启动 GUI（后端自动启动）
        launch_gui(ctrl)


if __name__ == "__main__":
    main()
