#!/usr/bin/env python3
"""
Live EIA smoke test for all MCP tool implementations.

Requires ``EIA_API_KEY`` in the environment (never commit a key). Typical use::

    cd mcp-server-eia
    source .venv/bin/activate
    pip install -e .
    export EIA_API_KEY=your-key
    python scripts/smoke_eia.py

Exit code 0 if every check passes, 1 otherwise.
"""

from __future__ import annotations

import os
import sys


def _require_key() -> None:
    if not (os.environ.get("EIA_API_KEY") or "").strip():
        print("ERROR: Set EIA_API_KEY in the environment.", file=sys.stderr)
        sys.exit(1)


def _assert_data(name: str, r: dict, *, min_count: int = 1) -> None:
    data = r.get("data") or []
    n = r.get("meta", {}).get("record_count", len(data))
    if len(data) < min_count:
        notes = r.get("meta", {}).get("notes")
        raise AssertionError(f"{name}: expected at least {min_count} rows, got {len(data)} (record_count={n}, notes={notes})")


def main() -> None:
    _require_key()

    from mcp_server_eia.tools.plants import (
        get_plant_operations_impl,
        get_plant_profile_impl,
        search_power_plants_impl,
    )
    from mcp_server_eia.tools.prices import get_electricity_prices_impl
    from mcp_server_eia.tools.projections import get_aeo_projections_impl
    from mcp_server_eia.tools.emissions import get_state_co2_emissions_impl

    print("search_power_plants …")
    r_search = search_power_plants_impl(fuel_type="gas", state="TX", limit=3)
    _assert_data("search_power_plants", r_search, min_count=2)
    ids = [row["plant_id"] for row in r_search["data"]]
    plant_a, plant_b = ids[0], ids[1]

    print(f"get_plant_operations ({plant_a}) …")
    r_ops_a = get_plant_operations_impl(plant_id=plant_a, frequency="annual")
    _assert_data("get_plant_operations A", r_ops_a, min_count=1)

    print(f"get_plant_operations ({plant_b}) …")
    r_ops_b = get_plant_operations_impl(plant_id=plant_b, frequency="annual")
    _assert_data("get_plant_operations B", r_ops_b, min_count=1)

    print(f"get_plant_profile ({plant_a}) …")
    r_prof = get_plant_profile_impl(plant_id=plant_a)
    _assert_data("get_plant_profile", r_prof, min_count=1)
    meta = r_prof["data"][0].get("metadata") or {}
    if not meta.get("nameplate_mw"):
        raise AssertionError("get_plant_profile: missing nameplate in metadata")

    print("get_electricity_prices …")
    r_price = get_electricity_prices_impl(state="US", sector="all", start_year=2023, end_year=2023)
    _assert_data("get_electricity_prices", r_price, min_count=1)

    print("get_aeo_projections fuel_prices …")
    r_aeo_f = get_aeo_projections_impl(
        category="fuel_prices",
        fuel_type="gas",
        scenario="reference",
        start_year=2030,
        end_year=2031,
    )
    _assert_data("get_aeo_projections fuel_prices", r_aeo_f, min_count=1)

    print("get_aeo_projections electricity_prices (EMM) …")
    r_aeo_e = get_aeo_projections_impl(
        category="electricity_prices",
        region="PJM",
        scenario="reference",
        start_year=2030,
        end_year=2030,
    )
    _assert_data("get_aeo_projections electricity_prices", r_aeo_e, min_count=1)

    print("get_aeo_projections capacity …")
    r_aeo_c = get_aeo_projections_impl(
        category="capacity",
        region="PJM",
        scenario="reference",
        start_year=2030,
        end_year=2030,
    )
    _assert_data("get_aeo_projections capacity", r_aeo_c, min_count=1)

    print("get_aeo_projections emissions …")
    r_aeo_m = get_aeo_projections_impl(
        category="emissions",
        region="PJM",
        scenario="reference",
        start_year=2030,
        end_year=2030,
    )
    _assert_data("get_aeo_projections emissions", r_aeo_m, min_count=1)

    print("get_state_co2_emissions …")
    r_co2 = get_state_co2_emissions_impl(
        state="OH",
        sector="total",
        fuel="total",
        start_year=2022,
        end_year=2022,
    )
    _assert_data("get_state_co2_emissions", r_co2, min_count=1)

    print("OK — all smoke checks passed.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)
