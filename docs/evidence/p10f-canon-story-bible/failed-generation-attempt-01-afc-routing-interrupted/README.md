# P10F Failed Generation Attempt 01

## Status

`interrupted_before_generation_completion`

## Exit status

`130`

## Cause

The initial runner invoked Models.generate_content directly.
The installed Google Gen AI SDK required AFC routing through
Chat.send_message. Demian manually interrupted the run.

## Resolution

The next accepted runner will use chats.create followed by exactly
one Chat.send_message invocation. No model output from this attempt
is accepted as Canon Story Bible evidence.
