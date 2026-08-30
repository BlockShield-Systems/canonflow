# Failed Source Audit Attempt 04

- Status: `rejected_incomplete`
- Stage: P10C source-audit execution
- Cause: Existing partial artifacts conflicted with the clean Tier 1 audit run.
- Disposition: The partial event stream and execution log were archived before restarting.
- Canonical output: None. Files in this directory must not be used as approved audit evidence.
- Database impact: The source-audit agent uses the enforced read-only ClickHouse policy.
