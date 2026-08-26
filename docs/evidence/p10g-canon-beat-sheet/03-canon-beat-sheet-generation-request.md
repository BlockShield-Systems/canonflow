# P10G Canon Beat Sheet – Controlled Generation Request

## Execution status

`ready_for_afc_chat_generation`

## Task

Generate a complete, production-usable feature-film Canon Beat Sheet for
**Y.D. – When Paradise Glitches**.

The Beat Sheet must transform the approved Story Bible into a sequential
feature-film beat structure without silently creating new canon.

## Authority precedence

1. Approved P10F Canon Story Bible
2. Approved Canon Decisions `YD-CANON-0001` through `YD-CANON-0006`
3. Accepted P10C source evidence and verified locators
4. Explicitly marked `non-canon-proposal` material

Lower-precedence material must not override higher-precedence authority.

## Canon decisions

- `YD-CANON-0001`
- `YD-CANON-0002`
- `YD-CANON-0003`
- `YD-CANON-0004`
- `YD-CANON-0005`
- `YD-CANON-0006`

## Required output

- Markdown only
- Minimum characters: `30000`
- Minimum sequential beat entries: `40`
- Beat ID format: `P10G-BEAT-###`
- Feature-film structure
- All 24 required sections
- All 17 beat fields where applicable
- Explicit source and Canon Decision traceability
- Unsupported connective material marked `non-canon-proposal`
- No fabricated citations
- No resolution of Y.D.'s corruption cause
- Demian remains unaware of Y.D.'s doll authorship during the Act 1 event
- Historical four-second frame timings are not binding
- Human review remains mandatory

## Required sections

- `1. Authority, Scope, and Precedence`
- `2. Feature-Film Structural Overview`
- `3. Character and Relationship Arc Baseline`
- `4. Prologue`
- `5. Act 1 – Setup`
- `6. Inciting Incident`
- `7. Act 1 – Doll and Seismic Hammer Sequence`
- `8. First Act Turning Point`
- `9. Act 2A – Escalation and Dependency`
- `10. Midpoint`
- `11. Act 2B – Systemic Escalation`
- `12. Amusement Park of Illusions`
- `13. Transition into the Mirror Room`
- `14. Act 2 Crisis and Lowest Point`
- `15. Act 3 – Mirror Room and Final Confrontation`
- `16. Climax and Resolution`
- `17. Epilogue`
- `18. Demian Character Arc`
- `19. Y.D. Character and Voice Progression`
- `20. Corruption Mystery and Ambiguity Control`
- `21. Dialogue, Dark Humor, Satire, and Performance`
- `22. Source Traceability`
- `23. Canon Decision Compliance Matrix`
- `24. Open Questions and Non-Canon Proposals`

## Required beat fields

- `Beat ID`
- `Act / structural position`
- `Sequence`
- `Narrative purpose`
- `Location`
- `Participating characters`
- `Action`
- `Conflict or pressure`
- `Emotional movement`
- `Reversal, reveal, or turn`
- `Demian knowledge state`
- `Y.D. state and voice stage`
- `Canon decision references`
- `Source references or verified locators`
- `Fact classification`
- `Continuity consequences`
- `Production or staging considerations`

## Transport contract

The runner must use:

`genai.Client → client.chats.create(...) → Chat.send_message(...)`

The runner must not call `client.models.generate_content(...)` directly.

- Streaming: disabled
- External tools: disabled
- Database access: disabled
- Database mutation: disabled
- Automatic canon release: disabled

## Required end marker

`P10G CANON BEAT SHEET DRAFT END`

## Acceptance boundary

The generated Beat Sheet remains a draft until strict local validation passes
and Demian explicitly approves the later human-review matrix.
