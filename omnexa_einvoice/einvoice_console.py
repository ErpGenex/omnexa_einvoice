# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Desk console: sign and send ETA e-invoices from Sales Invoices (USB agent or remote/HMAC)."""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate

from omnexa_einvoice.branch_eta import INVOICE_KIND, get_branch_eta_credentials, get_eta_invoice_branch_settings
from omnexa_einvoice.ereceipt_console import _match_eta_status, _parse_names
from omnexa_einvoice.sales_invoice_eta import (
	ETA_BILLING_EINVOICE,
	ensure_sales_invoice_eta_billing,
	normalize_eta_billing_type,
)


def _latest_einvoice_submissions(sales_invoice_names: list[str]) -> dict[str, frappe._dict]:
	if not sales_invoice_names:
		return {}
	rows = frappe.get_all(
		"E Invoice Submission",
		filters={
			"reference_doctype": "Sales Invoice",
			"reference_name": ["in", sales_invoice_names],
			"submission_kind": "E-Invoice",
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


def _submission_name_for_invoice(sales_invoice: str) -> str:
	from omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission import (
		ensure_submission_for_document,
	)

	return ensure_submission_for_document("Sales Invoice", sales_invoice)["name"]


def _require_submitted_si(sales_invoice: str):
	doc = frappe.get_doc("Sales Invoice", sales_invoice)
	if doc.docstatus != 1:
		frappe.throw(_("Sales Invoice must be submitted before e-invoice sign/send."), title=_("E-Invoice"))
	ensure_sales_invoice_eta_billing(doc, required=ETA_BILLING_EINVOICE)
	return doc


@frappe.whitelist()
def get_einvoice_queue(
	company: str | None = None,
	branch: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	eta_status: str | None = None,
	limit: int = 200,
	include_drafts: int = 1,
) -> list[dict[str, Any]]:
	"""Sales Invoices with billing type E-Invoice."""
	if not frappe.get_meta("Sales Invoice").has_field("eta_billing_type"):
		return []

	conditions = [
		"(si.eta_billing_type LIKE %(einv)s OR si.eta_billing_type = %(einv_exact)s)",
	]
	params: dict[str, Any] = {
		"einv": "%E-Invoice%",
		"einv_exact": ETA_BILLING_EINVOICE,
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
		WHERE {' AND '.join(conditions)}
		ORDER BY si.posting_date DESC, si.modified DESC
		LIMIT %(limit)s
		""",
		params,
		as_dict=True,
	)
	if not invoices:
		return []

	invoices = [
		inv for inv in invoices if normalize_eta_billing_type(inv.eta_billing_type) == ETA_BILLING_EINVOICE
	]
	if not invoices:
		return []

	customer_names: dict[str, str] = {}
	customers = {i.customer for i in invoices if i.customer}
	if customers:
		for row in frappe.get_all(
			"Customer",
			filters={"name": ["in", list(customers)]},
			fields=["name", "customer_name"],
		):
			customer_names[row.name] = row.customer_name

	from omnexa_einvoice.eta_invoice_signing import uses_browser_signing_agent

	subs = _latest_einvoice_submissions([i.name for i in invoices])
	branch_modes: dict[str, str] = {}
	rows: list[dict[str, Any]] = []
	for inv in invoices:
		sub = subs.get(inv.name)
		if not _match_eta_status(sub, (eta_status or "").strip()):
			continue
		br = inv.branch or ""
		if br and br not in branch_modes:
			try:
				branch_modes[br] = (get_eta_invoice_branch_settings(br).signer_mode or "").strip()
			except Exception:
				branch_modes[br] = ""
		signer_mode = branch_modes.get(br, "")
		browser_sign = uses_browser_signing_agent(br) if br else False
		eta_st = sub.status if sub else "Not Registered"
		can_sign = inv.docstatus == 1 and eta_st in ("", "Not Registered", "Draft", "Failed")
		can_send = inv.docstatus == 1 and eta_st == "Signed"
		docstatus_label = {0: _("Draft"), 1: _("Submitted"), 2: _("Cancelled")}.get(
			int(inv.docstatus or 0), ""
		)
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
				"eta_status": eta_st,
				"eta_uuid": (sub.eta_uuid or sub.authority_uuid) if sub else "",
				"provider_reference": sub.provider_reference if sub else "",
				"message": sub.integration_message if sub else "",
				"error_code": sub.eta_error_code if sub else "",
				"signer_mode": signer_mode,
				"browser_signing": browser_sign,
				"can_sign": can_sign,
				"can_send": can_send,
			}
		)
	return rows


@frappe.whitelist()
def preview_einvoice(sales_invoice: str, signed: int = 0) -> dict[str, Any]:
	"""Build or load ETA invoice JSON for review."""
	from omnexa_einvoice.branch_eta import resolve_branch_for_document
	from omnexa_einvoice.eta_einvoice_submission import build_unsigned_e_invoice_document

	doc = _require_submitted_si(sales_invoice)
	branch = resolve_branch_for_document(doc)
	if not branch:
		frappe.throw(_("Branch is required on the Sales Invoice."), title=_("E-Invoice"))

	sub_name = _submission_name_for_invoice(sales_invoice)
	if int(signed or 0):
		sub = frappe.get_doc("E Invoice Submission", sub_name)
		if sub.status not in ("Signed", "Completed") or not sub.result_data:
			frappe.throw(_("Invoice is not signed yet."), title=_("E-Invoice"))
		payload = json.loads(sub.result_data or "{}")
		document = payload.get("document") or payload
	else:
		document = build_unsigned_e_invoice_document(doc, branch)

	from omnexa_einvoice.eta_invoice_signing import uses_browser_signing_agent

	sub = frappe.get_doc("E Invoice Submission", sub_name)
	browser_sign = uses_browser_signing_agent(branch)
	eta_st = sub.status or "Not Registered"
	return {
		"sales_invoice": sales_invoice,
		"submission": sub_name,
		"branch": branch,
		"internal_id": document.get("internalID", ""),
		"signed": bool(int(signed or 0)),
		"document": document,
		"browser_signing": browser_sign,
		"can_sign": eta_st in ("", "Not Registered", "Draft", "Failed"),
		"can_send": eta_st == "Signed",
	}


@frappe.whitelist()
def test_eta_einvoice_connection(branch: str | None = None, company: str | None = None) -> dict[str, Any]:
	"""Test B2B e-Invoice OAuth token for branch credentials."""
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

	creds = get_branch_eta_credentials(branch, kind=INVOICE_KIND)
	settings = get_eta_invoice_branch_settings(branch)
	try:
		state = exchange_eta_token(
			client_id=creds["client_id"],
			client_secret=creds["client_secret"],
			environment=creds["environment"],
		)
		return {
			"ok": True,
			"branch": branch,
			"environment": creds["environment"],
			"api_base_url": settings.eta_base_url,
			"rin": settings.rin,
			"expires_in": state.get("expires_in"),
			"message": _("ETA e-Invoice authentication successful."),
		}
	except Exception as exc:
		return {
			"ok": False,
			"branch": branch,
			"environment": creds.get("environment"),
			"api_base_url": settings.eta_base_url,
			"error": str(exc),
			"message": _("ETA e-Invoice authentication failed."),
		}


@frappe.whitelist()
def sign_einvoice_server(sales_invoice: str) -> dict[str, Any]:
	"""Sign on server (remote/HMAC/windows_app) — not for USB token branches."""
	from omnexa_einvoice.eta_invoice_signing import uses_browser_signing_agent
	from omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission import sign_submission

	_require_submitted_si(sales_invoice)
	sub_name = _submission_name_for_invoice(sales_invoice)
	branch = frappe.db.get_value("E Invoice Submission", sub_name, "branch")
	if uses_browser_signing_agent(branch):
		frappe.throw(
			_(
				"This branch uses USB Signing Agent. Sign from this PC with the local agent running (browser flow)."
			),
			title=_("E-Invoice Signing"),
		)
	out = sign_submission(sub_name)
	sub = frappe.get_doc("E Invoice Submission", sub_name)
	return {
		"sales_invoice": sales_invoice,
		"submission": sub_name,
		"ok": True,
		"status": sub.status,
		"signer_method": out.get("signer_method"),
		"message": sub.integration_message,
	}


@frappe.whitelist()
def send_einvoice(sales_invoice: str, force: int = 0) -> dict[str, Any]:
	"""Send signed e-invoice to ETA (server-side; USB must sign in browser first)."""
	from omnexa_einvoice.eta_invoice_signing import uses_browser_signing_agent
	from omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission import (
		send_submission_to_eta,
	)

	_require_submitted_si(sales_invoice)
	sub_name = _submission_name_for_invoice(sales_invoice)
	sub = frappe.get_doc("E Invoice Submission", sub_name)
	branch = sub.branch
	if uses_browser_signing_agent(branch) and sub.status != "Signed":
		frappe.throw(
			_("Sign the invoice first (USB agent on Windows PC)."),
			title=_("E-Invoice"),
		)
	if sub.status == "Completed" and not int(force or 0):
		frappe.throw(
			_("Already accepted by ETA. Use force only to resubmit after rejection."),
			title=_("E-Invoice"),
		)
	if sub.status == "Completed" and int(force or 0):
		sub.status = "Failed"
		sub.save(ignore_permissions=True)

	out = send_submission_to_eta(sub_name)
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
def bulk_send_einvoices(sales_invoices) -> list[dict[str, Any]]:
	names = _parse_names(sales_invoices)
	results: list[dict[str, Any]] = []
	for name in names:
		try:
			row = send_einvoice(name)
			results.append({"sales_invoice": name, "ok": bool(row.get("ok")), **row})
		except Exception as exc:
			frappe.log_error(message=frappe.get_traceback(), title=f"E-Invoice send failed: {name}")
			results.append({"sales_invoice": name, "ok": False, "error": str(exc)})
	return results


@frappe.whitelist()
def get_review_summary(sales_invoices) -> list[dict[str, Any]]:
	names = _parse_names(sales_invoices)
	if not names:
		return []
	subs = _latest_einvoice_submissions(names)
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
				"eta_uuid": (sub.eta_uuid or sub.authority_uuid) if sub else "",
			}
		)
	return rows
