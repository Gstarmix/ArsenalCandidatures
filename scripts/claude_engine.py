import os
import subprocess
from scripts.config import CLAUDE_TIMEOUT
def call_claude(prompt: str, timeout: int = CLAUDE_TIMEOUT) -> str:
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.run(
        ["claude", "--print"],
        input=prompt, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
        env=env, creationflags=flags,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude CLI exit {proc.returncode}: {proc.stderr.strip()[:400]}")
    return (proc.stdout or "").strip()