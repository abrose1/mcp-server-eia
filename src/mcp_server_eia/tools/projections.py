"""get_aeo_projections — AEO annual projections."""

from __future__ import annotations

import logging
import time
from typing import Any

from mcp_server_eia.config import load_settings
from mcp_server_eia.eia_client import DEFAULT_PAGE, EIAClient
from mcp_server_eia.mappings import (
    AEO_DATA_LAST_YEAR,
    AEO_SERIES_NATIONAL_COAL,
    AEO_SERIES_NATIONAL_GAS,
    AEO_SERIES_NATIONAL_OIL,
    REGION_US,
    TABLE_EMM,
    TABLE_NATIONAL,
    scenario_code_for_name,
)
from mcp_server_eia.response_util import envelope, error_envelope

logger = logging.getLogger(__name__)


def _parse_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _prefer_projection(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = (row.get("seriesId"), row.get("regionId"), row.get("period"))
        prev = by_key.get(key)
        if prev is None:
            by_key[key] = row
            continue
        if prev.get("history") != "PROJECTION" and row.get("history") == "PROJECTION":
            by_key[key] = row
    return list(by_key.values())


def _aeo_facet_table_regions(client: EIAClient, release: str, table_id: str) -> list[tuple[str, str]]:
    body = client.get(
        f"aeo/{release}/facet/regionId",
        [("facets[tableId][]", table_id)],
    )
    err = body.get("error")
    if err:
        raise RuntimeError(str(err))
    facets = (body.get("response") or {}).get("facets") or []
    out: list[tuple[str, str]] = []
    for row in facets:
        rid = row.get("id")
        name = row.get("name")
        if rid and name:
            out.append((str(rid), str(name)))
    return out


def _emm_regions(regions: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(rid, name) for rid, name in regions if rid.startswith("5-") and rid != "5-0"]


def _resolve_region_id(
    client: EIAClient,
    release: str,
    region_query: str,
) -> tuple[str, str] | None:
    q = region_query.strip().lower()
    regions = _emm_regions(_aeo_facet_table_regions(client, release, TABLE_EMM))
    for rid, name in regions:
        if q in name.lower():
            return rid, name
    return None


def _national_fuel_series(fuel_type: str | None) -> str:
    if not fuel_type:
        return AEO_SERIES_NATIONAL_GAS
    k = fuel_type.strip().lower()
    if k == "coal":
        return AEO_SERIES_NATIONAL_COAL
    if k == "gas":
        return AEO_SERIES_NATIONAL_GAS
    if k == "oil":
        return AEO_SERIES_NATIONAL_OIL
    raise ValueError("fuel_type for fuel_prices must be coal, gas, or oil")


def get_aeo_projections_impl(
    *,
    category: str,
    fuel_type: str | None = None,
    region: str | None = None,
    scenario: str = "reference",
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
                source="aeo",
            )
        settings = load_settings()
        release = settings.eia_aeo_release
        scen = scenario_code_for_name(scenario)
        sy = start_year if start_year is not None else __import__("datetime").datetime.now().year
        ey = end_year if end_year is not None else AEO_DATA_LAST_YEAR
        if sy > ey:
            sy, ey = ey, sy
        start_s, end_s = str(sy), str(ey)
        cat = category.strip().lower()
        out_rows: list[dict[str, Any]] = []
        notes: list[str] = [f"AEO release {release}, scenario {scen}"]

        if cat == "fuel_prices":
            sid = _national_fuel_series(fuel_type)
            body = c.fetch_data(
                f"aeo/{release}",
                frequency="annual",
                data_fields=["value"],
                facets={
                    "scenario": [scen],
                    "tableId": [TABLE_NATIONAL],
                    "seriesId": [sid],
                    "regionId": [REGION_US],
                },
                length=5000,
                offset=0,
                start=start_s,
                end=end_s,
                sort=[("period", "asc")],
            )
            if body.get("error"):
                raise RuntimeError(str(body["error"]))
            raw = (body.get("response") or {}).get("data") or []
            for row in raw:
                if row.get("history") == "HISTORY":
                    continue
                y = int(str(row.get("period"))[:4])
                v = _parse_float(row.get("value"))
                if v is None:
                    continue
                out_rows.append(
                    {
                        "year": y,
                        "value": v,
                        "unit": "nominal $/MMBtu (electric power sector)",
                        "series_name": row.get("seriesName") or sid,
                        "scenario": scen,
                        "region": "U.S.",
                    }
                )
            return envelope(
                out_rows,
                source=f"aeo/{release}",
                frequency="annual",
                period_format="YYYY",
                units={"value": "nominal $/MMBtu"},
                notes=notes,
            )

        if cat in ("electricity_prices", "capacity", "emissions"):
            if not region or not str(region).strip():
                return error_envelope(
                    "This category requires a non-empty region (EMM region name, e.g. 'PJM / East').",
                    source=f"aeo/{release}",
                )
            resolved = _resolve_region_id(c, release, str(region))
            if not resolved:
                return error_envelope(
                    f"Could not match region {region!r} to an AEO EMM region for table {TABLE_EMM}.",
                    source=f"aeo/{release}",
                )
            region_id, region_name = resolved
            time.sleep(0.1)
            raw: list[dict[str, Any]] = []
            for row in c.iter_data(
                f"aeo/{release}",
                frequency="annual",
                data_fields=["value"],
                facets={
                    "scenario": [scen],
                    "tableId": [TABLE_EMM],
                    "regionId": [region_id],
                },
                page_size=DEFAULT_PAGE,
                start=start_s,
                end=end_s,
            ):
                raw.append(row)
            raw = _prefer_projection(raw)

            for row in raw:
                if row.get("history") == "HISTORY":
                    continue
                sid = str(row.get("seriesId") or "")
                sname = str(row.get("seriesName") or "")
                y = int(str(row.get("period"))[:4])
                v = _parse_float(row.get("value"))
                if v is None:
                    continue

                if cat == "electricity_prices":
                    if (
                        sid.startswith("prce_NA_elep_gen_elc_NA_")
                        and sid.endswith("_ncntpkwh")
                        and "y13" not in sid
                    ):
                        out_rows.append(
                            {
                                "year": y,
                                "value": v * 10.0,
                                "unit": "nominal $/MWh (wholesale, from cents/kWh)",
                                "series_name": sname,
                                "scenario": scen,
                                "region": region_name,
                            }
                        )
                elif cat == "capacity":
                    if sid.startswith("cap_NA_elep_NA_NA_NA_") and sid.endswith("_gw"):
                        if "Total Capacity" in sname and "Electric Power Sector" in sname:
                            out_rows.append(
                                {
                                    "year": y,
                                    "value": v * 1000.0,
                                    "unit": "MW",
                                    "series_name": sname,
                                    "scenario": scen,
                                    "region": region_name,
                                }
                            )
                elif cat == "emissions":
                    if str(sid).startswith("emi_co2_elep"):
                        out_rows.append(
                            {
                                "year": y,
                                "value": v,
                                "unit": row.get("unit") or "million metric tons CO2",
                                "series_name": sname,
                                "scenario": scen,
                                "region": region_name,
                            }
                        )

            if not out_rows:
                return error_envelope(
                    "No matching AEO series rows for this category and region.",
                    source=f"aeo/{release}",
                    notes=notes,
                )
            out_rows.sort(key=lambda r: (r["series_name"], r["year"]))
            return envelope(
                out_rows,
                source=f"aeo/{release}",
                frequency="annual",
                period_format="YYYY",
                units={"value": "see series"},
                notes=notes,
            )

        return error_envelope(
            f"Unknown category {category!r}. Use fuel_prices, electricity_prices, capacity, or emissions.",
            source="aeo",
        )
    except ValueError as ve:
        return error_envelope(str(ve), source="aeo")
    except Exception as e:
        logger.exception("get_aeo_projections failed")
        msg = str(e).lower()
        if "429" in msg:
            return error_envelope(
                "EIA API rate limit reached. Try again in a moment.",
                source="aeo",
            )
        return error_envelope(
            "EIA API is temporarily unavailable.",
            source="aeo",
        )
    finally:
        if own:
            c.close()
