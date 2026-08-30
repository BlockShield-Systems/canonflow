# P10E Mutation Authorization

- Status: `authorized`
- Authorized by: `Demian`
- Authorized at UTC: `2026-08-26T00:03:34.206Z`
- Authorization statement:
  `AUTHORIZE P10E INSERT YD-CANON-0003..0006`
- Project ID: `e8627781-5bf3-4c4d-905f-8dda49ab53d6`
- Target table: `canonflow.canon_decisions`
- Authorized IDs:
  - `YD-CANON-0003`
  - `YD-CANON-0004`
  - `YD-CANON-0005`
  - `YD-CANON-0006`
- Authorized operation: guarded INSERT only
- Package manifest SHA-256: `779b0c1863a81cad6596487c9427c3a09255bc3a31df6b78e617df7d7aa53b2b`
- Agent write authorization: `false`
- Manual ClickHouse Console execution: `true`

No UPDATE, DELETE, ALTER, DROP, or replacement of existing decisions is
authorized.
