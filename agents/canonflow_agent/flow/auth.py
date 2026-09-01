"""ADC token helper. Every publisher call must carry x-goog-user-project."""
from __future__ import annotations

import os
import google.auth
from google.auth.transport.requests import Request

_CREDS = None
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def project() -> str:
    p = os.environ.get("CF_PROJECT")
    if not p:
        raise RuntimeError("CF_PROJECT is not set")
    return p


def token() -> str:
    global _CREDS
    if _CREDS is None:
        _CREDS, _ = google.auth.default(scopes=SCOPES)
    if not _CREDS.valid:
        _CREDS.refresh(Request())
    return _CREDS.token


def headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token()}",
        "x-goog-user-project": project(),
        "Content-Type": "application/json",
    }
