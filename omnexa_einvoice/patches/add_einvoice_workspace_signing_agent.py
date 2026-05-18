# Copyright (c) 2026, Omnexa and contributors
# License: MIT

"""Add USB Signing Agent + ETA consoles to E-Invoice workspace (shortcuts visible on /app/e-invoice)."""

from __future__ import annotations

import json
from pathlib import Path

import frappe

WORKSPACE = "E-Invoice"
ZIP_NAME = "OmnexaESigningAgent-win64.zip"

PAGE_SHORTCUTS = [
	{
		"label": "USB Signing Agent (Windows)",
		"type": "Page",
		"link_to": "eta-signing-agent",
		"icon": "download",
	},
	{
		"label": "ETA E-Invoice Console",
		"type": "Page",
		"link_to": "eta-einvoice-console",
		"icon": "file",
	},
	{
		"label": "ETA E-Receipt Console",
		"type": "Page",
		"link_to": "eta-ereceipt-console",
		"icon": "receipt",
	},
]

CONTENT_SHORTCUTS = [
	{"id": "e-invoice-op4", "type": "shortcut", "data": {"shortcut_name": "USB Signing Agent (Windows)", "col": 4}},
	{"id": "e-invoice-op5", "type": "shortcut", "data": {"shortcut_name": "ETA E-Invoice Console", "col": 4}},
	{"id": "e-invoice-op6", "type": "shortcut", "data": {"shortcut_name": "ETA E-Receipt Console", "col": 4}},
]


def _zip_available() -> bool:
	try:
		path = Path(frappe.get_app_path("omnexa_einvoice", "public", "downloads", ZIP_NAME))
		return path.is_file()
	except Exception:
		return False


def _content_shortcut_names(content: list) -> set[str]:
	names: set[str] = set()
	for block in content:
		if block.get("type") == "shortcut":
			names.add((block.get("data") or {}).get("shortcut_name") or "")
	return {n for n in names if n}


def _insert_after_sales_invoice(content: list, blocks: list[dict]) -> list:
	names = _content_shortcut_names(content)
	to_add = [b for b in blocks if b["data"]["shortcut_name"] not in names]
	if not to_add:
		return content

	insert_at = len(content)
	for i, block in enumerate(content):
		if block.get("id") == "e-invoice-op3":
			insert_at = i + 1
			break
		if (block.get("data") or {}).get("shortcut_name") == "Sales Invoice":
			insert_at = i + 1

	for block in reversed(to_add):
		content.insert(insert_at, block)
	return content


def execute():
	if not frappe.db.exists("Workspace", WORKSPACE):
		return

	ws = frappe.get_doc("Workspace", WORKSPACE)
	existing_labels = {s.label for s in ws.shortcuts}

	for sc in PAGE_SHORTCUTS:
		if sc["label"] not in existing_labels:
			ws.append("shortcuts", sc)
			existing_labels.add(sc["label"])

	dl_label = "Download Signing Agent ZIP"
	if _zip_available() and dl_label not in existing_labels:
		ws.append(
			"shortcuts",
			{
				"label": dl_label,
				"type": "URL",
				"url": f"/assets/omnexa_einvoice/downloads/{ZIP_NAME}",
				"icon": "download",
			},
		)
		existing_labels.add(dl_label)

	content = json.loads(ws.content or "[]")
	content = _insert_after_sales_invoice(content, CONTENT_SHORTCUTS)
	if _zip_available() and dl_label not in _content_shortcut_names(content):
		content = _insert_after_sales_invoice(
			content,
			[
				{
					"id": "e-invoice-op-dl",
					"type": "shortcut",
					"data": {"shortcut_name": dl_label, "col": 4},
				}
			],
		)

	ws.content = json.dumps(content)

	# Sidebar links (card layout / link panel)
	link_labels = {row.label for row in ws.links}
	for sc in PAGE_SHORTCUTS:
		if sc["label"] in link_labels:
			continue
		ws.append(
			"links",
			{
				"label": sc["label"],
				"type": "Link",
				"link_type": sc["type"],
				"link_to": sc["link_to"],
				"is_query_report": 0,
				"hidden": 0,
				"onboard": 0,
			},
		)

	ws.save(ignore_permissions=True)
