from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional

class AgentConfig(BaseModel):
    project_root: Path = Field(..., description="Absolute path to the repo root the agent is jailed to.")
    backup_dir: Path | None = None
    allow_shell: bool = True
    shell: str = "bash"  # or "pwsh" on Windows; override in server startup
    max_read_bytes: int = 2_000_000  # 2MB per read
    max_edit_bytes: int = 1_000_000
    allow_patterns: list[str] = ["**/*"]
    deny_patterns: list[str] = [".git/**", "**/.git/**", "**/node_modules/**", ".env", "**/.env*"]
    
    # DeepSeek API configuration
    deepseek_api_key: Optional[str] = Field(None, description="DeepSeek API key for LLM integration")
    deepseek_base_url: str = Field("https://api.deepseek.com", description="DeepSeek API base URL")
    deepseek_model: str = Field("deepseek-coder", description="DeepSeek model to use")

    def resolve(self):
        self.project_root = self.project_root.resolve()
        if self.backup_dir is None:
            self.backup_dir = self.project_root / ".ai_agent_backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        return self
