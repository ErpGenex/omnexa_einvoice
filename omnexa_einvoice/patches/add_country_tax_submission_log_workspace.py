# Copyright (c) 2026, Omnexa and contributors
# License: MIT

"""Add Country Tax Submission Log to Tax Countries workspace."""

from __future__ import annotations

import json

import frappe

WORKSPACE = "Tax Countries"


def execute():
	if not frappe.db.exists("Workspace", WORKSPACE):
		return
	ws = frappe.get_doc("Workspace", WORKSPACE)
	names = {s.link_to for s in (ws.shortcuts or []) if s.link_to}
	if "Country Tax Submission Log" not in names:
		ws.append(
			"shortcuts",
			{
				"label": "Country Tax Submission Log",
				"type": "DocType",
				"link_to": "Country Tax Submission Log",
				"icon": "list"
	},
		)
	content = json.loads(ws.content or "[]")
	ids = {c.get("id") for c in content}
	if "tc-s5" not in ids:
		content.append(
			{
				"id": "tc-s5",
				"type": "shortcut",
				"data": {"shortcut_name": "Country Tax Submission Log", "col": 4}
	}
		)
	ws.content = json.dumps(content)
	ws.save(ignore_permissions=True)
