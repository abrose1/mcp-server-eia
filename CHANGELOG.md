# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-03-29

### Added

- Initial release: MCP stdio server for [EIA Open Data API v2](https://www.eia.gov/opendata/).
- Tools: `search_power_plants`, `get_plant_operations`, `get_plant_profile`, `get_electricity_prices`, `get_aeo_projections`, `get_state_co2_emissions`.
- Standard `{ "data", "meta" }` response envelope.
- `scripts/smoke_eia.py` for optional live API checks (requires `EIA_API_KEY`).
- Unit tests (`pytest`) and GitHub Actions workflow for tests (no API key).

<!-- After you publish on GitHub, add: [0.1.0]: https://github.com/<you>/mcp-server-eia/releases/tag/v0.1.0 -->
