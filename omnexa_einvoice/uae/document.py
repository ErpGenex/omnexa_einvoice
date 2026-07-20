# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Map Sales Invoice → UAE PINT document dict (read-only)."""

from __future__ import annotations

import uuid
from typing import Any

import frappe
from frappe.utils import flt, now_datetime

from omnexa_einvoice.uae.constants import CURRENCY_AED
from omnexa_einvoice.uae.settings import uae_effective_settings


def _buyer_from_customer(customer: str | None) -> dict[str, Any]:
	if not customer:
		return {}
	cust = frappe.db.get_value(
		"Customer",
		customer,
		["customer_name", "tax_id"],
		as_dict=True,
	)
	if not cust:
		return {}
	return {
		"name": cust.customer_name or customer,
		"tax_registration": (cust.tax_id or "").strip()
	}


def build_from_sales_invoice(si) -> dict[str, Any]:
	branch = (getattr(si, "branch", None) or "").strip() or None
	settings = uae_effective_settings(si.company, branch=branch)
	company = frappe.get_doc("Company", si.company)
	seller_name = company.company_name or si.company
	seller_tin = settings.seller_tin or (company.tax_id or "")
	lines = []
	for row in si.items:
		qty = flt(row.qty) or 1
		rate = flt(row.rate)
		net = flt(row.amount) or qty * rate
		tax_amt = flt(getattr(row, "tax_amount", 0) or 0)
		if not tax_amt and net:
			tax_amt = flt(net * 5 / 100, 2)
		lines.append(
			{
				"item_code": row.item_code,
				"description": row.description or row.item_name,
				"qty": qty,
				"rate": rate,
				"net_amount": net,
				"tax_amount": tax_amt
	}
		)
	issue_time = str(si.posting_time or "00:00:00")[:8]
	return {
		"uuid": str(uuid.uuid4()),
		"reference_name": si.name,
		"reference_doctype": "Sales Invoice",
		"issue_datetime": f"{si.posting_date}T{issue_time
	}",
		"currency": si.currency or CURRENCY_AED,
		"company": si.company,
		"branch": branch,
		"customer": si.customer,
		"invoice_type_code": settings.invoice_type_code,
		"seller": {
			"name": seller_name,
			"name_ar": settings.legal_name_ar or seller_name,
			"tax_registration": seller_tin,
			"peppol_id": settings.peppol_sender_id
	},
		"buyer": _buyer_from_customer(si.customer),
		"lines": lines,
		"totals": {
			"net_total": flt(si.net_total),
			"tax_total": flt(si.total_taxes_and_charges),
			"grand_total": flt(si.grand_total)
	},
		"uae_settings": settings
	}


def build_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
	if payload.get("document") and isinstance(payload["document"], dict):
		doc = dict(payload["document"])
		doc.setdefault("uuid", str(uuid.uuid4()))
		doc.setdefault("reference_name", payload.get("reference_name"))
		return doc
	ref = (payload.get("reference_name") or "").strip()
	company = payload.get("company") or ""
	if ref and frappe.db.exists("Sales Invoice", ref):
		doc = build_from_sales_invoice(frappe.get_doc("Sales Invoice", ref))
		doc["branch"] = payload.get("branch") or doc.get("branch")
		return doc
	settings = uae_effective_settings(company, branch=payload.get("branch")) if company else frappe._dict()
	return {
		"uuid": str(uuid.uuid4()),
		"reference_name": ref or "SI-AE-TEST",
		"reference_doctype": "Sales Invoice",
		"issue_datetime": now_datetime().strftime("%Y-%m-%dT%H:%M:%S"),
		"currency": CURRENCY_AED,
		"company": company,
		"invoice_type_code": settings.invoice_type_code or "380",
		"seller": {
			"name": payload.get("seller_name") or "Seller",
			"name_ar": payload.get("seller_name_ar") or "",
			"tax_registration": payload.get("tax_registration_number") or settings.seller_tin or "",
			"peppol_id": settings.peppol_sender_id
	},
		"buyer": payload.get("buyer") or {"name": "Buyer", "tax_registration": payload.get("buyer_tin") or ""
	},
		"lines": payload.get("lines")
		or [{"description": "Item", "qty": 1, "rate": 100, "net_amount": 100, "tax_amount": 5
	}],
		"totals": payload.get("totals") or {"net_total": 100, "tax_total": 5, "grand_total": 105
	},
		"uae_settings": settings
	}
