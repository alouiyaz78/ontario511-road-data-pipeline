
SELECT
    id AS alert_id,
    message,
    notes,
    starttime AS start_time,
    endtime AS end_time,
    lastupdated AS last_updated,
    regions,
    highimportance AS high_importance,
    sendnotification AS send_notification,
    (endtime IS NULL OR endtime >= NOW()) AS is_active
FROM {{ source('bronze', 'alerts') }}
