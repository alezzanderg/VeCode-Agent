from __future__ import annotations
from pathlib import Path
from typing import Iterable
import fnmatch, os, shutil, time, hashlib

def jail_path(root: Path, p: str | Path) -> Path:
    pp = (root / p).resolve()
    if not str(pp).startswith(str(root)):
        raise PermissionError(f"path escapes jail: {p}")
    return pp

def match_any(path: Path, patterns: Iterable[str]) -> bool:
    s = str(path)
    return any(fnmatch.fnmatch(s, pat) for pat in patterns)

def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)

def backup_file(backup_dir: Path, path: Path) -> Path:
    ts = time.strftime("%Y%m%d-%H%M%S")
    digest = hashlib.sha256(str(path).encode()).hexdigest()[:8]
    target = backup_dir / f"{path.name}.{ts}.{digest}.bak"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    return target
