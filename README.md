# VSCode AI Agent (Python)

A Python-based AI agent that integrates with VSCode to provide file system operations, code editing, and terminal management capabilities.

## Setup

### 1. Environment Setup

Run the following commands to set up the environment:

```bash
export AGENT_PROJECT_ROOT="/absolute/path/to/your/repo"
export AGENT_SHELL="bash"  # or "pwsh" on Windows
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. DeepSeek API Configuration

1. Get your API key from [DeepSeek Platform](https://platform.deepseek.com/)
2. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
3. Edit `.env` and add your DeepSeek API key:
   ```
   DEEPSEEK_API_KEY=your_actual_api_key_here
   ```

### 3. Start the Agent

```bash
python run.py
```

**Note:** The agent will work in fallback mode (simple comment injection) if no DeepSeek API key is provided.

## API Usage

The agent exposes an HTTP API endpoint at `POST /dispatch`. All requests should include a JSON payload with `kind` and `args` fields.

### File System Operations

**Get directory tree:**
```json
{"kind":"fs.tree","args":{"rel":".","max_depth":4}}
```

**Read a file:**
```json
{"kind":"fs.read","args":{"rel":"app/page.tsx"}}
```

**Write a file:**
```json
{"kind":"fs.write","args":{"rel":"docs/plan.md","content":"# Plan\n..."}}
```

**Create directory:**
```json
{"kind":"fs.create_dir","args":{"rel":"features/auth"}}
```

**Move files:**
```json
{"kind":"fs.move","args":{"src":"docs/plan.md","dst":"docs/v1/plan.md"}}
```

### Code Editing

**Suggest code change with LLM and apply:**
```json
{"kind":"edit.suggest","args":{"filename":"app/api/users/route.ts","goal":"add GET handler that returns current user from session"}}
```

**Apply your own unified diff:**
```json
{"kind":"edit.apply","args":{"filename":"app/page.tsx","diff_text":"--- a/app/page.tsx\n+++ b/app/page.tsx\n@@\n-import React from 'react'\n+import React from 'react'\n+// injected comment\n"}}
```

### Terminal Operations

**Terminal session management:**
```json
{"kind":"term.open","args":{"session_id":"build"}}
{"kind":"term.exec","args":{"session_id":"build","command":"npm run build"}}
{"kind":"term.read","args":{"session_id":"build"}}
{"kind":"term.close","args":{"session_id":"build"}}
```

## Security Features

- **Sandboxing:** Operations are jailed to `AGENT_PROJECT_ROOT`
- **File filtering:** Denies access to `.git/**`, `node_modules/**`, `.env*` by default
- **Backup system:** Automatic backups saved to `.ai_agent_backups/`

## LLM Integration

The agent now includes **DeepSeek API integration** for intelligent code editing:

- **Model**: Uses `deepseek-coder` for code generation and editing
- **Fallback**: Automatically falls back to simple comment injection if API key is missing
- **Error Handling**: Graceful error handling with logging for API failures
- **Configuration**: Configurable via environment variables or config parameters

### Custom LLM Providers

To integrate your own LLM provider, modify the `LLM` class in `agent/llm.py` and implement the `generate_unified_diff(...)` method to call your provider.

## VSCode Integration

For Electron-based VSCode forks, you can integrate the agent from the renderer or main process:

```typescript
// Agent integration helper
async function agent(kind: string, args: any) {
  const res = await fetch("http://127.0.0.1:3111/dispatch", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({kind, args})
  });
  if (!res.ok) throw new Error(await res.text());
  const {result} = await res.json();
  return result;
}

// Usage examples
await agent("fs.tree", {rel: ".", max_depth: 3});
await agent("fs.write", {rel: "notes/todo.md", content: "- [ ] wire API\n"});
await agent("term.open", {session_id: "dev"});
await agent("term.exec", {session_id: "dev", command: "pnpm dev"});
const out = await agent("term.read", {session_id: "dev"});
```

## Security Hardening

### Quick Security Notes

- **User isolation:** Run the Python agent with a dedicated user account with least privileges
- **Command allowlist:** Consider implementing an allow-list for shell commands (build/test/package) instead of allowing arbitrary shell access
- **Audit logging:** Log every action; optionally require a "dry-run + user confirm" workflow for edits over N KB
- **Git integration:** Consider git preconditions - refuse edits if working tree has uncommitted changes unless `force=true`
- **Network security:** Add rate limiting + CSRF token protection even on localhost in your fork

### Recommended Security Practices

1. **Process isolation:** Run the agent in a containerized environment
2. **File system permissions:** Restrict write access to only necessary directories
3. **Network policies:** Implement proper firewall rules for the agent's HTTP server
4. **Input validation:** Sanitize all user inputs and file paths
5. **Session management:** Implement proper session handling and timeout mechanisms
