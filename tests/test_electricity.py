"""Unit tests for electricity tools (no live EIA calls)."""

from __future__ import annotations

from mcp_server_eia.tools.electricity import _epod_headline_rows


def test_epod_headline_rows_remainder() -> None:
    by_fuel = {
        "ALL": {"generation": "100"},
        "COL": {"generation": "30"},
        "NGO": {"generation": "40"},
        "NUC": {"generation": "10"},
        "HYC": {"generation": "5"},
        "HPS": {"generation": "-1"},
        "AOR": {"generation": "10"},
        "PET": {"generation": "5"},
    }
    rows = _epod_headline_rows(by_fuel, 100.0)
    labels = [r["fuel_type"] for r in rows]
    assert labels[-1] == "other"
    assert rows[-1]["generation_mwh"] == 1000.0  # 1.0 * 1000 remainder
    assert abs(sum(r["share_pct"] for r in rows) - 100.0) < 0.01
