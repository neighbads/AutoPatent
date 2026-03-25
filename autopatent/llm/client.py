from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class OpenAICompatibleClient:
    base_url: str
    api_key: str
    model: str
    timeout_sec: int = 60
    max_tokens: int = 4096
    temperature: float = 0.2
    retries: int = 2

    @classmethod
    def from_runtime_mapping(cls, payload: Dict[str, Any]) -> "OpenAICompatibleClient":
        provider = str(payload.get("provider", "") or "").strip().lower()
        if provider != "openai-compatible":
            raise ValueError(f"Unsupported llm provider: {provider}")

        base_url = str(payload.get("base_url") or "").strip().rstrip("/")
        model = str(payload.get("model") or "").strip()
        api_key_env = str(payload.get("api_key_env") or "").strip()

        if not base_url:
            raise ValueError("llm base_url is required")
        if not model:
            raise ValueError("llm model is required")
        if not api_key_env:
            raise ValueError("llm api_key_env is required")
        api_key = str(os.getenv(api_key_env, "")).strip()
        if not api_key:
            raise ValueError(f"missing api key in env: {api_key_env}")

        timeout_sec = int(payload.get("timeout_sec", 60))
        max_tokens = int(payload.get("max_tokens", 4096))
        temperature = float(payload.get("temperature", 0.2))
        retries = int(payload.get("retries", 2))
        return cls(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_sec=timeout_sec,
            max_tokens=max_tokens,
            temperature=temperature,
            retries=retries,
        )

    def chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: Optional[int] = None,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": self.temperature,
        }

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        last_error: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    content = _extract_content(data)
                    if not content.strip():
                        raise ValueError("llm response content is empty")
                    return content.strip()
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                time.sleep(min(2.0, 0.5 * (attempt + 1)))
                continue

        raise RuntimeError(f"llm chat failed: {last_error}")


def _extract_content(payload: Dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("llm response missing choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise ValueError("llm response malformed choice")
    msg = first.get("message")
    if not isinstance(msg, dict):
        raise ValueError("llm response missing message")
    content = msg.get("content")
    if isinstance(content, str):
        return content
    # Some providers may return list of structured parts.
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content or "")
