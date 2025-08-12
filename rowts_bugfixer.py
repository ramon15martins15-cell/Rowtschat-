#!/usr/bin/env python3
"""
rowts_autofix.py

Ferramenta automatizada de detecção e correção de bugs para projetos Rowts.
- Roda linters/formatters (ruff, black, isort, autoflake)
- Roda mypy e pytest
- Tenta aplicar correções automáticas suportadas pelas ferramentas (--apply-tools)
- Tem heurísticas para corrigir NameError/AttributeError simples via similaridade
- Gera log e resumo, modo dry-run por padrão; use --yes para aplicar automaticamente

Uso:
  python rowts_autofix.py --path path/to/project [--apply-tools] [--yes] [--verbose]
"""

import argparse
import os
import subprocess
import sys
import traceback
import re
import shutil
import logging
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from difflib import get_close_matches, SequenceMatcher

# optional faster similarity
try:
    import Levenshtein  # type: ignore
    def similarity(a: str, b: str) -> float:
        return Levenshtein.ratio(a, b)
except Exception:
    def similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()

# --------------------------
# Config / Logger
# --------------------------
LOG_FILE = "rowts_autofix.log"
logging.basicConfig(
    filename=LOG_FILE,
    filemode="w",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s"
)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter("%(message)s")
console.setFormatter(formatter)
logging.getLogger().addHandler(console)

# --------------------------
# Utilities
# --------------------------
def run_cmd(cmd: List[str], cwd: Optional[str] = None, capture: bool = True) -> Tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    logging.info("EXEC: %s", " ".join(cmd))
    try:
        proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE if capture else None,
                              stderr=subprocess.PIPE if capture else None, text=True)
        out = proc.stdout or ""
        err = proc.stderr or ""
        logging.debug("OUT: %s", out)
        logging.debug("ERR: %s", err)
        return proc.returncode, out, err
    except FileNotFoundError:
        msg = f"Command not found: {cmd[0]}"
        logging.warning(msg)
        return 127, "", msg

def find_python_files(root: Path) -> List[Path]:
    return [p for p in root.rglob("*.py") if "venv" not in p.parts and ".venv" not in p.parts and "site-packages" not in p.parts]

def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

def write_file(path: Path, content: str):
    path.write_text(content, encoding="utf-8")

# --------------------------
# Tool runners
# --------------------------
def run_ruff(root: Path, fix: bool = False) -> Dict[str, str]:
    # ruff is a fast linter/formatter; supports --fix
    cmd = ["ruff", str(root)]
    if fix:
        cmd.append("--fix")
    code, out, err = run_cmd(cmd)
    return {"rc": code, "out": out, "err": err}

def run_black(root: Path, check: bool = False) -> Dict[str, str]:
    cmd = ["black", str(root)]
    if check:
        cmd.append("--check")
    code, out, err = run_cmd(cmd)
    return {"rc": code, "out": out, "err": err}

def run_isort(root: Path, check: bool = False) -> Dict[str, str]:
    cmd = ["isort", str(root)]
    if check:
        cmd.append("--check-only")
    code, out, err = run_cmd(cmd)
    return {"rc": code, "out": out, "err": err}

def run_autoflake(root: Path, fix: bool = False) -> Dict[str, str
