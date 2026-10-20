-- name: cm_failures_by_asset
-- MCP tool: get_downtime_summary (per-asset breakdown). Detects anomaly A2.
-- Params:
--   date_from  timestamptz  inclusive
--   date_to    timestamptz  exclusive
--   asset_type text         NULL = any
--   site_codes text[]       NULL = all
--   row_limit  int
-- Index: ops.work_orders (asset_id, wo_type, opened_at)
SELECT a.tag                                                              AS asset_tag,
       s.code                                                             AS site_code,
       a.asset_type                                                       AS asset_type,
       COUNT(*)                                                           AS cm_count,
       ROUND(COALESCE(SUM(EXTRACT(EPOCH FROM d.ended_at - d.started_at)), 0) / 3600.0, 1)
                                                                          AS downtime_hours
FROM ops.work_orders w
JOIN ops.assets a ON a.id = w.asset_id
JOIN ops.sites s ON s.id = w.site_id
LEFT JOIN ops.downtime_events d ON d.work_order_id = w.id
WHERE w.wo_type = 'CM'
  AND w.opened_at >= %(date_from)s AND w.opened_at < %(date_to)s
  AND (%(asset_type)s::text IS NULL OR a.asset_type = %(asset_type)s::text)
  AND (%(site_codes)s::text[] IS NULL OR s.code = ANY(%(site_codes)s::text[]))
GROUP BY a.tag, s.code, a.asset_type
ORDER BY cm_count DESC, a.tag
LIMIT %(row_limit)s
