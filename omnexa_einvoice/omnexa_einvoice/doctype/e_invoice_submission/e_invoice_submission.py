# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import subprocess

import frappe
import requests
from frappe import _
from frappe.model.document import Document

from omnexa_core.omnexa_core.integration_hub import IntegrationHubError, get_default_hub
from omnexa_einvoice.eta_integration import ensure_eta_access_token
from omnexa_einvoice.branch_eta import (
	INVOICE_KIND,
	RECEIPT_KIND,
	get_branch_eta_credentials,
	get_eta_branch_settings,
	get_eta_invoice_branch_settings,
	resolve_branch_for_document,
)
from omnexa_einvoice.eta_receipt import (
	build_eta_receipt_document,
	encode_eta_receipt_submission,
	ensure_receipt_uuid,
	parse_receipt_submission_response,
	refresh_receipt_datetime,
	validate_receipt_document,
)
from omnexa_einvoice.sales_invoice_eta import (
	get_eta_billing_type,
	resolve_submission_kind_for_sales_invoice,
	sales_invoice_is_eta_billing,
)


class EInvoiceSubmission(Document):
	def validate(self):
		if not self.reference_doctype or not self.reference_name:
			frappe.throw(_("Reference DocType and Reference Name are required."))
		if not frappe.db.exists(self.reference_doctype, self.reference_name):
			frappe.throw(_("Reference document does not exist."))
		if not self.company and self.reference_doctype in ("Sales Invoice", "POS Invoice"):
			row = frappe.db.get_value(
				self.reference_doctype,
				self.reference_name,
				["company", "branch"],
				as_dict=True,
			)
			if row:
				self.company = row.get("company") or self.company
				self.branch = self.branch or row.get("branch")
		self._resolve_branch()
		self._merge_branch_defaults()
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
		if (self.adapter_name or "").strip() == "einvoice_eta" and not self.branch:
			frappe.throw(
				_("Branch is mandatory for ETA. Set Branch on the invoice or configure Egypt ETA on the branch."),
				title=_("Compliance"),
			)
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
			source = frappe.get_doc("Sales Invoice", self.reference_name)
			billing = get_eta_billing_type(source)
			if billing == "E-Receipt":
				self.submission_kind = "E-Receipt"
			else:
				self.submission_kind = "E-Invoice"
			return
		self.submission_kind = "E-Invoice"

	def _resolve_branch(self) -> None:
		if self.branch:
			return
		if self.reference_doctype and self.reference_name and frappe.db.exists(
			self.reference_doctype, self.reference_name
		):
			source = frappe.get_doc(self.reference_doctype, self.reference_name)
			self.branch = resolve_branch_for_document(source)

	def _merge_branch_defaults(self) -> None:
		if not self.branch:
			return
		if not self.adapter_name:
			self.adapter_name = "einvoice_eta"
		base: dict = {}
		if self.extra_json and str(self.extra_json).strip():
			try:
				base = json.loads(self.extra_json)
			except json.JSONDecodeError:
				return
		if not isinstance(base, dict):
			return
		try:
			kind = RECEIPT_KIND if self.submission_kind == "E-Receipt" else INVOICE_KIND
			settings = get_eta_branch_settings(self.branch, kind=kind)
			if settings.rin:
				base.setdefault("taxpayer_rin", settings.rin)
			if kind == INVOICE_KIND:
				base.setdefault("signer_mode", settings.signer_mode)
			base.setdefault("branch", self.branch)
		except Exception:
			pass
		if base:
			self.extra_json = json.dumps(base, indent=2, sort_keys=True)

	def dispatch_now(self) -> None:
		self.reload()
		if self.submission_kind == "E-Receipt":
			frappe.throw(
				_(
					"E-Receipt is not sent through the integration hub. "
					"Use «Send to ETA» or the ETA E-Receipt Console."
				),
				title=_("E-Receipt"),
			)
		if self.status not in ("Draft", "", None):
			frappe.throw(_("Only submissions in Draft can be dispatched."))
		payload = self._build_payload()
		hub = get_default_hub()
		idem = f"{self.name}:{self.adapter_name}:{self.operation}"
		try:
			result = hub.dispatch(self.adapter_name, payload, idempotency_key=idem)
		except IntegrationHubError as err:
			self.db_set(
				{"status": "Failed", "integration_message": str(err)},
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
	for row in doc.get("items") or []:
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


def _sign_payload(canonical_text: str, branch: str, pin: str | None = None) -> str:
	settings = get_eta_invoice_branch_settings(branch)
	mode = settings.signer_mode
	if mode == "windows_app" and (settings.windows_signer_command or "").strip():
		cmd = settings.windows_signer_command.strip()
		args = [cmd, canonical_text]
		if pin:
			args.append(pin)
		out = subprocess.check_output(args, text=True).strip()
		if not out:
			frappe.throw(_("Windows signer returned empty signature."))
		return out
	secret = (settings.signing_secret or "").strip()
	if not secret and frappe.db.exists("Branch", branch):
		try:
			secret = (
				frappe.get_doc("Branch", branch).get_password("eta_signing_secret", raise_exception=False) or ""
			)
		except Exception:
			secret = ""
	if not secret:
		secret = frappe.local.site
	signature = hmac.new(secret.encode("utf-8"), canonical_text.encode("utf-8"), hashlib.sha256).digest()
	return base64.b64encode(signature).decode("utf-8")


@frappe.whitelist()
def ensure_submission_for_document(doctype: str, docname: str):
	if doctype not in ("Sales Invoice", "POS Invoice"):
		frappe.throw(_("Only Sales Invoice and POS Invoice are supported."))
	if doctype == "POS Invoice" and not frappe.db.exists("DocType", "POS Invoice"):
		frappe.throw(_("POS Invoice DocType is not installed on this site."))
	doc = frappe.get_doc(doctype, docname)
	branch = resolve_branch_for_document(doc)
	kind = "E-Invoice"
	if doctype == "POS Invoice":
		kind = "E-Receipt"
	elif doctype == "Sales Invoice":
		if not sales_invoice_is_eta_billing(doc):
			from omnexa_einvoice.sales_invoice_eta import eta_billing_type_required_message

			frappe.throw(eta_billing_type_required_message(), title=_("ETA"))
		kind = resolve_submission_kind_for_sales_invoice(doc)
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
			"branch": branch,
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


def _sync_submission_kind_from_source(doc, source) -> None:
	"""Keep submission_kind aligned with Sales Invoice billing type (receipt vs invoice)."""
	if doc.reference_doctype == "POS Invoice":
		doc.submission_kind = "E-Receipt"
		return
	if doc.reference_doctype == "Sales Invoice":
		doc.submission_kind = resolve_submission_kind_for_sales_invoice(source)


def _recover_ereceipt_from_hub_queue(doc) -> None:
	"""Hub dispatch only queues a stub — E-Receipt must use direct ETA send."""
	if doc.submission_kind != "E-Receipt" or doc.status != "Queued":
		return
	doc.status = "Draft"
	if (doc.provider_reference or "").startswith("ETA-"):
		doc.provider_reference = ""
	doc.integration_message = ""
	doc.save(ignore_permissions=True)


@frappe.whitelist()
def sign_submission(name: str, pin: str | None = None):
	"""E-Receipt: build ETA JSON + ITIDA UUID + validate. E-Invoice: canonical sign (USB/HMAC)."""
	doc = frappe.get_doc("E Invoice Submission", name)
	if doc.status not in ("Draft", "Failed", "Queued"):
		frappe.throw(_("Only Draft/Failed submission can be signed."))
	source = frappe.get_doc(doc.reference_doctype, doc.reference_name)
	_sync_submission_kind_from_source(doc, source)
	_recover_ereceipt_from_hub_queue(doc)
	is_receipt = doc.submission_kind == "E-Receipt"

	branch = doc.branch or resolve_branch_for_document(source)
	if not branch:
		frappe.throw(_("Branch is required. Set Branch on the source document."), title=_("ETA"))
	doc.branch = branch

	if is_receipt:
		payload = build_eta_receipt_document(source, branch=branch)
		validate_receipt_document(payload, strict_datetime=False)
		doc.eta_uuid = payload.get("header", {}).get("uuid", "")
		doc.canonical_hash = doc.eta_uuid
		doc.signature_value = ""
		merged = {"document": payload}
	else:
		payload = _build_sales_invoice_payload(source)
		canonical = _canonical_json(payload)
		signature = _sign_payload(canonical, branch, pin)
		doc.signature_value = signature
		doc.canonical_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
		merged = {"document": payload, "signatures": [{"signatureType": "I", "value": signature}]}

	doc.result_data = json.dumps(merged, ensure_ascii=False)
	doc.status = "Signed"
	doc.save(ignore_permissions=True)
	return {"ok": True, "status": doc.status, "uuid": doc.eta_uuid}


@frappe.whitelist()
def send_submission_to_eta(name: str):
	doc = frappe.get_doc("E Invoice Submission", name)
	source = frappe.get_doc(doc.reference_doctype, doc.reference_name)
	_sync_submission_kind_from_source(doc, source)
	_recover_ereceipt_from_hub_queue(doc)
	doc.reload()

	allowed = ("Signed", "Draft", "Failed")
	if doc.submission_kind == "E-Receipt":
		allowed = ("Signed", "Draft", "Failed", "Queued")
	if doc.status not in allowed:
		frappe.throw(_("Submission must be in Signed/Draft/Failed state before send."))
	if not doc.result_data or doc.status != "Signed":
		sign_submission(name)
		doc.reload()

	payload = json.loads(doc.result_data or "{}")
	branch = doc.branch or resolve_branch_for_document(frappe.get_doc(doc.reference_doctype, doc.reference_name))
	if not branch:
		frappe.throw(_("Branch is required for ETA send."), title=_("ETA"))
	eta_kind = RECEIPT_KIND if doc.submission_kind == "E-Receipt" else INVOICE_KIND
	settings = get_eta_branch_settings(branch, kind=eta_kind)
	token = ensure_eta_access_token(
		profile_key=f"eta:{branch}:{eta_kind}",
		credentials=get_branch_eta_credentials(branch, kind=eta_kind),
	)

	base_url = settings.eta_base_url.rstrip("/")
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {token}",
	}

	if doc.submission_kind == "E-Receipt":
		document = payload.get("document") or payload
		document = refresh_receipt_datetime(document)
		document = ensure_receipt_uuid(document)
		validate_receipt_document(document, strict_datetime=True)
		doc.eta_uuid = document.get("header", {}).get("uuid", "")
		# Submit: Authorization only (Temp-ETR / PowerBuilder). POS headers are token-only.
		url = f"{base_url}/api/v1/receiptsubmissions"
		body_bytes = encode_eta_receipt_submission(document)
	else:
		url = f"{base_url}/api/v1/documentsubmissions"
		document = payload.get("document") or payload
		if payload.get("signatures"):
			document["signatures"] = payload["signatures"]
		body = {"documents": [document]}

	if doc.submission_kind == "E-Receipt":
		res = requests.post(url, data=body_bytes, headers=headers, timeout=60)
	else:
		res = requests.post(url, json=body, headers=headers, timeout=45)
	response_body: dict = {}
	try:
		response_body = res.json()
	except Exception:
		response_body = {"raw": res.text}

	if doc.submission_kind == "E-Receipt":
		parsed = parse_receipt_submission_response(response_body, res.status_code)
		ok = parsed["ok"] and res.status_code in (200, 201, 202)
		doc.status = "Completed" if ok else "Failed"
		doc.provider_reference = (
			parsed["submission_id"] or parsed["authority_uuid"] or doc.eta_uuid or ""
		)[:140]
		doc.authority_uuid = parsed["authority_uuid"] or doc.eta_uuid
		doc.integration_message = parsed["message"]
		doc.eta_error_code = parsed["error_code"]
	else:
		ok = res.status_code < 300
		doc.status = "Completed" if ok else "Failed"
		doc.provider_reference = str(response_body.get("submissionId") or response_body.get("id") or "")[:140]
		doc.authority_uuid = str(response_body.get("uuid") or response_body.get("documentUUID") or "")[:140]
		doc.integration_message = str(response_body.get("message") or res.reason or "")[:140]
		doc.eta_error_code = str(response_body.get("errorCode") or "")[:140]

	if doc.submission_kind == "E-Receipt" and ok:
		stored = {"document": document, "eta_response": response_body}
		doc.result_data = json.dumps(stored, ensure_ascii=False)[:20000]
	else:
		doc.result_data = json.dumps(response_body, ensure_ascii=False)[:20000]

	doc.save(ignore_permissions=True)
	return {"ok": ok, "status_code": res.status_code, "status": doc.status, "uuid": doc.eta_uuid}


@frappe.whitelist()
def dispatch_submission(name: str):
	doc = frappe.get_doc("E Invoice Submission", name)
	doc.dispatch_now()
	return doc.as_dict()
