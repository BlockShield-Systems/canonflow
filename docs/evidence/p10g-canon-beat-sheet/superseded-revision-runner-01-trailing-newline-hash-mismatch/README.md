# Superseded P10G Revision Runner 01

## Reason

The runner calculated the revised-draft SHA-256 from `revised_text` but wrote
`revised_text + "\n"` to disk. The documented output hash would therefore not
match the persisted file.

## Disposition

- Runner executed against Gemini: false
- Revision output created: false
- Database mutation performed: false
- Automatic canon release performed: false
- Original runner preserved: true
- Corrective action: persist exactly the text used for SHA-256 calculation

This archived runner must not be executed.
