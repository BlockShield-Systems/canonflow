# P10G Failed Second-Revision Attempt 01

- Classification: `provider_transport_failure`
- Provider result: `HTTP 503 / unavailable`
- Model: `gemini-3.1-pro-preview`
- Route: `Chat.send_message`
- Provider response accepted as draft: `false`
- Runner modified: `false`
- Generation input modified: `false`
- Database mutation: `false`
- Automatic canon release: `false`
- Retry authorized: `true`

The failure occurred at the provider/transport layer before a valid second
revised draft was persisted. The frozen runner and generation package remain
unchanged. A later retry must use the exact same controlled command.
