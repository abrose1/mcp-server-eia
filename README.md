# mcp-server-eia

> **Model Context Protocol server for the U.S. EIA Open Data API** — domain tools for plants, operations, retail prices, AEO projections, and state CO₂ (not raw route mirrors).

Give any AI agent structured access to U.S. energy data from the [Energy Information Administration](https://www.eia.gov/) (EIA Open Data API v2).

This repo is the standalone MCP server described in the Burnout / StrandedAssets monorepo spec `eia-mcp-server-plan.md`. It is **not** the dashboard app: no Postgres, no stranded-asset model — live EIA calls only.

## API key (every user, including you)

1. Register a **free** key: [EIA Open Data registration](https://www.eia.gov/opendata/register.php).
2. **Recommended:** set `EIA_API_KEY` in your **MCP client config** for this server (see below). That keeps the key out of the repo, works the same for you and for anyone else who clones the project, and each person uses **their own** key on **their** machine.
3. **Optional:** for manual runs in a terminal, `export EIA_API_KEY=...` before `python -m mcp_server_eia`.

Do **not** commit keys. Do **not** put secrets in `.venv` (that directory is only for Python packages).

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
- Replace the key value with yours; other users replace it with theirs.
- Optional: add `"EIA_AEO_RELEASE": "2025"` to `env` if you need a different AEO release path than the default.

Cursor: MCP settings UI or the JSON config file your version uses. Claude Desktop: `claude_desktop_config.json` on macOS under Application Support.

## Why not call the EIA API directly?

- Fuel types are coded (`BIT`, `NG`, …), not “coal” and “gas”.
- Plant inventory is generator-level; useful answers need aggregation to plant.
- AEO data uses table IDs, scenario codes, and region facets that are hard to guess.
- This server wraps those details behind six domain tools and a stable `{ "data", "meta" }` response shape.

## Quick start (install)

```bash
cd mcp-server-eia
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Then add the MCP block above (or export `EIA_API_KEY` for a one-off terminal run).

## Tools (v1)

| Tool | Purpose |
|------|---------|
| `search_power_plants` | EIA-860 inventory aggregated to plants (fuel, state, capacity, status). |
| `get_plant_operations` | EIA-923 facility-fuel: generation, fuel use, CF, heat rate. |
| `get_plant_profile` | 860 + recent 923 in one response. |
| `get_electricity_prices` | `electricity/retail-sales` by state/sector. |
| `get_aeo_projections` | AEO national fuel prices or regional EMM series (prices, capacity, emissions). |
| `get_state_co2_emissions` | SEDS state CO2 (million metric tons) by sector/fuel group. |

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

This hits the real EIA API (tens of seconds), checks **two different plants** for `get_plant_operations`, and exercises every tool. Use it before releases or after changing EIA integration code. CI does **not** run this by default (no shared secret).

## Related

- Burnout / StrandedAssets — stranded-asset dashboard (same EIA ingestion patterns; different product).

## Publish this repo on GitHub

1. Create a **new public repository** on GitHub (e.g. `mcp-server-eia`) **without** adding a README or `.gitignore` (this project already has them).
2. From this directory:

   ```bash
   git remote add origin https://github.com/YOUR_USER/mcp-server-eia.git
   git branch -M main
   git push -u origin main
   git push origin v0.1.0
   ```

3. On GitHub: **Settings → General** — set the repository **description** (one line, e.g. the blockquote above) and optional **website** / topics (`mcp`, `eia`, `energy`, `python`).

4. Update the compare URL in `CHANGELOG.md` for `[0.1.0]` to point at your real GitHub user/org.

## License

MIT
