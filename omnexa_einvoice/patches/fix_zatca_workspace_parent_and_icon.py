# Copyright (c) 2026, Omnexa and contributors
# License: MIT

"""Fix ZATCA workspace: set parent_page to E-Invoice and change icon to avoid conflict with Asset Insurance."""

from __future__ import annotations

import frappe


def execute():
	if not frappe.db.exists("Workspace", "ZATCA"):
		return

	ws = frappe.get_doc("Workspace", "ZATCA")
	changed = False

	# Set parent_page to E-Invoice for sidebar nesting
	if (ws.parent_page or "").strip() != "E-Invoice":
		ws.parent_page = "E-Invoice"
		changed = True

	# Change icon from es-line-shield (same as Asset Insurance) to es-line-globe
	if (ws.icon or "").strip() in ("", "es-line-shield"):
		ws.icon = "es-line-globe"
		changed = True

	if changed:
		ws.flags.ignore_permissions = True
		ws.flags.ignore_version = True
		ws.save()
		frappe.clear_cache(doctype="Workspace")
		frappe.msgprint("ZATCA workspace updated: parent_page=E-Invoice, icon=es-line-globe")
