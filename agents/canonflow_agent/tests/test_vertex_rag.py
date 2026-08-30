from __future__ import annotations

import os
from unittest.mock import patch

from canonflow_agent.vertex_rag import (
    DEFAULT_CORPUS_ID,
    DEFAULT_LOCATION,
    DEFAULT_PROJECT_ID,
    DEFAULT_SOURCE_PREFIX,
    VertexRagError,
    VertexRagSettings,
    _build_request_body,
    _normalize_contexts,
    _validate_query,
)


def settings() -> VertexRagSettings:
    return VertexRagSettings(
        project_id=DEFAULT_PROJECT_ID,
        location=DEFAULT_LOCATION,
        corpus_id=DEFAULT_CORPUS_ID,
        source_prefix=DEFAULT_SOURCE_PREFIX,
        minimum_interval_seconds=15.0,
    )


def assert_raises(
    exception_type: type[Exception],
    callback,
) -> None:
    try:
        callback()
    except exception_type:
        return

    raise AssertionError(
        f"Expected {exception_type.__name__}"
    )


def test_default_settings_are_fixed() -> None:
    with patch.dict(os.environ, {}, clear=True):
        value = VertexRagSettings.from_environment()

    assert value.project_id == DEFAULT_PROJECT_ID
    assert value.location == DEFAULT_LOCATION
    assert value.corpus_id == DEFAULT_CORPUS_ID
    assert value.source_prefix == DEFAULT_SOURCE_PREFIX
    assert value.minimum_interval_seconds == 15.0


def test_rejects_different_project() -> None:
    with patch.dict(
        os.environ,
        {
            "CANONFLOW_VERTEX_RAG_PROJECT_ID": (
                "unauthorized-project"
            )
        },
        clear=True,
    ):
        assert_raises(
            VertexRagError,
            VertexRagSettings.from_environment,
        )


def test_rejects_rate_above_current_budget() -> None:
    with patch.dict(
        os.environ,
        {
            "CANONFLOW_VERTEX_RAG_MIN_INTERVAL_SECONDS": "14.9"
        },
        clear=True,
    ):
        assert_raises(
            VertexRagError,
            VertexRagSettings.from_environment,
        )


def test_normalizes_query() -> None:
    assert _validate_query(
        "  canon\n decisions   and context "
    ) == "canon decisions and context"


def test_rejects_empty_query() -> None:
    assert_raises(
        VertexRagError,
        lambda: _validate_query(" \n "),
    )


def test_request_is_bound_to_fixed_corpus() -> None:
    value = settings()
    body = _build_request_body(
        "canon decisions",
        value,
    )

    assert body == {
        "vertexRagStore": {
            "ragResources": [
                {
                    "ragCorpus": value.corpus_name,
                }
            ]
        },
        "query": {
            "text": "canon decisions",
        },
    }


def test_normalizes_valid_context() -> None:
    value = settings()
    response = {
        "contexts": {
            "contexts": [
                {
                    "sourceUri": (
                        DEFAULT_SOURCE_PREFIX
                        + "0000-agent-context-reminder-v2.md"
                    ),
                    "sourceDisplayName": (
                        "0000-agent-context-reminder-v2.md"
                    ),
                    "score": 0.25,
                    "text": "Source-grounded context.",
                }
            ]
        }
    }

    contexts = _normalize_contexts(response, value)

    assert len(contexts) == 1
    assert contexts[0]["rank"] == 1
    assert contexts[0]["text"] == (
        "Source-grounded context."
    )
    assert len(contexts[0]["text_sha256"]) == 64


def test_rejects_unapproved_source_prefix() -> None:
    response = {
        "contexts": {
            "contexts": [
                {
                    "sourceUri": (
                        "gs://unapproved-bucket/document.txt"
                    ),
                    "sourceDisplayName": "document.txt",
                    "score": 0.5,
                    "text": "Unapproved context.",
                }
            ]
        }
    }

    assert_raises(
        VertexRagError,
        lambda: _normalize_contexts(
            response,
            settings(),
        ),
    )


def test_rejects_empty_context_text() -> None:
    response = {
        "contexts": {
            "contexts": [
                {
                    "sourceUri": (
                        DEFAULT_SOURCE_PREFIX + "document.txt"
                    ),
                    "sourceDisplayName": "document.txt",
                    "score": 0.5,
                    "text": "",
                }
            ]
        }
    }

    assert_raises(
        VertexRagError,
        lambda: _normalize_contexts(
            response,
            settings(),
        ),
    )


def main() -> None:
    tests = [
        test_default_settings_are_fixed,
        test_rejects_different_project,
        test_rejects_rate_above_current_budget,
        test_normalizes_query,
        test_rejects_empty_query,
        test_request_is_bound_to_fixed_corpus,
        test_normalizes_valid_context,
        test_rejects_unapproved_source_prefix,
        test_rejects_empty_context_text,
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print(f"\nVertex RAG tests passed: {len(tests)}")
    print("CANONFLOW GOOGLE RAG READ-ONLY TOOL: OK")


if __name__ == "__main__":
    main()
