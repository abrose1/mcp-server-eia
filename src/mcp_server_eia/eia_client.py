"""
HTTP client for EIA Open Data API v2 (https://api.eia.gov/v2/).

Adapted from the Burnout (StrandedAssets) backend — no SQLAlchemy or app imports.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import httpx

from mcp_server_eia.config import Settings, load_settings

logger = logging.getLogger(__name__)

EIA_BASE = "https://api.eia.gov/v2"

DEFAULT_PAGE = 5000
MAX_RETRIES = 4
RETRYABLE_STATUS = frozenset({429, 502, 503, 504})
_BACKOFF_CAP_S = 30.0


def _default_timeout() -> httpx.Timeout:
    return httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)


class EIAClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        settings: Settings | None = None,
        timeout: httpx.Timeout | float | None = None,
    ) -> None:
        s = settings or load_settings()
        self._api_key = (api_key or s.eia_api_key or "").strip()
        t = timeout if timeout is not None else _default_timeout()
        self._client = httpx.Client(timeout=t)

    def _get(self, path: str, params: list[tuple[str, str]]) -> dict[str, Any]:
        url = f"{EIA_BASE}/{path.lstrip('/')}"
        full: list[tuple[str, str]] = [("api_key", self._api_key), *params]
        for attempt in range(MAX_RETRIES):
            try:
                r = self._client.get(url, params=full)
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as e:
                code = e.response.status_code if e.response is not None else 0
                if code in RETRYABLE_STATUS and attempt < MAX_RETRIES - 1:
                    wait = min(2**attempt + random.uniform(0.0, 1.0), _BACKOFF_CAP_S)
                    logger.warning(
                        "EIA HTTP %s (attempt %s/%s), retry in %.1fs: %s",
                        code,
                        attempt + 1,
                        MAX_RETRIES,
                        wait,
                        url[:120],
                    )
                    time.sleep(wait)
                    continue
                raise
            except httpx.RequestError as e:
                if attempt < MAX_RETRIES - 1:
                    wait = min(2**attempt + random.uniform(0.0, 1.0), _BACKOFF_CAP_S)
                    logger.warning(
                        "EIA request error (attempt %s/%s), retry in %.1fs: %s — %s",
                        attempt + 1,
                        MAX_RETRIES,
                        wait,
                        url[:120],
                        e,
                    )
                    time.sleep(wait)
                    continue
                raise

    def get(self, path: str, params: list[tuple[str, str]] | None = None) -> dict[str, Any]:
        return self._get(path, params or [])

    def get_latest_facility_fuel_annual_year(self) -> int:
        meta_body = self.get_route_metadata("electricity/facility-fuel")
        err = meta_body.get("error")
        if err:
            raise RuntimeError(str(err))
        r = meta_body.get("response") or meta_body
        end = r.get("endPeriod")
        if isinstance(end, str) and len(end) >= 4:
            try:
                return int(end[:4])
            except ValueError:
                pass
        sample = self.fetch_data(
            "electricity/facility-fuel",
            frequency="annual",
            data_fields=["generation"],
            facets={"fuel2002": ["ALL"]},
            length=1,
            offset=0,
            sort=[("period", "desc")],
        )
        if sample.get("error"):
            raise RuntimeError(str(sample["error"]))
        rows = (sample.get("response") or {}).get("data") or []
        if not rows:
            raise RuntimeError("Could not determine latest facility-fuel annual year")
        p = rows[0].get("period")
        if not p:
            raise RuntimeError("EIA row missing period")
        return int(str(p)[:4])

    def get_latest_inventory_period(self) -> str:
        meta_body = self.get_route_metadata("electricity/operating-generator-capacity")
        err = meta_body.get("error")
        if err:
            raise RuntimeError(str(err))
        r = meta_body.get("response") or meta_body
        end = r.get("endPeriod")
        if isinstance(end, str) and len(end) >= 7:
            return end[:7]
        sample = self.fetch_data(
            "electricity/operating-generator-capacity",
            frequency="monthly",
            data_fields=["nameplate-capacity-mw"],
            facets={"energy_source_code": ["NG"], "status": ["OP"]},
            length=1,
            offset=0,
            sort=[("period", "desc")],
        )
        if sample.get("error"):
            raise RuntimeError(str(sample["error"]))
        rows = (sample.get("response") or {}).get("data") or []
        if not rows:
            raise RuntimeError("Could not determine latest inventory period")
        p = rows[0].get("period")
        if not p:
            raise RuntimeError("EIA row missing period")
        return str(p)[:7]

    def get_route_metadata(self, route: str) -> dict[str, Any]:
        path = route.rstrip("/") + "/"
        return self._get(path, [])

    def fetch_data(
        self,
        route: str,
        *,
        frequency: str,
        data_fields: list[str] | None = None,
        facets: dict[str, list[str]] | None = None,
        length: int = DEFAULT_PAGE,
        offset: int = 0,
        sort: list[tuple[str, str]] | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> dict[str, Any]:
        path = route.rstrip("/") + "/data/"
        params: list[tuple[str, str]] = [
            ("frequency", frequency),
            ("length", str(length)),
            ("offset", str(offset)),
        ]
        if start:
            params.append(("start", start))
        if end:
            params.append(("end", end))
        if data_fields:
            for i, field in enumerate(data_fields):
                params.append((f"data[{i}]", field))
        if facets:
            for facet_name, values in facets.items():
                for v in values:
                    params.append((f"facets[{facet_name}][]", v))
        if sort:
            for i, (col, direction) in enumerate(sort):
                params.append((f"sort[{i}][column]", col))
                params.append((f"sort[{i}][direction]", direction))
        return self._get(path, params)

    def iter_data(
        self,
        route: str,
        *,
        frequency: str,
        data_fields: list[str] | None = None,
        facets: dict[str, list[str]] | None = None,
        page_size: int = DEFAULT_PAGE,
        max_rows: int | None = None,
        start: str | None = None,
        end: str | None = None,
        sort: list[tuple[str, str]] | None = None,
    ):
        offset = 0
        yielded = 0
        while True:
            body = self.fetch_data(
                route,
                frequency=frequency,
                data_fields=data_fields,
                facets=facets,
                length=page_size,
                offset=offset,
                start=start,
                end=end,
                sort=sort,
            )
            err = body.get("error")
            if err:
                raise RuntimeError(str(err))
            resp = body.get("response") or {}
            rows = resp.get("data") or []
            total = int(resp.get("total") or 0)
            for row in rows:
                yield row
                yielded += 1
                if max_rows is not None and yielded >= max_rows:
                    return
            offset += len(rows)
            if not rows or offset >= total:
                break

    def close(self) -> None:
        self._client.close()
