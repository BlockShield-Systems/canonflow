"""Deterministic nodes. No model, no cost."""
from __future__ import annotations

import importlib
from typing import Any

from .base import node


@node("python.fn")
def python_fn(*, target: str, args: dict | None = None, **_: Any) -> Any:
    mod_name, _, fn_name = target.rpartition(":")
    if not mod_name:
        raise ValueError("target must be 'package.module:function'")
    fn = getattr(importlib.import_module(mod_name), fn_name)
    return fn(**(args or {}))


@node("flow.assert")
def flow_assert(*, condition: Any, equals: Any = None,
                message: str = "assertion failed", **_: Any) -> dict:
    ok = (condition == equals) if equals is not None else bool(condition)
    if not ok:
        raise AssertionError(f"{message} (got: {condition!r})")
    return {"ok": True, "condition": condition}


@node("flow.passthrough")
def passthrough(**kwargs: Any) -> dict:
    kwargs.pop("_ctx", None)
    return kwargs
