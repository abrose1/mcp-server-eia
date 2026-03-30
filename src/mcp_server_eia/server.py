"""
MCP stdio server exposing EIA tools.

Run: ``python -m mcp_server_eia`` or ``python -m mcp_server_eia.server``
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server_eia.tools.emissions import get_state_co2_emissions_impl
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
        "retail electricity prices, AEO projections, and state CO2 (SEDS). "
        "Plant IDs must be STATE-plantid (e.g. OH-3470). Set EIA_API_KEY in the environment."
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
