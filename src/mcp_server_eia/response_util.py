"""Standard tool response envelope (see technical plan)."""

from __future__ import annotations

from typing import Any


def envelope(
    data: list[dict[str, Any]],
    *,
    source: str,
    frequency: str | None = None,
    period_format: str | None = None,
    units: dict[str, str] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "source": source,
        "record_count": len(data),
        "notes": list(notes or []),
    }
    if frequency is not None:
        meta["frequency"] = frequency
    if period_format is not None:
        meta["period_format"] = period_format
    if units is not None:
        meta["units"] = units
    return {"data": data, "meta": meta}


def error_envelope(
    message: str,
    *,
    source: str = "error",
    notes: list[str] | None = None,
) -> dict[str, Any]:
    extra = list(notes or [])
    extra.insert(0, message)
    return {"data": [], "meta": {"source": source, "record_count": 0, "notes": extra}}
