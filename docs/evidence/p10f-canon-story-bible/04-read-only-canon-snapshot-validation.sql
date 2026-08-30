SELECT
    expected.expected_id AS decision_id,
    countIf(actual.decision_id = expected.expected_id) AS row_count,
    countIf(
        actual.decision_id = expected.expected_id
        AND actual.status = 'approved'
    ) AS approved_row_count,
    countIf(
        actual.decision_id = expected.expected_id
        AND actual.approved_by = 'Demian'
    ) AS demian_approved_row_count
FROM
(
    SELECT arrayJoin
    (
        [
            'YD-CANON-0001',
            'YD-CANON-0002',
            'YD-CANON-0003',
            'YD-CANON-0004',
            'YD-CANON-0005',
            'YD-CANON-0006'
        ]
    ) AS expected_id
) AS expected
LEFT JOIN canonflow.canon_decisions AS actual
    ON actual.project_id =
       toUUID('e8627781-5bf3-4c4d-905f-8dda49ab53d6')
   AND actual.decision_id = expected.expected_id
GROUP BY expected.expected_id
ORDER BY expected.expected_id
FORMAT JSONEachRow;
