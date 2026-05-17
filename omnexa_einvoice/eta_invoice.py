# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Egypt ETA e-Invoice: document build, canonical JSON, validation (Temp-ETR / ETA SDK)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.eta_receipt import (
	_expected_t1_amount,
	_line_net_amount,
	_q2_rate,
	_q5,
	_resolve_line_tax,
)


class ETAInvoiceValidationError(frappe.ValidationError):
	def __init__(self, message: str, code: str = "INVOICE_VALIDATION_ERROR"):
		super().__init__(message)
		self.eta_error_code = code


def invoice_canonical_json(data: dict) -> str:
	"""Deterministic JSON for signing (Temp-ETR invoice_canonical_json)."""
	unsigned = json.loads(json.dumps(data, ensure_ascii=False))
	unsigned.pop("signatures", None)
	unsigned.pop("internalId", None)  # ETA schema uses internalID only
	return json.dumps(unsigned, separators=(",", ":"), ensure_ascii=False, sort_keys=True)


def eta_invoice_signature_block(signature_value: str) -> list[dict[str, str]]:
	"""ETA production schema expects signatureType (not type)."""
	return [{"signatureType": "I", "value": (signature_value or "").strip()}]


def sanitize_invoice_for_eta(document: dict) -> dict:
	"""Remove fields rejected by ETA (e.g. internalId alias)."""
	doc = json.loads(json.dumps(document, ensure_ascii=False))
	doc.pop("internalId", None)
	if "internalID" not in doc and doc.get("internalId"):
		doc["internalID"] = doc.pop("internalId")
	return doc


def _branch_invoice_context(branch: str) -> frappe._dict:
	from omnexa_einvoice.branch_eta import get_eta_invoice_branch_settings

	inv = get_eta_invoice_branch_settings(branch)
	row = frappe.db.get_value(
		"Branch",
		branch,
		[
			"branch_code",
			"branch_name",
			"eta_branch_code",
			"eta_company_trade_name",
			"eta_activity_code",
			"eta_address_country",
			"eta_address_governate",
			"eta_address_city",
			"eta_address_street",
			"eta_address_building_number",
			"eta_address_postal_code",
			"eta_address_floor",
			"eta_address_room",
			"eta_address_landmark",
			"eta_address_additional",
			"company",
		],
		as_dict=True,
	) or {}
	trade_name = (row.get("eta_company_trade_name") or row.get("branch_name") or "").strip()
	if not trade_name and row.get("company"):
		trade_name = frappe.db.get_value("Company", row.company, "company_name") or row.company
	return frappe._dict(
		{
			"rin": inv.rin,
			"trade_name": trade_name,
			"branch_code": (row.get("eta_branch_code") or row.get("branch_code") or "0").strip(),
			"activity_code": (row.get("eta_activity_code") or "6201").strip(),
			"address": {
				"branchID": (row.get("eta_branch_code") or row.get("branch_code") or "0").strip(),
				"country": (row.get("eta_address_country") or "EG").strip(),
				"governate": (row.get("eta_address_governate") or "Cairo").strip(),
				"regionCity": (row.get("eta_address_city") or "Cairo").strip(),
				"street": (row.get("eta_address_street") or "Main Street").strip(),
				"buildingNumber": (row.get("eta_address_building_number") or "1").strip(),
				"postalCode": (row.get("eta_address_postal_code") or "12345").strip(),
				"floor": (row.get("eta_address_floor") or "1").strip(),
				"room": (row.get("eta_address_room") or "1").strip(),
				"landmark": (row.get("eta_address_landmark") or "").strip(),
				"additionalInformation": (row.get("eta_address_additional") or "").strip(),
			},
		}
	)


def _resolve_receiver(source_doc) -> dict[str, Any]:
	name = (source_doc.get("customer_name") or source_doc.get("customer") or "Cash Customer").strip()
	customer = (source_doc.get("customer") or "").strip()
	tax_id = ""
	if customer and frappe.db.exists("Customer", customer):
		tax_id = re.sub(r"\D", "", frappe.db.get_value("Customer", customer, "tax_id") or "")
	receiver_type = "B" if len(tax_id) >= 9 else "P"
	receiver: dict[str, Any] = {
		"address": {
			"country": "EG",
			"governate": "",
			"regionCity": "",
			"street": "",
			"buildingNumber": "",
			"postalCode": "",
			"floor": "",
			"room": "",
			"landmark": "",
			"additionalInformation": "",
		},
		"type": receiver_type,
		"name": name,
	}
	if receiver_type == "B":
		receiver["id"] = tax_id
	else:
		receiver["id"] = ""
	return receiver


def build_eta_invoice_document(source_doc, branch: str | None = None) -> dict:
	"""Build full ETA e-Invoice JSON (issuer, receiver, invoiceLines, taxTotals)."""
	from omnexa_einvoice.branch_eta import resolve_branch_for_document

	if not branch:
		branch = resolve_branch_for_document(source_doc)
	if not branch:
		frappe.throw(_("Branch is required for e-Invoice."), title=_("E-Invoice"))

	ctx = _branch_invoice_context(branch)
	if not ctx.rin:
		frappe.throw(_("Taxpayer RIN is required on Branch (E-Invoice)."), title=_("E-Invoice"))

	rin_clean = str(ctx.rin).replace("-", "")
	invoice_lines: list[dict] = []
	tax_groups: dict[str, float] = {}
	total_sales = 0.0
	net_total = 0.0
	total_tax = 0.0
	line_idx = 0

	for row in source_doc.get("items") or []:
		qty = float(row.get("qty") or 0)
		if qty <= 0:
			continue
		line_idx += 1
		unit_price = float(row.get("rate") or 0)
		line_net = _line_net_amount(row)
		discount = 0.0
		line_sales = _q5(line_net + discount)
		tax_amount, tax_rate = _resolve_line_tax(row, source_doc)
		tax_f = _expected_t1_amount(line_sales, tax_rate)
		line_total = _q5(line_sales + tax_f)

		item_code_raw = (row.get("item_code") or f"{line_idx:04d}").strip()
		item_code = f"EG-{rin_clean}-{item_code_raw}"
		desc = (row.get("item_name") or row.get("description") or item_code_raw or f"Item_{line_idx}").strip()
		if not desc or any(ord(c) > 127 for c in desc):
			desc = f"Item_{line_idx}"

		invoice_lines.append(
			{
				"description": desc[:500],
				"itemType": "EGS",
				"itemCode": item_code,
				"unitType": (row.get("uom") or row.get("stock_uom") or "EA")[:10],
				"quantity": _q5(qty),
				"internalCode": str(line_idx),
				"salesTotal": line_sales,
				"netTotal": line_sales,
				"total": line_total,
				"valueDifference": 0.0,
				"totalTaxableFees": 0.0,
				"itemsDiscount": _q5(discount),
				"unitValue": {"currencySold": source_doc.get("currency") or "EGP", "amountEGP": _q5(unit_price)},
				"discount": {"rate": 0.0, "amount": _q5(discount)},
				"taxableItems": [
					{
						"taxType": "T1",
						"amount": tax_f,
						"subType": "V009",
						"rate": _q2_rate(tax_rate),
					}
				],
			}
		)
		total_sales += line_sales
		net_total += line_sales
		total_tax += tax_f
		rate_key = str(_q2_rate(tax_rate))
		tax_groups[rate_key] = tax_groups.get(rate_key, 0.0) + tax_f

	if not invoice_lines:
		frappe.throw(_("At least one invoice line is required."), title=_("E-Invoice"))

	tax_totals = [{"taxType": "T1", "amount": _q5(total_tax)}]
	total_amount = _q5(net_total + total_tax)

	return {
		"issuer": {
			"address": ctx.address,
			"type": "B",
			"id": str(ctx.rin).replace("-", ""),
			"name": ctx.trade_name,
		},
		"receiver": _resolve_receiver(source_doc),
		"documentType": "I",
		"documentTypeVersion": "1.0",
		"dateTimeIssued": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
		"taxpayerActivityCode": ctx.activity_code,
		"internalID": str(source_doc.name),
		"purchaseOrderReference": "",
		"purchaseOrderDescription": "",
		"salesOrderReference": "",
		"salesOrderDescription": "",
		"proformaInvoiceNumber": "",
		"payment": {
			"bankName": "",
			"bankAddress": "",
			"bankAccountNo": "",
			"bankAccountIBAN": "",
			"swiftCode": "",
			"terms": "C",
		},
		"delivery": {
			"approach": "",
			"packaging": "",
			"dateValidity": "",
			"exportPort": "",
			"grossWeight": 0,
		},
		"invoiceLines": invoice_lines,
		"totalDiscountAmount": 0.0,
		"totalSalesAmount": _q5(total_sales),
		"netAmount": _q5(net_total),
		"taxTotals": tax_totals,
		"totalAmount": total_amount,
		"extraDiscountAmount": 0.0,
		"totalItemsDiscountAmount": 0.0,
	}


def validate_invoice_document(document: dict, *, strict_datetime: bool = True) -> None:
	required_roots = ["issuer", "receiver", "invoiceLines", "taxTotals"]
	for key in required_roots:
		if key not in document:
			raise ETAInvoiceValidationError(
				_("Required invoice field missing: {0}").format(key), "MISSING_INVOICE_FIELD"
			)

	if not document.get("invoiceLines"):
		raise ETAInvoiceValidationError(_("Invoice must contain at least one line."), "EMPTY_INVOICE_LINES")

	if not (document.get("internalID") or "").strip():
		raise ETAInvoiceValidationError(_("internalID is required for ETA invoice."), "MISSING_INTERNAL_ID")
	if document.get("internalId") is not None:
		raise ETAInvoiceValidationError(
			_("Use internalID only; remove internalId from invoice JSON."), "INVALID_INTERNAL_ID_KEY"
		)

	sigs = document.get("signatures") or []
	if sigs and not (sigs[0].get("signatureType") or "").strip():
		raise ETAInvoiceValidationError(
			_("Invoice signature must use signatureType (not type)."), "INVALID_SIGNATURE_SHAPE"
		)

	dt_issued = document.get("dateTimeIssued")
	if not dt_issued:
		raise ETAInvoiceValidationError(_("dateTimeIssued is required."), "MISSING_INVOICE_DATETIME")

	if strict_datetime:
		try:
			dt_str = str(dt_issued).rstrip("Z")
			issued_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
			if issued_dt.tzinfo is None:
				issued_dt = issued_dt.replace(tzinfo=timezone.utc)
			else:
				issued_dt = issued_dt.astimezone(timezone.utc)
			if abs((datetime.now(timezone.utc) - issued_dt).total_seconds()) > 3600:
				raise ETAInvoiceValidationError(
					_("Invoice dateTimeIssued must be within one hour of current UTC time."),
					"INVOICE_DATETIME_OUT_OF_RANGE",
				)
		except ETAInvoiceValidationError:
			raise
		except ValueError as exc:
			raise ETAInvoiceValidationError(
				_("Invalid dateTimeIssued format."), "INVALID_INVOICE_DATETIME"
			) from exc

	net_amount = float(document.get("netAmount", 0))
	total_amount = float(document.get("totalAmount", 0))
	tax_sum = sum(float(t.get("amount", 0)) for t in document.get("taxTotals", []))
	if abs(net_amount + tax_sum - total_amount) > 0.01:
		raise ETAInvoiceValidationError(
			_("Invoice totals mismatch: net + tax = {0}, total = {1}.").format(
				net_amount + tax_sum, total_amount
			),
			"INVOICE_TOTAL_MISMATCH",
		)

	for idx, line in enumerate(document.get("invoiceLines") or [], start=1):
		net_line = float(line.get("netTotal", 0))
		line_total = float(line.get("total", 0))
		t1_sum = 0.0
		for tax in line.get("taxableItems") or []:
			if tax.get("taxType") != "T1":
				continue
			rate = float(tax.get("rate", 0))
			amount = float(tax.get("amount", 0))
			t1_sum += amount
			expected = _expected_t1_amount(net_line, rate)
			if abs(amount - expected) > 0.0001:
				raise ETAInvoiceValidationError(
					_("Line {0}: T1 amount {1} does not match net × rate ({2}).").format(
						idx, amount, expected
					),
					"RULE42T1_TAX_AMOUNT",
				)
		if abs(line_total - (net_line + t1_sum)) > 0.0001:
			raise ETAInvoiceValidationError(
				_("Line {0}: total must equal netTotal + T1 tax.").format(idx),
				"INVOICE_LINE_TOTAL_MISMATCH",
			)


def refresh_invoice_datetime(document: dict) -> dict:
	"""Update issue time before send; caller must re-sign afterward."""
	document = json.loads(json.dumps(document, ensure_ascii=False))
	document["dateTimeIssued"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
	return document


def parse_invoice_submission_response(response_body: dict, http_status: int) -> dict[str, Any]:
	"""Normalize ETA document submission API response."""
	raw_text = str(response_body.get("raw") or "")
	if raw_text and (
		"<html>" in raw_text.lower()
		or "request rejected" in raw_text.lower()
	):
		return {
			"ok": False,
			"submission_id": "",
			"authority_uuid": "",
			"message": _("ETA request blocked (firewall/WAF)."),
			"error_code": "ETA_WAF_BLOCKED",
			"accepted_count": 0,
			"rejected_count": 0,
		}

	accepted = (
		response_body.get("acceptedDocuments")
		or response_body.get("acceptedReceipts")
		or []
	)
	rejected = (
		response_body.get("rejectedDocuments")
		or response_body.get("rejectedReceipts")
		or []
	)
	submission_id = response_body.get("submissionId") or response_body.get("id") or ""
	header = response_body.get("header") if isinstance(response_body.get("header"), dict) else {}
	header_ok = str(header.get("statusCode") or header.get("code") or "").lower() == "success"

	uuid = ""
	if accepted:
		first = accepted[0] if isinstance(accepted[0], dict) else {}
		uuid = first.get("uuid") or first.get("documentUUID") or ""

	message = _("Invoice accepted by ETA.")
	ok = False
	if rejected and not accepted:
		ok = False
		first_rej = rejected[0] if isinstance(rejected[0], dict) else {}
		uuid = first_rej.get("uuid") or uuid
		err = first_rej.get("error") or {}
		if isinstance(err, dict):
			parts = [str(err.get("message") or "")]
			for detail in err.get("details") or []:
				if not isinstance(detail, dict):
					continue
				parts.append(
					str(detail.get("message") or "")
					+ " @ "
					+ str(detail.get("propertyPath") or detail.get("target") or "")
				)
			message = " — ".join(p for p in parts if p and p != "None") or _("Invoice rejected.")
		else:
			message = str(err or _("Invoice rejected by ETA."))
	elif http_status >= 300:
		ok = False
		err = response_body.get("error")
		message = (
			str(err)
			if err and not isinstance(err, dict)
			else response_body.get("message") or _("ETA request failed.")
		)
	elif accepted or submission_id or header_ok:
		ok = True

	return {
		"ok": ok,
		"submission_id": str(submission_id)[:140],
		"authority_uuid": str(uuid)[:140],
		"message": str(message)[:140],
		"error_code": str(response_body.get("errorCode") or header.get("code") or "")[:140],
		"accepted_count": len(accepted),
		"rejected_count": len(rejected),
	}


def build_usb_signing_test_document(branch: str) -> dict:
	"""Minimal valid ETA e-Invoice JSON for USB signing agent smoke-test (not submitted to ETA)."""
	branch = (branch or "").strip()
	ctx = _branch_invoice_context(branch)
	if not ctx.rin:
		frappe.throw(_("Taxpayer RIN is required on Branch (E-Invoice)."), title=_("USB Signing Test"))

	rin_clean = str(ctx.rin).replace("-", "")
	line_net = 100.0
	tax_rate = 14.0
	tax_amount = _expected_t1_amount(line_net, tax_rate)
	line_total = _q5(line_net + tax_amount)
	item_code = f"EG-{rin_clean}-TEST01"
	internal_id = f"OMNEXA-TEST-{branch}"[:50]

	invoice_lines = [
		{
			"description": "USB signing test line",
			"itemType": "EGS",
			"itemCode": item_code,
			"unitType": "EA",
			"quantity": 1.0,
			"internalCode": "1",
			"salesTotal": line_net,
			"netTotal": line_net,
			"total": line_total,
			"valueDifference": 0.0,
			"totalTaxableFees": 0.0,
			"itemsDiscount": 0.0,
			"unitValue": {"currencySold": "EGP", "amountEGP": line_net},
			"discount": {"rate": 0.0, "amount": 0.0},
			"taxableItems": [
				{
					"taxType": "T1",
					"amount": tax_amount,
					"subType": "V009",
					"rate": _q2_rate(tax_rate),
				}
			],
		}
	]

	return {
		"issuer": {
			"address": ctx.address,
			"type": "B",
			"id": rin_clean,
			"name": ctx.trade_name or branch,
		},
		"receiver": {
			"address": {
				"country": "EG",
				"governate": "",
				"regionCity": "",
				"street": "",
				"buildingNumber": "",
				"postalCode": "",
				"floor": "",
				"room": "",
				"landmark": "",
				"additionalInformation": "",
			},
			"type": "P",
			"id": "",
			"name": "USB Test Customer",
		},
		"documentType": "I",
		"documentTypeVersion": "1.0",
		"dateTimeIssued": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
		"taxpayerActivityCode": ctx.activity_code,
		"internalID": internal_id,
		"purchaseOrderReference": "",
		"purchaseOrderDescription": "",
		"salesOrderReference": "",
		"salesOrderDescription": "",
		"proformaInvoiceNumber": "",
		"payment": {
			"bankName": "",
			"bankAddress": "",
			"bankAccountNo": "",
			"bankAccountIBAN": "",
			"swiftCode": "",
			"terms": "C",
		},
		"delivery": {
			"approach": "",
			"packaging": "",
			"dateValidity": "",
			"exportPort": "",
			"grossWeight": 0,
		},
		"invoiceLines": invoice_lines,
		"totalDiscountAmount": 0.0,
		"totalSalesAmount": line_net,
		"netAmount": line_net,
		"taxTotals": [{"taxType": "T1", "amount": tax_amount}],
		"totalAmount": line_total,
		"extraDiscountAmount": 0.0,
		"totalItemsDiscountAmount": 0.0,
	}
