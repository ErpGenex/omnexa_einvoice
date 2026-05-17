# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Signing agent diagnostics and optional server-side HTTP (E-Invoice only)."""

from __future__ import annotations

import base64
import json
import platform
from typing import Any

import frappe
import requests
from frappe import _

from omnexa_einvoice.eta_invoice import (
	ETAInvoiceValidationError,
	build_usb_signing_test_document,
	validate_invoice_document,
)
from omnexa_einvoice.e_invoice.usb_session import DEFAULT_AGENT_URL, branch_usb_pin

# Re-export for tests / branch_eta
DEFAULT_SIGNING_AGENT_URL = DEFAULT_AGENT_URL


class ETASigningAgentError(frappe.ValidationError):
	pass


def normalize_signing_agent_url(url: str | None) -> str:
	base = (url or DEFAULT_AGENT_URL).strip().rstrip("/")
	if not base.startswith(("http://", "https://")):
		frappe.throw(
			_("Signing Agent URL must start with http:// or https:// (got: {0}).").format(base),
			title=_("Signing Agent"),
		)
	return base


def is_local_signing_agent_url(agent_url: str | None) -> bool:
	base = (agent_url or "").strip().lower()
	return "127.0.0.1" in base or "localhost" in base


def signing_agent_health(agent_url: str, timeout: int = 5) -> dict[str, Any]:
	base = normalize_signing_agent_url(agent_url)
	try:
		res = requests.get(f"{base}/health", timeout=timeout)
	except requests.RequestException as exc:
		return {"ok": False, "message": str(exc)}
	try:
		body = res.json()
	except Exception:
		body = {"raw": res.text}
	return {"ok": res.status_code < 400, "status_code": res.status_code, "body": body}


def _signing_check(ok: bool, step: str, message: str) -> dict[str, Any]:
	return {"ok": bool(ok), "step": step, "message": message}


def _connection_hint(agent_url: str) -> str:
	base = (agent_url or "").strip().lower()
	parts = []
	if "127.0.0.1" in base or "localhost" in base:
		if platform.system() == "Windows":
			parts.append(
				_("http://127.0.0.1:5002 on this PC. Start epass2003_agent.py with USB token inserted.")
			)
		else:
			parts.append(
				_(
					"ERP runs on {0}. Open ERP on the Windows PC with the token; agent uses sign_session to fetch PIN."
				).format(platform.system())
			)
	else:
		parts.append(_("Ensure epass2003_agent is reachable at {0}.").format(agent_url))
	return " ".join(parts)


def sign_invoice_via_signing_agent(
	document: dict,
	*,
	agent_url: str,
	pin: str | None = None,
	token_type: str = "epass2003",
	use_chilkat: bool = True,
	verify: bool = False,
	timeout: int = 120,
) -> str:
	"""POST /sign from ERP server (non-browser). Prefer sign_session from the user's PC."""
	base = normalize_signing_agent_url(agent_url)
	url = f"{base}/sign"
	unsigned = json.loads(json.dumps(document, ensure_ascii=False))
	unsigned.pop("signatures", None)
	if not (pin or "").strip():
		frappe.throw(
			_("USB Token PIN is empty. Set Branch → USB Token PIN."),
			exc=ETASigningAgentError,
			title=_("Signing Agent"),
		)
	payload = {
		"invoice": unsigned,
		"pin": (pin or "").strip(),
		"use_chilkat": bool(use_chilkat),
		"token_type": (token_type or "epass2003").strip() or "epass2003",
		"verify": bool(verify),
	}
	try:
		res = requests.post(url, json=payload, timeout=timeout)
	except requests.RequestException as exc:
		frappe.throw(
			_("Cannot reach signing agent at {0}. {1} Error: {2}").format(url, _connection_hint(agent_url), exc),
			exc=ETASigningAgentError,
			title=_("Signing Agent"),
		)
	try:
		body = res.json()
	except Exception:
		body = {}
	if res.status_code >= 400 or not body.get("success"):
		msg = body.get("message") or body.get("error") or (res.text[:500] if res.text else "") or _("Signing failed.")
		frappe.throw(str(msg), exc=ETASigningAgentError, title=_("Signing Agent"))
	signatures = body.get("signatures") or []
	if signatures and isinstance(signatures[0], dict):
		value = (signatures[0].get("value") or "").strip()
		if value:
			return value
	if (body.get("signature") or "").strip():
		return str(body["signature"]).strip()
	frappe.throw(_("Signing agent returned success but no signature."), exc=ETASigningAgentError)


def _prepare_branch_usb_signing_test(branch: str) -> dict[str, Any]:
	"""Server-side config checks + test invoice JSON (no agent HTTP from Linux for localhost)."""
	from omnexa_einvoice.branch_eta import get_eta_invoice_branch_settings

	branch = (branch or "").strip()
	checks: list[dict[str, Any]] = []

	def add(ok: bool, step: str, message: str) -> None:
		checks.append(_signing_check(ok, step, message))

	if not branch:
		add(False, "branch", _("Branch name is required."))
		return {"ok": False, "checks": checks, "browser_signing": False}
	if not frappe.db.exists("Branch", branch):
		add(False, "branch", _("Branch {0} does not exist.").format(branch))
		return {"ok": False, "checks": checks, "browser_signing": False}
	add(True, "branch", _("Branch {0} found.").format(branch))

	if not frappe.db.get_value("Branch", branch, "eta_einvoice_enabled"):
		add(False, "einvoice", _("E-Invoice is not enabled on this branch."))
		return {"ok": False, "checks": checks, "browser_signing": False}
	add(True, "einvoice", _("E-Invoice is enabled."))

	signer_mode = (frappe.db.get_value("Branch", branch, "eta_signer_mode") or "remote").strip().lower()
	if signer_mode not in ("signing_agent", "agent"):
		add(False, "signer_mode", _("Signer mode must be Signing Agent (current: {0}).").format(signer_mode or "—"))
		return {"ok": False, "checks": checks, "browser_signing": False}
	add(True, "signer_mode", _("Signing Agent mode is selected."))

	try:
		settings = get_eta_invoice_branch_settings(branch)
	except Exception as exc:
		add(False, "settings", str(exc))
		return {"ok": False, "checks": checks, "browser_signing": False}

	agent_url = normalize_signing_agent_url(settings.signing_agent_url or DEFAULT_AGENT_URL)
	add(True, "agent_url", agent_url)
	token_type = (settings.usb_token_type or "epass2003").strip() or "epass2003"
	add(True, "token_type", token_type)

	if not branch_usb_pin(branch):
		add(False, "usb_pin", _("USB Token PIN missing on Branch."))
		return {"ok": False, "checks": checks, "browser_signing": True, "agent_url": agent_url}
	add(True, "usb_pin", _("USB Token PIN is saved."))

	if not (settings.rin or "").strip():
		add(False, "rin", _("E-Invoice RIN required on Branch."))
		return {"ok": False, "checks": checks, "browser_signing": True, "agent_url": agent_url}
	add(True, "rin", _("Taxpayer RIN is set."))

	try:
		document = build_usb_signing_test_document(branch)
		validate_invoice_document(document, strict_datetime=False)
		add(True, "test_invoice", _("Valid test invoice ({0}).").format(document["internalID"]))
	except ETAInvoiceValidationError as exc:
		add(False, "test_invoice", str(exc))
		return {"ok": False, "checks": checks, "browser_signing": True, "agent_url": agent_url}

	add(True, "erp_server", _("ERP server OS: {0}").format(platform.system()))
	pin_b64 = base64.b64encode(branch_usb_pin(branch).encode("utf-8")).decode("ascii")

	return {
		"ok": all(c["ok"] for c in checks),
		"checks": checks,
		"browser_signing": True,
		"branch": branch,
		"agent_url": agent_url,
		"token_type": token_type,
		"usb_pin_b64": pin_b64,
		"document": document,
		"internal_id": document.get("internalID"),
	}


@frappe.whitelist()
def prepare_branch_usb_signing_test(branch: str) -> dict[str, Any]:
	return _prepare_branch_usb_signing_test(branch)


@frappe.whitelist()
def run_branch_usb_signing_test_on_server(branch: str) -> dict[str, Any]:
	data = _prepare_branch_usb_signing_test(branch)
	checks = list(data.get("checks") or [])
	if not data.get("ok"):
		return {**data, "checks": checks, "server_only": True, "summary": _("Fix failed checks and Save Branch.")}

	agent_url = data.get("agent_url") or DEFAULT_AGENT_URL
	browser_sign_required = False
	if is_local_signing_agent_url(agent_url) and platform.system() != "Windows":
		checks.append(
			_signing_check(
				True,
				"agent_ping",
				_("Skipped on server — use Windows browser + sign_session. ERP config OK."),
			)
		)
		browser_sign_required = True
	else:
		health = signing_agent_health(agent_url)
		if health.get("ok"):
			checks.append(_signing_check(True, "agent_ping", _("Agent /health OK.")))
		else:
			checks.append(_signing_check(False, "agent_ping", health.get("message") or _("Unreachable")))
			checks.append(_signing_check(True, "agent_hint", _connection_hint(agent_url)))

	all_ok = all(c["ok"] for c in checks)
	summary = _("Server checks passed.")
	if all_ok and browser_sign_required:
		summary = _("Server OK. Complete signing on Windows PC with USB token.")

	return {
		**data,
		"ok": all_ok,
		"checks": checks,
		"server_only": True,
		"browser_sign_required": browser_sign_required,
		"summary": summary,
	}


@frappe.whitelist()
def test_signing_agent_connection(agent_url: str | None = None, branch: str | None = None) -> dict[str, Any]:
	if branch:
		return run_branch_usb_signing_test_on_server(branch)
	url = normalize_signing_agent_url(agent_url or DEFAULT_AGENT_URL)
	if is_local_signing_agent_url(url) and platform.system() != "Windows":
		return {
			"ok": False,
			"agent_url": url,
			"message": _("Pass branch=BRANCH_NAME for server-side test."),
			"hint": _("Branch → Egypt ETA → Test USB Signing"),
		}
	result = signing_agent_health(url)
	result["agent_url"] = url
	result["hint"] = _connection_hint(url) if not result.get("ok") else ""
	return result


@frappe.whitelist()
def report_branch_usb_signing_test_result(
	branch: str, success: bool, message: str = "", signature_length: int = 0
) -> dict[str, Any]:
	frappe.logger("omnexa_einvoice").info(
		"USB test branch=%s ok=%s sig_len=%s %s",
		branch,
		success,
		signature_length,
		(message or "")[:200],
	)
	return {"logged": True}
