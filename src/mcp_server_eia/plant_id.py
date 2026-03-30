"""Canonical plant id: {STATE}-{plantid} (EIA-860 style)."""

from __future__ import annotations


def parse_plant_id(plant_id: str) -> tuple[str, str]:
    """
    Parse ``STATE-plantid`` (2-letter state + hyphen + EIA plant code).

    Rejects bare numeric ``plantid`` (ambiguous across states).
    """
    s = (plant_id or "").strip().upper()
    if not s:
        raise ValueError("plant_id is required")
    if s.isdigit():
        raise ValueError(
            "plant_id must be STATE-plantid (e.g. OH-3470), not a bare plant number"
        )
    parts = s.split("-", 1)
    if len(parts) != 2:
        raise ValueError("plant_id must look like STATE-plantid, e.g. OH-3470")
    state, code = parts[0].strip(), parts[1].strip()
    if len(state) != 2 or not state.isalpha():
        raise ValueError("plant_id must start with a 2-letter US state code")
    if not code:
        raise ValueError("plant_id is missing the plant code after the state")
    return state, code
