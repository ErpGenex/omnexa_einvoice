# Copyright (c) 2026, ErpGenEx
# License: MIT

from __future__ import annotations

import frappe


@frappe.whitelist()
def preview_sector_kpi(scenario: str | None = None, params: str | None = None) -> dict:
	"""SAP Wave C — e-invoice / tax authority KPI preview (omnexa_core bridge)."""
	from omnexa_core.omnexa_core.vertical_api import preview_sector_kpi as _core_preview

	return _core_preview("einvoice", scenario=scenario, params=params)
