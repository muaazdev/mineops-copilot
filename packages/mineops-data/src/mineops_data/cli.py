"""``mineops-data`` CLI: generate synthetic data and load it into Postgres."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Literal

import typer

from mineops_core.logging import configure_logging
from mineops_core.settings import get_settings
from mineops_data.generator import DEFAULT_END_DATE, generate, write_dataset
from mineops_data.loader import load

_DEFAULT_END = datetime.combine(DEFAULT_END_DATE, datetime.min.time())

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def _main() -> None:
    s = get_settings()
    configure_logging("mineops-data", s.log.level, s.log.json_format)


@app.command("generate")
def generate_cmd(
    seed: Annotated[int, typer.Option(help="RNG seed")] = 42,
    scale: Annotated[str, typer.Option(help="small | medium")] = "medium",
    out: Annotated[Path, typer.Option(help="output directory")] = Path("data/generated"),
    end_date: Annotated[
        datetime, typer.Option(formats=["%Y-%m-%d"], help="last day of data (UTC)")
    ] = _DEFAULT_END,
) -> None:
    """Write deterministic CSVs + ground_truth.json."""
    if scale not in ("small", "medium"):
        raise typer.BadParameter("scale must be small or medium", param_hint="--scale")
    sc: Literal["small", "medium"] = "small" if scale == "small" else "medium"
    end: date = end_date.date()
    counts = write_dataset(generate(seed, sc, end), out)
    typer.echo(json.dumps({"out": str(out), "seed": seed, "scale": scale, "rows": counts}))


@app.command("load")
def load_cmd(
    src: Annotated[Path, typer.Option("--from", help="directory with generated CSVs")] = Path(
        "data/generated"
    ),
) -> None:
    """Truncate and reload ops tables (connects as MINEOPS_DB__USER)."""
    counts = load(get_settings().db.conninfo(), src)
    typer.echo(json.dumps({"loaded": counts}))
