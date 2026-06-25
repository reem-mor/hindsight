"""Seed Open WebUI filter functions into the running Docker container."""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUNCTIONS_DIR = ROOT / "open-webui" / "functions"
CONTAINER = "open-webui"
DB_PATH = "/app/backend/data/webui.db"


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")
    return slug or "function"


def parse_frontmatter(content: str) -> dict:
    match = re.match(r'^"""\s*\n(.*?)\n"""', content, re.S)
    if not match:
        return {}
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta


def docker_exec(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "exec", CONTAINER, *args],
        capture_output=True,
        text=True,
        check=False,
    )


def get_admin_user_id() -> str:
    result = docker_exec(
        [
            "python",
            "-c",
            (
                f"import sqlite3; c=sqlite3.connect('{DB_PATH}'); "
                "row=c.execute(\"SELECT id FROM user WHERE role='admin' LIMIT 1\").fetchone(); "
                "print(row[0] if row else '')"
            ),
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    user_id = result.stdout.strip()
    if not user_id:
        raise RuntimeError("No admin user found in Open WebUI database")
    return user_id


def upsert_function(user_id: str, function_id: str, name: str, content: str, description: str) -> None:
    meta = {
        "description": description,
        "manifest": parse_frontmatter(content),
        "toggle": True,
    }
    now = int(time.time())
    record = {
        "id": function_id,
        "user_id": user_id,
        "name": name,
        "type": "filter",
        "content": content,
        "meta": json.dumps(meta),
        "valves": "{}",
        "is_active": 1,
        "is_global": 0,
        "updated_at": now,
        "created_at": now,
    }

    payload_path = ROOT / "open-webui" / ".seed_payload.json"
    payload_path.write_text(json.dumps(record), encoding="utf-8")
    docker_payload = f"/tmp/{function_id}_seed.json"
    subprocess.run(["docker", "cp", str(payload_path), f"{CONTAINER}:{docker_payload}"], check=True)

    seed_script = f"""
import json, sqlite3
record = json.load(open("{docker_payload}", encoding="utf-8"))
c = sqlite3.connect("{DB_PATH}")
row = c.execute("SELECT id FROM function WHERE id = ?", (record["id"],)).fetchone()
if row:
    c.execute(
        "UPDATE function SET name=?, type=?, content=?, meta=?, valves=?, is_active=?, updated_at=? WHERE id=?",
        (record["name"], record["type"], record["content"], record["meta"], record["valves"], record["is_active"], record["updated_at"], record["id"]),
    )
else:
    c.execute(
        "INSERT INTO function (id, user_id, name, type, content, meta, valves, is_active, is_global, updated_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (record["id"], record["user_id"], record["name"], record["type"], record["content"], record["meta"], record["valves"], record["is_active"], 0, record["updated_at"], record["created_at"]),
    )
c.commit()
print("ok")
"""
    result = docker_exec(["python", "-c", seed_script])
    payload_path.unlink(missing_ok=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def main() -> int:
    if not FUNCTIONS_DIR.is_dir():
        print(f"Missing {FUNCTIONS_DIR}")
        return 1

    files = sorted(FUNCTIONS_DIR.glob("*.py"))
    if not files:
        print("No function files to seed")
        return 1

    user_id = get_admin_user_id()
    for path in files:
        content = path.read_text(encoding="utf-8")
        meta = parse_frontmatter(content)
        function_id = slugify(meta.get("title") or path.stem)
        name = meta.get("title") or path.stem
        description = meta.get("description", "")
        upsert_function(user_id, function_id, name, content, description)
        print(f"Seeded {function_id}")

    subprocess.run(["docker", "restart", CONTAINER], check=True)
    print(f"Restarted {CONTAINER}. Open http://localhost:3000/admin/functions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
