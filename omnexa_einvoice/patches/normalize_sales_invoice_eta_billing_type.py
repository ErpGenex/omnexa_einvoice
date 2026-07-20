# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Fix Sales Invoice eta_billing_type values stored as Arabic label|value."""

from __future__ import annotations

import frappe

from omnexa_einvoice.sales_invoice_eta import normalize_eta_billing_type


def execute():
	if not frappe.get_meta("Sales Invoice").has_field("eta_billing_type"):
		return
	for row in frappe.get_all("Sales Invoice", fields=["name", "eta_billing_type"]):
		raw = row.eta_billing_type
		if not raw or raw in ("Regular", "E-Invoice", "E-Receipt"):
			continue
		normalized = normalize_eta_billing_type(raw)
		if normalized != raw:
			frappe.db.set_value("Sales Invoice", row.name, "eta_billing_type", normalized, update_modified=False)
