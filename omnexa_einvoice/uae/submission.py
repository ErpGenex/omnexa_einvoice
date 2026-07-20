# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.uae.service import run_phase1, run_phase2


@frappe.whitelist()
def process_uae_invoice(
	reference_name: str,
	*,
	company: str | None = None,
	phase: str = "phase1",
	sync: int | bool = False,
) -> dict[str, Any]:
	"""Desk / API entry for UAE PINT AE invoices."""
	if not (reference_name or "").strip():
		frappe.throw(_("reference_name is required."))
	payload = {
		"reference_name": reference_name.strip(),
		"company": company or frappe.defaults.get_user_default("company"),
		"document_type": "invoice"
	}
	ph = (phase or "phase1").strip().lower()
	if ph == "phase2":
		return run_phase2(payload, sync=bool(sync))
	return run_phase1(payload)
