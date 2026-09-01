"""Expression resolution for workflow parameters.

Syntax: ${nodes.<node_id>.output.<path>} | ${input.<key>} | ${config.<key>}
        | ${run.<key>} | ${env.<VAR>}
Paths support dots and [index]. A parameter whose whole value is a single
expression yields the referenced object; otherwise the value is interpolated
into a string.
"""
from __future__ import annotations

import os
import re
from typing import Any

EXPR = re.compile(r"\$\{([^}]+)\}")
_PART = re.compile(r"[^.\[\]]+")


def refs(value: Any) -> set[str]:
    """Return node ids referenced anywhere inside value."""
    out: set[str] = set()
    if isinstance(value, str):
        for m in EXPR.finditer(value):
            p = m.group(1).strip()
            if p.startswith("nodes."):
                out.add(_PART.findall(p)[1])
    elif isinstance(value, list):
        for v in value:
            out |= refs(v)
    elif isinstance(value, dict):
        for v in value.values():
            out |= refs(v)
    return out


def _walk(root: Any, path: str) -> Any:
    cur = root
    for part in _PART.findall(path):
        if isinstance(cur, list):
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            if part not in cur:
                raise KeyError(f"expression path not resolvable: ${{{path}}} at '{part}'")
            cur = cur[part]
        else:
            cur = getattr(cur, part)
    return cur


def _lookup(path: str, ctx: dict) -> Any:
    if path.startswith("env."):
        key = path[4:]
        val = os.environ.get(key)
        if val is None:
            raise KeyError(f"environment variable not set: {key}")
        return val
    return _walk(ctx, path)


def resolve(value: Any, ctx: dict) -> Any:
    if isinstance(value, str):
        whole = EXPR.fullmatch(value.strip())
        if whole:
            return _lookup(whole.group(1).strip(), ctx)
        return EXPR.sub(lambda m: str(_lookup(m.group(1).strip(), ctx)), value)
    if isinstance(value, list):
        return [resolve(v, ctx) for v in value]
    if isinstance(value, dict):
        return {k: resolve(v, ctx) for k, v in value.items()}
    return value
