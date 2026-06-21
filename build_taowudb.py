#!/usr/bin/env python3
"""
build_taowudb.py — taowuDB 完整打包脚本

将整个项目（引擎 + GUI + 玄武防火墙 + 脚本 + 所有资源）打包。

默认采用 **分体式打包 (onedir)**：
  - 所有 Python 代码 & 运行库 → _internal/ 目录（PyInstaller 管理）
  - 外部资源 (data, resources, taowu_data) → 放在 EXE 同级目录

用法:
    python build_taowudb.py                    默认分体打包 (onedir)
    python build_taowudb.py --onefile           单文件打包 (传统模式)
    python build_taowudb.py --fast              快速打包 (跳过 UPX 压缩)
    python build_taowudb.py --onefile --fast    单文件 + 快速
"""

import os
import sys
import shutil
import subprocess
import argparse
import time

# ── 修复中文 Windows 控制台编码 ────────────────────────────
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

# ── 确保所有项目包在 PyInstaller 分析时可导入 ──────────────
for _d in [ROOT, os.path.join(ROOT, "xuanwu_firewall")]:
    if _d not in sys.path:
        sys.path.insert(0, _d)

# ======================================================================
# 配置
# ======================================================================
EXE_NAME = "taowuDB"
ENTRY_SCRIPT = os.path.join("config_gui", "main.py")
BUILD_DIR = "build"
DIST_DIR = "dist"

# ── 运行时目录 — 放在 EXE 同级 ─────────────────────────────
RUNTIME_DIRS = [
    "taowu_data",
    "taowu_data/logs",
    "xuanwu_firewall/data/logs",
    "xuanwu_firewall/data/run",
    "xuanwu_firewall/data/plugins",
]

# ── 需要打包进 EXE 的数据目录（仅 onefile 模式使用）──────
# 格式: (源目录, 目标在 EXE 内的路径, 是否必需)
# 注意: onedir 模式下这些数据不打包进 _internal/，
#       而是在步骤 5 复制到 EXE 同级目录
DATA_DIRS = [
    (os.path.join("xuanwu_firewall", "data"), os.path.join("xuanwu_firewall", "data"), True),
    (os.path.join("config_gui", "resources"), os.path.join("config_gui", "resources"), False),
]

# ── 需要 collect-all 的第三方包 ─────────────────────────────
COLLECT_ALL_PKGS = [
    "PySide6",       # Qt GUI 全家桶
    "pyqtgraph",     # 监控图表
    "pygments",      # SQL 语法高亮
    "zhconv",        # 中文简繁转换
    "pymysql",       # MySQL 客户端
]

# ── 需要 collect-submodules 的项目包 ───────────────────────
COLLECT_SUBMODS = [
    "taowu",         # 核心数据库引擎
    "config_gui",    # GUI 管理界面
    "xwf",           # 玄武防火墙
    "scripts",       # CLI + init 脚本
]

# ── 强制隐藏导入（PyInstaller 静态分析可能漏掉的）─────────
HIDDEN_IMPORTS = [
    # 防火墙 — 确保 xwf 顶层包被包含
    "xwf",
    "xwf.types",
    "xwf.errors",
    "xwf.detection.engine",
    "xwf.detection.rules",
    "xwf.detection.rules_advanced",
    "xwf.detection.scoring",
    "xwf.detection.whitelist",
    "xwf.detection.learning",
    "xwf.parser.lexer",
    "xwf.parser.parser",
    "xwf.parser.ast",
    "xwf.parser.dialect",
    "xwf.parser.normalizer",
    "xwf.parser.fingerprint",
    "xwf.defense.deception",
    "xwf.defense.tarpit",
    "xwf.defense.counter",
    "xwf.defense.recon",
    "xwf.defense.retaliate",
    "xwf.defense.overmatch",
    "xwf.defense.system",
    "xwf.defense.cavalry",
    "xwf.defense.garrison",
    "xwf.access.model",
    "xwf.access.policy",
    "xwf.audit.logger",
    "xwf.audit.report",
    "xwf.alert.engine",
    "xwf.alert.channels",
    "xwf.crypto.engine",
    "xwf.crypto.key_manager",
    "xwf.crypto.hash_chain",
    "xwf.utils.logger",
    "xwf.utils.metrics",
    "xwf.utils.encoding",
    "xwf.utils.network",
    "xwf.utils.concurrency",
    "xwf.utils.time",
    "xwf.utils.validators",
    "xwf.config.schema",
    "xwf.config.defaults",
    "xwf.config.loader",
    "xwf.config.validator",
    "xwf.config.rules",
    "xwf.config.manager",
    "xwf.config.presets",
    "xwf.db.session",
    "xwf.db.models",
    "xwf.db.repository",
    "xwf.plugins.base",
    "xwf.plugins.manifest",
    "xwf.plugins.loader",
    "xwf.plugins.registry",
    "xwf.proxy.server",
    "xwf.proxy.session",
    "xwf.proxy.connection_pool",
    "xwf.proxy.rate_limiter",
    "xwf.protocol.base",
    "xwf.protocol.mysql",
    "xwf.protocol.postgresql",
    "xwf.protocol.sniffer",
    "xwf.core.engine",
    "xwf.api.server",
    "xwf.ha.cluster",
    # taowu 引擎
    "taowu.firewall",
    "taowu.firewall.engine",
    # 脚本
    "scripts.taowu_cli",
    "scripts.init_db",
    "scripts.benchmark",
    # pkg_resources (zhconv 间接依赖) — 需要 jaraco.text
    # setuptools >= 71 把 jaraco 等包放在 _vendor/ 并暴露到 sys.path
    # PyInstaller 的 pyi_rth_pkgres 运行时钩子需要这些
    "jaraco",
    "jaraco.text",
    "jaraco.functools",
    "jaraco.context",
]

# ── 排除的模块（减小体积，加快打包）──────────────────────
EXCLUDES = [
    # 不用的数据库驱动
    "pynvml",
    # 不用的重型库
    "matplotlib", "numpy", "scipy", "pandas", "PIL", "cv2",
    # Qt/QML 不用的模块
    "PySide6.Qml", "PySide6.QtQml", "PySide6.QtQuick",
    "PySide6.QtQuick3D", "PySide6.QtPositioning",
    # PySide6 内部 deploy 脚本（引用不存在的 project_lib）
    "PySide6.scripts.project",
    "PySide6.scripts.deploy_lib",
    # 排除 PyQt — 环境里有 PySide6 就够了，避免 Qt 绑定冲突
    "PyQt6", "PyQt6.sip", "PyQt6.QtCore",
    "PyQt5",
    # pyqtgraph 不需要的 OpenGL 子模块（省掉 PyOpenGL 依赖）
    "pyqtgraph.opengl",
    # 测试与工具
    # 注意: 不能排除 setuptools — zhconv → pkg_resources → jaraco.text
    # 而 jaraco.text 由 setuptools._vendor.jaraco.text 提供
    "tests", "test", "unittest", "pytest", "pip",
    "pycparser", "cffi",
    # xwf 测试 (不需要打包)
    "xwf.tests",
]

# ── PyInstaller 搜索路径 ──────────────────────────────────
PATHS = [
    ROOT,
    os.path.join(ROOT, "xuanwu_firewall"),
]

# ── 自定义 hooks 目录 (静默排除不需要的子模块) ───────────────
CUSTOM_HOOKS_DIR = os.path.join("pyinstaller", "hooks")

# ── 运行时 hook ────────────────────────────────────────────
RUNTIME_HOOK = os.path.join("pyinstaller", "runtime_hook.py")


# ======================================================================
# 辅助函数
# ======================================================================

def run(cmd, **kw):
    """运行命令并回显。"""
    if isinstance(cmd, list):
        print(f"  >> {' '.join(cmd)}")
    else:
        print(f"  >> {cmd}")
    return subprocess.run(cmd, shell=not isinstance(cmd, list), **kw)


def step(msg: str, num: int = 0, total: int = 0):
    """打印步骤标题。"""
    tag = f"[{num}/{total}]" if num and total else ""
    print(f"\n{'=' * 60}")
    print(f"  {tag} {msg}")
    print(f"{'=' * 60}")


def file_count(directory: str) -> int:
    """统计目录下文件数。"""
    if not os.path.exists(directory):
        return 0
    return sum(1 for _ in os.walk(directory) for f in _[2])


def get_output_root(onedir: bool) -> str:
    """获取打包输出根目录。

    onedir 模式: dist/taowuDB/  (EXE + 外部资源都在此)
    onefile 模式: dist/         (EXE 在 dist/ 下, 外部资源也在 dist/ 下)
    """
    if onedir:
        return os.path.join(ROOT, DIST_DIR, EXE_NAME)
    else:
        return os.path.join(ROOT, DIST_DIR)


def get_exe_path(onedir: bool) -> str:
    """获取 EXE 路径。"""
    return os.path.join(get_output_root(onedir), EXE_NAME + ".exe")


# ======================================================================
# 步骤 1: 清理
# ======================================================================

def clean_old_artifacts():
    step("清理旧构建产物", 1, 6)
    for d in [BUILD_DIR, DIST_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d, ignore_errors=True)
            print(f"  已删除: {d}/")
    # 清理 spec 文件（PyInstaller 生成的）
    for f in os.listdir(ROOT):
        if f.endswith(".spec") and f != "taowuDB.spec":
            p = os.path.join(ROOT, f)
            os.remove(p)
            print(f"  已删除: {f}")
    # 清理 __pycache__
    for root, dirs, _ in os.walk(ROOT, topdown=False):
        for d in dirs:
            if d == "__pycache__":
                p = os.path.join(root, d)
                shutil.rmtree(p, ignore_errors=True)
    print("  清理完成 [OK]")


# ======================================================================
# 步骤 2: 验证依赖
# ======================================================================

def check_dependencies():
    step("验证运行时依赖", 2, 6)
    required = {
        "PySide6": "GUI 框架",
        "pyqtgraph": "监控图表",
        "Pygments": "SQL 语法高亮",
        "zhconv": "中文简繁转换",
        "pymysql": "MySQL 客户端",
    }
    all_ok = True
    for mod, desc in required.items():
        try:
            pkg_name = mod.split("[")[0] if "[" in mod else mod
            __import__(pkg_name)
            print(f"  [{chr(10003)}] {mod:20s} — {desc}")
        except ImportError:
            print(f"  [!] {mod:20s} — {desc} [MISSING — 尝试安装...]")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", mod, "-q"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                print(f"       已安装 [OK]")
            else:
                print(f"       安装失败! {result.stderr.strip()}")
                all_ok = False
    if all_ok:
        print("  依赖检查完成 [OK]")
    else:
        print("  依赖检查完成 [部分缺失]")
    return all_ok


# ======================================================================
# 步骤 3: PyInstaller 打包
# ======================================================================

def build_exe(fast_mode: bool = False, onedir: bool = True):
    step("PyInstaller 打包", 3, 6)

    mode_label = "onedir (分体式 — 代码+库在 _internal/, 资源在 EXE 同级)" if onedir else "onefile (单文件)"
    upx_label = "禁用" if fast_mode else "启用"
    print(f"  模式:      {mode_label}")
    print(f"  UPX:       {upx_label}")
    print(f"  入口脚本:  {ENTRY_SCRIPT}")
    print(f"  输出名称:  {EXE_NAME}.exe")
    print(f"  第三方包:  {len(COLLECT_ALL_PKGS)} 个 (collect-all)")
    print(f"  项目模块:  {len(COLLECT_SUBMODS)} 个 (collect-submodules)")
    print(f"  隐藏导入:  {len(HIDDEN_IMPORTS)} 个")
    print(f"  排除模块:  {len(EXCLUDES)} 个")

    pyi_cmd = [sys.executable, "-m", "PyInstaller"]

    # ── 基本信息 ────────────────────────────────────────────
    pyi_cmd += [
        "--name=" + EXE_NAME,
        "--clean",
        "--noconfirm",
        "--log-level=WARN",
    ]

    # ── 打包模式 ────────────────────────────────────────────
    if onedir:
        pyi_cmd.append("--onedir")
        # onedir 模式下，外部数据目录不打包进 _internal/，
        # 而是在步骤 5 复制到 EXE 同级目录
        print(f"  外部数据:   不打包进 _internal/，将复制到 EXE 同级")
    else:
        pyi_cmd.append("--onefile")
        print(f"  数据目录:   {len(DATA_DIRS)} 个 (打包进 EXE)")

    # ── UPX 压缩（fast 模式跳过，大 Qt 库压缩非常耗时）────
    if fast_mode:
        pyi_cmd.append("--noupx")

    # ── 控制台模式（显示终端日志） ─────────────────────────
    pyi_cmd.append("--console")

    # ── 搜索路径 ────────────────────────────────────────────
    for p in PATHS:
        pyi_cmd.append(f"--paths={p}")

    # ── 运行时 hook ─────────────────────────────────────────
    if os.path.exists(RUNTIME_HOOK):
        pyi_cmd.append(f"--runtime-hook={RUNTIME_HOOK}")
        print(f"  运行时钩子:  {RUNTIME_HOOK}")

    # ── 自定义 hooks 目录 ───────────────────────────────────
    if os.path.exists(CUSTOM_HOOKS_DIR):
        pyi_cmd.append(f"--additional-hooks-dir={CUSTOM_HOOKS_DIR}")
        print(f"  自定义hooks: {CUSTOM_HOOKS_DIR}")

    # ── 数据目录 ────────────────────────────────────────────
    # onedir 模式: 不打包数据目录，它们将作为外部资源放在 EXE 同级
    # onefile 模式: 打包数据目录进 EXE 内部
    if not onedir:
        for src, dst, required in DATA_DIRS:
            if os.path.exists(src):
                # Windows 用 ; 作分隔符
                pyi_cmd.append(f"--add-data={src}{os.pathsep}{dst}")
                n = file_count(src)
                print(f"  add-data:   {src}/ -> {dst}/ ({n} 个文件)")
            elif required:
                print(f"  [WARN] 必需的数据目录不存在: {src}")
    else:
        # onedir 模式下列出将要作为外部资源复制的目录
        for src, dst, required in DATA_DIRS:
            if os.path.exists(src):
                n = file_count(src)
                print(f"  ext-data:   {src}/ -> (EXE同级) {dst}/ ({n} 个文件, 外部)")
            elif required:
                print(f"  [WARN] 必需的数据目录不存在: {src}")

    # ── 第三方包（collect-all） ─────────────────────────────
    for pkg in COLLECT_ALL_PKGS:
        pyi_cmd.append(f"--collect-all={pkg}")

    # ── 项目模块（collect-submodules） ──────────────────────
    for mod in COLLECT_SUBMODS:
        pyi_cmd.append(f"--collect-submodules={mod}")

    # ── 隐藏导入 ────────────────────────────────────────────
    for imp in HIDDEN_IMPORTS:
        pyi_cmd.append(f"--hidden-import={imp}")

    # ── 排除模块 ────────────────────────────────────────────
    for exc in EXCLUDES:
        pyi_cmd.append(f"--exclude-module={exc}")

    # ── 入口脚本 ────────────────────────────────────────────
    pyi_cmd.append(ENTRY_SCRIPT)

    # ── 执行 ────────────────────────────────────────────────
    print(f"\n  正在运行 PyInstaller (这可能需要几分钟)...")
    t0 = time.time()

    result = subprocess.run(pyi_cmd)

    elapsed = time.time() - t0
    mins = int(elapsed // 60)
    secs = int(elapsed % 60)
    print(f"\n  PyInstaller 耗时: {mins}分{secs}秒")

    if result.returncode != 0:
        print("\n" + "!" * 60)
        print("  [ERROR] PyInstaller 打包失败! 查看上方错误信息。")
        print("!" * 60)
        sys.exit(1)

    print("  EXE 构建完成 [OK]")


# ======================================================================
# 步骤 4: 创建运行时目录
# ======================================================================

def create_runtime_dirs(onedir: bool = True):
    step("创建运行时目录", 4, 6)
    output_root = get_output_root(onedir)
    for d in RUNTIME_DIRS:
        full = os.path.join(output_root, d)
        os.makedirs(full, exist_ok=True)
        print(f"  {full}/")
    print(f"  共 {len(RUNTIME_DIRS)} 个目录 [OK]")


# ======================================================================
# 步骤 5: 复制外部资源（放在 EXE 同级目录）
# ======================================================================

def copy_external_resources(onedir: bool = True):
    step("复制外部资源文件 -> EXE 同级目录", 5, 6)
    output_root = get_output_root(onedir)

    # ── xuanwu_firewall data ──────────────────────────────────
    xf_data_src = os.path.join(ROOT, "xuanwu_firewall", "data")
    xf_data_dst = os.path.join(output_root, "xuanwu_firewall", "data")
    if os.path.exists(xf_data_src):
        os.makedirs(os.path.dirname(xf_data_dst), exist_ok=True)
        if os.path.exists(xf_data_dst):
            shutil.rmtree(xf_data_dst, ignore_errors=True)
        shutil.copytree(xf_data_src, xf_data_dst)
        n = file_count(xf_data_dst)
        print(f"  xuanwu_firewall/data/     -> {n} 个文件")

    # ── config_gui resources ──────────────────────────────────
    cg_res_src = os.path.join(ROOT, "config_gui", "resources")
    cg_res_dst = os.path.join(output_root, "config_gui", "resources")
    if os.path.exists(cg_res_src):
        os.makedirs(os.path.dirname(cg_res_dst), exist_ok=True)
        if os.path.exists(cg_res_dst):
            shutil.rmtree(cg_res_dst, ignore_errors=True)
        shutil.copytree(cg_res_src, cg_res_dst)
        n = file_count(cg_res_dst)
        print(f"  config_gui/resources/     -> {n} 个文件")

    print("  外部资源复制完成 [OK]")


# ======================================================================
# 步骤 6: 创建使用指南 + 构建摘要
# ======================================================================

def create_readme_and_summary(onedir: bool = True):
    step("创建使用指南 + 构建摘要", 6, 6)

    output_root = get_output_root(onedir)
    exe_path = get_exe_path(onedir)

    if not os.path.exists(exe_path):
        print("\n  [ERROR] EXE 文件不存在! 构建可能失败。")
        return

    exe_mb = os.path.getsize(exe_path) / (1024 * 1024)

    # 统计输出目录
    total_files = 0
    total_size = 0
    for r, _, fs in os.walk(output_root):
        for f in fs:
            total_files += 1
            total_size += os.path.getsize(os.path.join(r, f))

    # ── 收集输出目录下的顶层内容 ────────────────────────────
    file_list_lines = []
    for item in sorted(os.listdir(output_root)):
        p = os.path.join(output_root, item)
        if os.path.isdir(p):
            # 统计子目录大小
            dir_size = 0
            dir_files = 0
            for r2, _, fs2 in os.walk(p):
                for f2 in fs2:
                    dir_size += os.path.getsize(os.path.join(r2, f2))
                    dir_files += 1
            size_mb = dir_size / (1024 * 1024)
            file_list_lines.append(f"  {item}/  ({dir_files} 个文件, {size_mb:.1f} MB)")
        else:
            size_kb = os.path.getsize(p) / 1024
            if size_kb > 1024:
                file_list_lines.append(f"  {item}  ({size_kb / 1024:.1f} MB)")
            else:
                file_list_lines.append(f"  {item}  ({size_kb:.0f} KB)")

    if onedir:
        readme = f"""+--------------------------------------------------------------+
|              taowuDB — 自研关系型数据库                          |
+--------------------------------------------------------------+

[如何启动]
  双击 taowuDB.exe 启动程序。

[启动后你会看到]
  1. 控制台终端 (黑色窗口)
     -> 引擎启动日志、SQL 执行日志
     -> 关闭此窗口会同时退出程序

  2. GUI 管理窗口
     -> 连接配置 -> 数据库管理 -> SQL 查询
     -> 修复面板 -> 备份恢复 -> 性能监控

[主界面快捷键]
  Ctrl+1  数据库管理   - 浏览数据库/表结构
  Ctrl+2  数据查看     - 查看表数据
  Ctrl+3  SQL 查询     - 执行 SQL 语句
  Ctrl+4  仪表盘       - 系统概览
  Ctrl+5  配置管理     - 服务器参数配置
  Ctrl+6  性能监控     - 实时性能指标
  Ctrl+7  备份恢复     - 数据备份与恢复
  Ctrl+8  修复面板     - 数据库诊断与修复
  Ctrl+9  用户管理     - 账户和权限管理
  Ctrl+0  防火墙       - 玄武数据库防火墙

[连接配置]
  启动后弹出连接对话框:
    - 本地模式: 直接使用内置引擎 (数据存储在 taowu_data/)
    - 远程模式: 连接到远程 taowuDB 服务器 (端口 3306)

[目录结构 (分体式打包)]
  taowuDB.exe              主程序入口
  _internal/               所有 Python 代码 & 运行库 (PyInstaller 管理)
  taowu_data/              数据库数据文件 (自动创建)
  taowu_data/logs/         运行日志
  xuanwu_firewall/data/    防火墙数据
  config_gui/resources/    GUI 资源文件
  Readme.txt               本文件

[命令行参数 (可选)]
  taowuDB.exe --data-dir <path>    指定数据目录
  taowuDB.exe --host <IP>          指定监听地址
  taowuDB.exe --port <port>        指定端口

[注意事项]
  - 首次启动自动创建 taowu_data/ 目录
  - 数据文件位于 taowu_data/taowu_data_0.dat
  - JSON 备份位于 taowu_data/databases/
  - 不要关闭控制台窗口，否则程序退出
  - _internal/ 目录由 PyInstaller 管理，请勿手动修改

[技术规格]
  引擎版本:     0.1.0
  协议兼容:     MySQL 5.7 wire protocol v10
  存储引擎:     B+ Tree on 64KB pages
  事务隔离:     MVCC (REPEATABLE READ)
  安全防护:     玄武数据库防火墙
  前端框架:     PySide6 (Qt for Python)

[文件列表]
"""
    else:
        readme = f"""+--------------------------------------------------------------+
|              taowuDB — 自研关系型数据库                          |
+--------------------------------------------------------------+

[如何启动]
  双击 taowuDB.exe 启动程序。

[启动后你会看到]
  1. 控制台终端 (黑色窗口)
     -> 引擎启动日志、SQL 执行日志
     -> 关闭此窗口会同时退出程序

  2. GUI 管理窗口
     -> 连接配置 -> 数据库管理 -> SQL 查询
     -> 修复面板 -> 备份恢复 -> 性能监控

[主界面快捷键]
  Ctrl+1  数据库管理   - 浏览数据库/表结构
  Ctrl+2  数据查看     - 查看表数据
  Ctrl+3  SQL 查询     - 执行 SQL 语句
  Ctrl+4  仪表盘       - 系统概览
  Ctrl+5  配置管理     - 服务器参数配置
  Ctrl+6  性能监控     - 实时性能指标
  Ctrl+7  备份恢复     - 数据备份与恢复
  Ctrl+8  修复面板     - 数据库诊断与修复
  Ctrl+9  用户管理     - 账户和权限管理
  Ctrl+0  防火墙       - 玄武数据库防火墙

[连接配置]
  启动后弹出连接对话框:
    - 本地模式: 直接使用内置引擎 (数据存储在 taowu_data/)
    - 远程模式: 连接到远程 taowuDB 服务器 (端口 3306)

[目录结构 (单文件打包)]
  taowuDB.exe              主程序 (包含所有代码+库+资源)
  taowu_data/              数据库数据文件 (自动创建)
  taowu_data/logs/         运行日志
  xuanwu_firewall/data/    防火墙数据
  config_gui/resources/    GUI 资源文件
  Readme.txt               本文件

[命令行参数 (可选)]
  taowuDB.exe --data-dir <path>    指定数据目录
  taowuDB.exe --host <IP>          指定监听地址
  taowuDB.exe --port <port>        指定端口

[注意事项]
  - 首次启动自动创建 taowu_data/ 目录
  - 数据文件位于 taowu_data/taowu_data_0.dat
  - JSON 备份位于 taowu_data/databases/
  - 不要关闭控制台窗口，否则程序退出

[技术规格]
  引擎版本:     0.1.0
  协议兼容:     MySQL 5.7 wire protocol v10
  存储引擎:     B+ Tree on 64KB pages
  事务隔离:     MVCC (REPEATABLE READ)
  安全防护:     玄武数据库防火墙
  前端框架:     PySide6 (Qt for Python)

[文件列表]
"""

    readme += "\n".join(file_list_lines)

    readme_path = os.path.join(output_root, "Readme.txt")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme)
    print(f"  Readme.txt -> {len(readme)} 字符 [OK]")

    # ── 构建摘要 ────────────────────────────────────────────
    if onedir:
        print(f"""
  +--------------------------------------------------------------+
  |              [SUCCESS] 构建完成! (分体式打包)                 |
  +--------------------------------------------------------------+

  输出目录:     {output_root}

  ─── 主程序 ───────────────────────────────────────────────
    {EXE_NAME}.exe              {exe_mb:>8.1f} MB
    双击启动 -> 控制台 + GUI 双窗口

  ─── Python 代码 & 运行库 ──────────────────────────────────
    _internal/                  PyInstaller 管理 (Python/DLL/PySide6/...)
                                ↑ 程序运行时自动加载，请勿手动修改

  ─── 外部资源 (与 EXE 同级) ───────────────────────────────
    taowu_data/                  数据库文件 (自动创建)
    taowu_data/logs/             运行日志
    xuanwu_firewall/data/        防火墙密钥/数据库
    config_gui/resources/        GUI 资源文件

  ─── 文档 ─────────────────────────────────────────────────
    Readme.txt                   使用指南

  +--------------------------------------------------------------+

  总计: {total_files} 个文件, {total_size / 1024 / 1024:.1f} MB

  [分发]
    将 {EXE_NAME}/ 整个文件夹打包为 ZIP，分发给用户。
    用户解压后进入文件夹，双击 taowuDB.exe 即可启动。

  [首次启动]
    1. 双击 taowuDB.exe
    2. 在连接对话框中选择"本地模式"
    3. 确认数据目录 (默认: taowu_data/)
    4. 点击确定 -> 数据库自动初始化

  [分体式打包说明]
    - Python 代码和运行库在 _internal/ 目录下
    - 更新程序时只需替换 _internal/ 目录即可，无需重新下载整个包
    - 外部数据独立存放，升级不会覆盖用户数据
""")
    else:
        print(f"""
  +--------------------------------------------------------------+
  |              [SUCCESS] 构建完成! (单文件打包)                 |
  +--------------------------------------------------------------+

  输出目录:     {output_root}

  ─── 主程序 ───────────────────────────────────────────────
    {EXE_NAME}.exe              {exe_mb:>8.1f} MB
    双击启动 -> 控制台 + GUI 双窗口

  ─── 运行时目录 ───────────────────────────────────────────
    taowu_data/                  数据库文件 (自动创建)
    taowu_data/logs/             运行日志
    xuanwu_firewall/data/        防火墙密钥/数据库

  ─── 外部资源 ─────────────────────────────────────────────
    config_gui/resources/        GUI 资源文件

  ─── 文档 ─────────────────────────────────────────────────
    Readme.txt                   使用指南

  +--------------------------------------------------------------+

  总计: {total_files} 个文件, {total_size / 1024 / 1024:.1f} MB

  [分发]
    将 dist/ 下所有内容打包为 ZIP，分发给用户。
    用户解压后双击 taowuDB.exe 即可启动。

  [首次启动]
    1. 双击 taowuDB.exe
    2. 在连接对话框中选择"本地模式"
    3. 确认数据目录 (默认: taowu_data/)
    4. 点击确定 -> 数据库自动初始化
""")


# ======================================================================
# 主入口
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        description="taowuDB 构建打包脚本 — 默认分体式打包 (onedir)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python build_taowudb.py                     默认分体打包 (onedir, 推荐)
  python build_taowudb.py --fast               快速分体打包 (跳过 UPX)
  python build_taowudb.py --onefile            传统单文件打包
  python build_taowudb.py --onefile --fast     单文件快速打包
        """,
    )
    parser.add_argument("--fast", action="store_true",
                        help="快速模式（跳过 UPX 压缩，加快打包速度）")
    parser.add_argument("--onefile", action="store_true",
                        help="单文件打包模式（所有内容打包进单个 EXE）")
    parser.add_argument("--onedir", action="store_true",
                        help="分体式打包（默认，代码+库在 _internal/，资源在 EXE 同级）")
    args = parser.parse_args()

    # ── 确定打包模式：默认 onedir ─────────────────────────
    onedir = not args.onefile  # --onefile 显式指定时才用单文件

    print(f"  Python:     {sys.version.split()[0]}")
    print(f"  项目根:     {ROOT}")
    print(f"  入口:       {ENTRY_SCRIPT}")
    print(f"  打包模式:   {'onedir (分体式)' if onedir else 'onefile (单文件)'}")
    print(f"  快速模式:   {'是' if args.fast else '否'}")

    try:
        clean_old_artifacts()
        check_dependencies()
        build_exe(fast_mode=args.fast, onedir=onedir)
        create_runtime_dirs(onedir=onedir)
        copy_external_resources(onedir=onedir)
        create_readme_and_summary(onedir=onedir)
    except KeyboardInterrupt:
        print("\n\n  构建已取消。")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n  [ERROR] 构建失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
