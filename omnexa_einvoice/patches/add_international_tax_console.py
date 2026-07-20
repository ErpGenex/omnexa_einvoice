# Copyright (c) 2026, Omnexa and contributors
# License: MIT

"""Add International Tax Console shortcut to Tax Countries workspace."""

from __future__ import annotations

import json

import frappe

WORKSPACE = "Tax Countries"


def execute():
	if not frappe.db.exists("Workspace", WORKSPACE):
		return
	ws = frappe.get_doc("Workspace", WORKSPACE)
	shortcuts = ws.shortcuts or []
	names = {s.link_to for s in shortcuts if s.link_to}
	if "international-tax-console" not in names:
		ws.append(
			"shortcuts",
			{
				"label": "International Tax Console",
				"type": "Page",
				"link_to": "international-tax-console",
				"icon": "globe",
			},
		)
	content = json.loads(ws.content or "[]")
	ids = {c.get("id") for c in content}
	if "tc-s4" not in ids:
		content.append(
			{
				"id": "tc-s4",
				"type": "shortcut",
				"data": {"shortcut_name": "International Tax Console", "col": 4},
			}
		)
	ws.content = json.dumps(content)
	ws.save(ignore_permissions=True)
