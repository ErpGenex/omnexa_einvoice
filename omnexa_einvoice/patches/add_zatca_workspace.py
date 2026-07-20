# Copyright (c) 2026, Omnexa and contributors
# License: MIT

"""Create ZATCA workspace with shortcuts (isolated from Egypt E-Invoice workspace)."""

from __future__ import annotations

import json

import frappe

WORKSPACE = "ZATCA"
MODULE = "Omnexa Einvoice"


def execute():
	if frappe.db.exists("Workspace", WORKSPACE):
		_ensure_shortcuts(frappe.get_doc("Workspace", WORKSPACE))
		return

	content = [
		{"id": "zatca-h1", "type": "header", "data": {"text": "Saudi ZATCA E-Invoicing", "col": 12}},
		{"id": "zatca-s1", "type": "shortcut", "data": {"shortcut_name": "ZATCA Company Settings", "col": 4}},
		{"id": "zatca-s2", "type": "shortcut", "data": {"shortcut_name": "ZATCA Submission Log", "col": 4}},
		{"id": "zatca-s3", "type": "shortcut", "data": {"shortcut_name": "ZATCA Console", "col": 4}},
	]

	ws = frappe.get_doc(
		{
			"doctype": "Workspace",
			"name": WORKSPACE,
			"label": WORKSPACE,
			"title": WORKSPACE,
			"module": MODULE,
			"public": 1,
			"content": json.dumps(content),
			"shortcuts": [
				{
					"label": "ZATCA Company Settings",
					"type": "DocType",
					"link_to": "ZATCA Company Settings",
					"icon": "setting",
					"color": "Cyan",
				},
				{
					"label": "ZATCA Submission Log",
					"type": "DocType",
					"link_to": "ZATCA Submission Log",
					"icon": "list",
					"color": "Blue",
				},
				{
					"label": "ZATCA Console",
					"type": "Page",
					"link_to": "zatca-console",
					"icon": "dashboard",
					"color": "Purple",
				},
			],
			"links": [
				{
					"label": "ZATCA Company Settings",
					"type": "Link",
					"link_type": "DocType",
					"link_to": "ZATCA Company Settings",
				},
				{
					"label": "ZATCA Submission Log",
					"type": "Link",
					"link_type": "DocType",
					"link_to": "ZATCA Submission Log",
				},
				{
					"label": "ZATCA Console",
					"type": "Link",
					"link_type": "Page",
					"link_to": "zatca-console",
				},
			],
		}
	)
	ws.insert(ignore_permissions=True)


def _ensure_shortcuts(ws):
	labels = {s.label for s in ws.shortcuts}
	for sc in [
		{"label": "ZATCA Company Settings", "type": "DocType", "link_to": "ZATCA Company Settings", "icon": "setting", "color": "Cyan"},
		{"label": "ZATCA Submission Log", "type": "DocType", "link_to": "ZATCA Submission Log", "icon": "list", "color": "Blue"},
		{"label": "ZATCA Console", "type": "Page", "link_to": "zatca-console", "icon": "dashboard", "color": "Purple"},
	]:
		if sc["label"] not in labels:
			ws.append("shortcuts", sc)
	ws.save(ignore_permissions=True)
