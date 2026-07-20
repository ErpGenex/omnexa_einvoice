# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""
E-Invoice signing only (USB agent / HMAC / CLI).
Must never be imported from eta_receipt.py or E-Receipt submission paths.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import subprocess

import frappe
from frappe import _

from omnexa_einvoice.branch_eta import get_eta_invoice_branch_settings
from omnexa_einvoice.eta_invoice import invoice_canonical_json


def assert_eta_invoice_document_shape(document: dict) -> None:
	"""Block accidental use on e-Receipt JSON."""
	if not isinstance(document, dict):
		frappe.throw(_("Invalid invoice document."), title=_("E-Invoice Signing"))
	if document.get("header") and document.get("seller"):
		frappe.throw(
			_("E-Receipt payload cannot use e-Invoice signing. Use the E-Receipt path only."),
			title=_("E-Invoice Signing"),
		)
	if not document.get("issuer"):
		frappe.throw(_("Document is not a valid ETA e-Invoice JSON."), title=_("E-Invoice Signing"))


def resolve_usb_signing_pin(branch: str) -> str:
	"""PIN from Branch settings only — never from Sign/Send dialogs."""
	settings = get_eta_invoice_branch_settings(branch)
	stored = (settings.usb_signing_pin or "").strip()
	if stored:
		return stored
	frappe.throw(
		_(
			"USB Token PIN is not configured on Branch {0}. "
			"Set it once on Branch → Egypt ETA → USB Token PIN, then Save. It is not requested when signing."
		).format(branch),
		title=_("E-Invoice Signing"),
	)


def uses_browser_signing_agent(branch: str) -> bool:
	"""signing_agent is always invoked from the user's browser (127.0.0.1 on the token PC)."""
	settings = get_eta_invoice_branch_settings(branch)
	return (settings.signer_mode or "remote").strip().lower() in ("signing_agent", "agent")


def sign_eta_invoice_document(
	document: dict,
	branch: str,
	*,
	client_signature: str | None = None,
) -> tuple[str, str]:
	"""
	Sign ETA e-Invoice JSON. Returns (signature_value, signer_method).
	E-Receipt must never call this function.
	"""
	assert_eta_invoice_document_shape(document)
	settings = get_eta_invoice_branch_settings(branch)
	mode = (settings.signer_mode or "remote").strip().lower()
	if mode in ("signing_agent", "agent", "windows_app"):
		resolve_usb_signing_pin(branch)  # validate configured before send

	if mode in ("signing_agent", "agent"):
		sig = (client_signature or "").strip()
		if not sig:
			frappe.throw(
				_(
					"E-Invoice signing uses the USB agent on your PC (http://127.0.0.1:5002). "
					"Open ERP in the browser on that PC, start epass2003_agent, then Sign again. "
					"The ERP server cannot call your local USB token directly."
				),
				title=_("Signing Agent"),
			)
		return sig, "signing_agent"

	if mode == "windows_app":
		if not (settings.windows_signer_command or "").strip():
			frappe.throw(_("Windows Signer Command is not configured on branch {0}.").format(branch))
		branch_pin = resolve_usb_signing_pin(branch)
		canonical = invoice_canonical_json(document)
		cmd = settings.windows_signer_command.strip()
		args = [cmd, canonical, branch_pin]
		out = subprocess.check_output(args, text=True).strip()
		if not out:
			frappe.throw(_("Windows signer returned empty signature."))
		return out, "windows_app"

	if mode == "remote":
		canonical = invoice_canonical_json(document)
		return _sign_hmac_remote(canonical, settings, branch), "remote"

	frappe.throw(
		_("Unsupported signer mode “{0}” on branch {1}.").format(mode, branch),
		title=_("E-Invoice Signing"),
	)


def _sign_hmac_remote(canonical_text: str, settings, branch: str) -> str:
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
