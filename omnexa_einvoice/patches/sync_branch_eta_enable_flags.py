# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Ensure eta_ereceipt_enabled / eta_einvoice_enabled match populated credentials."""

from __future__ import annotations

import frappe


def execute():
	if not frappe.db.exists("DocType", "Branch"):
		return
	meta = frappe.get_meta("Branch")
	if not meta.has_field("eta_ereceipt_enabled"):
		return

	for row in frappe.get_all("Branch", fields=["name"]):
		branch = frappe.db.get_value(
			"Branch",
			row.name,
			[
				"eta_ereceipt_enabled",
				"eta_einvoice_enabled",
				"eta_receipt_client_id",
				"eta_pos_device_serial",
				"eta_invoice_client_id",
			],
			as_dict=True,
		)
		if not branch:
			continue
		updates = {}
		if (branch.get("eta_receipt_client_id") or branch.get("eta_pos_device_serial")) and not int(
			branch.get("eta_ereceipt_enabled") or 0
		):
			updates["eta_ereceipt_enabled"] = 1
		if branch.get("eta_invoice_client_id") and not int(branch.get("eta_einvoice_enabled") or 0):
			updates["eta_einvoice_enabled"] = 1
		if updates:
			frappe.db.set_value("Branch", row.name, updates, update_modified=False)
