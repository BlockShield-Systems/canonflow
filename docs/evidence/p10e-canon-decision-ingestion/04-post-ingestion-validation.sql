-- P10E post-ingestion validation

SELECT
    decision_id,
    status,
    entity_type,
    entity_id,
    field,
    approved_by,
    approved_at,
    ingested_at,
    isValidJSON(previous_value_json) AS previous_json_valid,
    isValidJSON(approved_value_json) AS approved_json_valid,
    isValidJSON(decision_json) AS decision_json_valid
FROM canonflow.canon_decisions
WHERE project_id = toUUID('e8627781-5bf3-4c4d-905f-8dda49ab53d6')
  AND decision_id IN (
        'YD-CANON-0003',
        'YD-CANON-0004',
        'YD-CANON-0005',
        'YD-CANON-0006'
  )
ORDER BY decision_id;

SELECT
    decision_id,
    count() AS row_count
FROM canonflow.canon_decisions
WHERE project_id = toUUID('e8627781-5bf3-4c4d-905f-8dda49ab53d6')
  AND decision_id IN (
        'YD-CANON-0003',
        'YD-CANON-0004',
        'YD-CANON-0005',
        'YD-CANON-0006'
  )
GROUP BY decision_id
ORDER BY decision_id;

SELECT
    count() AS approved_decision_count
FROM canonflow.canon_decisions
WHERE project_id = toUUID('e8627781-5bf3-4c4d-905f-8dda49ab53d6')
  AND decision_id IN (
        'YD-CANON-0003',
        'YD-CANON-0004',
        'YD-CANON-0005',
        'YD-CANON-0006'
  )
  AND status = 'approved';
