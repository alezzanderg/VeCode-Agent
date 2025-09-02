from __future__ import annotations
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys
from pathlib import Path
import os

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip loading

from agent.config import AgentConfig
from agent.tools.executor import Executor

app = FastAPI(title="VSCode AI Agent", version="0.1.0")

class DispatchIn(BaseModel):
    kind: str
    args: dict = {}

@app.on_event("startup")
def startup():
    project_root = os.environ.get("AGENT_PROJECT_ROOT", os.getcwd())
    shell = os.environ.get("AGENT_SHELL", "bash")
    app.state.cfg = AgentConfig(project_root=Path(project_root), shell=shell).resolve()
    app.state.exec = Executor(app.state.cfg)

@app.post("/dispatch")
def dispatch(inp: DispatchIn):
    try:
        return {"result": app.state.exec.dispatch(inp.kind, inp.args)}
    except Exception as e:
        raise HTTPException(400, detail=str(e))

@app.get("/health")
def health():
    return {"ok": True}
