"""
taowuDB setup.py — Build system with Cython compilation support.

Build:
    python setup.py build_ext --inplace    # Compile .pyx → .pyd
    python setup.py install                # Install package
    python setup.py develop                # Dev install (editable)

Cython extensions are built only if Cython is installed and .pyx files exist.
Pure-Python fallback modules are always available.
"""

import os
import sys
from pathlib import Path

from setuptools import setup, find_packages, Extension

HERE = Path(__file__).resolve().parent
VERSION = "0.1.0"

# ---------------------------------------------------------------------------
# Cython extensions (optional — pure-Python fallback always available)
# ---------------------------------------------------------------------------
ext_modules = []

try:
    from Cython.Build import cythonize

    USE_CYTHON = True
except ImportError:
    USE_CYTHON = False

if USE_CYTHON:
    cython_ext_dir = HERE / "taowu" / "cython_ext"
    pyx_files = list(cython_ext_dir.glob("*.pyx"))
    if pyx_files:
        ext_modules = cythonize(
            [str(p) for p in pyx_files],
            compiler_directives={
                "language_level": "3",
                "boundscheck": False,
                "wraparound": False,
                "cdivision": True,
                "embedsignature": True,
            },
            annotate=True,
        )

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
setup(
    name="taowudb",
    version=VERSION,
    description="taowuDB — self-developed relational database with MySQL protocol compatibility",
    long_description=(HERE / "README.md").read_text(encoding="utf-8", errors="replace"),
    long_description_content_type="text/markdown",
    author="taowuDB Team",
    url="https://github.com/taowudb/taowudb",
    packages=find_packages(include=["taowu", "taowu.*", "config_gui", "config_gui.*"]),
    ext_modules=ext_modules,
    python_requires=">=3.10",
    install_requires=[
        "PySide6>=6.5.0",
        "pyqtgraph>=0.13.0",
        "Pygments>=2.15.0",
        "zhconv>=1.4.0",
        "pymysql>=1.1.0",
    ],
    extras_require={
        "cython": ["cython>=3.0.0"],
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "ruff>=0.1.0",
            "mypy>=1.5.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "taowudb=taowu.server:main",
            "taowudb-gui=config_gui.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Cython",
        "Topic :: Database :: Database Engines/Servers",
    ],
)
