# mcp-server-eia

> **Model Context Protocol server for the U.S. EIA Open Data API** — domain tools for plants, operations, retail and historical fuel spot prices, AEO projections, and state CO₂ (not raw route mirrors).

Give any AI agent structured access to U.S. energy data from the [Energy Information Administration](https://www.eia.gov/) (EIA Open Data API v2).

**Scope:** stateless **live** calls to the EIA API only — no database, no hosted projections. Tools return a consistent `{ "data", "meta" }` shape so agents can rely on stable fields.

## Prerequisites

- **Python 3.11+** (see `requires-python` in `pyproject.toml`)
- A free **EIA API key** (below)
- An MCP client that supports **stdio** (Cursor, Claude Desktop, etc.)

## API key

1. Register: [EIA Open Data registration](https://www.eia.gov/opendata/register.php).
2. **Recommended:** set `EIA_API_KEY` in the **MCP server `env`** (see below). Keys stay out of the repo; each machine uses its own key.
3. **Optional:** for a terminal, `export EIA_API_KEY=...` before `python -m mcp_server_eia`.

Do **not** commit API keys or paste them into issues/PRs.

### Cursor / Claude Desktop / any stdio MCP host

Point the client at this repo’s Python module and pass **your** key in `env`:

```json
{
  "mcpServers": {
    "eia": {
      "command": "python3",
      "args": ["-m", "mcp_server_eia"],
      "cwd": "/absolute/path/to/mcp-server-eia",
      "env": {
        "EIA_API_KEY": "paste-your-key-here"
      }
    }
  }
}
```

- **`cwd`** must be the folder where you cloned `mcp-server-eia` (so imports resolve after `pip install -e .`).
- Optional: add `"EIA_AEO_RELEASE": "2025"` to `env` if you need a different AEO release path than the default.

**Where to edit config:** Cursor — MCP settings (UI or JSON, depending on version). **Claude Desktop — macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`. **Windows:** `%APPDATA%\Claude\claude_desktop_config.json` (path may vary slightly by version).

## Why not call the EIA API directly?

- Fuel types are coded (`BIT`, `NG`, …), not “coal” and “gas”.
- Plant inventory is generator-level; useful answers need aggregation to plant.
- AEO data uses table IDs, scenario codes, and region facets that are hard to guess.
- This server wraps those details behind nine domain tools and a stable `{ "data", "meta" }` response shape.

## Quick start (install)

```bash
git clone https://github.com/abrose1/mcp-server-eia.git
cd mcp-server-eia
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Then add the MCP JSON block above (or export `EIA_API_KEY` for a one-off terminal run).

### Troubleshooting

| Issue | What to check |
|-------|----------------|
| Import / module errors | **`cwd`** in MCP config must be the repo root (where `pyproject.toml` lives). Re-run `pip install -e ".[dev]"` in that environment. |
| `401` / invalid key | Key typo, or key not passed in `env` / shell. |
| Slow calls or `429` | EIA rate-limits heavy use; back off and retry. This server retries transient errors; sustained 429s need a pause or fewer parallel tools. |

## Tools

| Tool | Purpose |
|------|---------|
| `search_power_plants` | EIA-860 inventory aggregated to plants (fuel, state, capacity, status). |
| `get_plant_operations` | EIA-923 facility-fuel: generation, fuel use, CF, heat rate. |
| `get_plant_profile` | 860 + recent 923 in one response. |
| `get_generation_mix` | EIA-923 `electric-power-operational-data`: headline generation mix by fuel (coal, gas, nuclear, hydro, renewables, petroleum, other) for U.S. or a state; annual or one month. |
| `get_capacity_by_fuel` | EIA-860 `operating-generator-capacity`: nameplate MW **summed by energy source** with plant counts (not plant-level search). |
| `get_electricity_prices` | `electricity/retail-sales` by state/sector. |
| `get_aeo_projections` | AEO national fuel prices or regional EMM series (prices, capacity, emissions). |
| `get_fuel_prices` | Historical spot/market fuel prices: natural gas (Henry Hub, U.S. citygate/wellhead), coal by basin (`coal/market-sales-price`), crude WTI/Brent (`petroleum/pri/spt`). Not the same as AEO `category=fuel_prices`. |
| `get_steo_forecast` | STEO (Short-Term Energy Outlook) 18-month forecasts with historical actuals (monthly or quarterly). |
| `get_state_co2_emissions` | SEDS state CO2 (million metric tons) by sector/fuel group. |

## Example prompts (natural language)

`get_fuel_prices` returns historical **benchmark** (spot/market) fuel prices:

| Example prompt | What you’ll get |
|---|---|
| `Henry Hub natural gas spot prices for 2024 by month` | `natural_gas + henry_hub + monthly` |
| `Citygate natural gas prices (U.S.) for 2022 monthly` | `natural_gas + citygate + monthly` |
| `U.S. wellhead acquisition price trend, annual from 2018 to 2022` | `natural_gas + wellhead + annual` |
| `Coal open-market price in the Powder River Basin, annual from 2020 through 2023` | `coal + powder_river + annual` |
| `WTI spot crude oil price monthly for 2023` | `crude_oil + wti + monthly` |
| `Brent crude spot price daily in January 2024` | `crude_oil + brent + daily` |

`get_steo_forecast` returns STEO **historical actuals + forecast**:

| Example prompt | What you’ll get |
|---|---|
| `natural_gas_price forecast by month for the next 18 months` | `natural_gas_price + monthly` |
| `crude_oil_price forecast by quarter for the next 18 months` | `crude_oil_price + quarterly` |
| `electricity_demand forecast by month for the next 18 months` | `electricity_demand + monthly` |
| `natural_gas_price forecast by quarter` | `natural_gas_price + quarterly` |

STEO `series` keys: `natural_gas_price`, `crude_oil_price`, `electricity_demand`; `frequency` is `monthly` or `quarterly`.

**Plant IDs** must be `STATE-plantid` (e.g. `OH-3470`), not a bare numeric code.

## Development

```bash
pytest
ruff check src tests
```

### Live API smoke test (optional)

After `pip install -e .`, set **`EIA_API_KEY`** (same as in MCP `env`) and run:

```bash
export EIA_API_KEY=your-key
python scripts/smoke_eia.py
```

This hits the real EIA API (tens of seconds), checks **two different plants** for `get_plant_operations`, and exercises every tool (including `get_generation_mix`, `get_capacity_by_fuel`, and `get_fuel_prices`). Use before releases or after changing EIA integration code. **CI** runs unit tests only; smoke needs `EIA_API_KEY` locally.

## Contributing

Issues and PRs welcome. Run **`pytest`**, **`ruff check src tests`**, and (if you touch EIA calls) **`python scripts/smoke_eia.py`** with your key before submitting.

## Related

**[Project Burnout](https://github.com/abrose1/ProjectBurnout)** — a separate **web dashboard** (Burnout / Stranded Assets) that explores US fossil plants using EIA-backed data and its own hosted stack. It is a different product from this MCP server: no shared install, and this repo’s tools are for **live EIA API** access from MCP clients, not the Burnout app UI.

## Releases

See [CHANGELOG.md](CHANGELOG.md) and [tags](https://github.com/abrose1/mcp-server-eia/tags) on GitHub.

## License

MIT
