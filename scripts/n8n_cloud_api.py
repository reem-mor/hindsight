"""Shared n8n Cloud REST helpers for HINDSIGHT scripts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

WORKFLOW_ID = "aYEv22StywIPL3Rq"
SHEET_ID_DEFAULT = "1Z7tiPISHB5siYby_lQnWA9wtXbDXVSGTu4HGZ5Dk2tk"

NODE_FILES = {
    "Prepare Document": "prepare.js",
    "Parse Gemini JSON": "parse.js",
    "HINDSIGHT Enrich": "enrich.js",
    "Compose Outputs": "compose.js",
    "Flatten for Sheets": "sheet_row.js",
}

SHEET_HEADERS = [
    "document_id",
    "filename",
    "file_type",
    "processed_at",
    "classification",
    "department",
    "sentiment",
    "confidence_score",
    "summary",
    "routing_tag",
    "sensitivity",
    "action_items",
    "cvss_score",
    "cve_ids",
]


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def api_request(base: str, key: str, method: str, path: str, body: dict | None = None) -> dict:
    url = f"{base.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = Request(
        url,
        data=data,
        method=method,
        headers={
            "X-N8N-API-KEY": key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=120) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        err_body = exc.read().decode() if exc.fp else ""
        raise HTTPError(exc.url, exc.code, f"{exc.reason}: {err_body[:800]}", exc.headers, exc.fp)


def api_get(base: str, key: str, path: str) -> dict:
    return api_request(base, key, "GET", path)


def strip_workflow_meta(wf: dict) -> dict:
    settings = wf.get("settings") or {}
    clean_settings = {"executionOrder": settings.get("executionOrder", "v1")}
    return {
        "name": wf.get("name"),
        "nodes": wf.get("nodes", []),
        "connections": wf.get("connections", {}),
        "settings": clean_settings,
    }


def read_node_bodies(root: Path) -> dict[str, str]:
    nodes_dir = root / "n8n" / "cloud" / "nodes"
    out: dict[str, str] = {}
    for node_name, filename in NODE_FILES.items():
        out[node_name] = (nodes_dir / filename).read_text(encoding="utf-8")
    return out


def patch_workflow_nodes(
    wf: dict,
    bodies: dict[str, str],
    sheet_id: str | None = None,
) -> int:
    patched = 0
    for node in wf.get("nodes", []):
        name = node.get("name", "")
        if name in bodies:
            node.setdefault("parameters", {})
            node["parameters"]["jsCode"] = bodies[name]
            patched += 1
        if sheet_id and name == "Append to Registry":
            node.setdefault("parameters", {})
            node["parameters"]["documentId"] = {
                "__rl": True,
                "mode": "id",
                "value": sheet_id,
                "cachedResultName": "HINDSIGHT Incident Registry",
            }
            node["parameters"]["sheetName"] = {
                "__rl": True,
                "mode": "name",
                "value": "Incidents",
                "cachedResultName": "Incidents",
            }
            node["parameters"]["options"] = {
                "handlingExtraData": "ignoreIt",
                "useAppend": True,
            }
            patched += 1
    return patched


def ensure_flatten_sheets_node(wf: dict, root: Path) -> bool:
    """Insert Flatten for Sheets between Compose Outputs and Append to Registry."""
    nodes = wf.get("nodes", [])
    names = {n.get("name") for n in nodes}
    if "Flatten for Sheets" in names:
        return False
    compose = next((n for n in nodes if n.get("name") == "Compose Outputs"), None)
    append = next((n for n in nodes if n.get("name") == "Append to Registry"), None)
    if not compose or not append:
        return False
    sheet_js = (root / "n8n" / "cloud" / "nodes" / "sheet_row.js").read_text(encoding="utf-8")
    flatten_id = str(__import__("uuid").uuid4())
    cx, cy = compose.get("position", [1320, 460])
    ax, ay = append.get("position", [1540, 320])
    flatten_node = {
        "id": flatten_id,
        "name": "Flatten for Sheets",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [int((cx + ax) / 2), int((cy + ay) / 2)],
        "parameters": {
            "mode": "runOnceForAllItems",
            "language": "javaScript",
            "jsCode": sheet_js,
        },
    }
    nodes.append(flatten_node)
    conns = wf.setdefault("connections", {})
    compose_main = conns.get("Compose Outputs", {}).get("main", [])
    if not compose_main:
        compose_main = [[{"node": "Append to Registry", "type": "main", "index": 0}]]
    new_main = []
    for branch in compose_main:
        new_branch = []
        for target in branch:
            if target.get("node") == "Append to Registry":
                new_branch.append({"node": "Flatten for Sheets", "type": "main", "index": 0})
            else:
                new_branch.append(target)
        new_main.append(new_branch)
    conns["Compose Outputs"] = {"main": new_main}
    conns["Flatten for Sheets"] = {
        "main": [[{"node": "Append to Registry", "type": "main", "index": 0}]]
    }
    return True
