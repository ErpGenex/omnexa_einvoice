# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""
USB signing agent integration (E-Invoice only).
Temp-ETR flow: browser → local agent with sign_session; agent fetches PIN from ERP.
"""

from __future__ import annotations

import base64
import json

import frappe
from frappe import _

from omnexa_einvoice.branch_eta import get_eta_invoice_branch_settings, resolve_branch_for_document
from omnexa_einvoice.eta_einvoice_submission import (
	build_unsigned_e_invoice_document,
	prepare_e_invoice_for_send_unsigned,
)
from omnexa_einvoice.eta_invoice_signing import uses_browser_signing_agent

CACHE_PREFIX = "omnexa_usb_sign:"
SESSION_TTL_SEC = 180
DEFAULT_AGENT_URL = "http://127.0.0.1:5002"


def client_signing_secrets(branch: str) -> dict:
	"""PIN payload for legacy browser clients (prefer sign_session)."""
	raw = branch_usb_pin(branch)
	b64 = base64.b64encode(raw.encode("utf-8")).decode("ascii") if raw else ""
	return {
		"signing_secret_b64": b64,
		"usb_pin_b64": b64,
		"has_signing_secret": bool(b64),
	}


def branch_usb_pin(branch: str) -> str:
	if not branch:
		return ""
	try:
		return (get_eta_invoice_branch_settings(branch).usb_signing_pin or "").strip()
	except Exception:
		return ""


def require_branch_usb_pin(branch: str) -> str:
	pin = branch_usb_pin(branch)
	if not pin:
		frappe.throw(
			_("USB Token PIN is missing on Branch {0}. Enter it under Egypt ETA → USB Token PIN and Save.").format(
				branch
			),
			title=_("Signing Agent"),
		)
	return pin


def _store_session(branch: str) -> str:
	pin = require_branch_usb_pin(branch)
	session_id = frappe.generate_hash(length=32)
	frappe.cache().set_value(
		f"{CACHE_PREFIX}{session_id}",
		{"pin": pin, "user": frappe.session.user, "branch": branch},
		expires_in_sec=SESSION_TTL_SEC,
	)
	return session_id


def build_agent_session_body(unsigned: dict, branch: str, token_type: str, session_id: str) -> dict:
	"""POST /sign body — PIN loaded by agent via sign_session (no PIN in browser)."""
	unsigned = json.loads(json.dumps(unsigned or {}, ensure_ascii=False))
	unsigned.pop("signatures", None)
	return {
		"invoice": unsigned,
		"sign_session": session_id,
		"erp_base_url": frappe.utils.get_url(),
		"token_type": (token_type or "epass2003").strip() or "epass2003",
		"use_chilkat": True,
		"verify": False,
	}


def build_agent_sign_payload(unsigned: dict, branch: str, token_type: str = "epass2003") -> dict:
	"""Full /sign body with PIN (server-side or legacy clients). Matches Temp-ETR DirectSigner."""
	plain_pin = require_branch_usb_pin(branch)
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


def resolve_usb_sign_session(session_id: str) -> dict:
	"""epass2003_agent on Windows — one-time PIN fetch (allow_guest, session id is the secret)."""
	session_id = (session_id or "").strip()
	if not session_id:
		frappe.throw(_("session_id is required."), frappe.PermissionError)
	key = f"{CACHE_PREFIX}{session_id}"
	data = frappe.cache().get_value(key)
	if not data:
		frappe.throw(_("Signing session expired. Click Sign E-Invoice again."), frappe.PermissionError)
	frappe.cache().delete_value(key)
	pin = (data.get("pin") or "").strip()
	if not pin:
		frappe.throw(_("USB PIN missing in signing session."), frappe.PermissionError)
	return {"pin": pin, "usb_token_pin": pin}


def _submission_context(name: str, for_send: int) -> tuple[dict, str, str, str]:
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
	token_type = (settings.usb_token_type or "epass2003").strip()
	agent_url = (settings.signing_agent_url or DEFAULT_AGENT_URL).strip()
	return unsigned, branch, token_type, agent_url


def create_usb_sign_session_for_submission(name: str, for_send: int = 0) -> dict:
	"""Primary API for browser signing — returns agent_body with sign_session only."""
	unsigned, branch, token_type, agent_url = _submission_context(name, for_send)
	session_id = _store_session(branch)
	agent_body = build_agent_session_body(unsigned, branch, token_type, session_id)
	return {
		"ok": True,
		"branch": branch,
		"agent_url": agent_url,
		"agent_body": agent_body,
		"sign_session": session_id,
		"erp_base_url": agent_body["erp_base_url"],
		"internal_id": unsigned.get("internalID"),
	}


def create_usb_sign_session_for_branch_test(branch: str) -> dict:
	from omnexa_einvoice.eta_invoice import build_usb_signing_test_document

	branch = (branch or "").strip()
	settings = get_eta_invoice_branch_settings(branch)
	document = build_usb_signing_test_document(branch)
	token_type = (settings.usb_token_type or "epass2003").strip()
	session_id = _store_session(branch)
	agent_body = build_agent_session_body(document, branch, token_type, session_id)
	return {
		"ok": True,
		"branch": branch,
		"agent_url": (settings.signing_agent_url or DEFAULT_AGENT_URL).strip(),
		"agent_body": agent_body,
		"internal_id": document.get("internalID"),
	}
