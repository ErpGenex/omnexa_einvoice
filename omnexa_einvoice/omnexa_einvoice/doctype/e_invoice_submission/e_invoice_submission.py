# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import subprocess

import frappe
from frappe import _
from frappe.model.document import Document
import requests

from omnexa_core.omnexa_core.integration_hub import IntegrationHubError, get_default_hub
from omnexa_einvoice.eta_integration import ensure_eta_access_token


class EInvoiceSubmission(Document):
	def validate(self):
		if not self.reference_doctype or not self.reference_name:
			frappe.throw(_("Reference DocType and Reference Name are required."))
		if not frappe.db.exists(self.reference_doctype, self.reference_name):
			frappe.throw(_("Reference document does not exist."))
		if not self.company and self.reference_doctype == "Sales Invoice":
			co = frappe.db.get_value("Sales Invoice", self.reference_name, "company")
			if co:
				self.company = co
		self._merge_company_defaults()
		if not self.adapter_name:
			frappe.throw(_("Adapter is required."))
		self._normalize_submission_kind()
		self._validate_lifecycle_controls()
		if self.extra_json and str(self.extra_json).strip():
			try:
				parsed = json.loads(self.extra_json)
			except json.JSONDecodeError as exc:
				raise frappe.ValidationError(_("Extra Payload must be valid JSON.")) from exc
			if not isinstance(parsed, dict):
				raise frappe.ValidationError(_("Extra Payload must be a JSON object."))

	def _validate_lifecycle_controls(self):
		if not self.company:
			frappe.throw(_("Company is mandatory for e-invoice submission."), title=_("Compliance"))
		if not self.submission_channel:
			frappe.throw(_("Submission Channel is mandatory."), title=_("Compliance"))
		if self.operation in {"submit", "cancel"} and not self.reference_name:
			frappe.throw(_("Reference Name is mandatory for submit/cancel operations."), title=_("Reference"))
		if self.status == "Completed" and not self.provider_reference:
			frappe.throw(_("Provider Reference is mandatory when status is Completed."), title=_("Result"))
		if self.submission_kind == "E-Receipt" and self.reference_doctype not in ("POS Invoice", "Sales Invoice"):
			frappe.throw(_("E-Receipt must reference POS Invoice/Sales Invoice."), title=_("Reference"))
		if self.submission_kind == "E-Invoice" and self.reference_doctype != "Sales Invoice":
			frappe.throw(_("E-Invoice must reference Sales Invoice."), title=_("Reference"))

	def _normalize_submission_kind(self):
		if self.submission_kind:
			return
		if self.reference_doctype == "POS Invoice":
			self.submission_kind = "E-Receipt"
			return
		if self.reference_doctype == "Sales Invoice":
			try:
				is_pos = int(frappe.db.get_value("Sales Invoice", self.reference_name, "is_pos") or 0)
			except Exception:
				is_pos = 0
			self.submission_kind = "E-Receipt" if is_pos else "E-Invoice"
			return
		self.submission_kind = "E-Invoice"

	def _merge_company_defaults(self) -> None:
		"""Fill adapter / extra_json from Tax Authority Profile + Signing Profile (setdefault semantics)."""
		if not self.company:
			return
		if not frappe.db.exists("DocType", "Tax Authority Profile"):
			return
		base: dict = {}
		if self.extra_json and str(self.extra_json).strip():
			try:
				base = json.loads(self.extra_json)
			except json.JSONDecodeError:
				return
		if not isinstance(base, dict):
			return
		tap = frappe.db.get_value(
			"Tax Authority Profile",
			{"company": self.company},
			["default_einvoice_adapter", "taxpayer_registration_id", "zatca_reporting_phase"],
			as_dict=True,
		)
		if tap:
			if not self.adapter_name and tap.get("default_einvoice_adapter"):
				self.adapter_name = tap.get("default_einvoice_adapter")
			if tap.get("taxpayer_registration_id"):
				base.setdefault("taxpayer_rin", tap.get("taxpayer_registration_id"))
			if tap.get("zatca_reporting_phase"):
				base.setdefault("phase", tap.get("zatca_reporting_phase"))
		if frappe.db.exists("DocType", "Signing Profile"):
			sign = frappe.db.get_value(
				"Signing Profile",
				{"company": self.company},
				["default_signer_mode"],
				as_dict=True,
			)
			if sign and sign.get("default_signer_mode"):
				base.setdefault("signer_mode", sign.get("default_signer_mode"))
		if base:
			self.extra_json = json.dumps(base, indent=2, sort_keys=True)

	def dispatch_now(self) -> None:
		"""Send payload to IntegrationHub and persist result (idempotent per name+adapter+operation)."""
		self.reload()
		if self.status not in ("Draft", "", None):
			frappe.throw(_("Only submissions in Draft can be dispatched."))
		payload = self._build_payload()
		hub = get_default_hub()
		idem = f"{self.name}:{self.adapter_name}:{self.operation}"
		try:
			result = hub.dispatch(self.adapter_name, payload, idempotency_key=idem)
		except IntegrationHubError as err:
			self.db_set(
				{
					"status": "Failed",
					"integration_message": str(err),
				},
				update_modified=False,
			)
			raise
		next_status = "Queued" if (result.status or "").lower() == "queued" else "Completed"
		self.db_set(
			{
				"status": next_status,
				"provider_reference": result.provider_reference or "",
				"integration_message": result.message or "",
				"result_data": json.dumps(result.data, default=str) if result.data else "",
			},
			update_modified=False,
		)

	def _build_payload(self) -> dict:
		payload: dict = {
			"reference_name": self.reference_name,
			"document_type": (self.document_type or "invoice").strip().lower(),
			"operation": (self.operation or "submit").strip().lower(),
		}
		if self.extra_json and self.extra_json.strip():
			extra = json.loads(self.extra_json)
			payload.update(extra)
		return payload


def _canonical_json(data: dict) -> str:
	return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _build_sales_invoice_payload(doc) -> dict:
	items = []
	for row in (doc.get("items") or []):
		items.append(
			{
				"code": row.get("item_code"),
				"name": row.get("item_name"),
				"qty": row.get("qty"),
				"rate": row.get("rate"),
				"amount": row.get("amount"),
			}
		)
	return {
		"documentType": "I",
		"internalId": doc.name,
		"issueDate": str(doc.get("posting_date") or ""),
		"currency": doc.get("currency") or "EGP",
		"customer": doc.get("customer"),
		"grandTotal": doc.get("grand_total"),
		"items": items,
	}


def _build_pos_receipt_payload(doc) -> dict:
	items = []
	for row in (doc.get("items") or []):
		items.append(
			{
				"internalCode": row.get("item_code"),
				"description": row.get("item_name"),
				"quantity": row.get("qty"),
				"unitPrice": row.get("rate"),
				"total": row.get("amount"),
			}
		)
	payload = {
		"header": {
			"receiptNumber": doc.name,
			"dateTimeIssued": str(doc.get("posting_date") or ""),
			"uuid": "",
		},
		"documentType": {"receiptType": "s", "typeVersion": "1.2"},
		"buyer": {"name": doc.get("customer_name") or doc.get("customer") or "Cash Customer"},
		"itemData": items,
		"totalAmount": doc.get("grand_total") or doc.get("rounded_total") or 0,
	}
	base = json.loads(json.dumps(payload))
	base["header"]["uuid"] = ""
	payload["header"]["uuid"] = hashlib.sha256(_canonical_json(base).encode("utf-8")).hexdigest()
	return payload


def _get_signing_profile(company: str) -> frappe._dict:
	return frappe.db.get_value(
		"Signing Profile",
		{"company": company},
		["default_signer_mode", "signing_secret", "windows_signer_command"],
		as_dict=True,
	) or frappe._dict()


def _sign_payload(canonical_text: str, company: str, pin: str | None = None) -> str:
	profile = _get_signing_profile(company)
	mode = (profile.get("default_signer_mode") or "remote").strip().lower()
	if mode == "windows_app" and (profile.get("windows_signer_command") or "").strip():
		cmd = (profile.get("windows_signer_command") or "").strip()
		args = [cmd, canonical_text]
		if pin:
			args.append(pin)
		out = subprocess.check_output(args, text=True).strip()
		if not out:
			frappe.throw(_("Windows signer returned empty signature."))
		return out
	secret = (profile.get("signing_secret") or "").strip()
	if not secret:
		secret = frappe.local.site
	signature = hmac.new(secret.encode("utf-8"), canonical_text.encode("utf-8"), hashlib.sha256).digest()
	return base64.b64encode(signature).decode("utf-8")


def _get_tax_profile(company: str) -> frappe._dict:
	row = frappe.db.get_value(
		"Tax Authority Profile",
		{"company": company},
		["eta_base_url", "eta_client_id", "eta_client_secret", "eta_environment", "taxpayer_registration_id"],
		as_dict=True,
	)
	return frappe._dict(row or {})


@frappe.whitelist()
def ensure_submission_for_document(doctype: str, docname: str):
	if doctype not in ("Sales Invoice", "POS Invoice"):
		frappe.throw(_("Only Sales Invoice and POS Invoice are supported."))
	if doctype == "POS Invoice" and not frappe.db.exists("DocType", "POS Invoice"):
		frappe.throw(_("POS Invoice DocType is not installed on this site."))
	doc = frappe.get_doc(doctype, docname)
	kind = "E-Invoice"
	if doctype == "POS Invoice":
		kind = "E-Receipt"
	elif doctype == "Sales Invoice":
		kind = "E-Receipt" if int(doc.get("is_pos") or 0) else "E-Invoice"
	existing = frappe.db.get_value(
		"E Invoice Submission",
		{"reference_doctype": doctype, "reference_name": docname, "operation": "submit"},
		"name",
		order_by="creation desc",
	)
	if existing:
		return {"name": existing, "created": False}
	sub = frappe.get_doc(
		{
			"doctype": "E Invoice Submission",
			"company": doc.company,
			"reference_doctype": doctype,
			"reference_name": docname,
			"submission_kind": kind,
			"adapter_name": "einvoice_eta",
			"document_type": "receipt" if kind == "E-Receipt" else "invoice",
			"operation": "submit",
			"status": "Draft",
		}
	)
	sub.insert(ignore_permissions=True)
	return {"name": sub.name, "created": True}


@frappe.whitelist()
def sign_submission(name: str, pin: str | None = None):
	doc = frappe.get_doc("E Invoice Submission", name)
	if doc.status not in ("Draft", "Failed"):
		frappe.throw(_("Only Draft/Failed submission can be signed."))
	source = frappe.get_doc(doc.reference_doctype, doc.reference_name)
	is_receipt = doc.submission_kind == "E-Receipt"
	payload = _build_pos_receipt_payload(source) if is_receipt else _build_sales_invoice_payload(source)
	canonical = _canonical_json(payload)
	signature = _sign_payload(canonical, doc.company, pin)
	doc.signature_value = signature
	doc.canonical_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
	if is_receipt:
		doc.eta_uuid = payload.get("header", {}).get("uuid", "")
		merged = {"document": payload, "signature": signature}
	else:
		merged = {"document": payload, "signatures": [{"signatureType": "I", "value": signature}]}
	doc.result_data = json.dumps(merged, ensure_ascii=False)
	doc.status = "Signed"
	doc.save(ignore_permissions=True)
	return {"ok": True, "status": doc.status, "uuid": doc.eta_uuid}


@frappe.whitelist()
def send_submission_to_eta(name: str):
	doc = frappe.get_doc("E Invoice Submission", name)
	if doc.status not in ("Signed", "Draft", "Failed"):
		frappe.throw(_("Submission must be in Signed/Draft/Failed state before send."))
	if not doc.result_data:
		sign_submission(name)
		doc.reload()
	payload = json.loads(doc.result_data or "{}")
	tax = _get_tax_profile(doc.company)
	base_url = (tax.get("eta_base_url") or "").rstrip("/")
	if not base_url:
		frappe.throw(_("ETA Base URL is required in Tax Authority Profile."))
	token = ensure_eta_access_token(
		profile_key=f"eta:{doc.company}",
		credentials={
			"client_id": tax.get("eta_client_id"),
			"client_secret": tax.get("eta_client_secret"),
			"environment": tax.get("eta_environment") or "preprod",
		},
	)
	headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
	if doc.submission_kind == "E-Receipt":
		url = f"{base_url}/api/v1/receiptsubmissions"
		body = {"receipts": [payload.get("document") or payload]}
	else:
		url = f"{base_url}/api/v1/documentsubmissions"
		document = payload.get("document") or payload
		if payload.get("signatures"):
			document["signatures"] = payload["signatures"]
		body = {"documents": [document]}
	res = requests.post(url, json=body, headers=headers, timeout=45)
	response_body = {}
	try:
		response_body = res.json()
	except Exception:
		response_body = {"raw": res.text}
	doc.status = "Completed" if res.status_code < 300 else "Failed"
	doc.provider_reference = str(response_body.get("submissionId") or response_body.get("id") or "")[:140]
	doc.authority_uuid = str(response_body.get("uuid") or response_body.get("documentUUID") or "")[:140]
	doc.integration_message = str(response_body.get("message") or res.reason or "")[:140]
	doc.eta_error_code = str(response_body.get("errorCode") or "")[:140]
	doc.result_data = json.dumps(response_body, ensure_ascii=False)[:20000]
	doc.save(ignore_permissions=True)
	return {"ok": res.status_code < 300, "status_code": res.status_code, "status": doc.status}


@frappe.whitelist()
def dispatch_submission(name: str):
	"""Desk / API entry point to run hub dispatch for a draft submission."""
	doc = frappe.get_doc("E Invoice Submission", name)
	doc.dispatch_now()
	return doc.as_dict()
