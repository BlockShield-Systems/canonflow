from __future__ import annotations

from typing import Any

__all__ = ["root_agent"]


def __getattr__(name: str) -> Any:
    """Load the ADK root agent only when explicitly requested."""
    if name == "root_agent":
        from .agent import root_agent

        return root_agent

    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )
