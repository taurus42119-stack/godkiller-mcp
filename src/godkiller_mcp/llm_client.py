"""OpenAI-compatible chat client (stdlib only) for multi-agent council."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from godkiller_mcp.ssrf import SafeHTTPError, safe_urlopen


ChatFn = Callable[[str, str], str]  # (system, user) -> assistant text


@dataclass
class LLMConfig:
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    timeout_sec: int = 60

    @property
    def chat_url(self) -> str:
        return self.base_url.rstrip("/") + "/chat/completions"


def load_llm_config() -> Optional[LLMConfig]:
    key = (
        os.environ.get("GODKILLER_LLM_API_KEY", "").strip()
        or os.environ.get("OPENAI_API_KEY", "").strip()
    )
    if not key:
        return None
    base = os.environ.get("GODKILLER_LLM_BASE_URL", "https://api.openai.com/v1").strip()
    model = os.environ.get("GODKILLER_LLM_MODEL", "gpt-4o-mini").strip()
    timeout = int(os.environ.get("GODKILLER_LLM_TIMEOUT", "60"))
    return LLMConfig(api_key=key, base_url=base, model=model, timeout_sec=timeout)


def chat_completion(config: LLMConfig, system: str, user: str) -> str:
    payload = {
        "model": config.model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload).encode("utf-8")
    host = (urllib.parse.urlparse(config.chat_url).hostname or "").strip().lower()
    allow = [host] if host else None
    try:
        with safe_urlopen(
            config.chat_url,
            timeout=float(config.timeout_sec),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.api_key}",
            },
            data=data,
            method="POST",
            allowed_hosts=allow,
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except SafeHTTPError as e:
        raise RuntimeError(f"LLM SSRF blocked: {e}") from e
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")[:500]
        raise RuntimeError(f"LLM HTTP {e.code}: {detail}") from e
    except Exception as e:
        raise RuntimeError(f"LLM request failed: {e}") from e

    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Unexpected LLM response shape: {body!r}") from e


def make_chat_fn(config: LLMConfig) -> ChatFn:
    def _fn(system: str, user: str) -> str:
        return chat_completion(config, system, user)

    return _fn


def parse_agent_json(raw: str) -> Dict[str, Any]:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    # salvage first {...}
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        return json.loads(raw[start : end + 1])
    return {"vote": "REJECT", "critique": raw[:1000], "severity": 8, "parse_error": True}
