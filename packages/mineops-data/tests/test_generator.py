"""Generator unit tests: determinism and scale targets (no database needed)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mineops_data.generator import TABLE_COLUMNS, generate, write_dataset

# Golden digest of all CSVs + ground_truth.json for seed 42 / small. If you change the
# generator on purpose, re-run and update this value in the same commit.
GOLDEN_SMALL_42 = "468088f427635e6ec22f4f6983b86d2ccbf2a60cc5f85ece3215796c8e0508f5"


def _digest(out: Path) -> str:
    h = hashlib.sha256()
    for name in [*(f"{t}.csv" for t in TABLE_COLUMNS), "ground_truth.json"]:
        h.update(name.encode())
        h.update((out / name).read_bytes())
    return h.hexdigest()


def test_same_seed_is_byte_identical(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    write_dataset(generate(42, "small"), a)
    write_dataset(generate(42, "small"), b)
    assert _digest(a) == _digest(b)


def test_golden_digest(tmp_path: Path) -> None:
    write_dataset(generate(42, "small"), tmp_path)
    assert _digest(tmp_path) == GOLDEN_SMALL_42


def test_different_seed_differs(tmp_path: Path) -> None:
    write_dataset(generate(42, "small"), tmp_path / "a")
    write_dataset(generate(7, "small"), tmp_path / "b")
    assert _digest(tmp_path / "a") != _digest(tmp_path / "b")


def test_medium_scale_targets(tmp_path: Path) -> None:
    counts = write_dataset(generate(42, "medium"), tmp_path)
    assert counts["sites"] == 3
    assert counts["assets"] == 120
    assert counts["production_daily"] == 3 * 548  # 18 months daily
    assert 4500 <= counts["work_orders"] <= 6000
    assert 250 <= counts["safety_incidents"] <= 350


def test_bilingual_share_and_ground_truth(tmp_path: Path) -> None:
    ds = generate(42, "medium")
    wos = ds.tables["work_orders"]
    ar = sum(1 for w in wos if w["lang"] == "ar") / len(wos)
    assert 0.20 <= ar <= 0.30
    assert all(s["name_ar"] and s["name_en"] for s in ds.tables["sites"])
    ids = [a["id"] for a in ds.ground_truth["anomalies"]]
    assert len(ids) == 4
    write_dataset(ds, tmp_path)
    gt = json.loads((tmp_path / "ground_truth.json").read_text("utf-8"))
    assert gt["row_counts"]["assets"] == 120
