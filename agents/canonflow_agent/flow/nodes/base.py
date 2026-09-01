from __future__ import annotations

from typing import Any, Callable

REGISTRY: dict[str, "NodeSpec"] = {}


class NodeSpec:
    def __init__(self, kind: str, fn: Callable[..., Any], costs: bool):
        self.kind = kind
        self.fn = fn
        self.costs = costs


def node(kind: str, costs: bool = False):
    def deco(fn):
        REGISTRY[kind] = NodeSpec(kind, fn, costs)
        return fn
    return deco


def get(kind: str) -> NodeSpec:
    if kind not in REGISTRY:
        raise KeyError(f"unknown node kind: {kind} (known: {sorted(REGISTRY)})")
    return REGISTRY[kind]
