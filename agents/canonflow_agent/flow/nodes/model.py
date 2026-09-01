"""Structured model calls. Only reasoning models are used here; renderer
models support neither structured output nor function calling."""
from __future__ import annotations

import json
from typing import Any

import os
import time
import sys
import random

import httpx

from ..auth import headers, project
from .base import node

TEXT_HOST = "https://aiplatform.googleapis.com"
TEXT_LOCATION = "global"

# Keys accepted by the Vertex Schema object. Anything else returns HTTP 400,
# so JSON Schema fragments must be reduced before they are sent.
ALLOWED_SCHEMA_KEYS = {
    "type", "format", "title", "description", "nullable", "items", "minItems",
    "maxItems", "enum", "properties", "required", "minProperties",
    "maxProperties", "minimum", "maximum", "pattern", "anyOf",
    "propertyOrdering", "default",
}


def normalize_schema(node: Any) -> Any:
    """Reduce a JSON Schema fragment to the Vertex subset.

    Two structural rules matter. First, 'properties' is a map of field name to
    schema, so its keys must survive the allow-list untouched while its values
    are normalized. Second, enum is only valid on type string: an integer enum
    such as {"type": "integer", "enum": [4, 6, 8, 10]} is rejected, so the
    values are stringified and the type is switched. Pydantic coerces them back
    when the typed shot object is built.
    """
    if isinstance(node, list):
        return [normalize_schema(x) for x in node]
    if not isinstance(node, dict):
        return node

    out: dict[str, Any] = {}
    for key, value in node.items():
        if key not in ALLOWED_SCHEMA_KEYS:
            continue
        if key == "properties" and isinstance(value, dict):
            out[key] = {name: normalize_schema(sub) for name, sub in value.items()}
        elif key == "items":
            out[key] = normalize_schema(value)
        elif key == "anyOf" and isinstance(value, list):
            out[key] = [normalize_schema(x) for x in value]
        else:
            out[key] = value

    if "enum" in out:
        values = out["enum"]
        if not all(isinstance(v, str) for v in values):
            out["enum"] = [str(v) for v in values]
            out["type"] = "string"
            hint = "One of: " + ", ".join(out["enum"]) + "."
            out["description"] = (out.get("description", "") + " " + hint).strip()
        else:
            out.setdefault("type", "string")

    return out


def _fail(model: str, r: httpx.Response) -> None:
    try:
        msg = r.json().get("error", {}).get("message", r.text)
    except Exception:  # noqa: BLE001
        msg = r.text
    raise RuntimeError(f"{model} HTTP {r.status_code}: {str(msg)[:900]}")


_TIMEOUT = httpx.Timeout(
    connect=30.0,
    read=float(os.environ.get("CF_MODEL_READ_TIMEOUT", "240")),
    write=60.0,
    pool=30.0,
)


@node("model.json")
def model_json(*, model: str, system: str = "", prompt: str,
               response_schema: dict, temperature: float = 0.4,
               thinking_level: str | None = None,
               max_output_tokens: int = 8192, **_: Any) -> dict:
    url = (f"{TEXT_HOST}/v1/projects/{project()}/locations/{TEXT_LOCATION}"
           f"/publishers/google/models/{model}:generateContent")
    gen: dict[str, Any] = {
        "temperature": temperature,
        "maxOutputTokens": max_output_tokens,
        "responseMimeType": "application/json",
        "responseSchema": normalize_schema(response_schema),
    }
    if thinking_level:
        gen["thinkingConfig"] = {"thinkingLevel": thinking_level}
    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": gen,
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}

    attempts = int(os.environ.get("CF_MODEL_MAX_ATTEMPTS", "6"))
    transport_budget = int(os.environ.get("CF_MODEL_TRANSPORT_RETRIES", "3"))
    for attempt in range(1, attempts + 1):
        delay = 0.0
        try:
            r = httpx.post(url, headers=headers(), json=body, timeout=_TIMEOUT)
            if r.status_code == 200:
                break
            if (r.status_code not in (429, 499, 500, 502, 503, 504)
                    or attempt == attempts):
                _fail(model, r)
            reason = f"HTTP {r.status_code}"
            ra = r.headers.get("Retry-After")
            if ra and ra.isdigit():
                delay = float(ra)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            transport_budget -= 1
            if transport_budget < 0 or attempt == attempts:
                raise RuntimeError(
                    f"{model} transport failure, giving up: {exc!r}") from exc
            reason = type(exc).__name__
        if not delay:
            delay = min(15.0 * 2 ** (attempt - 1), 300.0) * (0.7 + random.random() * 0.6)
        print(f"WARN {model} {reason}, retry {attempt}/{attempts - 1} "
              f"in {delay:.1f}s", file=sys.stderr)
        time.sleep(delay)

    data = r.json()
    cand = data["candidates"][0]
    reason = cand.get("finishReason")
    if reason not in (None, "STOP"):
        raise RuntimeError(
            f"{model} finished with {reason}; raise max_output_tokens or "
            f"simplify the schema")

    parts = cand.get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts)
    if not text.strip():
        raise RuntimeError(f"{model} returned an empty candidate ({reason})")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{model} returned invalid JSON: {exc}; first 300 chars: "
            f"{text[:300]}") from exc

    usage = data.get("usageMetadata", {})
    return {
        "model": model,
        "output": parsed,
        "usage": {
            "prompt_tokens": usage.get("promptTokenCount", 0),
            "output_tokens": usage.get("candidatesTokenCount", 0),
            "thoughts_tokens": usage.get("thoughtsTokenCount", 0),
        },
    }


@node("model.count_tokens")
def count_tokens(*, model: str, prompt: str, **_: Any) -> dict:
    url = (f"{TEXT_HOST}/v1/projects/{project()}/locations/{TEXT_LOCATION}"
           f"/publishers/google/models/{model}:countTokens")
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    r = httpx.post(url, headers=headers(), json=body, timeout=60.0)
    if r.status_code != 200:
        _fail(model, r)
    return r.json()
