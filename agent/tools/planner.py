from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Any

@dataclass
class Step:
    kind: Literal["fs.tree","fs.read","fs.write","fs.create_dir","fs.delete","fs.move","term.open","term.exec","term.read","edit.apply","edit.suggest"]
    args: dict

class Planner:
    """placeholder for higher-level task decomposition."""
    def plan(self, goal: str) -> list[Step]:
        # naive baseline: just return empty plan; you can grow this with an LLM.
        return []
