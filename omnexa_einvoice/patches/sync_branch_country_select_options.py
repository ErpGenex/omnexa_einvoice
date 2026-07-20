# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Refresh Branch.country_code Select options (CODE — country name)."""

from __future__ import annotations

import frappe

from omnexa_einvoice.tax_engine.country_catalog import (
	branch_country_label_for_code,
	branch_country_options,
	normalize_country_code,
)


def execute():
	if not frappe.db.exists("DocType", "Branch"):
		return
	options = branch_country_options()
	df = frappe.get_meta("Branch").get_field("country_code")
	if not df:
		return
	frappe.db.set_value(
		"DocField",
		{"parent": "Branch", "fieldname": "country_code"
	},
		"options",
		options,
		update_modified=False,
	)
	frappe.clear_cache(doctype="Branch")

	# Select value = label; country_iso = 2-letter code for depends_on / routing
	for name, raw in frappe.get_all("Branch", fields=["name", "country_code"], as_list=True):
		code = normalize_country_code(raw)
		updates = {"country_code": branch_country_label_for_code(code)
	}
		if frappe.get_meta("Branch").has_field("country_iso"):
			updates["country_iso"] = code
		if frappe.get_meta("Branch").has_field("country_name"):
			from omnexa_einvoice.tax_engine.country_catalog import country_display_name

			updates["country_name"] = country_display_name(code)
		frappe.db.set_value("Branch", name, updates, update_modified=False)
