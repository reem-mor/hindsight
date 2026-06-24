"""One-shot local Docker n8n setup: credentials + workflow import + publish.

Prerequisites:
  docker compose up -d
  Owner registered at http://localhost:5678 (N8N_LOCAL_EMAIL / N8N_LOCAL_PASSWORD in .env)
  .env filled: GEMINI_API_KEY, HINDSIGHT_SHEET_ID, HINDSIGHT_ALERT_EMAIL

Usage:
  python scripts/setup_local_stack.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTAINER = "hindsight-n8n"
WORKFLOW_ID = "2401581a-0001-4000-8000-hindsight001"


def _run(label: str, cmd: list[str]) -> int:
    print(f"\n--- {label} ---")
    proc = subprocess.run(cmd, cwd=ROOT)
    if proc.returncode != 0:
        print(f"FAILED: {label}")
    return proc.returncode


def main() -> int:
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    if not py.is_file():
        py = Path(sys.executable)

    steps = [
        ("Import credentials", [str(py), "scripts/import_local_credentials.py"]),
        ("Import workflow", [str(py), "scripts/import_selfhosted_workflow.py"]),
        (
            "Publish workflow",
            ["docker", "exec", CONTAINER, "n8n", "publish:workflow", f"--id={WORKFLOW_ID}"],
        ),
        ("Restart n8n", ["docker", "restart", CONTAINER]),
    ]

    for label, cmd in steps:
        if _run(label, cmd) != 0:
            return 1

    print("\nLocal stack ready. Connect Google OAuth for Sheets + Gmail in the n8n UI once.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
