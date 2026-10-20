-- name: overdue_work_orders_by_site
-- MCP tool: list_overdue_work_orders (summary form). Detects anomaly A3.
-- Params:
--   as_of      timestamptz
--   wo_type    text      NULL = any
--   site_codes text[]    NULL = all
-- Index: ops.work_orders (site_id, status, due_at)
SELECT s.code                                       AS site_code,
       COUNT(w.id)                                  AS overdue_count,
       MIN(w.due_at)                                AS oldest_due_at
FROM ops.sites s
LEFT JOIN ops.work_orders w
       ON w.site_id = s.id
      AND w.status IN ('open', 'in_progress', 'on_hold')
      AND w.due_at < %(as_of)s
      AND (%(wo_type)s::text IS NULL OR w.wo_type = %(wo_type)s::text)
WHERE (%(site_codes)s::text[] IS NULL OR s.code = ANY(%(site_codes)s::text[]))
GROUP BY s.code
ORDER BY overdue_count DESC, s.code
