-- name: incidents_by_week
-- MCP tool: get_incidents (weekly trend form). Detects anomaly A4.
-- Weeks are ISO weeks (Monday start, UTC). Zero-incident weeks are returned as 0.
-- Params:
--   date_from  date      inclusive (snapped to its week start)
--   date_to    date      inclusive
--   site_codes text[]    NULL = all
-- Index: ops.safety_incidents (site_id, occurred_at)
WITH weeks AS (
    SELECT generate_series(date_trunc('week', %(date_from)s::date),
                           date_trunc('week', %(date_to)s::date),
                           interval '1 week')::date AS week_start
)
SELECT s.code                                           AS site_code,
       wk.week_start                                    AS week_start,
       COUNT(i.id)                                      AS incidents,
       COUNT(i.id) FILTER (WHERE i.shift = 'night')     AS night_incidents
FROM ops.sites s
CROSS JOIN weeks wk
LEFT JOIN ops.safety_incidents i
       ON i.site_id = s.id
      AND i.occurred_at >= wk.week_start::timestamp AT TIME ZONE 'UTC'
      AND i.occurred_at <  (wk.week_start + 7)::timestamp AT TIME ZONE 'UTC'
WHERE (%(site_codes)s::text[] IS NULL OR s.code = ANY(%(site_codes)s::text[]))
GROUP BY s.code, wk.week_start
ORDER BY s.code, wk.week_start
