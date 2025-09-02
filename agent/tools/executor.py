from __future__ import annotations
from typing import Any
from ..config import AgentConfig
from .fs import FileSystemTool
from .terminal import TerminalTool
from .edit import EditTool
from ..llm import LLM

class Executor:
    def __init__(self, cfg: AgentConfig):
        self.cfg = cfg
        self.fs = FileSystemTool(cfg)
        self.term = TerminalTool(cfg)
        # Initialize LLM with DeepSeek configuration
        llm = LLM(
            api_key=cfg.deepseek_api_key,
            base_url=cfg.deepseek_base_url
        )
        self.edit = EditTool(cfg, llm)

    def dispatch(self, kind: str, args: dict) -> Any:
        k = kind
        m = {
            "fs.tree": lambda: self.fs.tree(**args),
            "fs.read": lambda: self.fs.read(**args),
            "fs.write": lambda: self.fs.write(**args),
            "fs.create_dir": lambda: self.fs.create_dir(**args),
            "fs.delete": lambda: self.fs.delete(**args),
            "fs.move": lambda: self.fs.move(**args),
            "term.open": lambda: self.term.open(**args),
            "term.exec": lambda: self.term.exec(**args),
            "term.read": lambda: self.term.read(**args),
            "edit.apply": lambda: self.edit.apply_unified_diff(**args),
            "edit.suggest": lambda: self.edit.suggest_and_apply(**args),
        }.get(k)
        if not m:
            raise ValueError(f"unknown action: {k}")
        return m()
