# Copyright (c) 2026, Omnexa and contributors
# License: MIT

"""Workspace for international tax countries (non-EG)."""

from __future__ import annotations

import json

import frappe

WORKSPACE = "Tax Countries"


def execute():
	if frappe.db.exists("Workspace", WORKSPACE):
		return

	content = [
		{"id": "tc-h1", "type": "header", "data": {"text": "International e-Invoicing", "col": 12}
	},
		{"id": "tc-s1", "type": "shortcut", "data": {"shortcut_name": "Country Tax Settings", "col": 4}
	},
		{"id": "tc-s2", "type": "shortcut", "data": {"shortcut_name": "ZATCA Company Settings", "col": 4}
	},
		{"id": "tc-s3", "type": "shortcut", "data": {"shortcut_name": "ZATCA Console", "col": 4}
	},
	]

	frappe.get_doc(
		{
			"doctype": "Workspace",
			"name": WORKSPACE,
			"label": WORKSPACE,
			"title": WORKSPACE,
			"module": "Omnexa Einvoice",
			"public": 1,
			"content": json.dumps(content),
			"shortcuts": [
				{
					"label": "Country Tax Settings",
					"type": "DocType",
					"link_to": "Country Tax Settings",
					"icon": "globe",
					"color": "Cyan"
	},
				{
					"label": "ZATCA Company Settings",
					"type": "DocType",
					"link_to": "ZATCA Company Settings",
					"icon": "setting",
					"color": "Blue"
	},
				{
					"label": "ZATCA Console",
					"type": "Page",
					"link_to": "zatca-console",
					"icon": "dashboard",
					"color": "Purple"
	},
			]}
	).insert(ignore_permissions=True)
