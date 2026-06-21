"""Service catalog: resolve messy service names to owning teams, tiers, SLOs.

Gemini emits human-written service names ("the payment gateway", "wallet-svc").
This module normalises those against the catalog so routing is deterministic and
testable rather than relying on the LLM to know your org chart.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger("hindsight.routing")


@dataclass(frozen=True)
class ServiceEntry:
    name: str
    team: str
    tier: str
    slo: float
    jurisdictions: tuple[str, ...]


def _norm(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for fuzzy matching."""
    text = text.lower().strip()
    text = re.sub(r"[_\-/]+", " ", text)
    text = re.sub(r"[^a-z0-9 ]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class ServiceCatalog:
    def __init__(self, path: Path):
        self.path = path
        self._lookup: dict[str, ServiceEntry] = {}
        self._entries: list[ServiceEntry] = []
        self._type_routing: dict[str, str] = {}
        self._defaults: dict = {}
        self._load()

    def _load(self) -> None:
        with open(self.path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}

        self._defaults = data.get("defaults", {})
        self._type_routing = data.get("type_routing", {})

        for raw in data.get("services", []):
            entry = ServiceEntry(
                name=raw["name"],
                team=raw.get("team", self._defaults.get("team", "SRE-Platform")),
                tier=raw.get("tier", self._defaults.get("tier", "standard")),
                slo=float(raw.get("slo", self._defaults.get("slo", 99.9))),
                jurisdictions=tuple(raw.get("jurisdictions", self._defaults.get("jurisdictions", ["GLOBAL"]))),
            )
            self._entries.append(entry)
            keys = [entry.name] + list(raw.get("aliases", []))
            for key in keys:
                self._lookup[_norm(key)] = entry

        logger.info(
            "service catalog loaded",
            extra={"services": len(self._entries), "aliases": len(self._lookup)},
        )

    # ---- public API ------------------------------------------------------- #
    @property
    def teams(self) -> list[str]:
        teams = {e.team for e in self._entries} | set(self._type_routing.values())
        return sorted(teams)

    @property
    def service_count(self) -> int:
        return len(self._entries)

    def resolve(self, service_name: str) -> ServiceEntry | None:
        """Resolve a single service name to a catalog entry (exact, then substring)."""
        if not service_name:
            return None
        key = _norm(service_name)
        if key in self._lookup:
            return self._lookup[key]
        # Substring match: catalog alias appears inside the emitted name or vice versa.
        for alias_key, entry in self._lookup.items():
            if alias_key and (alias_key in key or key in alias_key):
                return entry
        return None

    def resolve_many(self, service_names: list[str]) -> list[ServiceEntry]:
        seen: dict[str, ServiceEntry] = {}
        for name in service_names:
            entry = self.resolve(name)
            if entry and entry.name not in seen:
                seen[entry.name] = entry
        return list(seen.values())

    def team_for_type(self, incident_type: str) -> str:
        return self._type_routing.get(incident_type, self._defaults.get("team", "SRE-Platform"))
