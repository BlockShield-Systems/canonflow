"""Free nodes: RAG retrieval and read-only ClickHouse via MCP.

Request shape per RagQuery: query.text plus query.ragRetrievalConfig.topK and
query.ragRetrievalConfig.filter.vectorDistanceThreshold. The top-level
vectorDistanceThreshold on VertexRagStore is deprecated and rejected.
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

from ..auth import headers, project
from .base import node

RAG_LOCATION = "us-central1"


def _fail(label: str, r: httpx.Response) -> None:
    try:
        msg = r.json().get("error", {}).get("message", r.text)
    except Exception:  # noqa: BLE001
        msg = r.text
    raise RuntimeError(f"{label} HTTP {r.status_code}: {str(msg)[:600]}")


@node("rag.retrieve")
def rag_retrieve(*, query: str, corpus: str, top_k: int = 10,
                 distance_threshold: float = 0.6,
                 ranker_model: str | None = None, **_: Any) -> dict:
    url = (f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1/projects/"
           f"{project()}/locations/{RAG_LOCATION}:retrieveContexts")

    cfg: dict[str, Any] = {
        "topK": int(top_k),
        "filter": {"vectorDistanceThreshold": float(distance_threshold)},
    }
    if ranker_model:
        cfg["ranking"] = {"llmRanker": {"modelName": ranker_model}}

    body = {
        "vertexRagStore": {"ragResources": [{"ragCorpus": corpus}]},
        "query": {"text": query, "ragRetrievalConfig": cfg},
    }

    r = httpx.post(url, headers=headers(), json=body, timeout=90.0)
    if r.status_code != 200:
        _fail("retrieveContexts", r)

    ctxs = r.json().get("contexts", {}).get("contexts", [])
    items = [
        {"source": c.get("sourceUri") or c.get("sourceDisplayName", ""),
         "distance": c.get("distance"),
         "score": c.get("score"),
         "text": c.get("text", "")}
        for c in ctxs
    ]
    joined = "\n\n".join(
        f"[{i + 1}] {c['source']}\n{c['text']}" for i, c in enumerate(items))
    return {"query": query, "count": len(items), "contexts": items, "text": joined}


@node("mcp.query")
def mcp_query(*, sql: str, tool: str = "run_query",
              endpoint: str | None = None, **_: Any) -> dict:
    ep = endpoint or os.environ.get("CF_MCP_ENDPOINT", "http://127.0.0.1:8000/mcp")
    hdrs = {"Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"}
    _tok = (os.environ.get("CF_MCP_TOKEN")
            or os.environ.get("CLICKHOUSE_MCP_AUTH_TOKEN"))
    if _tok:
        hdrs["Authorization"] = f"Bearer {_tok}"

    try:
        with httpx.Client(timeout=120.0) as cli:
            # 1) initialize -> Mcp-Session-Id
            init = cli.post(ep, headers=hdrs, json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                           "clientInfo": {"name": "canonflow", "version": "0.1"}}})
            if init.status_code != 200:
                _fail("mcp initialize", init)
            sid = init.headers.get("mcp-session-id")
            if sid:
                hdrs["Mcp-Session-Id"] = sid

            # 2) initialized notification (no response body expected)
            cli.post(ep, headers=hdrs, json={
                "jsonrpc": "2.0", "method": "notifications/initialized"})

            # 3) tools/call
            r = cli.post(ep, headers=hdrs, json={
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": tool, "arguments": {"query": sql}}})
    except httpx.ConnectError as exc:
        raise RuntimeError(f"MCP server unreachable at {ep}: {exc}") from exc
    if r.status_code != 200:
        _fail("mcp", r)

    raw = r.text
    for line in raw.splitlines():
        if line.startswith("data:"):
            raw = line[5:].strip()
            break
    if not raw.strip():
        raise RuntimeError(
            f"mcp empty response: status={r.status_code} "
            f"ct={r.headers.get('content-type')!r}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"mcp non-JSON response: status={r.status_code} "
            f"ct={r.headers.get('content-type')!r} "
            f"body[:400]={r.text[:400]!r}") from exc
    if "error" in data:
        raise RuntimeError(f"MCP error: {data['error']}")
    content = data.get("result", {}).get("content", [])
    text = "\n".join(c.get("text", "") for c in content if c.get("type") == "text")
    return {"sql": sql, "text": text}


@node("rag.list_corpora")
def rag_list_corpora(**_: Any) -> dict:
    """Free diagnostic. Confirms corpus name and location before a retrieval."""
    url = (f"https://{RAG_LOCATION}-aiplatform.googleapis.com/v1/projects/"
           f"{project()}/locations/{RAG_LOCATION}/ragCorpora")
    r = httpx.get(url, headers=headers(), timeout=60.0)
    if r.status_code != 200:
        _fail("listRagCorpora", r)
    corpora = r.json().get("ragCorpora", [])
    return {"count": len(corpora),
            "corpora": [{"name": c.get("name"),
                         "display_name": c.get("displayName")} for c in corpora]}
