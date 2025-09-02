from __future__ import annotations
from pathlib import Path
import io, difflib
from ..config import AgentConfig
from ..utils import jail_path, backup_file, atomic_write
from ..llm import LLM, EditInstruction

class EditTool:
    def __init__(self, cfg: AgentConfig, llm: LLM):
        self.cfg = cfg
        self.llm = llm

    def apply_unified_diff(self, filename: str, diff_text: str) -> dict:
        # minimal unified-diff applier (single-file)
        try:
            target = (self.cfg.project_root / filename).resolve()
            if not str(target).startswith(str(self.cfg.project_root)):
                return {"ok": False, "error": "Permission denied: path outside project root"}
            
            if not target.exists():
                old_lines = []
            else:
                with open(target, "r", encoding="utf-8", errors="ignore") as f:
                    old_lines = f.read().splitlines(keepends=True)

            patched = self._patch(old_lines, diff_text)
            if patched is None:
                return {"ok": False, "error": "Failed to parse diff or apply changes"}
                
            backup_file(self.cfg.backup_dir, target) if target.exists() else None
            atomic_write(target, "".join(patched).encode("utf-8"))
            return {"ok": True, "file": filename}
            
        except Exception as e:
            return {"ok": False, "error": f"Failed to apply diff: {str(e)}"}

    def suggest_and_apply(self, filename: str, goal: str) -> dict:
        path = (self.cfg.project_root / filename).resolve()
        text = ""
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="ignore")
        diff = self.llm.generate_unified_diff(filename, text, EditInstruction(goal=goal, context=text))
        return self.apply_unified_diff(filename, diff)

    def _patch(self, old_lines: list[str], diff_text: str) -> list[str] | None:
        # very small unified diff parser; good enough for typical hunks
        try:
            if not diff_text or not diff_text.strip():
                return None
                
            patched = old_lines[:]
            s = io.StringIO(diff_text)
            # skip header lines
            while True:
                line = s.readline()
                if not line:
                    break
                if line.startswith('@@'):
                    # start hunk
                    break
            if not line:
                # No hunk found, try to rebuild from entire diff
                s.seek(0)
                new = []
                for l in s.readlines():
                    if l.startswith('@@'):
                        continue
                    if l.startswith('+') and not l.startswith('+++'):
                        new.append(l[1:])
                    elif l.startswith('-') and not l.startswith('---'):
                        # skip removed line
                        continue
                    elif l.startswith('\\ No newline'):
                        continue
                    else:
                        if l.startswith('---') or l.startswith('+++'):
                            continue
                        new.append(l[1:] if l.startswith(' ') else l)
                return new if new else None
                
            # naive: rebuild from diff body
            new = []
            # Rewind one hunk header line processed
            body = [line] + s.readlines()
            for l in body:
                if l.startswith('@@'):
                    continue
                if l.startswith('+') and not l.startswith('+++'):
                    new.append(l[1:])
                elif l.startswith('-') and not l.startswith('---'):
                    # skip removed line
                    continue
                elif l.startswith('\\ No newline'):
                    continue
                else:
                    if l.startswith('---') or l.startswith('+++'):
                        continue
                    new.append(l[1:] if l.startswith(' ') else l)
            return new
        except Exception:
            return None
