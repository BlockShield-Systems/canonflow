# CanonFlow Source Audit Request

Conduct a complete, read-only source audit for:

- Project ID: `e8627781-5bf3-4c4d-905f-8dda49ab53d6`
- Slug: `yd-when-paradise-glitches`
- Canonical title: `Y.D. – When Paradise Glitches`

## Mandatory database verification

1. Resolve the project through `canonflow.projects FINAL`.
2. Retrieve all approved project canon decisions.
3. Retrieve the complete source-document inventory.
4. Retrieve all source-quality dispositions.
5. Confirm total, indexable and non-indexable page and chunk counts.
6. Read every indexable source chunk.
7. Process chunks in deterministic order:
   - `source_path`
   - `page_number`
   - `sequence`
   - `chunk_id`
8. Retrieve no more than 10 source chunks per query.
9. Maintain a coverage ledger so no indexable chunk is silently omitted.
10. Do not execute any state-changing SQL.

## Canon precedence

Apply this order:

1. Explicit approved canon decisions
2. Directly confirmed user decisions
3. Detailed authored scenes, frames, shots and dialogue
4. Detailed story and character documents
5. Plot summaries and early drafts
6. Earlier AI-generated proposals
7. New creative recommendations

Do not silently delete lower-priority material. Classify it as historical,
alternative, superseded or contradictory.

## Required analysis

Classify and extract:

- project identity;
- themes, genres and tone;
- world history and timeline;
- factions and social context;
- character profiles;
- Y.D.'s dual personas;
- relationship evolution;
- acts and story beats;
- scenes and locations;
- frames and shots;
- dialogue and speaker attribution;
- visual direction;
- camera and animation instructions;
- sound, voice and music direction;
- production constraints;
- historical drafts and superseded information;
- unresolved contradictions;
- missing information requiring Demian's decision.

## Required canon overrides

Verify them through `canonflow.canon_decisions`:

- Demian's canonical age is 40, not 38.
- The maximum 15-minute runtime is obsolete.
- The project is a full-length film.
- Final target runtime remains to be determined.
- Historical short-film act timings are non-binding.

## Required final report

Write the final report in English while preserving source quotations in their
original language.

Use these sections:

1. Executive Audit Status
2. Verified Project Identity
3. Approved Canon Decisions
4. Source Coverage Ledger
5. Document Classification
6. Canon Inventory
7. Character and Relationship Inventory
8. Act, Scene, Frame and Shot Inventory
9. Dialogue Inventory
10. Visual, Camera, Animation and Sound Inventory
11. Historical and Superseded Material
12. Proposed Continuity Findings
13. Missing-information Questions for Demian
14. Recommended Next Controlled Workflow

For every proposed continuity finding include:

- proposed finding ID;
- severity;
- category;
- description;
- evidence with source path and locator;
- affected story scope;
- recommendation;
- whether Demian's decision is required;
- status `proposed`.

Clearly distinguish:

- source fact;
- approved canon;
- interpretation;
- recommendation.

Do not write to ClickHouse. Do not rewrite the screenplay. Do not claim that
the audit is complete unless every indexable chunk appears in the coverage
ledger.
