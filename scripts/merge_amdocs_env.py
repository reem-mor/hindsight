"""Merge env vars from amdocs-ai-course into hindsight .env (no secrets printed)."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AMDOCS = Path(os.environ.get("AMDOCS_COURSE_ROOT", "c:/dev/amdocs-ai-course"))

COPY_KEYS = [
    "N8N_API_URL",
    "N8N_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "AWS_PROFILE",
    "AWS_REGION",
    "CONTEXT7_API_KEY",
    "PERPLEXITY_API_KEY",
    "LOVABLE_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "GOOGLE_OAUTH_REFRESH_TOKEN",
]

SOURCE_FILES = [
    AMDOCS / ".env",
    AMDOCS / "lectures/08_mcp/.env",
    AMDOCS / "lectures/09_flows_bedrock_n8n/.env",
    AMDOCS / "course_assistant/.env",
    AMDOCS / "oz_veruach_bot/.env",
]


def parse_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, _, val = s.partition("=")
        v = val.strip().strip('"').strip("'")
        if not v or "your_" in v:
            continue
        if key.strip() == "N8N_API_URL" and "your-instance" in v:
            continue
        out[key.strip()] = v
    return out


def read_existing(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def main() -> int:
    merged: dict[str, str] = {}
    for src in SOURCE_FILES:
        merged.update(parse_env(src))
    for k in COPY_KEYS:
        if os.environ.get(k):
            merged.setdefault(k, os.environ[k])

    defaults = {
        "N8N_API_URL": "https://reemmor.app.n8n.cloud",
        "AMDOCS_COURSE_ROOT": str(AMDOCS).replace("\\", "/"),
    }
    for k, v in defaults.items():
        merged[k] = v  # always prefer correct hindsight n8n URL

    dest = ROOT / ".env"
    lines = read_existing(dest)
    existing_keys = set()
    new_lines: list[str] = []
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            k = line.split("=", 1)[0].strip()
            existing_keys.add(k)
            if k in merged and merged[k]:
                new_lines.append(f"{k}={merged[k]}")
                merged.pop(k, None)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    if not dest.is_file():
        new_lines = ["# Merged from amdocs-ai-course + hindsight defaults", ""]
        existing_keys = set()

    append = []
    for k in COPY_KEYS + ["AMDOCS_COURSE_ROOT"]:
        if k not in existing_keys and merged.get(k):
            append.append(f"{k}={merged[k]}")

    if append:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        new_lines.append("# ── Copied from amdocs-ai-course ──")
        new_lines.extend(append)

    dest.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    status = {k: "SET" if parse_env(dest).get(k) else "MISSING" for k in COPY_KEYS}
    print("hindsight .env after merge:")
    for k, v in status.items():
        print(f"  {k}: {v}")
    print("  AMDOCS_COURSE_ROOT: SET")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
