"""get_state_co2_emissions — SEDS CO2 series."""

from __future__ import annotations

import logging
from typing import Any

from mcp_server_eia.eia_client import DEFAULT_PAGE, EIAClient
from mcp_server_eia.mappings import seds_co2_series_id
from mcp_server_eia.response_util import envelope, error_envelope

logger = logging.getLogger(__name__)

SEDS_ROUTE = "seds"


def _parse_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def get_state_co2_emissions_impl(
    *,
    state: str,
    sector: str = "total",
    fuel: str = "total",
    start_year: int | None = None,
    end_year: int | None = None,
    client: EIAClient | None = None,
) -> dict[str, Any]:
    own = client is None
    c = client or EIAClient()
    try:
        if not c._api_key:
            return error_envelope(
                "EIA_API_KEY is not set. Add it to the environment for this MCP server.",
                source="seds",
            )
        st = str(state).strip().upper()[:2]
        series_id = seds_co2_series_id(sector, fuel)
        meta_body = c.get_route_metadata(SEDS_ROUTE)
        err = meta_body.get("error")
        if err:
            raise RuntimeError(str(err))
        r = meta_body.get("response") or meta_body
        end_p = r.get("endPeriod")
        latest_year = 2023
        if isinstance(end_p, str) and len(end_p) >= 4:
            try:
                latest_year = int(end_p[:4])
            except ValueError:
                pass
        ey = end_year if end_year is not None else latest_year
        sy = start_year if start_year is not None else ey - 10
        if sy > ey:
            sy, ey = ey, sy

        rows_out: list[dict[str, Any]] = []
        for row in c.iter_data(
            SEDS_ROUTE,
            frequency="annual",
            data_fields=["value"],
            facets={"stateId": [st], "seriesId": [series_id]},
            page_size=DEFAULT_PAGE,
            start=str(sy),
            end=str(ey),
            sort=[("period", "desc")],
        ):
            period = row.get("period")
            if not period:
                continue
            try:
                y = int(str(period)[:4])
            except ValueError:
                continue
            v = _parse_float(row.get("value"))
            if v is None:
                continue
            rows_out.append(
                {
                    "year": y,
                    "emissions_million_metric_tons": v,
                    "state": st,
                    "sector": sector,
                    "fuel": fuel,
                }
            )
        rows_out.sort(key=lambda r: r["year"], reverse=True)
        return envelope(
            rows_out,
            source="seds",
            frequency="annual",
            period_format="YYYY",
            units={"emissions_million_metric_tons": "million metric tons CO2"},
            notes=[f"SEDS seriesId={series_id}"],
        )
    except ValueError as ve:
        return error_envelope(str(ve), source="seds")
    except Exception as e:
        logger.exception("get_state_co2_emissions failed")
        msg = str(e).lower()
        if "429" in msg:
            return error_envelope(
                "EIA API rate limit reached. Try again in a moment.",
                source="seds",
            )
        return error_envelope(
            "No data found for this combination. Check that the state/fuel/frequency values are valid.",
            source="seds",
        )
    finally:
        if own:
            c.close()
