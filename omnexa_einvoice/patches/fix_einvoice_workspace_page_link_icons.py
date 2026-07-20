# Copyright (c) 2026, Omnexa and contributors
# License: MIT

"""Backfill Workspace Link icons for ETA console pages on E-Invoice desk."""

from __future__ import annotations

import frappe

WORKSPACE = "E-Invoice"
PAGE_ICONS = {
	"eta-signing-agent": "download",
	"eta-einvoice-console": "file",
	"eta-ereceipt-console": "receipt",
}


def execute() -> None:
	if not frappe.db.exists("Workspace", WORKSPACE):
		return

	ws = frappe.get_doc("Workspace", WORKSPACE)
	changed = False
	for row in ws.links or []:
		if row.type != "Link" or row.link_type != "Page":
			continue
		icon = PAGE_ICONS.get((row.link_to or "").strip())
		if not icon or row.icon == icon:
			continue
		row.icon = icon
		changed = True

	if changed:
		ws.save(ignore_permissions=True)

	frappe.clear_cache()
