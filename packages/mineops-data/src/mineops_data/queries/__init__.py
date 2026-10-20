"""Named, parameterized SQL templates (ADR-0003).

These are the only SQL shapes the AI layer can ever trigger: MCP tools (M4) load a template by
name and bind validated arguments as psycopg parameters. Nothing here is built from strings at
runtime, and the LLM never sees or edits SQL.
"""

from __future__ import annotations

from functools import cache
from importlib import resources
from typing import LiteralString

QUERY_NAMES = (
    "production_vs_target",
    "cm_failures_by_asset",
    "overdue_work_orders_by_site",
    "incidents_by_week",
)


@cache
def _load(name: str) -> str:
    return resources.files(__package__).joinpath(f"{name}.sql").read_text(encoding="utf-8")


def load_query(name: str) -> LiteralString:
    """Return the SQL text for a named template. Unknown names raise ``KeyError``."""
    if name not in QUERY_NAMES:
        raise KeyError(f"unknown query template: {name}")
    # The text comes from a packaged file, never from input; mark it as literal for psycopg.
    return _load(name)
