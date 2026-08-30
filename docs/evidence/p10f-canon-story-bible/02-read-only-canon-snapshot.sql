SELECT *
FROM canonflow.canon_decisions
WHERE project_id = toUUID('e8627781-5bf3-4c4d-905f-8dda49ab53d6')
  AND decision_id IN
  (
    'YD-CANON-0001',
    'YD-CANON-0002',
    'YD-CANON-0003',
    'YD-CANON-0004',
    'YD-CANON-0005',
    'YD-CANON-0006'
  )
ORDER BY decision_id
FORMAT JSONEachRow;
