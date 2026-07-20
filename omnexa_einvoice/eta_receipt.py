# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Egypt ETA e-Receipt: document build, ITIDA UUID, validation (aligned with Temp-ETR / ETA SDK)."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import frappe
from frappe import _

ETA_TOKEN_URLS = {
	"preprod": "https://id.preprod.eta.gov.eg/connect/token",
	"prod": "https://id.eta.gov.eg/connect/token",
}
ETA_DEFAULT_API_BASE = {
	"preprod": "https://api.preprod.invoicing.eta.gov.eg",
	"prod": "https://api.invoicing.eta.gov.eg",
}


class ETAReceiptValidationError(frappe.ValidationError):
	def __init__(self, message: str, code: str = "RECEIPT_VALIDATION_ERROR"):
		super().__init__(message)
		self.eta_error_code = code


def serialize_eta(data: Any) -> str:
	"""ITIDA canonical serialization (matches Temp-ETR / EtaReceiptService.php)."""
	serialized = ""
	if isinstance(data, dict):
		for key, value in data.items():
			serialized += '"' + str(key).upper() + '"'
			if isinstance(value, list):
				for item in value:
					serialized += '"' + str(key).upper() + '"'
					serialized += serialize_eta(item)
			elif isinstance(value, dict):
				serialized += serialize_eta(value)
			else:
				serialized += '"' + str(value) + '"'
	elif isinstance(data, list):
		for item in data:
			serialized += serialize_eta(item)
	return serialized


def _uuid_via_chilkat(receipt_copy: dict) -> str | None:
	try:
		import chilkat2

		json_obj = chilkat2.JsonObject()
		json_obj.Load(json.dumps(receipt_copy, ensure_ascii=False))
		json_obj.UpdateString("header.uuid", "")
		json_obj.EmitCompact = True
		json_document = json_obj.Emit()
		sb = chilkat2.StringBuilder()
		sb.Append(json_document)
		sb.Encode("itida", "utf-8")
		return sb.GetHash("sha256", "hex_lower", "utf-8")
	except Exception:
		return None


def generate_receipt_uuid(receipt_data: dict) -> str:
	"""SHA256 hex (64 chars) after ITIDA canonicalization; uuid must be empty in source."""
	receipt_copy = json.loads(json.dumps(receipt_data, ensure_ascii=False))
	receipt_copy.setdefault("header", {})["uuid"] = ""

	uuid_hash = _uuid_via_chilkat(receipt_copy)
	if uuid_hash and len(uuid_hash) == 64:
		return uuid_hash

	canonical_string = serialize_eta(receipt_copy)
	return hashlib.sha256(canonical_string.encode("utf-8")).hexdigest()


def _q5(value) -> float:
	return float(Decimal(str(value or 0)).quantize(Decimal("0.00000"), rounding=ROUND_HALF_UP))


def _q2_rate(value) -> float:
	return float(Decimal(str(value or 0)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP))


def get_eta_company_settings(company: str, branch: str | None = None) -> frappe._dict:
	"""Deprecated alias — use get_eta_branch_settings from branch_eta."""
	from omnexa_einvoice.branch_eta import get_eta_branch_settings, resolve_branch_for_document

	if branch:
		return get_eta_branch_settings(branch)
	doc = frappe._dict({"company": company})
	resolved = resolve_branch_for_document(doc)
	if not resolved:
		frappe.throw(_("No branch found for company {0}. Configure Branch → Egypt ETA.").format(company))
	return get_eta_branch_settings(resolved)


def _datetime_issued_utc(doc) -> str:
	posting_date = doc.get("posting_date")
	posting_time = doc.get("posting_time") or "00:00:00"
	if isinstance(posting_date, datetime):
		issued_dt = posting_date
	elif posting_date:
		try:
			issued_dt = datetime.strptime(f"{posting_date} {posting_time}", "%Y-%m-%d %H:%M:%S")
		except ValueError:
			issued_dt = datetime.strptime(str(posting_date), "%Y-%m-%d")
	else:
		issued_dt = datetime.now()
	if issued_dt.tzinfo is None:
		issued_dt = issued_dt.replace(tzinfo=timezone.utc)
	else:
		issued_dt = issued_dt.astimezone(timezone.utc)
	return issued_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _line_net_amount(row) -> float:
	qty = float(row.get("qty") or 0)
	rate = float(row.get("rate") or 0)
	return float(row.get("amount") or row.get("net_amount") or (qty * rate))


def _resolve_line_tax(row, source_doc) -> tuple[float, float]:
	"""Tax from Omnexa Tax Rule (Temp-ETR Rule42T1: amount = netSale * rate / 100)."""
	from frappe.utils import flt

	line_net = _line_net_amount(row)
	tax_rate = 0.0
	tax_amount = 0.0

	rule_name = (row.get("tax_rule") or source_doc.get("default_tax_rule") or "").strip()
	if rule_name and frappe.db.exists("Tax Rule", rule_name):
		rule = frappe.get_cached_doc("Tax Rule", rule_name)
		if (rule.tax_type or "").strip() == "standard" and flt(rule.rate):
			tax_rate = float(rule.rate)
			tax_amount = line_net * tax_rate / 100.0
		return tax_amount, tax_rate

	# ERPNext-style tax columns when present (legacy / imported data)
	tax_amt = float(row.get("item_tax_amount") or row.get("tax_amount") or 0)
	if row.get("item_tax_rate"):
		try:
			rates = json.loads(row.item_tax_rate) if isinstance(row.item_tax_rate, str) else row.item_tax_rate
			if isinstance(rates, dict) and rates:
				tax_rate = float(next(iter(rates.values())))
		except Exception:
			tax_rate = 0.0
	if not tax_amt and tax_rate:
		tax_amount = line_net * tax_rate / 100.0
	elif tax_amt:
		tax_amount = tax_amt
		if line_net and not tax_rate:
			tax_rate = round(tax_amount / line_net * 100.0, 2)

	return tax_amount, tax_rate


def _expected_t1_amount(net_sale: float, rate: float) -> float:
	return _q5(net_sale * float(rate or 0) / 100.0)


def _clean_item_description(name: str, counter: int) -> str:
	text = (name or "").strip()
	if not text or any(ord(c) > 127 for c in text):
		return f"Item_{counter}"
	return text[:500]


def _resolve_buyer(source_doc) -> dict[str, Any]:
	"""Buyer block — type P (person) or B (business) when Customer has tax_id (Temp-ETR)."""
	name = (source_doc.get("customer_name") or source_doc.get("customer") or "Cash Customer").strip()
	customer = (source_doc.get("customer") or "").strip()
	tax_id = ""
	if customer and frappe.db.exists("Customer", customer):
		tax_id = (frappe.db.get_value("Customer", customer, "tax_id") or "").strip()
	tax_digits = re.sub(r"\D", "", tax_id)
	if len(tax_digits) >= 9:
		return {"type": "B", "id": tax_digits, "name": name}
	return {"type": "P", "name": name}


def encode_eta_receipt_submission(document: dict) -> bytes:
	"""POST body like PowerBuilder: ``{\"receipts\":[`` + compact JSON + ``]}``."""
	try:
		import chilkat2

		json_obj = chilkat2.JsonObject()
		json_obj.Load(json.dumps(document, ensure_ascii=False))
		json_obj.EmitCompact = True
		receipt_json_string = json_obj.Emit()
	except Exception:
		receipt_json_string = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
	return ('{"receipts":[' + receipt_json_string + "]}").encode("utf-8")


def ensure_receipt_uuid(document: dict) -> dict:
	"""Regenerate UUID when missing or wrong length (Temp-ETR send_to_eta guard)."""
	uuid_val = (document.get("header") or {}).get("uuid") or ""
	if re.fullmatch(r"[a-f0-9]{64}", uuid_val):
		return document
	document = json.loads(json.dumps(document, ensure_ascii=False))
	document.setdefault("header", {})["uuid"] = ""
	document["header"]["uuid"] = generate_receipt_uuid(document)
	return document


def build_eta_receipt_document(source_doc, branch: str | None = None) -> dict:
	"""Build full ETA receipt JSON from POS Invoice or POS-mode Sales Invoice."""
	from omnexa_einvoice.branch_eta import get_eta_receipt_branch_settings, resolve_branch_for_document

	if not branch:
		branch = resolve_branch_for_document(source_doc)
	if not branch:
		frappe.throw(
			_("Select a Branch on the invoice, or set a default branch for the user."),
			title=_("ETA Receipt"),
		)
	settings = get_eta_receipt_branch_settings(branch)
	if not settings.rin:
		frappe.throw(
			_("Taxpayer RIN is required on Branch {0} (Egypt ETA tab).").format(branch),
			title=_("ETA Receipt"),
		)
	if not settings.device_serial_number:
		frappe.throw(
			_("POS Device Serial is required on Branch {0} (Egypt ETA tab).").format(branch),
			title=_("ETA Receipt"),
		)

	receipt_number = str(source_doc.name)

	document: dict[str, Any] = {
		"header": {
			"dateTimeIssued": _datetime_issued_utc(source_doc),
			"receiptNumber": receipt_number,
			"uuid": "",
			"previousUUID": "",
			"referenceOldUUID": "",
			"currency": source_doc.get("currency") or "EGP",
			"exchangeRate": 0,
			"sOrderNameCode": "sOrderNameCode",
			"orderdeliveryMode": "FC",
		},
		"documentType": {"receiptType": "s", "typeVersion": "1.2"},
		"seller": {
			"rin": settings.rin,
			"companyTradeName": settings.company_trade_name,
			"branchCode": settings.branch_code,
			"branchAddress": settings.address,
			"deviceSerialNumber": settings.device_serial_number,
			"syndicateLicenseNumber": "",
			"activityCode": settings.activity_code,
		},
		"buyer": _resolve_buyer(source_doc),
		"itemData": [],
		"taxTotals": [],
		"extraReceiptDiscountData": [
			{"amount": 0.0, "description": "Receipt Level Discount", "rate": 0.0},
		],
		"totalCommercialDiscount": 0.0,
		"totalItemsDiscount": 0.0,
		"feesAmount": 0.0,
		"adjustment": 0.0,
		"paymentMethod": "C",
	}

	tax_groups: dict[str, float] = {}
	total_tax = 0.0
	net_total = 0.0
	item_counter = 0
	rin_clean = settings.rin.replace("-", "")

	for row in source_doc.get("items") or []:
		item_counter += 1
		qty = float(row.get("qty") or 0)
		if qty <= 0:
			continue
		unit_price = float(row.get("rate") or 0)
		line_net = _line_net_amount(row)
		tax_amount, tax_rate = _resolve_line_tax(row, source_doc)
		# Rule42T1: T1 amount must match netSale * rate / 100 (Temp-ETR)
		net_f = _q5(line_net)
		tax_f = _expected_t1_amount(net_f, tax_rate)
		total_f = _q5(net_f + tax_f)

		qty_f = _q5(qty)
		unit_f = _q5(unit_price)

		item_code_raw = (row.get("item_code") or f"{item_counter:04d}").strip()
		item_code = f"EG-{rin_clean}-{item_code_raw}"

		document["itemData"].append(
			{
				"internalCode": str(item_counter),
				"description": _clean_item_description(row.get("item_name") or row.get("description"), item_counter),
				"itemType": "EGS",
				"itemCode": item_code,
				"unitType": (row.get("uom") or row.get("stock_uom") or "EA")[:10],
				"quantity": qty_f,
				"unitPrice": unit_f,
				"netSale": net_f,
				"totalSale": net_f,
				"total": total_f,
				"commercialDiscountData": [{"amount": 0.0, "description": "XYZ"}],
				"itemDiscountData": [
					{"amount": 0.0, "description": "ABC"},
					{"amount": 0.0, "description": "XYZ"},
				],
				"valueDifference": 0.0,
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

		rate_key = str(_q2_rate(tax_rate))
		tax_groups[rate_key] = tax_groups.get(rate_key, 0.0) + tax_f
		total_tax += tax_f
		net_total += net_f

	if not document["itemData"]:
		frappe.throw(_("At least one receipt line item is required."), title=_("ETA Receipt"))

	# Single T1 total (Temp-ETR merges by taxType)
	document["taxTotals"].append({"taxType": "T1", "amount": _q5(total_tax)})

	net_amount = _q5(net_total)
	total_amount = _q5(sum(float(item["total"]) for item in document["itemData"]))
	document["totalSales"] = net_amount
	document["netAmount"] = net_amount
	document["totalAmount"] = total_amount

	receipt_uuid = generate_receipt_uuid(document)
	document["header"]["uuid"] = receipt_uuid
	return document


def validate_receipt_document(document: dict, *, strict_datetime: bool = True) -> None:
	"""Hard-stop validation before ETA submission."""
	doc_type = document.get("documentType")
	if not isinstance(doc_type, dict) or doc_type.get("receiptType") != "s":
		raise ETAReceiptValidationError(_("Receipt documentType.receiptType must be 's'."), "INVALID_RECEIPT_DOCUMENT_TYPE")

	dt_issued = (document.get("header") or {}).get("dateTimeIssued")
	if not dt_issued:
		raise ETAReceiptValidationError(_("header.dateTimeIssued is required."), "MISSING_RECEIPT_DATETIME")

	if strict_datetime:
		try:
			dt_str = str(dt_issued).rstrip("Z")
			issued_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
			if issued_dt.tzinfo is None:
				issued_dt = issued_dt.replace(tzinfo=timezone.utc)
			else:
				issued_dt = issued_dt.astimezone(timezone.utc)
			diff = abs((datetime.now(timezone.utc) - issued_dt).total_seconds())
			if diff > 3600:
				raise ETAReceiptValidationError(
					_("Receipt dateTimeIssued must be within one hour of current UTC time."),
					"RECEIPT_DATETIME_OUT_OF_RANGE",
				)
		except ValueError as exc:
			raise ETAReceiptValidationError(_("Invalid dateTimeIssued format."), "INVALID_RECEIPT_DATETIME_FORMAT") from exc

	uuid_val = (document.get("header") or {}).get("uuid") or ""
	if not re.fullmatch(r"[a-f0-9]{64}", uuid_val):
		raise ETAReceiptValidationError(_("Receipt UUID must be a 64-character lowercase SHA256 hex string."), "INVALID_RECEIPT_UUID")

	required_paths = [
		"header.receiptNumber",
		"seller.rin",
		"seller.companyTradeName",
		"seller.deviceSerialNumber",
		"buyer.name",
		"totalSales",
		"netAmount",
		"totalAmount",
	]
	for path in required_paths:
		parts = path.split(".")
		cur: Any = document
		for part in parts:
			if not isinstance(cur, dict) or part not in cur:
				raise ETAReceiptValidationError(
					_("Required receipt field missing: {0}").format(path), "MISSING_RECEIPT_REQUIRED_FIELD"
				)
			cur = cur[part]
		if isinstance(cur, str) and not cur.strip():
			raise ETAReceiptValidationError(
				_("Required receipt field empty: {0}").format(path), "MISSING_RECEIPT_REQUIRED_FIELD"
			)

	if not document.get("itemData"):
		raise ETAReceiptValidationError(_("Receipt must contain at least one item."), "EMPTY_RECEIPT_ITEMS")

	total_sales = float(document.get("totalSales", 0))
	total_amount = float(document.get("totalAmount", 0))
	tax_sum = sum(float(t.get("amount", 0)) for t in document.get("taxTotals", []))
	expected = total_sales + tax_sum
	if abs(expected - total_amount) > 0.01:
		raise ETAReceiptValidationError(
			_("Receipt totals mismatch: expected {0}, got {1}.").format(expected, total_amount),
			"RECEIPT_TOTAL_MISMATCH",
		)

	for idx, item in enumerate(document.get("itemData") or [], start=1):
		net_sale = float(item.get("netSale", 0))
		line_total = float(item.get("total", 0))
		t1_sum = 0.0
		for tax in item.get("taxableItems") or []:
			if tax.get("taxType") != "T1":
				continue
			rate = float(tax.get("rate", 0))
			amount = float(tax.get("amount", 0))
			t1_sum += amount
			expected_tax = _expected_t1_amount(net_sale, rate)
			if abs(amount - expected_tax) > 0.0001:
				raise ETAReceiptValidationError(
					_("Line {0}: T1 tax amount {1} does not match netSale × rate ({2}).").format(
						idx, amount, expected_tax
					),
					"RULE42T1_TAX_AMOUNT",
				)
		if abs(line_total - (net_sale + t1_sum)) > 0.0001:
			raise ETAReceiptValidationError(
				_("Line {0}: total must equal netSale + T1 amount.").format(idx),
				"RECEIPT_LINE_TOTAL_MISMATCH",
			)


def refresh_receipt_datetime(document: dict) -> dict:
	"""Set dateTimeIssued to now UTC and regenerate UUID (call immediately before send)."""
	document = json.loads(json.dumps(document, ensure_ascii=False))
	document.setdefault("header", {})["dateTimeIssued"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
	document["header"]["uuid"] = ""
	document["header"]["uuid"] = generate_receipt_uuid(document)
	return document


def parse_receipt_submission_response(response_body: dict, http_status: int) -> dict[str, Any]:
	"""Normalize ETA receipt submission API response (Temp-ETR uses acceptedDocuments)."""
	raw_text = str(response_body.get("raw") or "")
	if raw_text and (
		"<html>" in raw_text.lower()
		or "request rejected" in raw_text.lower()
		or "request was rejected" in raw_text.lower()
	):
		return {
			"ok": False,
			"submission_id": "",
			"authority_uuid": "",
			"message": _("ETA request blocked (firewall/WAF). Try again from an allowed network."),
			"error_code": "ETA_WAF_BLOCKED",
			"accepted_count": 0,
			"rejected_count": 0,
		}

	accepted = (
		response_body.get("acceptedReceipts")
		or response_body.get("acceptedDocuments")
		or []
	)
	rejected = (
		response_body.get("rejectedReceipts")
		or response_body.get("rejectedDocuments")
		or []
	)
	submission_id = response_body.get("submissionId") or response_body.get("id") or ""
	header = response_body.get("header") if isinstance(response_body.get("header"), dict) else {}
	header_ok = str(header.get("statusCode") or header.get("code") or "").lower() == "success"

	uuid = ""
	if accepted:
		first = accepted[0] if isinstance(accepted[0], dict) else {}
		uuid = first.get("uuid") or first.get("receiptUUID") or ""

	message = _("Receipt accepted by ETA.")
	ok = False
	if rejected and not accepted:
		ok = False
		first_rej = rejected[0] if isinstance(rejected[0], dict) else {}
		uuid = first_rej.get("uuid") or uuid
		errs = first_rej.get("error") or first_rej.get("errors") or first_rej.get("message")
		message = str(errs) if errs else _("Receipt rejected by ETA.")
	elif http_status >= 300:
		ok = False
		message = response_body.get("message") or response_body.get("error") or _("ETA request failed.")
	elif accepted or submission_id or header_ok:
		ok = True
		if not uuid and submission_id:
			uuid = submission_id

	return {
		"ok": ok,
		"submission_id": str(submission_id)[:140],
		"authority_uuid": str(uuid)[:140],
		"message": str(message)[:140],
		"error_code": str(response_body.get("errorCode") or header.get("code") or "")[:140],
		"accepted_count": len(accepted),
		"rejected_count": len(rejected),
	}
