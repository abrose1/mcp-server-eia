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
from mcp_server_eia.tools.steo import get_steo_forecast_impl

mcp = FastMCP(
    "EIA Open Data",
    instructions=(
        "Use these MCP tools to access U.S. Energy Information Administration (EIA) Open Data (v2). "
        "Domain scope: power plants, generation mix and capacity by fuel, retail electricity prices, "
        "historical fuel spot/market prices, AEO long-term projections, STEO short-term forecasts, "
        "and state CO2 emissions (SEDS). "
        "Plant IDs must be STATE-plantid (e.g. OH-3470). "
        "Set `EIA_API_KEY` in the environment. "
        "\n\n"
        "Tool selection guide (pick the closest match): "
        "\n- Plant inventory (which facilities/locations exist): use `search_power_plants` "
        "(list plants filtered by fuel/state/capacity/status). "
        "\n- Plant time series operations (generation + fuel + CF/heat rate): use `get_plant_operations` "
        "(for one plant over years/months). "
        "\n- Full plant snapshot (inventory + recent operations): use `get_plant_profile`. "
        "\n- Electricity generation mix (share of generation by fuel, for a state or U.S. total): use `get_generation_mix`. "
        "\n- Installed capacity by fuel (nameplate MW totals, aggregated by energy source): use `get_capacity_by_fuel`. "
        "\n- Historical fuel benchmark prices (Henry Hub/citygate/wellhead; coal basins; WTI/Brent; spot/market): "
        "use `get_fuel_prices`. "
        "\n- AEO long-term projections (to ~2050): use `get_aeo_projections`. "
        "   - category `fuel_prices` = national fuel-price projections (no EMM `region` needed). "
        "   - categories `electricity_prices`, `capacity`, `emissions` = require an EMM region name in `region` "
        "(e.g. 'PJM / East'). "
        "\n- STEO short-term forecast (typically next ~18 months; returns both HISTORY and PROJECTION rows): "
        "use `get_steo_forecast`. "
        "   - series keys: `natural_gas_price`, `crude_oil_price`, `electricity_demand`. "
        "\n- Retail electricity prices (annual prices/revenue/sales by state + sector): use `get_electricity_prices`. "
        "\n- State CO2 emissions (SEDS, million metric tons by sector/fuel group): use `get_state_co2_emissions`."
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
    """Search EIA-860 operating generator inventory aggregated to plant level.

    Use this when you need to answer: "Which plants match X?" (inventory/listing).

    Plant-level outputs include: `plant_id`, `name`, `state`, `county`, `primary_fuel`,
    `nameplate_mw`, `commission_year`, `operator`, and planned retirement year.
    """
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
    """EIA Form 923 facility-fuel operations for a single plant.

    Use this when you need time-series operations for one plant:
    "How did generation, fuel use, heat rate, and capacity factor change over time?"

    - `frequency`: `annual` or `monthly`
    - `years`: list of years to include (if omitted, defaults to a recent window)
    """
    return get_plant_operations_impl(
        plant_id=plant_id,
        years=years,
        frequency=frequency,
    )


@mcp.tool()
def get_plant_profile(plant_id: str) -> dict:
    """Combined plant profile (single call).

    Use this when you want a comprehensive answer for one plant:
    inventory metadata from EIA-860 plus recent operations from EIA-923.
    """
    return get_plant_profile_impl(plant_id=plant_id)


@mcp.tool()
def get_generation_mix(
    state: str | None = None,
    year: int | None = None,
    frequency: str = "annual",
    month: int | None = None,
) -> dict:
    """Headline electricity generation mix by fuel (EIA-923 EPOD).

    Use this for "What share of generation comes from coal/gas/nuclear/hydro/renewables/etc.?"

    - Omit `state` to get U.S. total. Provide a 2-letter state code for state-level mix.
    - `frequency`: `annual` (use `year`) or `monthly` (use `year` + `month`).
    - Returns MWh generation by fuel bucket plus `share_pct` (percent of total).
    """
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
    """Installed generating capacity summed by fuel (EIA-860), aggregated by energy source.

    Use this for questions like "How much capacity is installed by fuel type?" (aggregation),
    not for "Which plants?" (use `search_power_plants`).

    - Output is nameplate MW totals plus `plant_count` per fuel bucket.
    - `fuel_type` supports coarse buckets like `coal`, `gas`, `oil`, `nuclear`, `solar`, `wind`, `hydro`, or `all`.
    """
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
    """Retail electricity prices (and revenue/sales) by state and sector (electricity/retail-sales).

    Use this for "What are retail electricity prices in <state> for <residential|commercial|industrial>?"

    - Omit `state` to get U.S. total.
    - `sector`: `residential`, `commercial`, `industrial`, or `all`.
    - Returns annual values over the requested year range (or sensible defaults).
    """
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
    """Annual Energy Outlook (AEO) long-term projections (to ~2050), annual values.

    Use this for "AEO projections ..." (not historical spot/market prices).

    Parameters / categories:
    - `category` (required):
      - `fuel_prices`: national fuel price projections; set `fuel_type` (optional) for `coal`, `gas`, or `oil`.
        `region` is not required.
      - `electricity_prices`: requires an EMM `region` name in `region` (e.g. 'PJM / East')
      - `capacity`: requires an EMM `region` name in `region`
      - `emissions`: requires an EMM `region` name in `region`
    - `scenario`: one of `reference`, `high_oil`, `low_oil`, `high_renewables` (default: `reference`)
    - `start_year` / `end_year`: optional; default range is used when omitted.
    """
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
    """Historical spot / market fuel prices (NOT AEO projections).

    Use this for "historical benchmark prices" like Henry Hub, citygate, wellhead,
    coal basin open-market prices, or WTI/Brent.

    Supported inputs (fuel + benchmark):
    - `fuel` = `natural_gas`
      - `price_type`:
        - `henry_hub`: daily/weekly/monthly/annual
        - `citygate` or `wellhead`: monthly/annual
    - `fuel` = `coal`
      - `price_type`:
        `powder_river`, `appalachian`, `appalachian_northern`, `appalachian_southern`,
        `illinois`, `illinois_basin` (annual only)
    - `fuel` = `crude_oil`
      - `price_type`: `wti` or `brent` (daily/weekly/monthly/annual)

    If the user asks for "projections" (long-term) use `get_aeo_projections`;
    if they ask for "short-term forecast" use `get_steo_forecast`.
    """
    return get_fuel_prices_impl(
        fuel=fuel,
        price_type=price_type,
        frequency=frequency,
        start_year=start_year,
        end_year=end_year,
    )


@mcp.tool()
def get_steo_forecast(
    series: str,
    frequency: str = "monthly",
) -> dict:
    """STEO (Short-Term Energy Outlook) forecast with historical actuals (HISTORY + PROJECTION).

    Use this when the question is explicitly short-term forecasting (typically the next ~18 months).
    This is distinct from:
    - `get_fuel_prices`: historical spot/market prices
    - `get_aeo_projections`: long-term AEO projections

    Supported `series` keys:
    - `natural_gas_price`
    - `crude_oil_price`
    - `electricity_demand`

    - `frequency`: `monthly` or `quarterly`
    """
    return get_steo_forecast_impl(series=series, frequency=frequency)


@mcp.tool()
def get_state_co2_emissions(
    state: str,
    sector: str = "total",
    fuel: str = "total",
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict:
    """State-level CO2 emissions from SEDS (million metric tons) by sector and fuel group.

    Use this for "CO2 emissions in <state> over time" (not plant-specific operations).
    """
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
