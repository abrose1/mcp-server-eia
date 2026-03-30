"""get_electricity_prices — electricity/retail-sales."""

from __future__ import annotations

import logging
from typing import Any

from mcp_server_eia.eia_client import DEFAULT_PAGE, EIAClient
from mcp_server_eia.mappings import sector_id_for_retail
from mcp_server_eia.response_util import envelope, error_envelope

logger = logging.getLogger(__name__)

RETAIL_ROUTE = "electricity/retail-sales"


def _parse_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _eia_err(e: BaseException) -> dict[str, Any]:
    msg = str(e).lower()
    if "429" in msg:
        return error_envelope(
            "EIA API rate limit reached. Try again in a moment.",
            source=RETAIL_ROUTE,
        )
    if any(x in msg for x in ("503", "502", "504", "timeout")):
        return error_envelope("EIA API is temporarily unavailable.", source=RETAIL_ROUTE)
    return error_envelope(
        "No data found for this combination. Check that the state/fuel/frequency values are valid.",
        source=RETAIL_ROUTE,
    )


def get_electricity_prices_impl(
    *,
    state: str | None = None,
    sector: str = "all",
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
                source=RETAIL_ROUTE,
            )
        sec = sector_id_for_retail(sector)
        facets: dict[str, list[str]] = {"sectorid": [sec]}
        if state is not None and str(state).strip():
            facets["stateid"] = [str(state).strip().upper()[:2]]
        else:
            facets["stateid"] = ["US"]

        meta_body = c.get_route_metadata(RETAIL_ROUTE)
        err = meta_body.get("error")
        if err:
            raise RuntimeError(str(err))
        r = meta_body.get("response") or meta_body
        end_p = r.get("endPeriod")
        latest_year = None
        if isinstance(end_p, str) and len(end_p) >= 4:
            try:
                latest_year = int(end_p[:4])
            except ValueError:
                pass
        if latest_year is None:
            latest_year = 2025

        ey = end_year if end_year is not None else latest_year
        sy = start_year if start_year is not None else ey - 20
        if sy > ey:
            sy, ey = ey, sy

        start_s, end_s = str(sy), str(ey)
        rows_out: list[dict[str, Any]] = []
        for row in c.iter_data(
            RETAIL_ROUTE,
            frequency="annual",
            data_fields=["price", "revenue", "sales"],
            facets=facets,
            page_size=DEFAULT_PAGE,
            start=start_s,
            end=end_s,
            sort=[("period", "desc")],
        ):
            period = row.get("period")
            if not period:
                continue
            try:
                y = int(str(period)[:4])
            except ValueError:
                continue
            price = _parse_float(row.get("price"))
            rev = _parse_float(row.get("revenue"))
            sales = _parse_float(row.get("sales"))
            rows_out.append(
                {
                    "state": row.get("stateid"),
                    "sector": row.get("sectorName") or row.get("sectorid"),
                    "year": y,
                    "price_cents_per_kwh": price,
                    "revenue_million_dollars": rev,
                    "sales_million_kwh": sales,
                }
            )

        rows_out.sort(key=lambda r: r["year"], reverse=True)
        return envelope(
            rows_out,
            source=RETAIL_ROUTE,
            frequency="annual",
            period_format="YYYY",
            units={
                "price_cents_per_kwh": "cents per kilowatt-hour",
                "revenue_million_dollars": "million dollars",
                "sales_million_kwh": "million kilowatt-hours",
            },
            notes=[],
        )
    except Exception as e:
        logger.exception("get_electricity_prices failed")
        return _eia_err(e)
    finally:
        if own:
            c.close()
