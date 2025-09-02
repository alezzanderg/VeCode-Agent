import uvicorn
import os

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip loading

if __name__ == "__main__":
    # set the root to the VS Code workspace folder when launching from your fork
    root = os.environ.get("AGENT_PROJECT_ROOT", os.getcwd())
    print(f"AI agent jailed to: {root}")
    uvicorn.run("server.api:app", host="127.0.0.1", port=3111, reload=False)
