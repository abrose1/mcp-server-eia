"""Unit tests for get_fuel_prices (no live EIA calls)."""

from __future__ import annotations

from typing import Any, Iterator

from mcp_server_eia.tools.fuel_prices import get_fuel_prices_impl


class _FakeEIAClient:
    """Minimal stub for get_fuel_prices_impl."""

    _api_key = "test-key"

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []
        self.last_iter_kwargs: dict[str, Any] | None = None

    def get_route_metadata(self, route: str) -> dict[str, Any]:
        return {"response": {"endPeriod": "2024-12-31"}}

    def iter_data(self, route: str, **kwargs: Any) -> Iterator[dict[str, Any]]:
        self.last_iter_kwargs = {"route": route, **kwargs}
        yield from self.rows

    def close(self) -> None:
        pass


def test_get_fuel_prices_henry_hub_maps_row() -> None:
    c = _FakeEIAClient(
        rows=[
            {
                "period": "2024-01-31",
                "value": "2.5",
                "units": "$/MMBTU",
            }
        ]
    )
    r = get_fuel_prices_impl(
        fuel="natural_gas",
        price_type="henry_hub",
        frequency="daily",
        start_year=2024,
        end_year=2024,
        client=c,
    )
    assert r["meta"]["source"] == "natural-gas/pri/fut"
    assert r["meta"]["record_count"] == 1
    assert r["data"][0] == {"period": "2024-01-31", "price": 2.5, "unit": "$/MMBTU"}
    assert c.last_iter_kwargs is not None
    assert c.last_iter_kwargs["facets"]["series"] == ["RNGWHHD"]


def test_get_fuel_prices_coal_rejects_monthly_frequency() -> None:
    c = _FakeEIAClient()
    r = get_fuel_prices_impl(
        fuel="coal",
        price_type="powder_river",
        frequency="monthly",
        client=c,
    )
    assert r["data"] == []
    assert "not available" in (r["meta"]["notes"][0] or "")


def test_get_fuel_prices_missing_api_key() -> None:
    c = _FakeEIAClient()
    c._api_key = ""
    r = get_fuel_prices_impl(fuel="natural_gas", client=c)
    assert r["data"] == []
    assert "EIA_API_KEY" in r["meta"]["notes"][0]


def test_get_fuel_prices_invalid_fuel() -> None:
    c = _FakeEIAClient()
    r = get_fuel_prices_impl(fuel="uranium", client=c)
    assert r["data"] == []
    assert "natural_gas" in r["meta"]["notes"][0]
