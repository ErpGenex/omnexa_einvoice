# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

from __future__ import annotations

import base64
import json

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
	resolve_branch_for_document,
)
from omnexa_einvoice.eta_ereceipt_submission import (
	apply_e_receipt_send_result,
	encode_e_receipt_body,
	prepare_e_receipt_for_send,
	sign_e_receipt_submission,
)
from omnexa_einvoice.branch_eta import get_eta_invoice_branch_settings
from omnexa_einvoice.eta_einvoice_submission import (
	apply_e_invoice_send_result,
	build_e_invoice_submit_body,
	build_unsigned_e_invoice_document,
	prepare_e_invoice_for_send,
	prepare_e_invoice_for_send_unsigned,
	sign_e_invoice_submission,
)
from omnexa_einvoice.eta_invoice_signing import uses_browser_signing_agent
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


def _branch_usb_pin_for_client(branch: str) -> str:
	"""Return stored USB PIN for browser→local agent (authenticated session only)."""
	if not branch:
		return ""
	try:
		return (get_eta_invoice_branch_settings(branch).usb_signing_pin or "").strip()
	except Exception:
		return ""


def _branch_usb_pin_b64_for_client(branch: str) -> str:
	"""Base64 PIN for browser (avoids empty ``pin`` key in some clients)."""
	raw = _branch_usb_pin_for_client(branch)
	if not raw:
		return ""
	return base64.b64encode(raw.encode("utf-8")).decode("ascii")


def _client_signing_secrets(branch: str) -> dict:
	"""PIN payload for browser→agent (field names avoid accidental API redaction)."""
	b64 = _branch_usb_pin_b64_for_client(branch)
	return {
		"signing_secret_b64": b64,
		"usb_pin_b64": b64,
		"has_signing_secret": bool(b64),
	}


def build_agent_sign_payload(unsigned: dict, branch: str, token_type: str = "epass2003") -> dict:
	"""
	Full POST body for epass2003_agent /sign (matches Temp-ETR DirectSigner.sign_with_agent).
	PIN always from Branch — never from the browser UI.
	"""
	plain_pin = _branch_usb_pin_for_client(branch)
	if not plain_pin:
		frappe.throw(
			_("USB Token PIN is missing on Branch {0}. Enter it under Egypt ETA → USB Token PIN and Save.").format(
				branch
			),
			title=_("Signing Agent"),
		)
	pin_b64 = base64.b64encode(plain_pin.encode("utf-8")).decode("ascii")
	unsigned = json.loads(json.dumps(unsigned or {}, ensure_ascii=False))
	unsigned.pop("signatures", None)
	return {
		"invoice": unsigned,
		"pin": plain_pin,
		"usb_token_pin": plain_pin,
		"pin_b64": pin_b64,
		"signing_secret_b64": pin_b64,
		"token_type": (token_type or "epass2003").strip() or "epass2003",
		"use_chilkat": True,
		"verify": False,
	}


@frappe.whitelist()
def get_agent_sign_payload_for_branch_test(branch: str) -> dict:
	"""Server-built test /sign payload (Branch USB test button on Windows)."""
	from omnexa_einvoice.eta_invoice import build_usb_signing_test_document

	branch = (branch or "").strip()
	settings = get_eta_invoice_branch_settings(branch)
	document = build_usb_signing_test_document(branch)
	token_type = (settings.usb_token_type or "epass2003").strip()
	agent_payload = build_agent_sign_payload(document, branch, token_type=token_type)
	return {
		"ok": True,
		"branch": branch,
		"agent_url": (settings.signing_agent_url or "http://127.0.0.1:5002").strip(),
		"agent_payload": agent_payload,
		"internal_id": document.get("internalID"),
	}


@frappe.whitelist()
def get_agent_sign_payload_for_submission(name: str, for_send: int = 0) -> dict:
	"""
	Server-built /sign payload for browser → local agent (E-Invoice only).
	Avoids empty PIN when cached client JS is outdated.
	"""
	doc = frappe.get_doc("E Invoice Submission", name)
	if doc.submission_kind == "E-Receipt":
		frappe.throw(_("E-Receipt does not use USB signing."), title=_("E-Receipt"))
	source = frappe.get_doc(doc.reference_doctype, doc.reference_name)
	branch = doc.branch or resolve_branch_for_document(source)
	settings = get_eta_invoice_branch_settings(branch)
	if not uses_browser_signing_agent(branch):
		frappe.throw(_("Branch signer mode is not Signing Agent."), title=_("E-Invoice Signing"))

	if int(for_send or 0):
		payload = json.loads(doc.result_data or "{}")
		unsigned = prepare_e_invoice_for_send_unsigned(payload)
	else:
		unsigned = build_unsigned_e_invoice_document(source, branch)

	agent_url = (settings.signing_agent_url or "http://127.0.0.1:5002").strip()
	token_type = (settings.usb_token_type or "epass2003").strip()
	agent_payload = build_agent_sign_payload(unsigned, branch, token_type=token_type)
	return {
		"ok": True,
		"branch": branch,
		"agent_url": agent_url,
		"agent_payload": agent_payload,
		"internal_id": (unsigned.get("internalID") or ""),
		"pin_configured": True,
	}


@frappe.whitelist()
def get_branch_signing_secret_b64(branch: str) -> dict:
	"""Return branch USB signing secret for authenticated browser→local agent only."""
	branch = (branch or "").strip()
	if not branch or not frappe.db.exists("Branch", branch):
		frappe.throw(_("Branch {0} does not exist.").format(branch or "—"), title=_("Signing"))
	secrets = _client_signing_secrets(branch)
	if not secrets["has_signing_secret"]:
		frappe.throw(
			_("USB Token PIN is missing on Branch {0}. Enter it under Egypt ETA → USB Token PIN and Save.").format(
				branch
			),
			title=_("Signing Agent"),
		)
	return {"ok": True, "branch": branch, **secrets}


@frappe.whitelist()
def get_branch_usb_signing_status(branch: str) -> dict:
	"""Whether Branch has USB PIN saved (does not expose the PIN)."""
	branch = (branch or "").strip()
	if not branch or not frappe.db.exists("Branch", branch):
		return {"ok": False, "has_pin": False}
	pin = _branch_usb_pin_for_client(branch)
	signer_mode = ""
	agent_url = ""
	token_type = "epass2003"
	if frappe.db.get_value("Branch", branch, "eta_einvoice_enabled"):
		try:
			settings = get_eta_invoice_branch_settings(branch)
			signer_mode = (settings.signer_mode or "").strip()
			agent_url = (settings.signing_agent_url or "").strip()
			token_type = (settings.usb_token_type or "epass2003").strip()
		except Exception:
			pass
	return {
		"ok": True,
		"has_pin": bool(pin),
		"signer_mode": signer_mode,
		"agent_url": agent_url,
		"token_type": token_type,
	}


@frappe.whitelist()
def get_e_invoice_signing_settings(name: str) -> dict:
	"""Client-side USB agent settings (E-Invoice only). E-Receipt never uses this."""
	doc = frappe.get_doc("E Invoice Submission", name)
	if doc.submission_kind == "E-Receipt":
		return {"browser_signing": False}
	source = frappe.get_doc(doc.reference_doctype, doc.reference_name)
	branch = doc.branch or resolve_branch_for_document(source)
	settings = get_eta_invoice_branch_settings(branch)
	return {
		"browser_signing": uses_browser_signing_agent(branch),
		"agent_url": (settings.signing_agent_url or "http://127.0.0.1:5002").strip(),
		"token_type": (settings.usb_token_type or "epass2003").strip(),
		"signer_mode": (settings.signer_mode or "remote").strip(),
		"has_branch_pin": bool(_branch_usb_pin_for_client(branch)),
	}


@frappe.whitelist()
def prepare_e_invoice_for_client_sign(name: str) -> dict:
	"""Unsigned ETA invoice JSON for browser signing agent (E-Invoice only)."""
	doc = frappe.get_doc("E Invoice Submission", name)
	if doc.submission_kind == "E-Receipt":
		frappe.throw(_("E-Receipt does not use USB signing."), title=_("E-Receipt"))
	source = frappe.get_doc(doc.reference_doctype, doc.reference_name)
	branch = doc.branch or resolve_branch_for_document(source)
	document = build_unsigned_e_invoice_document(source, branch)
	unsigned = json.loads(json.dumps(document, ensure_ascii=False))
	unsigned.pop("signatures", None)
	ctx = get_e_invoice_signing_settings(name)
	secrets = _client_signing_secrets(branch)
	if ctx.get("browser_signing") and not secrets["has_signing_secret"]:
		frappe.throw(
			_("USB Token PIN is missing on Branch {0}. Enter it under Egypt ETA → USB Token PIN and Save.").format(
				branch
			),
			title=_("Signing Agent"),
		)
	return {"document": unsigned, "branch": branch, **ctx, **secrets}


@frappe.whitelist()
def prepare_e_invoice_for_client_send(name: str) -> dict:
	"""Refresh issue time; return unsigned document for browser re-sign before ETA send."""
	doc = frappe.get_doc("E Invoice Submission", name)
	if doc.submission_kind == "E-Receipt":
		frappe.throw(_("E-Receipt does not use USB signing."), title=_("E-Receipt"))
	payload = json.loads(doc.result_data or "{}")
	unsigned = prepare_e_invoice_for_send_unsigned(payload)
	ctx = get_e_invoice_signing_settings(name)
	source = frappe.get_doc(doc.reference_doctype, doc.reference_name)
	branch = doc.branch or resolve_branch_for_document(source)
	secrets = _client_signing_secrets(branch)
	if ctx.get("browser_signing") and not secrets["has_signing_secret"]:
		frappe.throw(
			_("USB Token PIN is missing on Branch {0}. Enter it under Egypt ETA → USB Token PIN and Save.").format(
				branch
			),
			title=_("Signing Agent"),
		)
	return {"document": unsigned, "branch": branch, **ctx, **secrets}


@frappe.whitelist()
def sign_submission(name: str, client_signature: str | None = None):
	"""E-Receipt: build ETA JSON. E-Invoice: sign via Branch USB PIN (never prompted)."""
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
		merged = sign_e_receipt_submission(doc, source, branch)
	else:
		merged = sign_e_invoice_submission(doc, source, branch, client_signature=client_signature)

	doc.result_data = json.dumps(merged, ensure_ascii=False)
	doc.status = "Signed"
	doc.save(ignore_permissions=True)
	signer_method = merged.get("signer_method", "") if not is_receipt else ""
	return {"ok": True, "status": doc.status, "uuid": doc.eta_uuid, "signer_method": signer_method}


@frappe.whitelist()
def send_submission_to_eta(name: str, client_signature: str | None = None):
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
		sign_submission(name, client_signature=client_signature)
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
		document = prepare_e_receipt_for_send(payload.get("document") or payload)
		doc.eta_uuid = document.get("header", {}).get("uuid", "")
		url = f"{base_url}/api/v1/receiptsubmissions"
		body_bytes = encode_e_receipt_body(document)
		res = requests.post(url, data=body_bytes, headers=headers, timeout=60)
	else:
		document, doc.canonical_hash, signer_method, doc.signature_value = prepare_e_invoice_for_send(
			payload, branch, client_signature=client_signature
		)
		doc.integration_message = _("Signed via {0} before send.").format(signer_method)
		url = f"{base_url}/api/v1/documentsubmissions"
		body = build_e_invoice_submit_body(document)
		res = requests.post(url, json=body, headers=headers, timeout=60)
	response_body: dict = {}
	try:
		response_body = res.json()
	except Exception:
		response_body = {"raw": res.text}

	if doc.submission_kind == "E-Receipt":
		send_out = apply_e_receipt_send_result(doc, document, response_body, res.status_code)
	else:
		send_out = apply_e_invoice_send_result(doc, document, response_body, res.status_code)
	ok = send_out["ok"]
	parsed = send_out["parsed"]

	doc.save(ignore_permissions=True)
	return {
		"ok": ok,
		"status_code": res.status_code,
		"status": doc.status,
		"uuid": doc.eta_uuid,
		"message": doc.integration_message,
		"submission_id": (parsed.get("submission_id") if doc.submission_kind != "E-Receipt" else parsed.get("submission_id")),
	}


@frappe.whitelist()
def dispatch_submission(name: str):
	doc = frappe.get_doc("E Invoice Submission", name)
	doc.dispatch_now()
	return doc.as_dict()
