"""Enforce docs/design.md § What may depend on what, by reading imports.

Every module under src/paperkist belongs to one part of the design. Each part
may import only the parts and outside libraries the design allows it. A
module that belongs to no part fails too: a new part is a design change,
so docs/design.md and PARTS below change together.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src" / "paperkist"

# Module name (relative to the paperkist package) -> part. A name ending in "."
# claims that subpackage and everything under it.
PARTS = {
    "": "package",
    "crypto": "crypto",
    "vault.": "vault",  # vault, index and migrate: one part in these rules
    "search": "search",
    "expiry": "expiry",
    "suggest": "suggest",
    "extract.": "extract",
    "export": "export",
    "errors": "errors",
    "ui.": "ui",
    "__main__": "app",
}

# Rules 3, 8 and 9, and "every part may import errors".
ALLOWED_PARTS = {
    "package": set(),
    "crypto": {"errors"},
    "vault": {"crypto", "errors"},
    "search": {"errors"},
    "expiry": {"errors"},
    "suggest": {"errors"},
    "extract": {"errors"},
    "export": {"vault", "errors"},
    "errors": set(),
    "ui": {"vault", "search", "expiry", "suggest", "extract", "export", "errors"},
    "app": {"ui", "errors"},
}

QT = {"PySide6", "shiboken6"}
NETWORK = {"socket", "ssl", "http", "urllib", "ftplib", "smtplib", "requests", "httpx"}
DISK = {"os", "pathlib", "io", "shutil", "subprocess", "glob"}
THREADS = {"threading", "concurrent", "multiprocessing"}

# Outside libraries forbidden per part. Rule 7 (no network) and rule 4 (no
# decrypted temporary file, so no tempfile) apply to every part.
FORBIDDEN_EVERYWHERE = NETWORK | {"tempfile"}
FORBIDDEN = {
    "search": QT | DISK,  # rule 5: pure
    "expiry": QT | DISK,
    "suggest": QT | DISK,
    "extract": QT | THREADS,  # rule 6: no thread or Qt signal
}
ONLY_IN = {  # library -> the parts that alone may import it
    "PySide6": {"ui", "app"},  # rule 1
    "shiboken6": {"ui", "app"},
    "nacl": {"crypto"},  # rule 2
}


def part_of(module: str) -> str | None:
    """The design part that owns `module` (a name relative to paperkist)."""
    for prefix, part in PARTS.items():
        if prefix.endswith("."):
            if module == prefix[:-1] or module.startswith(prefix):
                return part
        elif module == prefix:
            return part
    return None


def module_name(path: Path, root: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imports_of(path: Path, module: str) -> list[str]:
    """Absolute dotted names imported by the file at `path`."""
    is_package = path.name == "__init__.py"
    names = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module or ""
            else:
                here = ["paperkist", *filter(None, module.split("."))]
                if not is_package:
                    here.pop()
                here = here[: len(here) - (node.level - 1)]
                base = ".".join([*here, *filter(None, [node.module])])
            # `from paperkist import crypto` imports the submodule crypto,
            # not the package.
            if base == "paperkist":
                names += [f"paperkist.{alias.name}" for alias in node.names]
            else:
                names.append(base)
    return names


def violations(root: Path) -> list[str]:
    found = []
    for path in sorted(root.rglob("*.py")):
        module = module_name(path, root)
        part = part_of(module)
        where = path.relative_to(root).as_posix()
        if part is None:
            found.append(f"{where}: belongs to no part in docs/design.md")
            continue
        for name in imports_of(path, module):
            top = name.split(".")[0]
            if top == "paperkist":
                target = part_of(name.removeprefix("paperkist").removeprefix("."))
                if (
                    target is not None
                    and target != part
                    and target not in ALLOWED_PARTS[part]
                ):
                    found.append(f"{where}: {part} may not import {target} ({name})")
                continue
            if top in FORBIDDEN_EVERYWHERE or top in FORBIDDEN.get(part, set()):
                found.append(f"{where}: {part} may not import {top}")
            if top in ONLY_IN and part not in ONLY_IN[top]:
                found.append(f"{where}: only {sorted(ONLY_IN[top])} may import {top}")
    return found


def test_source_tree_follows_the_design():
    assert violations(SRC) == []


# Each case writes one file into a scratch package and names the rule it
# breaks, so every rule above is shown to fail when broken.
BREACHES = [
    ("search.py", "import PySide6", "rule 1: Qt outside ui and app"),
    (
        "vault/vault.py",
        "import nacl.secret",
        "rule 2: encryption library outside crypto",
    ),
    ("ui/main.py", "from paperkist import crypto", "rule 8: ui calls crypto"),
    ("search.py", "from .vault import vault", "rule 3: search reaches vault"),
    ("vault/index.py", "import tempfile", "rule 4: a temporary file"),
    ("expiry.py", "import pathlib", "rule 5: pure part touches disk"),
    ("extract/ocr.py", "import threading", "rule 6: extract holds a thread"),
    ("export.py", "import urllib.request", "rule 7: network"),
    ("vault/vault.py", "from ..ui import main", "rule 9: something depends on ui"),
    ("sync.py", "", "a module in no part"),
]


@pytest.mark.parametrize(
    ("file", "source", "rule"), BREACHES, ids=[b[2] for b in BREACHES]
)
def test_each_rule_catches_its_breach(tmp_path, file, source, rule):
    target = tmp_path / file
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source + "\n", encoding="utf-8")
    assert violations(tmp_path), rule


def test_allowed_imports_pass(tmp_path):
    (tmp_path / "vault").mkdir()
    (tmp_path / "vault" / "vault.py").write_text(
        "from .. import crypto\nfrom ..errors import VaultCorrupt\nimport pathlib\n",
        encoding="utf-8",
    )
    (tmp_path / "__main__.py").write_text(
        "from paperkist.ui import main\n", encoding="utf-8"
    )
    assert violations(tmp_path) == []
