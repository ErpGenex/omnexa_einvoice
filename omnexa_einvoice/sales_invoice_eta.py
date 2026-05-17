# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Sales Invoice ETA billing type: Regular, E-Invoice, or E-Receipt."""

from __future__ import annotations

import frappe
from frappe import _

ETA_BILLING_REGULAR = "Regular"
ETA_BILLING_EINVOICE = "E-Invoice"
ETA_BILLING_ERECEIPT = "E-Receipt"

ETA_BILLING_TYPES = (ETA_BILLING_REGULAR, ETA_BILLING_EINVOICE, ETA_BILLING_ERECEIPT)

# Legacy/corrupt Select values (label|value stored as one string).
_ETA_BILLING_ALIASES = {
	"regular": ETA_BILLING_REGULAR,
	"e-invoice": ETA_BILLING_EINVOICE,
	"e-receipt": ETA_BILLING_ERECEIPT,
	"فاتورة عادية": ETA_BILLING_REGULAR,
	"فاتورة إلكترونية": ETA_BILLING_EINVOICE,
	"إيصال إلكتروني": ETA_BILLING_ERECEIPT,
}


def normalize_eta_billing_type(raw: str | None) -> str:
	"""Map stored Select value to canonical Regular / E-Invoice / E-Receipt."""
	value = (raw or "").strip()
	if not value:
		return ETA_BILLING_REGULAR
	if value in ETA_BILLING_TYPES:
		return value
	if "|" in value:
		value = value.split("|")[-1].strip()
		if value in ETA_BILLING_TYPES:
			return value
	lower = value.lower()
	if lower in _ETA_BILLING_ALIASES:
		return _ETA_BILLING_ALIASES[lower]
	for key, canonical in _ETA_BILLING_ALIASES.items():
		if key in value:
			return canonical
	if "E-Receipt" in value or "إيصال" in value:
		return ETA_BILLING_ERECEIPT
	if "E-Invoice" in value or "إلكترونية" in value:
		return ETA_BILLING_EINVOICE
	return ETA_BILLING_REGULAR


def sales_invoice_has_billing_type_field() -> bool:
	return bool(frappe.get_meta("Sales Invoice").has_field("eta_billing_type"))


def get_eta_billing_type(doc) -> str:
	"""Return Regular, E-Invoice, or E-Receipt for a Sales Invoice document."""
	if doc.doctype != "Sales Invoice":
		return ETA_BILLING_REGULAR
	if sales_invoice_has_billing_type_field():
		return normalize_eta_billing_type(doc.get("eta_billing_type"))
	# Legacy ERPNext-style POS flag when custom field is absent
	if int(doc.get("is_pos") or 0):
		return ETA_BILLING_ERECEIPT
	return ETA_BILLING_REGULAR


def sales_invoice_is_eta_billing(doc) -> bool:
	return get_eta_billing_type(doc) in (ETA_BILLING_EINVOICE, ETA_BILLING_ERECEIPT)


def eta_billing_type_required_message() -> str:
	return _(
		"This Sales Invoice has billing type «Regular». Open the invoice, set "
		"**Billing Type** (section Egypt ETA) to «Electronic Invoice» or «Electronic Receipt», save, then retry."
	)


def ensure_sales_invoice_eta_billing(doc, required: str | None = None) -> str:
	"""Ensure SI has an ETA billing type; optionally set E-Receipt from console workflows."""
	billing = get_eta_billing_type(doc)
	if required == ETA_BILLING_ERECEIPT and billing == ETA_BILLING_REGULAR:
		if doc.meta.has_field("eta_billing_type") and doc.docstatus == 1:
			doc.eta_billing_type = ETA_BILLING_ERECEIPT
			doc.save(ignore_permissions=True)
			return ETA_BILLING_ERECEIPT
	if required and billing != required:
		if billing == ETA_BILLING_REGULAR:
			frappe.throw(eta_billing_type_required_message(), title=_("ETA"))
		if required == ETA_BILLING_ERECEIPT and billing == ETA_BILLING_EINVOICE:
			frappe.throw(
				_("This invoice is Electronic Invoice. Use E-Invoice submission, not E-Receipt."),
				title=_("ETA"),
			)
		if required == ETA_BILLING_EINVOICE and billing == ETA_BILLING_ERECEIPT:
			frappe.throw(
				_("This invoice is Electronic Receipt. Use E-Receipt submission, not E-Invoice."),
				title=_("ETA"),
			)
	if not sales_invoice_is_eta_billing(doc):
		frappe.throw(eta_billing_type_required_message(), title=_("ETA"))
	return billing


def resolve_submission_kind_for_sales_invoice(doc) -> str:
	"""Map Sales Invoice billing type to E Invoice Submission submission_kind."""
	billing = ensure_sales_invoice_eta_billing(doc)
	if billing == ETA_BILLING_ERECEIPT:
		return "E-Receipt"
	return "E-Invoice"


def normalize_sales_invoice_eta_billing_type_field(doc, method=None) -> None:
	"""Persist canonical Select value (fixes label|value corruption)."""
	if doc.doctype != "Sales Invoice" or not sales_invoice_has_billing_type_field():
		return
	raw = doc.get("eta_billing_type")
	if not raw:
		return
	normalized = normalize_eta_billing_type(raw)
	if normalized != raw:
		doc.eta_billing_type = normalized


def validate_sales_invoice_eta_billing_type(doc, method=None) -> None:
	if doc.doctype != "Sales Invoice" or doc.get("is_return"):
		return
	normalize_sales_invoice_eta_billing_type_field(doc)
	billing = get_eta_billing_type(doc)
	if billing == ETA_BILLING_REGULAR:
		return
	branch = None
	try:
		from omnexa_einvoice.branch_eta import (
			branch_einvoice_enabled,
			branch_ereceipt_enabled,
			resolve_branch_for_document,
		)

		branch = resolve_branch_for_document(doc)
	except ImportError:
		return
	if not branch:
		frappe.throw(_("Branch is required for ETA billing types."), title=_("ETA"))
	if billing == ETA_BILLING_ERECEIPT and not branch_ereceipt_enabled(branch):
		frappe.throw(
			_("E-Receipt is not enabled on Branch {0}. Enable it under Branch → Egypt ETA.").format(branch),
			title=_("E-Receipt"),
		)
	if billing == ETA_BILLING_EINVOICE and not branch_einvoice_enabled(branch):
		frappe.throw(
			_("E-Invoice is not enabled on Branch {0}. Enable it under Branch → Egypt ETA.").format(branch),
			title=_("E-Invoice"),
		)
