# Failed attempt 09 — model returned no content

- Status: `rejected_model_no_content`
- Stage: P10C source-audit execution
- Model: `gemini-3.1-pro-preview`
- API: Gemini Interactions API through Google ADK
- Disposition: archived; no canonical report produced

## Result

The ADK workflow successfully completed:

- 14 MCP tool calls
- 14 matching MCP tool responses
- seven paginated source-chunk queries
- no SQL-policy blocks

After receiving the final batch of tool responses, Gemini returned:

- `finish_reason=STOP`
- `error_code=MODEL_RETURNED_NO_CONTENT`
- empty content parts

The runner correctly rejected the execution because no final textual audit
report was produced.

## Resolution

The runner will implement one controlled continuation turn in the same ADK
session. Recovery is allowed only when all tool calls have matching responses
and the final model error is exactly `MODEL_RETURNED_NO_CONTENT`.
