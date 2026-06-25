"""
title: GetWeather
author: HINDSIGHT
version: 0.1
description: Calls the local weather proxy when users ask about weather.
"""

import json
import re
from typing import Optional

import requests
from pydantic import BaseModel, Field


class Filter:
    class Valves(BaseModel):
        weather_api_url: str = Field(
            default="http://host.docker.internal:5000/weather",
            description="Weather proxy URL (host.docker.internal from Open WebUI Docker)",
        )
        default_city: str = Field(
            default="Tel Aviv",
            description="Fallback city when none is detected in the prompt",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.toggle = True

    async def inlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__=None,
    ) -> dict:
        messages = body.get("messages") or []
        if not messages:
            return body

        last = messages[-1]
        if last.get("role") != "user":
            return body

        content = self._message_text(last.get("content", ""))
        if not re.search(
            r"\b(weather|temperature|forecast|rain|wind|humidity|celsius|fahrenheit)\b",
            content,
            re.I,
        ):
            return body

        city = self._extract_city(content) or self.valves.default_city

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Fetching weather for {city}...",
                        "done": False,
                    },
                }
            )

        try:
            response = requests.get(
                self.valves.weather_api_url,
                params={"city": city},
                timeout=10,
            )
            response.raise_for_status()
            weather = response.json()
            weather_text = json.dumps(weather, ensure_ascii=False)
        except Exception as exc:
            weather_text = json.dumps({"error": str(exc), "city": city})

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Weather loaded for {city}",
                        "done": True,
                    },
                }
            )

        context = {
            "role": "system",
            "content": (
                f"Live weather for {city}: {weather_text}. "
                "Answer the user's weather question using this data."
            ),
        }
        body["messages"] = messages[:-1] + [context, last]
        return body

    @staticmethod
    def _message_text(content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(str(item.get("text") or item.get("content") or ""))
                else:
                    parts.append(str(item))
            return " ".join(parts)
        return str(content)

    @staticmethod
    def _extract_city(text: str) -> Optional[str]:
        patterns = [
            r"(?:weather|temperature|forecast)\s+(?:in|for|at)\s+([A-Za-z][A-Za-z\s\-']{1,40})",
            r"(?:in|for|at)\s+([A-Za-z][A-Za-z\s\-']{1,40})\?",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return match.group(1).strip().rstrip("?.,!")
        return None
