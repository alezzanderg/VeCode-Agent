from __future__ import annotations
from pathlib import Path
from typing import Literal, Optional
import os, shutil, json

from ..config import AgentConfig
from ..utils import jail_path, match_any, atomic_write, backup_file

class FileSystemTool:
    def __init__(self, cfg: AgentConfig):
        self.cfg = cfg

    def tree(self, rel: str = ".", max_depth: int = 6) -> list[dict]:
        root = self.cfg.project_root
        base = jail_path(root, rel)
        out = []
        for dirpath, dirnames, filenames in os.walk(base):
            depth = Path(dirpath).relative_to(base).parts
            if len(depth) > max_depth:
                dirnames[:] = []
                continue
            for d in dirnames:
                p = Path(dirpath) / d
                if not self._allowed(p): 
                    continue
                out.append({"path": str(p.relative_to(root)), "type": "dir"})
            for f in filenames:
                p = Path(dirpath) / f
                if not self._allowed(p): 
                    continue
                out.append({"path": str(p.relative_to(root)), "type": "file"})
        return sorted(out, key=lambda x: (x["type"], x["path"]))

    def read(self, rel: str, start: int = 0, length: Optional[int] = None) -> dict:
        path = self._check_file(rel)
        with open(path, "rb") as f:
            f.seek(start)
            data = f.read(self.cfg.max_read_bytes if length is None else min(length, self.cfg.max_read_bytes))
        try:
            text = data.decode("utf-8")
            mode = "text"
            content = text
        except UnicodeDecodeError:
            mode = "bytes"
            content = data.hex()
        return {"mode": mode, "content": content}

    def write(self, rel: str, content: str, backup: bool = True) -> dict:
        path = self._target(rel)
        if backup and path.exists():
            backup_file(self.cfg.backup_dir, path)
        atomic_write(path, content.encode("utf-8"))
        return {"ok": True, "path": rel}

    def create_dir(self, rel: str) -> dict:
        p = self._target(rel)
        p.mkdir(parents=True, exist_ok=True)
        return {"ok": True}

    def delete(self, rel: str) -> dict:
        p = self._target(rel)
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
        return {"ok": True}

    def move(self, src: str, dst: str) -> dict:
        s = self._target(src)
        d = self._target(dst)
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(s), str(d))
        return {"ok": True}

    def _allowed(self, p: Path) -> bool:
        if not match_any(p, self.cfg.allow_patterns): 
            return False
        if match_any(p, self.cfg.deny_patterns): 
            return False
        return True

    def _target(self, rel: str) -> Path:
        root = self.cfg.project_root
        p = jail_path(root, rel)
        if not self._allowed(p):
            raise PermissionError(f"blocked by pattern: {rel}")
        return p

    def _check_file(self, rel: str) -> Path:
        p = self._target(rel)
        if not p.is_file():
            raise FileNotFoundError(rel)
        return p
