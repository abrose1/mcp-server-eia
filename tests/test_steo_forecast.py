"""Unit tests for get_steo_forecast (no live EIA calls)."""

from __future__ import annotations

from typing import Any, Iterator

from mcp_server_eia.tools.steo import get_steo_forecast_impl


class _FakeEIAClient:
    _api_key = "test-key"

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []
        self.last_iter_kwargs: dict[str, Any] | None = None

    def get_route_metadata(self, route: str) -> dict[str, Any]:
        assert route == "steo"
        return {"response": {"endPeriod": "2024-12", "defaultFrequency": "monthly"}}

    def get(self, path: str, params: list[tuple[str, str]] | None = None) -> dict[str, Any]:
        assert params is not None
        assert path == "steo/facet/seriesId"
        return {
            "response": {
                "facets": [
                    {"id": "NGGAS", "name": "Henry Hub Natural Gas Spot Price"},
                    {"id": "WCOIL", "name": "Crude Oil (WTI) Spot Price"},
                    {"id": "EDEMAND", "name": "Electricity Demand"},
                ]
            }
        }

    def iter_data(self, route: str, **kwargs: Any) -> Iterator[dict[str, Any]]:
        assert route == "steo"
        self.last_iter_kwargs = kwargs
        yield from self.rows

    def close(self) -> None:
        pass


def test_get_steo_forecast_maps_series_and_returns_rows() -> None:
    c = _FakeEIAClient(
        rows=[
            {
                "period": "2024-08",
                "value": "2.1",
                "units": "$/MMBtu",
                "history": "HISTORY",
            },
            {
                "period": "2024-09",
                "value": "2.2",
                "units": "$/MMBtu",
                "history": "PROJECTION",
            },
        ]
    )
    r = get_steo_forecast_impl(
        series="natural_gas_price",
        frequency="monthly",
        client=c,  # type: ignore[arg-type]
    )

    assert r["meta"]["source"] == "steo"
    assert r["meta"]["record_count"] == 2
    assert r["data"][0] == {"period": "2024-09", "value": 2.2, "unit": "$/MMBtu"}
    assert r["data"][1] == {"period": "2024-08", "value": 2.1, "unit": "$/MMBtu"}
    assert c.last_iter_kwargs is not None
    assert c.last_iter_kwargs["start"] == "2022-12"
    assert c.last_iter_kwargs["end"] == "2024-12"
    assert c.last_iter_kwargs["facets"]["seriesId"] == ["NGGAS"]
    notes = r["meta"]["notes"]
    assert any("PROJECTION" in n for n in notes)
    assert any("HISTORY" in n for n in notes)


def test_get_steo_forecast_missing_api_key() -> None:
    c = _FakeEIAClient()
    c._api_key = ""
    r = get_steo_forecast_impl(series="natural_gas_price", frequency="monthly", client=c)  # type: ignore[arg-type]
    assert r["data"] == []
    assert "EIA_API_KEY" in (r["meta"]["notes"][0] or "")


def test_get_steo_forecast_invalid_series() -> None:
    c = _FakeEIAClient()
    r = get_steo_forecast_impl(series="uranium_price", frequency="monthly", client=c)  # type: ignore[arg-type]
    assert r["data"] == []
    assert "Unknown STEO series" in (r["meta"]["notes"][0] or "")

