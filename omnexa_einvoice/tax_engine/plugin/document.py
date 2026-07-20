# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Build canonical invoice dict from Sales Invoice (read-only)."""

from __future__ import annotations

import uuid
from typing import Any

import frappe
from frappe.utils import flt, now_datetime


def build_from_sales_invoice(si, *, country_code: str, currency: str) -> dict[str, Any]:
	"""Map Sales Invoice to neutral document payload — no DocType customization."""
	company = frappe.get_doc("Company", si.company)
	seller_name = company.company_name or si.company
	tax_id = company.tax_id or ""
	branch = (getattr(si, "branch", None) or "").strip() or None
	if branch:
		from omnexa_einvoice.tax_engine.country_tax_settings import get_country_tax_settings

		settings = get_country_tax_settings(si.company, country_code, branch=branch)
		if settings and settings.get("tax_registration_number"):
			tax_id = settings.tax_registration_number
	elif frappe.db.exists("Country Tax Settings", {"company": si.company, "country_code": country_code
	}):
		tax_id = (
			frappe.db.get_value(
				"Country Tax Settings",
				{"company": si.company, "country_code": country_code
	},
				"tax_registration_number",
			)
			or tax_id
		)
	lines = []
	cc = (country_code or "").strip().upper()
	for row in si.items:
		qty = flt(row.qty) or 1
		rate = flt(row.rate)
		amount = flt(row.amount) or qty * rate
		tax_amt = flt(getattr(row, "tax_amount", 0) or 0)
		line = {
			"item_code": row.item_code,
			"description": row.description or row.item_name,
			"qty": qty,
			"rate": rate,
			"amount": amount,
			"tax_amount": tax_amt
	}
		if cc == "IN" and row.item_code:
			hsn = getattr(row, "gst_hsn_code", None) or frappe.db.get_value(
				"Item", row.item_code, "gst_hsn_code"
			)
			if hsn:
				line["hsn_code"] = str(hsn).strip()
		lines.append(line)
	doc_type = "credit_note" if int(getattr(si, "is_return", 0) or 0) else "invoice"
	invoice_type_code = "381" if doc_type == "credit_note" else "380"
	return {
		"uuid": str(uuid.uuid4()),
		"reference_name": si.name,
		"reference_doctype": "Sales Invoice",
		"document_type": doc_type,
		"invoice_type_code": invoice_type_code,
		"issue_datetime": f"{si.posting_date}T{si.posting_time or '00:00:00'
	}",
		"currency": si.currency or currency,
		"company": si.company,
		"branch": branch,
		"customer": si.customer,
		"seller": {
			"name": seller_name,
			"tax_registration": tax_id
	},
		"lines": lines,
		"totals": {
			"net_total": flt(si.net_total),
			"tax_total": flt(si.total_taxes_and_charges),
			"grand_total": flt(si.grand_total)}
	}


def build_from_payload(payload: dict[str, Any], *, country_code: str, currency: str) -> dict[str, Any]:
	if payload.get("document") and isinstance(payload["document"], dict):
		doc = dict(payload["document"])
		doc.setdefault("uuid", str(uuid.uuid4()))
		doc.setdefault("reference_name", payload.get("reference_name"))
		_apply_document_type(doc, payload)
		return doc
	ref = (payload.get("reference_name") or "").strip()
	if ref and frappe.db.exists("Sales Invoice", ref):
		doc = build_from_sales_invoice(
			frappe.get_doc("Sales Invoice", ref), country_code=country_code, currency=currency
		)
		doc["branch"] = payload.get("branch") or doc.get("branch")
		_apply_document_type(doc, payload)
		return doc
	doc = {
		"uuid": str(uuid.uuid4()),
		"reference_name": ref or f"{country_code
	}-TEST",
		"issue_datetime": now_datetime().strftime("%Y-%m-%dT%H:%M:%S"),
		"currency": currency,
		"company": payload.get("company") or "",
		"branch": payload.get("branch"),
		"seller": {
			"name": payload.get("seller_name") or "Seller",
			"tax_registration": payload.get("tax_registration_number") or ""
	},
		"lines": payload.get("lines") or [{"description": "Item", "qty": 1, "rate": 100, "amount": 100, "tax_amount": 15
	}],
		"totals": payload.get("totals") or {"net_total": 100, "tax_total": 15, "grand_total": 115}
	}
	_apply_document_type(doc, payload)
	return doc


def _apply_document_type(document: dict[str, Any], payload: dict[str, Any]) -> None:
	dt = (payload.get("document_type") or document.get("document_type") or "invoice").strip().lower()
	if int(payload.get("is_return") or 0):
		dt = "credit_note"
	document["document_type"] = dt
	document["invoice_type_code"] = "381" if dt == "credit_note" else document.get("invoice_type_code") or "380"
