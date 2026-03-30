"""
MCP stdio server exposing EIA tools.

Run: ``python -m mcp_server_eia`` or ``python -m mcp_server_eia.server``
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server_eia.tools.electricity import get_capacity_by_fuel_impl, get_generation_mix_impl
from mcp_server_eia.tools.emissions import get_state_co2_emissions_impl
from mcp_server_eia.tools.fuel_prices import get_fuel_prices_impl
from mcp_server_eia.tools.plants import (
    get_plant_operations_impl,
    get_plant_profile_impl,
    search_power_plants_impl,
)
from mcp_server_eia.tools.prices import get_electricity_prices_impl
from mcp_server_eia.tools.projections import get_aeo_projections_impl

mcp = FastMCP(
    "EIA Open Data",
    instructions=(
        "Tools for U.S. Energy Information Administration (EIA) data: power plants, "
        "generation mix and capacity by fuel, retail electricity prices, historical fuel spot prices, "
        "AEO projections, and state CO2 (SEDS). Plant IDs must be STATE-plantid (e.g. OH-3470). "
        "Set EIA_API_KEY in the environment."
    ),
)


@mcp.tool()
def search_power_plants(
    fuel_type: str = "all",
    state: str | None = None,
    min_capacity_mw: float = 0.0,
    max_capacity_mw: float | None = None,
    status: str = "operating",
    limit: int = 25,
) -> dict:
    """Search EIA-860 operating generator inventory aggregated to plant level (fuel, state, capacity)."""
    return search_power_plants_impl(
        fuel_type=fuel_type,
        state=state,
        min_capacity_mw=min_capacity_mw,
        max_capacity_mw=max_capacity_mw,
        status=status,
        limit=limit,
    )


@mcp.tool()
def get_plant_operations(
    plant_id: str,
    years: list[int] | None = None,
    frequency: str = "annual",
) -> dict:
    """Form 923 facility-fuel operations: generation, fuel use, capacity factor, heat rate."""
    return get_plant_operations_impl(
        plant_id=plant_id,
        years=years,
        frequency=frequency,
    )


@mcp.tool()
def get_plant_profile(plant_id: str) -> dict:
    """Combined 860 inventory + recent 923 operations for one plant."""
    return get_plant_profile_impl(plant_id=plant_id)


@mcp.tool()
def get_generation_mix(
    state: str | None = None,
    year: int | None = None,
    frequency: str = "annual",
    month: int | None = None,
) -> dict:
    """Utility-scale generation mix by fuel (EIA-923 EPOD). Omit state for U.S. total; annual or one month."""
    return get_generation_mix_impl(
        state=state,
        year=year,
        frequency=frequency,
        month=month,
    )


@mcp.tool()
def get_capacity_by_fuel(
    state: str | None = None,
    fuel_type: str = "all",
    year: int | None = None,
    status: str = "operating",
) -> dict:
    """Installed nameplate capacity summed by energy source (EIA-860), with plant counts — not plant search."""
    return get_capacity_by_fuel_impl(
        state=state,
        fuel_type=fuel_type,
        year=year,
        status=status,
    )


@mcp.tool()
def get_electricity_prices(
    state: str | None = None,
    sector: str = "all",
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict:
    """Retail electricity prices (and revenue / sales) by state and sector; omit state for U.S. total."""
    return get_electricity_prices_impl(
        state=state,
        sector=sector,
        start_year=start_year,
        end_year=end_year,
    )


@mcp.tool()
def get_aeo_projections(
    category: str,
    fuel_type: str | None = None,
    region: str | None = None,
    scenario: str = "reference",
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict:
    """Annual Energy Outlook projections. Use category fuel_prices (national) or regional categories with an EMM region name."""
    return get_aeo_projections_impl(
        category=category,
        fuel_type=fuel_type,
        region=region,
        scenario=scenario,
        start_year=start_year,
        end_year=end_year,
    )


@mcp.tool()
def get_fuel_prices(
    fuel: str,
    price_type: str | None = None,
    frequency: str = "monthly",
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict:
    """
    Historical spot / market fuel prices (not AEO projections).

    Supports these fuel+benchmarks:
    - `natural_gas` via Henry Hub (`price_type=henry_hub`, daily/weekly/monthly/annual) or U.S. citygate/wellhead (`price_type=citygate|wellhead`, monthly/annual)
    - `coal` via open-market basin price (`price_type=powder_river|appalachian|appalachian_northern|appalachian_southern|illinois|illinois_basin`; annual only)
    - `crude_oil` via crude spot benchmarks (`price_type=wti|brent`; daily/weekly/monthly/annual)

    Example natural-language prompts you can ask the LLM:
    - "Henry Hub natural gas spot prices for 2024 by month"
    - "Citygate natural gas prices (U.S.) for 2022 monthly"
    - "U.S. wellhead acquisition price trend, annual from 2018 to 2022"
    - "Coal open-market price in the Powder River Basin, annual from 2020 through 2023"
    - "WTI spot crude oil price monthly for 2023"
    - "Brent crude spot price daily in January 2024"
    """
    return get_fuel_prices_impl(
        fuel=fuel,
        price_type=price_type,
        frequency=frequency,
        start_year=start_year,
        end_year=end_year,
    )


@mcp.tool()
def get_state_co2_emissions(
    state: str,
    sector: str = "total",
    fuel: str = "total",
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict:
    """State-level CO2 emissions from SEDS (million metric tons) by sector and fuel group."""
    return get_state_co2_emissions_impl(
        state=state,
        sector=sector,
        fuel=fuel,
        start_year=start_year,
        end_year=end_year,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
