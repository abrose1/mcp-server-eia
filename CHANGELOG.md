# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] — 2026-03-30

### Added

- `get_fuel_prices` — historical spot/market fuel prices: natural gas Henry Hub (`natural-gas/pri/fut`), U.S. citygate and wellhead (`natural-gas/pri/sum`), coal open-market price by basin (`coal/market-sales-price`), crude WTI/Brent spot (`petroleum/pri/spt`). Parameters: `fuel`, `price_type`, `frequency`, optional `start_year` / `end_year`.

[0.3.0]: https://github.com/abrose1/mcp-server-eia/releases/tag/v0.3.0

## [0.2.0] — 2026-03-30

### Added

- `get_generation_mix` — `electricity/electric-power-operational-data`, Electric Power sector (98), headline non-overlapping fuel buckets (COL, NGO, NUC, HYC+HPS, AOR, PET) plus remainder `other`; annual or monthly period.
- `get_capacity_by_fuel` — `electricity/operating-generator-capacity` aggregated by `energy_source_code` (MW and distinct plant counts).

[0.2.0]: https://github.com/abrose1/mcp-server-eia/releases/tag/v0.2.0

## [0.1.0] — 2026-03-29

### Added

- Initial release: MCP stdio server for [EIA Open Data API v2](https://www.eia.gov/opendata/).
- Tools: `search_power_plants`, `get_plant_operations`, `get_plant_profile`, `get_electricity_prices`, `get_aeo_projections`, `get_state_co2_emissions`.
- Standard `{ "data", "meta" }` response envelope.
- `scripts/smoke_eia.py` for optional live API checks (requires `EIA_API_KEY`).
- Unit tests (`pytest`) and GitHub Actions workflow for tests (no API key).

[0.1.0]: https://github.com/abrose1/mcp-server-eia/releases/tag/v0.1.0
