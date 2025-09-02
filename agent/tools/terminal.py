from __future__ import annotations
import subprocess, threading, queue, os, shlex
from pathlib import Path
from typing import Dict
from ..config import AgentConfig

class ShellSession:
    def __init__(self, cfg: AgentConfig, session_id: str):
        self.cfg = cfg
        self.session_id = session_id
        self.proc = subprocess.Popen(
            [cfg.shell],
            cwd=str(cfg.project_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        self.q = queue.Queue()
        self._t = threading.Thread(target=self._pump, daemon=True)
        self._t.start()

    def _pump(self):
        for line in self.proc.stdout:
            self.q.put(line)

    def send(self, command: str):
        if not self.proc or not self.proc.stdin:
            raise RuntimeError("session closed")
        self.proc.stdin.write(command + "\n")
        self.proc.stdin.flush()

    def read(self, max_lines: int = 400) -> str:
        lines = []
        while not self.q.empty() and len(lines) < max_lines:
            lines.append(self.q.get_nowait())
        return "".join(lines)

    def close(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.send("exit")
            except Exception:
                pass
            self.proc.terminate()

class TerminalTool:
    def __init__(self, cfg: AgentConfig):
        self.cfg = cfg
        self.sessions: Dict[str, ShellSession] = {}

    def open(self, session_id: str) -> dict:
        if not self.cfg.allow_shell:
            raise PermissionError("shell disabled by config")
        if session_id in self.sessions:
            return {"ok": True, "existing": True}
        self.sessions[session_id] = ShellSession(self.cfg, session_id)
        return {"ok": True}

    def exec(self, session_id: str, command: str) -> dict:
        s = self.sessions.get(session_id)
        if not s:
            s = ShellSession(self.cfg, session_id)
            self.sessions[session_id] = s
        s.send(command)
        return {"ok": True}

    def read(self, session_id: str) -> dict:
        s = self.sessions.get(session_id)
        if not s:
            return {"output": ""}
        return {"output": s.read()}

    def close(self, session_id: str) -> dict:
        s = self.sessions.pop(session_id, None)
        if s:
            s.close()
        return {"ok": True}
