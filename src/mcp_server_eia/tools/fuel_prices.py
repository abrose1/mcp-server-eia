"""get_fuel_prices — historical spot / market fuel prices (natural gas, coal, crude oil)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from mcp_server_eia.eia_client import DEFAULT_PAGE, EIAClient
from mcp_server_eia.mappings import (
    COAL_MARKET_SALES_ROUTE,
    COAL_MARKET_TYPE_OPEN,
    COAL_REGION_BY_PRICE_TYPE,
    NG_CITYGATE_FACETS,
    NG_HENRY_HUB_FACETS,
    NG_HENRY_HUB_ROUTE,
    NG_SUM_ROUTE,
    NG_WELLHEAD_FACETS,
    PETROLEUM_SPOT_ROUTE,
    PETROLEUM_SPOT_SERIES,
)
from mcp_server_eia.response_util import envelope, error_envelope

logger = logging.getLogger(__name__)

_MAX_ROWS = 10_000


@dataclass(frozen=True)
class _FuelPriceTarget:
    route: str
    facets: dict[str, list[str]]
    data_fields: list[str]
    price_field: str
    allowed_frequency: frozenset[str]
    notes: list[str]


def _parse_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _eia_err(route: str, e: BaseException) -> dict[str, Any]:
    msg = str(e).lower()
    if "429" in msg:
        return error_envelope(
            "EIA API rate limit reached. Try again in a moment.",
            source=route,
        )
    if any(x in msg for x in ("503", "502", "504", "timeout")):
        return error_envelope("EIA API is temporarily unavailable.", source=route)
    return error_envelope(
        "No data found for this combination. Check that the fuel, price_type, and frequency values are valid.",
        source=route,
    )


def _normalize_token(s: str) -> str:
    return re.sub(r"[\s-]+", "_", s.strip().lower())


def _resolve_target(fuel: str, price_type: str | None) -> _FuelPriceTarget:
    f = _normalize_token(fuel)
    pt = _normalize_token(price_type) if price_type is not None and str(price_type).strip() else None

    if f in ("natural_gas", "gas"):
        key = pt or "henry_hub"
        if key == "henry_hub":
            return _FuelPriceTarget(
                route=NG_HENRY_HUB_ROUTE,
                facets=dict(NG_HENRY_HUB_FACETS),
                data_fields=["value"],
                price_field="value",
                allowed_frequency=frozenset({"daily", "weekly", "monthly", "annual"}),
                notes=[
                    "Henry Hub natural gas spot price via natural-gas/pri/fut (process PS0, series RNGWHHD).",
                    "Units are typically $/MMBtu.",
                ],
            )
        if key == "citygate":
            return _FuelPriceTarget(
                route=NG_SUM_ROUTE,
                facets=dict(NG_CITYGATE_FACETS),
                data_fields=["value"],
                price_field="value",
                allowed_frequency=frozenset({"monthly", "annual"}),
                notes=[
                    "U.S. citygate price (natural-gas/pri/sum, process PG1, duoarea NUS).",
                    "Units are typically $/MCF (thousand cubic feet).",
                ],
            )
        if key == "wellhead":
            return _FuelPriceTarget(
                route=NG_SUM_ROUTE,
                facets=dict(NG_WELLHEAD_FACETS),
                data_fields=["value"],
                price_field="value",
                allowed_frequency=frozenset({"monthly", "annual"}),
                notes=[
                    "U.S. wellhead acquisition price (natural-gas/pri/sum, process FWA, duoarea NUS).",
                    "Units are typically $/MCF.",
                ],
            )
        raise ValueError(
            "price_type for natural_gas must be henry_hub, citygate, or wellhead "
            f"(got {price_type!r})."
        )

    if f == "coal":
        key = pt or "powder_river"
        region = COAL_REGION_BY_PRICE_TYPE.get(key)
        if region is None:
            raise ValueError(
                "price_type for coal must be one of: "
                + ", ".join(sorted(COAL_REGION_BY_PRICE_TYPE))
                + f" (got {price_type!r})."
            )
        return _FuelPriceTarget(
            route=COAL_MARKET_SALES_ROUTE,
            facets={
                "marketTypeId": [COAL_MARKET_TYPE_OPEN],
                "stateRegionId": [region],
            },
            data_fields=["price"],
            price_field="price",
            allowed_frequency=frozenset({"annual"}),
            notes=[
                f"Coal open-market sales price ({region}) via coal/market-sales-price (annual; $/short ton).",
                "appalachian maps to APC (Appalachia Central); use appalachian_northern or appalachian_southern for APN/APS.",
            ],
        )

    if f in ("crude_oil", "petroleum", "oil"):
        key = pt or "wti"
        sid = PETROLEUM_SPOT_SERIES.get(key)
        if sid is None:
            raise ValueError(
                "price_type for crude_oil must be wti or brent "
                f"(got {price_type!r})."
            )
        return _FuelPriceTarget(
            route=PETROLEUM_SPOT_ROUTE,
            facets={"series": [sid]},
            data_fields=["value"],
            price_field="value",
            allowed_frequency=frozenset({"daily", "weekly", "monthly", "annual"}),
            notes=[
                f"Crude spot benchmark {key.upper()} via petroleum/pri/spt (series {sid}).",
                "Units are typically $/bbl.",
            ],
        )

    raise ValueError(
        "fuel must be natural_gas, coal, or crude_oil "
        f"(got {fuel!r})."
    )


def _meta_end_period(c: EIAClient, route: str) -> str:
    meta_body = c.get_route_metadata(route)
    err = meta_body.get("error")
    if err:
        raise RuntimeError(str(err))
    r = meta_body.get("response") or meta_body
    end = r.get("endPeriod")
    if isinstance(end, str) and end.strip():
        return end.strip()
    return ""


def _subtract_months(ym: str, months: int) -> str:
    y, m = map(int, ym.split("-")[:2])
    total = y * 12 + (m - 1) - months
    ny, nm = divmod(total, 12)
    return f"{ny:04d}-{nm + 1:02d}"


def _period_bounds(
    *,
    frequency: str,
    start_year: int | None,
    end_year: int | None,
    meta_end: str,
) -> tuple[str, str]:
    freq = frequency.strip().lower()
    ey = end_year
    sy = start_year

    if freq == "annual":
        if meta_end and len(meta_end) >= 4:
            default_end_y = int(meta_end[:4])
        else:
            default_end_y = datetime.now().year
        end_y = ey if ey is not None else default_end_y
        start_y = sy if sy is not None else end_y - 5
        if start_y > end_y:
            start_y, end_y = end_y, start_y
        return str(start_y), str(end_y)

    if freq == "monthly":
        if len(meta_end) >= 7:
            end_ym = meta_end[:7]
        else:
            end_ym = f"{datetime.now().year:04d}-{datetime.now().month:02d}"
        if ey is not None:
            end_ym = f"{ey:04d}-12"
        if sy is not None:
            start_ym = f"{sy:04d}-01"
        else:
            start_ym = _subtract_months(end_ym, 24)
        if start_ym > end_ym:
            start_ym, end_ym = end_ym, start_ym
        return start_ym, end_ym

    if freq == "daily":
        if len(meta_end) >= 10:
            end_d = meta_end[:10]
        else:
            end_d = date.today().isoformat()
        try:
            end_dt = date.fromisoformat(end_d)
        except ValueError:
            end_dt = date.today()
        if ey is not None:
            end_dt = date(ey, 12, 31)
        if sy is not None:
            start_dt = date(sy, 1, 1)
        else:
            start_dt = end_dt - timedelta(days=365)
        if start_dt > end_dt:
            start_dt, end_dt = end_dt, start_dt
        return start_dt.isoformat(), end_dt.isoformat()

    if freq == "weekly":
        # EIA weekly periods are YYYY-MM-DD (week ending); use same as daily window logic.
        if len(meta_end) >= 10:
            end_d = meta_end[:10]
        else:
            end_d = date.today().isoformat()
        try:
            end_dt = date.fromisoformat(end_d)
        except ValueError:
            end_dt = date.today()
        if ey is not None:
            end_dt = date(ey, 12, 31)
        if sy is not None:
            start_dt = date(sy, 1, 1)
        else:
            start_dt = end_dt - timedelta(days=365)
        if start_dt > end_dt:
            start_dt, end_dt = end_dt, start_dt
        return start_dt.isoformat(), end_dt.isoformat()

    raise ValueError(f"Unsupported frequency {frequency!r} for this tool.")


def _period_format(freq: str) -> str:
    k = freq.strip().lower()
    if k == "annual":
        return "YYYY"
    if k == "monthly":
        return "YYYY-MM"
    if k == "weekly":
        return "YYYY-MM-DD"
    if k == "daily":
        return "YYYY-MM-DD"
    return k


def get_fuel_prices_impl(
    *,
    fuel: str,
    price_type: str | None = None,
    frequency: str = "monthly",
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
                source="fuel-prices",
            )

        target = _resolve_target(fuel, price_type)
        freq = frequency.strip().lower()
        if freq not in target.allowed_frequency:
            return error_envelope(
                f"frequency {frequency!r} is not available for this fuel/price_type. "
                f"Use one of: {', '.join(sorted(target.allowed_frequency))}.",
                source=target.route,
                notes=target.notes,
            )

        meta_end = _meta_end_period(c, target.route)
        start_s, end_s = _period_bounds(
            frequency=freq,
            start_year=start_year,
            end_year=end_year,
            meta_end=meta_end,
        )

        rows_out: list[dict[str, Any]] = []
        for row in c.iter_data(
            target.route,
            frequency=freq,
            data_fields=target.data_fields,
            facets=target.facets,
            page_size=DEFAULT_PAGE,
            max_rows=_MAX_ROWS,
            start=start_s,
            end=end_s,
            sort=[("period", "desc")],
        ):
            period = row.get("period")
            if not period:
                continue
            raw = row.get(target.price_field)
            price = _parse_float(raw)
            if price is None:
                continue
            unit = row.get("units") or row.get(f"{target.price_field}-units")
            if not unit and target.price_field == "price":
                unit = "dollars per short ton"
            rows_out.append(
                {
                    "period": str(period),
                    "price": price,
                    "unit": unit or "",
                }
            )

        if not rows_out:
            return error_envelope(
                "No data found for this combination. Check that the fuel/price_type/frequency/date range are valid.",
                source=target.route,
                notes=[*target.notes, f"Requested window: {start_s} to {end_s}."],
            )

        units_meta: dict[str, str] = {"price": "see each row's unit string (EIA `units`)"}
        if rows_out and all(rows_out[i].get("unit") == rows_out[0].get("unit") for i in range(len(rows_out))):
            u = rows_out[0].get("unit") or ""
            if u:
                units_meta = {"price": u}

        return envelope(
            rows_out,
            source=target.route,
            frequency=freq,
            period_format=_period_format(freq),
            units=units_meta,
            notes=[
                *target.notes,
                f"Date window: {start_s} to {end_s} (EIA `start`/`end`).",
                f"Rows capped at {_MAX_ROWS} for safety.",
            ],
        )
    except ValueError as ve:
        return error_envelope(str(ve), source="fuel-prices")
    except Exception as e:
        logger.exception("get_fuel_prices failed")
        return _eia_err("fuel-prices", e)
    finally:
        if own:
            c.close()
