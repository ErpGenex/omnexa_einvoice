# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""HTTP client for local ETA USB signing agents (ePass2003 / sign_agent on port 5002)."""

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

DEFAULT_SIGNING_AGENT_URL = "http://127.0.0.1:5002"


class ETASigningAgentError(frappe.ValidationError):
	pass


def normalize_signing_agent_url(url: str | None) -> str:
	base = (url or DEFAULT_SIGNING_AGENT_URL).strip().rstrip("/")
	if not base.startswith(("http://", "https://")):
		frappe.throw(
			_("Signing Agent URL must start with http:// or https:// (got: {0}).").format(base),
			title=_("Signing Agent"),
		)
	return base


def signing_agent_health(agent_url: str, timeout: int = 5) -> dict[str, Any]:
	"""GET /health — optional preflight before sign."""
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
	"""
	POST /sign with full ETA invoice JSON (unsigned).
	Matches Docs/USB/epass2003_agent.py and sign_agent.py.
	"""
	base = normalize_signing_agent_url(agent_url)
	url = f"{base}/sign"
	unsigned = json.loads(json.dumps(document, ensure_ascii=False))
	unsigned.pop("signatures", None)

	if not (pin or "").strip():
		frappe.throw(
			_("USB Token PIN is empty. Set Branch → USB Token PIN (E-Invoice signing)."),
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
		hint = _signing_agent_connection_hint(agent_url)
		frappe.throw(
			_("Cannot reach signing agent at {0}. {1} Error: {2}").format(url, hint, exc),
			exc=ETASigningAgentError,
			title=_("Signing Agent"),
		)

	try:
		body = res.json()
	except Exception:
		body = {}

	if res.status_code >= 400 or not body.get("success"):
		msg = (
			body.get("message")
			or body.get("error")
			or (res.text[:500] if res.text else "")
			or _("Signing agent rejected the request.")
		)
		frappe.throw(str(msg), exc=ETASigningAgentError, title=_("Signing Agent"))

	signatures = body.get("signatures") or []
	if signatures and isinstance(signatures[0], dict):
		value = (signatures[0].get("value") or "").strip()
		if value:
			return value

	if (body.get("signature") or "").strip():
		return str(body["signature"]).strip()

	frappe.throw(_("Signing agent returned success but no signature value."), exc=ETASigningAgentError)


def is_local_signing_agent_url(agent_url: str | None) -> bool:
	"""True when URL points at loopback (agent on the user's PC, not the ERP server)."""
	base = (agent_url or "").strip().lower()
	return "127.0.0.1" in base or "localhost" in base


def _signing_agent_connection_hint(agent_url: str) -> str:
	"""Extra guidance when the signing agent is unreachable."""
	import platform

	base = (agent_url or "").strip().lower()
	parts = []
	is_local = "127.0.0.1" in base or "localhost" in base
	erp_os = platform.system()

	if is_local:
		if erp_os == "Windows":
			parts.append(
				_(
					"http://127.0.0.1:5002 is correct when bench and epass2003_agent run on this Windows PC "
					"(same as Temp-ETR). Start epass2003_agent.py on port 5002."
				)
			)
		else:
			parts.append(
				_(
					"ERP (bench) runs on {0}: 127.0.0.1 refers to this server, not your browser PC. "
					"Either run bench on the Windows PC with the USB token and use http://127.0.0.1:5002, "
					"or set Signing Agent URL to http://TOKEN_PC_IP:5002 and AGENT_HOST=0.0.0.0 on that PC."
				).format(erp_os)
			)
	else:
		parts.append(
			_("Ensure epass2003_agent is running and reachable from this ERP server at {0}.").format(
				agent_url
			)
		)

	try:
		import socket

		host = socket.gethostname()
		lan = socket.gethostbyname(host)
		if lan and lan not in ("127.0.0.1", "127.0.1.1"):
			parts.append(_("ERP server: {0} ({1}).").format(host, lan))
	except Exception:
		pass
	return " ".join(parts)


@frappe.whitelist()
def test_signing_agent_connection(agent_url: str | None = None, branch: str | None = None) -> dict[str, Any]:
	"""Run server-side branch signing checks (same as Test USB Signing on Branch)."""
	if branch:
		return run_branch_usb_signing_test_on_server(branch)

	if not agent_url:
		agent_url = DEFAULT_SIGNING_AGENT_URL
	url = normalize_signing_agent_url(agent_url)

	if is_local_signing_agent_url(url) and platform.system() != "Windows":
		return {
			"ok": False,
			"agent_url": url,
			"message": _("Pass branch=BRANCH_NAME for a full server-side test."),
			"hint": _(
				"Use Branch → Egypt ETA → “Test USB Signing”, or: "
				"bench execute omnexa_einvoice.eta_signing_agent.run_branch_usb_signing_test_on_server "
				"--kwargs '{\"branch\": \"YOUR_BRANCH\"}'"
			),
		}

	result = signing_agent_health(url)
	result["agent_url"] = url
	result["hint"] = _signing_agent_connection_hint(url) if not result.get("ok") else ""
	return result


def _signing_check(ok: bool, step: str, message: str) -> dict[str, Any]:
	return {"ok": bool(ok), "step": step, "message": message}


def _branch_usb_pin_b64(branch: str) -> str:
	from omnexa_einvoice.branch_eta import get_eta_invoice_branch_settings

	raw = (get_eta_invoice_branch_settings(branch).usb_signing_pin or "").strip()
	if not raw:
		return ""
	return base64.b64encode(raw.encode("utf-8")).decode("ascii")


def _prepare_branch_usb_signing_test_data(branch: str) -> dict[str, Any]:
	"""Shared branch checks + test invoice (no HTTP to signing agent)."""
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
		add(
			False,
			"signer_mode",
			_("Signer mode must be “Signing Agent” (current: {0}).").format(signer_mode or "—"),
		)
		return {"ok": False, "checks": checks, "browser_signing": False, "signer_mode": signer_mode}
	add(True, "signer_mode", _("Signing Agent mode is selected."))

	try:
		from omnexa_einvoice.branch_eta import get_eta_invoice_branch_settings

		settings = get_eta_invoice_branch_settings(branch)
	except Exception as exc:
		add(False, "settings", str(exc))
		return {"ok": False, "checks": checks, "browser_signing": False}

	agent_url = normalize_signing_agent_url(settings.signing_agent_url or DEFAULT_SIGNING_AGENT_URL)
	add(True, "agent_url", agent_url)

	token_type = (settings.usb_token_type or "epass2003").strip() or "epass2003"
	add(True, "token_type", token_type)

	pin_b64 = _branch_usb_pin_b64(branch)
	if not pin_b64:
		add(
			False,
			"usb_pin",
			_("USB Token PIN is missing. Enter it under USB Token PIN, Save, then run the test again."),
		)
		return {
			"ok": False,
			"checks": checks,
			"browser_signing": True,
			"agent_url": agent_url,
			"token_type": token_type,
		}
	add(True, "usb_pin", _("USB Token PIN is saved on the branch."))

	if not (settings.rin or "").strip():
		add(False, "rin", _("E-Invoice Taxpayer RIN is required on the branch."))
		return {"ok": False, "checks": checks, "browser_signing": True, "agent_url": agent_url}
	add(True, "rin", _("Taxpayer RIN is set."))

	try:
		document = build_usb_signing_test_document(branch)
		validate_invoice_document(document, strict_datetime=False)
		add(True, "test_invoice", _("Test invoice JSON is valid (internalID: {0}).").format(document["internalID"]))
	except ETAInvoiceValidationError as exc:
		add(False, "test_invoice", str(exc))
		return {"ok": False, "checks": checks, "browser_signing": True, "agent_url": agent_url}
	except Exception as exc:
		add(False, "test_invoice", str(exc))
		return {"ok": False, "checks": checks, "browser_signing": True, "agent_url": agent_url}

	erp_os = platform.system()
	add(True, "erp_server", _("ERP server OS: {0}").format(erp_os))

	all_ok = all(c["ok"] for c in checks)
	return {
		"ok": all_ok,
		"checks": checks,
		"browser_signing": True,
		"branch": branch,
		"agent_url": agent_url,
		"token_type": token_type,
		"usb_pin_b64": pin_b64,
		"signing_secret_b64": pin_b64,
		"has_signing_secret": bool(pin_b64),
		"document": document,
		"internal_id": document.get("internalID"),
		"signer_mode": signer_mode,
	}


@frappe.whitelist()
def prepare_branch_usb_signing_test(branch: str) -> dict[str, Any]:
	"""Server checks + payload for browser → local signing agent (E-Invoice only)."""
	return _prepare_branch_usb_signing_test_data(branch)


@frappe.whitelist()
def run_branch_usb_signing_test_on_server(branch: str) -> dict[str, Any]:
	"""
	Full signing configuration test runnable from ERP on Linux (bench / Branch form).
	Does not call http://127.0.0.1 on the server when that URL is the Windows token PC.
	"""
	data = _prepare_branch_usb_signing_test_data(branch)
	checks: list[dict[str, Any]] = list(data.get("checks") or [])
	if not data.get("ok"):
		return {
			**data,
			"checks": checks,
			"server_only": True,
			"summary": _("Fix failed checks, Save the branch, then run the test again."),
		}

	agent_url = data.get("agent_url") or DEFAULT_SIGNING_AGENT_URL
	erp_os = platform.system()
	browser_sign_required = False
	agent_reachable = None

	if is_local_signing_agent_url(agent_url) and erp_os != "Windows":
		checks.append(
			_signing_check(
				True,
				"agent_ping",
				_(
					"Skipped from ERP server: {0} is the Windows PC with the USB token, not this Linux server. "
					"Configuration on ERP is OK."
				).format(agent_url),
			)
		)
		browser_sign_required = True
	else:
		health = signing_agent_health(agent_url)
		agent_reachable = bool(health.get("ok"))
		if agent_reachable:
			checks.append(
				_signing_check(True, "agent_ping", _("Agent /health OK at {0}").format(agent_url))
			)
		else:
			msg = health.get("message") or _("Agent not reachable from ERP server.")
			checks.append(_signing_check(False, "agent_ping", msg))
			checks.append(
				_signing_check(
					True,
					"agent_hint",
					_signing_agent_connection_hint(agent_url),
				)
			)

	all_ok = all(c["ok"] for c in checks)
	summary = ""
	if all_ok and browser_sign_required:
		summary = _(
			"Server checks passed. To verify USB signing, open ERP on the Windows PC with the token "
			"and click “Test USB Signing” again (or sign an E-Invoice Submission)."
		)
	elif all_ok:
		summary = _("All server checks passed, including signing agent /health.")
	elif not all_ok:
		summary = _("One or more checks failed — see details below.")

	return {
		**data,
		"ok": all_ok,
		"checks": checks,
		"server_only": True,
		"browser_sign_required": browser_sign_required,
		"agent_reachable": agent_reachable,
		"summary": summary,
	}


@frappe.whitelist()
def report_branch_usb_signing_test_result(
	branch: str,
	success: bool,
	message: str = "",
	signature_length: int = 0,
) -> dict[str, Any]:
	"""Optional audit log after client-side USB signing test."""
	frappe.logger("omnexa_einvoice").info(
		"Branch USB signing test branch=%s success=%s sig_len=%s msg=%s",
		branch,
		success,
		signature_length,
		(message or "")[:200],
	)
	return {"logged": True}
