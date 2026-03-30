"""get_steo_forecast — STEO (Short-Term Energy Outlook) 18-month forecasts."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from mcp_server_eia.eia_client import DEFAULT_PAGE, EIAClient
from mcp_server_eia.mappings import steo_series_id_for_key
from mcp_server_eia.response_util import envelope, error_envelope

logger = logging.getLogger(__name__)

STEO_ROUTE = "steo"

# Heuristic defaults:
# - STEO forecasts are typically ~18 months (monthly) / ~6 quarters (quarterly).
# - We include a small tail of HISTORY "actuals" by backing up a fixed window.
DEFAULT_MONTHS_BACK = 24
DEFAULT_QUARTERS_BACK = 8


def _parse_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _subtract_months(ym: str, months: int) -> str:
    y, m = map(int, ym.split("-")[:2])
    total = y * 12 + (m - 1) - months
    ny, nm = divmod(total, 12)
    return f"{ny:04d}-{nm + 1:02d}"


def _parse_quarter(period: str) -> tuple[int, int] | None:
    s = str(period).strip().upper()
    if not s:
        return None
    # Common patterns: "YYYY-Q1"
    if "-" in s:
        a, b = s.split("-", 1)
        if not a.isdigit():
            return None
        y = int(a)
        b = b.strip()
        if b.startswith("Q") and b[1:].isdigit():
            return y, int(b[1:])
        if b.isdigit():  # "YYYY-1" edge case
            return y, int(b)
    return None


def _format_quarter(year: int, quarter: int) -> str:
    q = int(quarter)
    if q < 1 or q > 4:
        q = max(1, min(4, q))
    return f"{int(year):04d}-Q{q}"


def _subtract_quarters(period: str, quarters: int) -> str:
    pq = _parse_quarter(period)
    if pq is None:
        raise ValueError(f"Unrecognized quarterly period format: {period!r}")
    y, q = pq
    total = y * 4 + (q - 1) - quarters
    ny, nq = divmod(total, 4)
    return _format_quarter(ny, nq + 1)


def _normalize_end_period(meta_end: Any, *, frequency: str) -> str:
    s = str(meta_end or "").strip()
    if not s:
        now = datetime.now()
        if frequency == "monthly":
            return f"{now.year:04d}-{now.month:02d}"
        return f"{now.year:04d}-Q{(now.month - 1) // 3 + 1}"

    if frequency == "monthly":
        # EIA monthly periods are usually "YYYY-MM" (sometimes longer).
        if len(s) >= 7 and s[4] == "-":
            return s[:7]
        return s

    # quarterly: usually "YYYY-Q1"
    return s


def _period_format(frequency: str) -> str:
    if frequency == "monthly":
        return "YYYY-MM"
    return "YYYY-Q#"


def _eia_err_message(e: BaseException, *, route: str) -> str:
    msg = str(e).lower()
    if "429" in msg:
        return "EIA API rate limit reached. Try again in a moment."
    if any(x in msg for x in ("503", "502", "504", "timeout")):
        return "EIA API is temporarily unavailable."
    # Keep generic on unexpected failures: no raw HTTP/status details.
    return "EIA API request failed. Try again in a moment."


def get_steo_forecast_impl(
    *,
    series: str,
    frequency: str = "monthly",
    client: EIAClient | None = None,
) -> dict[str, Any]:
    """STEO 18-month forecasts for prices, production, and demand.

    Returns both HISTORY (actuals) and PROJECTION (forecast) rows for the
    selected series.
    """

    own = client is None
    c = client or EIAClient()
    try:
        if not c._api_key:
            return error_envelope(
                "EIA_API_KEY is not set. Add it to the environment for this MCP server.",
                source=STEO_ROUTE,
            )

        freq = frequency.strip().lower()
        if freq not in ("monthly", "quarterly"):
            return error_envelope(
                "frequency must be 'monthly' or 'quarterly'.",
                source=STEO_ROUTE,
            )

        series_id, series_name = steo_series_id_for_key(c, series)

        meta_body = c.get_route_metadata(STEO_ROUTE)
        err = meta_body.get("error")
        if err:
            raise RuntimeError(str(err))
        r = meta_body.get("response") or meta_body

        meta_end = r.get("endPeriod") or ""
        end_p = _normalize_end_period(meta_end, frequency=freq)

        if freq == "monthly":
            end_ym = end_p[:7]
            start_p = _subtract_months(end_ym, DEFAULT_MONTHS_BACK)
        else:
            start_p = _subtract_quarters(end_p, DEFAULT_QUARTERS_BACK)

        history_seen: set[str] = set()
        rows_out: list[dict[str, Any]] = []

        for row in c.iter_data(
            STEO_ROUTE,
            frequency=freq,
            data_fields=["value"],
            facets={"seriesId": [series_id]},
            page_size=DEFAULT_PAGE,
            start=start_p,
            end=end_p,
            sort=[("period", "desc")],
        ):
            period = str(row.get("period") or "").strip()
            if not period:
                continue
            v = _parse_float(row.get("value"))
            if v is None:
                continue

            unit = (
                row.get("units")
                or row.get("unit")
                or row.get("value-units")
                or row.get("value_units")
                or ""
            )
            hist = str(row.get("history") or "").strip().upper()
            if hist:
                history_seen.add(hist)

            rows_out.append(
                {
                    "period": period,
                    "value": v,
                    "unit": str(unit),
                }
            )

        if not rows_out:
            return error_envelope(
                "No STEO data found for this series and frequency in the selected window.",
                source=STEO_ROUTE,
                notes=[f"series key={series!r}, seriesId={series_id}, window={start_p}..{end_p}"],
            )

        # Ensure stable ordering even if EIA changes sort semantics.
        rows_out.sort(key=lambda r2: r2.get("period") or "", reverse=True)

        first_unit = rows_out[0].get("unit") or ""
        if all((r2.get("unit") or "") == first_unit for r2 in rows_out):
            units_meta = {"value": first_unit}
        else:
            units_meta = {"value": "see each row's unit string (EIA `units`)"}  # pragma: no cover

        history_note = (
            "Rows include " + " & ".join(sorted(history_seen))
            if history_seen
            else "Rows include both history and forecast values."
        )

        notes = [
            f"Resolved series key {series!r} -> seriesId {series_id} ({series_name}).",
            history_note,
            f"Window: {start_p} to {end_p}.",
        ]

        return envelope(
            rows_out,
            source=STEO_ROUTE,
            frequency=freq,
            period_format=_period_format(freq),
            units=units_meta,
            notes=notes,
        )
    except ValueError as ve:
        return error_envelope(str(ve), source=STEO_ROUTE)
    except Exception as e:
        logger.exception("get_steo_forecast failed")
        return error_envelope(_eia_err_message(e, route=STEO_ROUTE), source=STEO_ROUTE)
    finally:
        if own:
            c.close()

