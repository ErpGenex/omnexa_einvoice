# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Phase 1 + Phase 2 orchestration — delegates to country pipeline."""

from __future__ import annotations

from typing import Any

from omnexa_einvoice.tax_engine.plugin.pipeline import run_country_phase1, run_country_phase2


def run_phase1(payload: dict[str, Any], *, country_code: str) -> dict[str, Any]:
	return run_country_phase1(payload, country_code=country_code)


def run_phase2(payload: dict[str, Any], *, country_code: str, sync: bool = False) -> dict[str, Any]:
	return run_country_phase2(payload, country_code=country_code, sync=sync)
