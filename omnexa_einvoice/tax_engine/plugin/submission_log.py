# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

from typing import Any

import frappe


def create_log(payload: dict[str, Any], *, country_code: str, phase: str, status: str) -> str | None:
	if not frappe.db.table_exists("tabCountry Tax Submission Log"):
		return None
	row = {
		"doctype": "Country Tax Submission Log",
		"company": payload.get("company"),
		"country_code": country_code,
		"reference_doctype": payload.get("reference_doctype") or "Sales Invoice",
		"reference_name": payload.get("reference_name"),
		"phase": phase,
		"status": status
	}
	if payload.get("idempotency_key"):
		row["idempotency_key"] = payload.get("idempotency_key")
	if payload.get("signing_family"):
		row["signing_family"] = payload.get("signing_family")
	doc = frappe.get_doc(row)
	doc.insert(ignore_permissions=True)
	return doc.name


def update_log(name: str | None, **kwargs) -> None:
	if not name:
		return
	frappe.db.set_value("Country Tax Submission Log", name, kwargs, update_modified=True)
