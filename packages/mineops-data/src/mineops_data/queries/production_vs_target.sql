-- name: production_vs_target
-- MCP tool: get_production_vs_target. Detects anomaly A1.
-- Params:
--   date_from  date      inclusive
--   date_to    date      inclusive
--   site_codes text[]    caller's permitted sites; NULL = all (engineer/executive)
-- Index: ops.production_daily PK (site_id, date)
SELECT s.code                                                  AS site_code,
       SUM(p.ore_tonnes)                                       AS ore_tonnes,
       SUM(p.target_tonnes)                                    AS target_tonnes,
       ROUND(SUM(p.ore_tonnes) / SUM(p.target_tonnes), 4)      AS attainment,
       COUNT(*) FILTER (WHERE p.ore_tonnes < p.target_tonnes)  AS days_under_target,
       COUNT(*)                                                AS days,
       ROUND(AVG(p.availability_pct), 2)                       AS avg_availability_pct
FROM ops.production_daily p
JOIN ops.sites s ON s.id = p.site_id
WHERE p.date BETWEEN %(date_from)s AND %(date_to)s
  AND (%(site_codes)s::text[] IS NULL OR s.code = ANY(%(site_codes)s::text[]))
GROUP BY s.code
ORDER BY s.code
