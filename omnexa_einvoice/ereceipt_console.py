# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Desk console: register and send ETA e-receipts from Sales Invoices (single or bulk)."""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate

from omnexa_einvoice.sales_invoice_eta import (
	ETA_BILLING_ERECEIPT,
	ensure_sales_invoice_eta_billing,
	get_eta_billing_type,
)


def _parse_names(raw) -> list[str]:
	if not raw:
		return []
	if isinstance(raw, str):
		raw = json.loads(raw) if raw.strip().startswith("[") else [raw]
	return [str(n).strip() for n in raw if str(n).strip()]


def _latest_submissions(sales_invoice_names: list[str]) -> dict[str, frappe._dict]:
	if not sales_invoice_names:
		return {}
	rows = frappe.get_all(
		"E Invoice Submission",
		filters={
			"reference_doctype": "Sales Invoice",
			"reference_name": ["in", sales_invoice_names],
			"submission_kind": "E-Receipt",
			"operation": "submit",
		},
		fields=[
			"name",
			"reference_name",
			"status",
			"eta_uuid",
			"authority_uuid",
			"provider_reference",
			"integration_message",
			"eta_error_code",
			"modified",
		],
		order_by="creation desc",
	)
	out: dict[str, frappe._dict] = {}
	for row in rows:
		if row.reference_name not in out:
			out[row.reference_name] = frappe._dict(row)
	return out


def _match_eta_status(sub: frappe._dict | None, eta_status: str) -> bool:
	if not eta_status:
		return True
	status = (sub.status if sub else "") or "Not Registered"
	if eta_status == "pending":
		return status in ("", "Not Registered", "Draft", "Failed", "Queued")
	if eta_status == "ready":
		return status == "Signed"
	if eta_status == "completed":
		return status == "Completed"
	if eta_status == "in_progress":
		return status in ("Queued", "Signed")
	return True


@frappe.whitelist()
def get_ereceipt_queue(
	company: str | None = None,
	branch: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	eta_status: str | None = None,
	limit: int = 200,
	include_drafts: int = 1,
) -> list[dict[str, Any]]:
	"""Sales Invoices with billing type E-Receipt (submitted; optionally drafts/cancelled visible)."""
	if not frappe.get_meta("Sales Invoice").has_field("eta_billing_type"):
		return []

	conditions = [
		"si.eta_billing_type LIKE %(ereceipt)s",
		"OR si.eta_billing_type = %(ereceipt_exact)s",
	]
	params: dict[str, Any] = {
		"ereceipt": "%E-Receipt%",
		"ereceipt_exact": ETA_BILLING_ERECEIPT,
		"limit": int(limit or 200),
	}
	if int(include_drafts or 0):
		conditions.append("si.docstatus IN (0, 1, 2)")
	else:
		conditions.append("si.docstatus = 1")

	if company:
		conditions.append("si.company = %(company)s")
		params["company"] = company
	if branch:
		conditions.append("si.branch = %(branch)s")
		params["branch"] = branch
	if from_date and to_date:
		conditions.append("si.posting_date BETWEEN %(from_date)s AND %(to_date)s")
		params["from_date"] = getdate(from_date)
		params["to_date"] = getdate(to_date)
	elif from_date:
		conditions.append("si.posting_date >= %(from_date)s")
		params["from_date"] = getdate(from_date)
	elif to_date:
		conditions.append("si.posting_date <= %(to_date)s")
		params["to_date"] = getdate(to_date)

	invoices = frappe.db.sql(
		f"""
		SELECT
			si.name, si.posting_date, si.customer, si.branch, si.company,
			si.grand_total, si.currency, si.eta_billing_type, si.docstatus
		FROM `tabSales Invoice` si
		WHERE ({' '.join(conditions[:2])})
			AND {' AND '.join(conditions[2:])}
		ORDER BY si.posting_date DESC, si.modified DESC
		LIMIT %(limit)s
		""",
		params,
		as_dict=True,
	)
	if not invoices:
		return []

	from omnexa_einvoice.sales_invoice_eta import normalize_eta_billing_type

	invoices = [inv for inv in invoices if normalize_eta_billing_type(inv.eta_billing_type) == ETA_BILLING_ERECEIPT]
	if not invoices:
		return []

	customers = {i.customer for i in invoices if i.customer}
	customer_names: dict[str, str] = {}
	if customers:
		for row in frappe.get_all(
			"Customer",
			filters={"name": ["in", list(customers)]},
			fields=["name", "customer_name"],
		):
			customer_names[row.name] = row.customer_name

	subs = _latest_submissions([i.name for i in invoices])
	rows: list[dict[str, Any]] = []
	for inv in invoices:
		sub = subs.get(inv.name)
		if not _match_eta_status(sub, (eta_status or "").strip()):
			continue
		docstatus_label = {0: _("Draft"), 1: _("Submitted"), 2: _("Cancelled")}.get(int(inv.docstatus or 0), "")
		rows.append(
			{
				"sales_invoice": inv.name,
				"posting_date": str(inv.posting_date),
				"customer": inv.customer,
				"customer_name": customer_names.get(inv.customer) or inv.customer,
				"branch": inv.branch,
				"company": inv.company,
				"grand_total": inv.grand_total,
				"currency": inv.currency,
				"docstatus": inv.docstatus,
				"invoice_status": docstatus_label,
				"submission": sub.name if sub else "",
				"eta_status": sub.status if sub else "Not Registered",
				"eta_uuid": sub.eta_uuid if sub else "",
				"provider_reference": sub.provider_reference if sub else "",
				"message": sub.integration_message if sub else "",
				"error_code": sub.eta_error_code if sub else "",
			}
		)
	return rows


@frappe.whitelist()
def preview_ereceipt(sales_invoice: str) -> dict[str, Any]:
	"""Build ETA receipt JSON for review (no DB write)."""
	from omnexa_einvoice.branch_eta import resolve_branch_for_document
	from omnexa_einvoice.eta_receipt import (
		build_eta_receipt_document,
		encode_eta_receipt_submission,
		validate_receipt_document,
	)

	doc = frappe.get_doc("Sales Invoice", sales_invoice)
	if doc.docstatus != 1:
		frappe.throw(_("Sales Invoice must be submitted before sending e-receipt."), title=_("E-Receipt"))
	ensure_sales_invoice_eta_billing(doc, required=ETA_BILLING_ERECEIPT)
	doc = frappe.get_doc("Sales Invoice", sales_invoice)
	branch = resolve_branch_for_document(doc)
	if not branch:
		frappe.throw(_("Branch is required on the Sales Invoice."), title=_("E-Receipt"))
	payload = build_eta_receipt_document(doc, branch=branch)
	validate_receipt_document(payload, strict_datetime=False)
	body_bytes = encode_eta_receipt_submission(payload)
	return {
		"sales_invoice": sales_invoice,
		"branch": branch,
		"uuid": payload.get("header", {}).get("uuid", ""),
		"receipt_number": payload.get("header", {}).get("receiptNumber", ""),
		"document": payload,
		"submission_body": body_bytes.decode("utf-8")[:8000],
	}


def _submission_name_for_invoice(sales_invoice: str) -> str:
	from omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission import (
		ensure_submission_for_document,
	)

	result = ensure_submission_for_document("Sales Invoice", sales_invoice)
	return result["name"]


@frappe.whitelist()
def test_eta_receipt_connection(branch: str | None = None, company: str | None = None) -> dict[str, Any]:
	"""Test OAuth token for e-Receipt (POS headers) — use from console before send."""
	from omnexa_einvoice.branch_eta import RECEIPT_KIND, get_branch_eta_credentials
	from omnexa_einvoice.eta_integration import exchange_eta_token

	if not branch and company:
		branch = frappe.db.get_value(
			"Branch",
			{"company": company, "is_head_office": 1},
			"name",
			order_by="creation asc",
		) or frappe.db.get_value("Branch", {"company": company}, "name")
	if not branch:
		frappe.throw(_("Select a branch or company."), title=_("ETA"))

	creds = get_branch_eta_credentials(branch, kind=RECEIPT_KIND)
	from omnexa_einvoice.branch_eta import get_eta_receipt_branch_settings
	from omnexa_einvoice.eta_receipt import ETA_TOKEN_URLS

	settings = get_eta_receipt_branch_settings(branch)
	token_url = ETA_TOKEN_URLS.get(creds["environment"], ETA_TOKEN_URLS["preprod"])
	try:
		state = exchange_eta_token(
			client_id=creds["client_id"],
			client_secret=creds["client_secret"],
			environment=creds["environment"],
			pos_headers=creds.get("pos_headers"),
		)
		return {
			"ok": True,
			"branch": branch,
			"environment": creds["environment"],
			"token_url": token_url,
			"api_base_url": settings.eta_base_url,
			"pos_serial": settings.device_serial_number,
			"expires_in": state.get("expires_in"),
			"message": _("ETA production authentication successful.") if creds["environment"] == "prod" else _("ETA authentication successful."),
		}
	except Exception as exc:
		err_text = str(exc)
		checklist = [
			_("1. On invoicing.eta.gov.eg register POS device with serial {0} (exact match).").format(
				settings.device_serial_number or ""
			),
			_("2. Use Client ID/Secret created for that POS device (not B2B e-Invoice credentials)."),
			_("3. If ETA gave a Pre-Shared Key, paste it in Branch → POS Pre-Shared Key."),
			_("4. POS OS Version = windows for production (do not use os in prod)."),
			_("5. Taxpayer profile must allow e-Receipt (B2C / receipt tag on ETA)."),
		]
		if "unauthorized_client" in err_text.lower():
			summary = _(
				"ETA accepts Client ID/Secret but rejects this POS (unauthorized_client). "
				"Use credentials created for POS serial {0} on invoicing.eta.gov.eg — not B2B e-Invoice credentials."
			).format(settings.device_serial_number or "")
		elif "invalid_client" in err_text.lower():
			summary = _("Wrong Client ID/Secret or wrong environment (preprod vs prod).")
		else:
			summary = _("ETA authentication failed.")
		return {
			"ok": False,
			"branch": branch,
			"environment": creds.get("environment"),
			"token_url": token_url,
			"api_base_url": settings.eta_base_url,
			"pos_serial": settings.device_serial_number,
			"pos_os_version": (creds.get("pos_headers") or {}).get("pososversion"),
			"pos_model_framework": settings.pos_model_framework,
			"has_preshared_key": bool((creds.get("pos_headers") or {}).get("presharedkey")),
			"client_id_prefix": (creds.get("client_id") or "")[:8],
			"error": err_text,
			"summary": summary,
			"checklist": checklist,
			"message": summary,
		}


@frappe.whitelist()
def prepare_ereceipt(sales_invoice: str) -> dict[str, Any]:
	"""Create/update submission and prepare (sign / UUID) without sending to ETA."""
	from omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission import sign_submission

	doc = frappe.get_doc("Sales Invoice", sales_invoice)
	if doc.docstatus != 1:
		frappe.throw(_("Sales Invoice must be submitted."), title=_("E-Receipt"))
	ensure_sales_invoice_eta_billing(doc, required=ETA_BILLING_ERECEIPT)

	sub_name = _submission_name_for_invoice(sales_invoice)
	out = sign_submission(sub_name)
	return {"sales_invoice": sales_invoice, "submission": sub_name, **out}


@frappe.whitelist()
def send_ereceipt(sales_invoice: str, force: int = 0) -> dict[str, Any]:
	"""Prepare and send one e-receipt to ETA immediately."""
	from omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission import (
		send_submission_to_eta,
	)

	doc = frappe.get_doc("Sales Invoice", sales_invoice)
	if doc.docstatus != 1:
		frappe.throw(_("Sales Invoice must be submitted."), title=_("E-Receipt"))
	ensure_sales_invoice_eta_billing(doc, required=ETA_BILLING_ERECEIPT)

	sub_name = _submission_name_for_invoice(sales_invoice)
	sub = frappe.get_doc("E Invoice Submission", sub_name)
	from omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission import (
		_recover_ereceipt_from_hub_queue,
	)

	_recover_ereceipt_from_hub_queue(sub)
	sub.reload()
	if sub.status == "Completed" and not int(force or 0):
		frappe.throw(
			_("This receipt was already accepted by ETA. Use force=1 only to resubmit after a rejection."),
			title=_("E-Receipt"),
		)
	if sub.status == "Completed" and int(force or 0):
		sub.status = "Failed"
		sub.save(ignore_permissions=True)
	# send_submission_to_eta signs when Draft/Failed; skips re-sign when already Signed
	out = send_submission_to_eta(sub_name)
	sub = frappe.get_doc("E Invoice Submission", sub_name)
	sub.reload()
	return {
		"sales_invoice": sales_invoice,
		"submission": sub_name,
		"ok": out.get("ok"),
		"status": sub.status,
		"uuid": sub.eta_uuid,
		"provider_reference": sub.provider_reference,
		"message": sub.integration_message,
		"error_code": sub.eta_error_code,
	}


@frappe.whitelist()
def bulk_prepare_ereceipts(sales_invoices) -> list[dict[str, Any]]:
	names = _parse_names(sales_invoices)
	results: list[dict[str, Any]] = []
	for name in names:
		try:
			row = prepare_ereceipt(name)
			results.append({"sales_invoice": name, "ok": True, **row})
		except Exception as exc:
			frappe.log_error(message=frappe.get_traceback(), title=f"E-Receipt prepare failed: {name}")
			results.append({"sales_invoice": name, "ok": False, "error": str(exc)})
	return results


@frappe.whitelist()
def bulk_send_ereceipts(sales_invoices) -> list[dict[str, Any]]:
	names = _parse_names(sales_invoices)
	results: list[dict[str, Any]] = []
	for name in names:
		try:
			row = send_ereceipt(name)
			results.append({"sales_invoice": name, "ok": bool(row.get("ok")), **row})
		except Exception as exc:
			frappe.log_error(message=frappe.get_traceback(), title=f"E-Receipt send failed: {name}")
			results.append({"sales_invoice": name, "ok": False, "error": str(exc)})
	return results


@frappe.whitelist()
def get_review_summary(sales_invoices) -> list[dict[str, Any]]:
	"""Lightweight rows for bulk review dialog before send."""
	names = _parse_names(sales_invoices)
	if not names:
		return []
	subs = _latest_submissions(names)
	rows: list[dict[str, Any]] = []
	for name in names:
		if not frappe.db.exists("Sales Invoice", name):
			continue
		inv = frappe.db.get_value(
			"Sales Invoice",
			name,
			["grand_total", "currency", "customer", "branch", "docstatus"],
			as_dict=True,
		)
		sub = subs.get(name)
		rows.append(
			{
				"sales_invoice": name,
				"grand_total": inv.grand_total,
				"currency": inv.currency,
				"customer": inv.customer,
				"branch": inv.branch,
				"docstatus": inv.docstatus,
				"submission": sub.name if sub else "",
				"eta_status": sub.status if sub else "Not Registered",
				"eta_uuid": sub.eta_uuid if sub else "",
			}
		)
	return rows
