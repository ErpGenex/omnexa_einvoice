# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Copy legacy shared ETA credentials into receipt- and invoice-specific Branch fields."""

from __future__ import annotations

import frappe


def execute():
	if not frappe.db.exists("DocType", "Branch"):
		return
	meta = frappe.get_meta("Branch")
	if not meta.has_field("eta_receipt_client_id"):
		return

	for row in frappe.get_all("Branch", fields=["name", "eta_einvoice_enabled", "eta_ereceipt_enabled"]):
		updates: dict = {}
		branch = frappe.get_doc("Branch", row.name)

		# Legacy: old single master flag enabled both channels
		if int(branch.get("eta_einvoice_enabled") or 0):
			updates.setdefault("eta_ereceipt_enabled", 1)
			updates.setdefault("eta_einvoice_enabled", 1)
		if (branch.get("eta_receipt_client_id") or branch.get("eta_pos_device_serial")) and not int(
			branch.get("eta_ereceipt_enabled") or 0
		):
			updates["eta_ereceipt_enabled"] = 1
		if (branch.get("eta_invoice_client_id") or branch.get("eta_invoice_rin")) and not int(
			branch.get("eta_einvoice_enabled") or 0
		):
			updates["eta_einvoice_enabled"] = 1

		shared_map = (
			("eta_environment", "eta_receipt_environment", "eta_invoice_environment"),
			("eta_base_url", "eta_receipt_base_url", "eta_invoice_base_url"),
			("eta_client_id", "eta_receipt_client_id", "eta_invoice_client_id"),
			("eta_client_secret", "eta_receipt_client_secret", "eta_invoice_client_secret"),
			("eta_rin", "eta_receipt_rin", "eta_invoice_rin"),
		)
		for old_field, receipt_field, invoice_field in shared_map:
			if not meta.has_field(old_field):
				continue
			val = branch.get(old_field)
			if val and not branch.get(receipt_field):
				updates[receipt_field] = val
			if val and not branch.get(invoice_field):
				updates[invoice_field] = val

		if updates:
			frappe.db.set_value("Branch", row.name, updates, update_modified=False)
