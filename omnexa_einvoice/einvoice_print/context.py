# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Build print context for Sales Invoice e-invoice (per branch country)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt, formatdate, format_datetime

from omnexa_einvoice.branch_eta import resolve_branch_for_document
from omnexa_einvoice.einvoice_print.design_catalog import EInvoicePrintDesign, get_print_design
from omnexa_einvoice.tax_engine.router import resolve_tax_provider_for_branch


def _branch_country(doc) -> str:
	branch = resolve_branch_for_document(doc)
	if not branch:
		return "EG"
	from omnexa_einvoice.tax_engine.country_catalog import normalize_country_code

	return normalize_country_code(frappe.db.get_value("Branch", branch, "country_code") or "EG")


def _seller_from_company(company: str) -> dict[str, str]:
	row = frappe.db.get_value(
		"Company",
		company,
		["company_name", "tax_id"],
		as_dict=True,
	) or {}
	return {
		"name": row.get("company_name") or company,
		"tax_id": (row.get("tax_id") or "").strip()
	}


def _buyer_from_customer(customer: str | None) -> dict[str, str]:
	if not customer:
		return {"name": "", "tax_id": ""
	}
	row = frappe.db.get_value("Customer", customer, ["customer_name", "tax_id"], as_dict=True) or {}
	return {
		"name": row.get("customer_name") or customer,
		"tax_id": (row.get("tax_id") or "").strip()
	}


def _tax_submission_for_invoice(doc, country_code: str) -> dict[str, Any]:
	"""Latest tax submission metadata + QR for print."""
	out: dict[str, Any] = {
		"uuid": "",
		"invoice_hash": "",
		"qr_tlv_base64": "",
		"qr_image_base64": "",
		"status": "",
		"authority_status": ""
	}
	ref = doc.name
	company = doc.company

	if country_code == "EG":
		rows = frappe.get_all(
			"E Invoice Submission",
			filters={"reference_name": ref, "reference_doctype": "Sales Invoice"
	},
			fields=["eta_uuid", "canonical_hash", "status", "authority_uuid"],
			order_by="modified desc",
			limit=1,
		)
		if rows:
			row = rows[0]
			out["uuid"] = row.get("eta_uuid") or row.get("authority_uuid") or ""
			out["invoice_hash"] = row.get("canonical_hash") or ""
			out["status"] = row.get("status") or ""

	elif country_code == "SA" and frappe.db.table_exists("tabZATCA Submission Log"):
		rows = frappe.get_all(
			"ZATCA Submission Log",
			filters={"reference_name": ref, "company": company
	},
			fields=["uuid", "invoice_hash", "qr_base64", "status", "zatca_status"],
			order_by="modified desc",
			limit=1,
		)
		if rows:
			row = rows[0]
			out["uuid"] = row.get("uuid") or ""
			out["invoice_hash"] = row.get("invoice_hash") or ""
			out["qr_tlv_base64"] = row.get("qr_base64") or ""
			out["status"] = row.get("status") or ""
			out["authority_status"] = row.get("zatca_status") or ""
			if out["qr_tlv_base64"]:
				try:
					from omnexa_einvoice.zatca.phase1.qr_embed import qr_tlv_to_png_base64

					out["qr_image_base64"] = qr_tlv_to_png_base64(out["qr_tlv_base64"])
				except Exception:
					pass

	elif frappe.db.table_exists("tabCountry Tax Submission Log"):
		rows = frappe.get_all(
			"Country Tax Submission Log",
			filters={"reference_name": ref, "company": company, "country_code": country_code
	},
			fields=["uuid", "invoice_hash", "status", "authority_status", "response_payload"],
			order_by="modified desc",
			limit=1,
		)
		if rows:
			row = rows[0]
			out["uuid"] = row.get("uuid") or ""
			out["invoice_hash"] = row.get("invoice_hash") or ""
			out["status"] = row.get("status") or ""
			out["authority_status"] = row.get("authority_status") or ""
			if country_code == "IN":
				_enrich_india_tax_from_response(out, row.get("response_payload"))

	return out


def _enrich_india_tax_from_response(out: dict[str, Any], response_payload: str | None) -> None:
	if not response_payload:
		return
	try:
		import json

		data = json.loads(response_payload)
	except Exception:
		return
	if isinstance(data, dict):
		irn = data.get("Irn") or data.get("irn") or out.get("uuid")
		if irn:
			out["uuid"] = irn
			out["irn"] = irn
		signed_qr = data.get("SignedQRCode") or data.get("signed_qr_code") or data.get("signedQRCode")
		if signed_qr:
			out["signed_qr_code"] = signed_qr
			try:
				from omnexa_einvoice.einvoice_print.india_qr import signed_qr_to_png_base64

				out["qr_image_base64"] = signed_qr_to_png_base64(signed_qr)
			except Exception:
				pass


def get_sales_invoice_print_context(doc, *, lang: str | None = None) -> dict[str, Any]:
	"""Full Jinja context for country-specific e-invoice print."""
	if isinstance(doc, str):
		doc = frappe.get_doc("Sales Invoice", doc)

	country_code = _branch_country(doc)
	design = get_print_design(country_code)
	use_ar = (lang or frappe.local.lang or "en").startswith("ar")
	branch = resolve_branch_for_document(doc)
	routing = resolve_tax_provider_for_branch(branch) if branch else {}
	seller = _seller_from_company(doc.company)
	buyer = _buyer_from_customer(doc.customer)
	tax = _tax_submission_for_invoice(doc, country_code)

	lines = []
	for row in doc.items:
		desc = (
			getattr(row, "description", None)
			or getattr(row, "item_name", None)
			or getattr(row, "item_code", None)
			or ""
		)
		lines.append(
			{
				"idx": row.idx,
				"item_code": getattr(row, "item_code", None),
				"description": desc,
				"qty": flt(getattr(row, "qty", 0)),
				"rate": flt(getattr(row, "rate", 0)),
				"amount": flt(getattr(row, "amount", 0))}
		)

	return {
		"doc": doc,
		"country_code": country_code,
		"design": design,
		"design_dict": _design_to_dict(design),
		"rtl": design.rtl if not use_ar else True,
		"dir": "rtl" if (design.rtl or use_ar) else "ltr",
		"lang_ar": use_ar,
		"title": design.invoice_title_ar if use_ar else design.invoice_title_en,
		"country_label": design.label_ar if use_ar else design.label_en,
		"framework": design.framework,
		"authority": design.authority,
		"tax_provider": routing.get("tax_provider") or "",
		"branch": branch,
		"seller": seller,
		"buyer": buyer,
		"lines": lines,
		"tax": tax,
		"posting_date": formatdate(doc.posting_date),
		"posting_datetime": format_datetime(doc.posting_date),
		"currency": doc.currency,
		"net_total": flt(getattr(doc, "net_total", 0)),
		"tax_total": flt(
			getattr(doc, "total_taxes_and_charges", None) or getattr(doc, "total_tax", 0)
		),
		"grand_total": flt(getattr(doc, "grand_total", 0)),
		"footer": design.footer_ar if use_ar else design.footer_en
	}


def _design_to_dict(design: EInvoicePrintDesign) -> dict[str, str]:
	return {
		"country_code": design.country_code,
		"label_en": design.label_en,
		"label_ar": design.label_ar,
		"framework": design.framework,
		"authority": design.authority,
		"primary_color": design.primary_color,
		"accent_color": design.accent_color,
		"header_bg": design.header_bg,
		"invoice_title_en": design.invoice_title_en,
		"invoice_title_ar": design.invoice_title_ar,
		"footer_en": design.footer_en,
		"footer_ar": design.footer_ar,
		"template_family": design.template_family
	}
