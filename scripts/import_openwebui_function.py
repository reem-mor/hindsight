"""Import Open WebUI filter/tool Python files via the admin API."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEBUI = os.environ.get("OPEN_WEBUI_URL", "http://localhost:3000").rstrip("/")


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


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


def request_json(method: str, url: str, token: str | None = None, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def sign_in(base: str, email: str, password: str) -> str:
    payload = {"email": email, "password": password}
    result = request_json("POST", f"{base}/api/v1/auths/signin", payload=payload)
    token = result.get("token")
    if not token:
        raise RuntimeError("Sign-in succeeded but no token returned")
    return token


def import_function(base: str, token: str, path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    meta = parse_frontmatter(content)
    function_id = slugify(meta.get("title") or path.stem)
    payload = {
        "id": function_id,
        "name": meta.get("title") or path.stem,
        "meta": {
            "description": meta.get("description", ""),
            "manifest": meta,
        },
        "content": content,
    }

    try:
        return request_json("POST", f"{base}/api/v1/functions/create", token, payload)
    except urllib.error.HTTPError as exc:
        if exc.code != 400:
            raise
        detail = exc.read().decode("utf-8", errors="replace")
        if "taken" not in detail.lower():
            raise
        return request_json(
            "POST",
            f"{base}/api/v1/functions/id/{function_id}/update",
            token,
            payload,
        )


def activate_function(base: str, token: str, function_id: str) -> None:
    fn = request_json("GET", f"{base}/api/v1/functions/id/{function_id}", token)
    if not fn.get("is_active"):
        request_json("POST", f"{base}/api/v1/functions/id/{function_id}/toggle", token)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Open WebUI functions")
    parser.add_argument("files", nargs="*", type=Path, help="Function .py files to import")
    parser.add_argument("--url", default=DEFAULT_WEBUI)
    parser.add_argument("--email", default=os.environ.get("OPEN_WEBUI_EMAIL", ""))
    parser.add_argument("--password", default=os.environ.get("OPEN_WEBUI_PASSWORD", ""))
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")

    email = args.email or os.environ.get("OPEN_WEBUI_EMAIL", "")
    password = args.password or os.environ.get("OPEN_WEBUI_PASSWORD", "")
    if not email or not password:
        print("Set OPEN_WEBUI_EMAIL and OPEN_WEBUI_PASSWORD in .env or pass --email/--password")
        return 1

    files = args.files or list((ROOT / "open-webui" / "functions").glob("*.py"))
    if not files:
        print("No function files found")
        return 1

    token = sign_in(args.url, email, password)
    for path in files:
        result = import_function(args.url, token, path)
        function_id = result.get("id") or slugify(path.stem)
        activate_function(args.url, token, function_id)
        print(f"Imported and activated: {function_id} ({path.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
