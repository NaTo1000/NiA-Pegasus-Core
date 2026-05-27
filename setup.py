#!/usr/bin/env python3
"""Setuptools configuration with metadata fallbacks."""

from pathlib import Path
from typing import Iterable, List
from setuptools import setup

ROOT = Path(__file__).resolve().parent
EXCLUDED_MODULE_FILES = {"setup.py"}
EXCLUDED_MODULE_PREFIXES = ("test_",)


def _read_first(paths: Iterable[str], default: str = "") -> str:
    for candidate in paths:
        path = ROOT / candidate
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return default


def _read_requirements(paths: Iterable[str]) -> List[str]:
    content = _read_first(paths, default="")
    requirements: List[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        requirements.append(stripped)
    return requirements


def _discover_py_modules() -> List[str]:
    modules: List[str] = []
    for path in ROOT.glob("*.py"):
        if path.name in EXCLUDED_MODULE_FILES:
            continue
        if path.name.startswith(EXCLUDED_MODULE_PREFIXES):
            continue
        modules.append(path.stem)
    return sorted(modules)


LONG_DESCRIPTION = _read_first(
    [
        "README.md",
        "ARCHITECTURE.md",
        "OPTIMIZATION_README.md",
    ],
    default="NayDoeV! Pegasus Core runtime and orchestration tooling.",
)

INSTALL_REQUIRES = _read_requirements(
    [
        "requirements.txt",
        "packaging/requirements.txt",
    ]
)

setup(
    name="nia-pegasus-core",
    version="1.0.0",
    description="NayDoeV! Pegasus Core runtime",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    py_modules=_discover_py_modules(),
    install_requires=INSTALL_REQUIRES,
    python_requires=">=3.10",
)
