# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""ZATCA Submission Log helpers."""

from __future__ import annotations

from typing import Any

import frappe


def create_submission_log(payload: dict[str, Any], *, phase: str, status: str) -> str:
	doc = frappe.get_doc(
		{
			"doctype": "ZATCA Submission Log",
			"company": payload.get("company"),
			"reference_name": payload.get("reference_name"),
			"document_type": payload.get("document_type"),
			"phase": phase,
			"status": status,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def update_submission_log(name: str, **kwargs) -> None:
	if not name:
		return
	frappe.db.set_value("ZATCA Submission Log", name, kwargs, update_modified=True)
