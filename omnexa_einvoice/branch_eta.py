# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""ETA settings on Branch only — separate e-Receipt vs e-Invoice credentials."""

from __future__ import annotations

import frappe
from frappe import _

from omnexa_einvoice.eta_receipt import ETA_DEFAULT_API_BASE

RECEIPT_KIND = "receipt"
INVOICE_KIND = "invoice"

ETA_ENV_PREPROD = "preprod"
ETA_ENV_PROD = "prod"


def normalize_eta_environment(env: str | None) -> str:
	"""Map Branch environment select value to preprod or prod."""
	value = (env or ETA_ENV_PREPROD).strip().lower()
	if value in {ETA_ENV_PROD, "production", "live", "prod."}:
		return ETA_ENV_PROD
	if value in {ETA_ENV_PREPROD, "test", "staging", "sandbox"}:
		return ETA_ENV_PREPROD
	return ETA_ENV_PREPROD if value not in {ETA_ENV_PROD} else value


def resolve_branch_for_document(doc, user: str | None = None) -> str | None:
	branch = (getattr(doc, "branch", None) or doc.get("branch") or "").strip()
	if branch and frappe.db.exists("Branch", branch):
		return branch
	company = (getattr(doc, "company", None) or doc.get("company") or "").strip()
	if not company:
		return None
	try:
		from omnexa_core.omnexa_core.branch_access import get_default_branch

		return get_default_branch(company, user or frappe.session.user)
	except Exception:
		return frappe.db.get_value("Branch", {"company": company, "status": "Active"}, "name", order_by="is_head_office desc")


def _branch_row(branch: str, fields: list[str]) -> frappe._dict:
	return frappe._dict(frappe.db.get_value("Branch", branch, fields, as_dict=True) or {})


def branch_ereceipt_enabled(branch: str | None) -> bool:
	if not branch:
		return False
	return bool(frappe.db.get_value("Branch", branch, "eta_ereceipt_enabled"))


def branch_einvoice_enabled(branch: str | None) -> bool:
	if not branch:
		return False
	return bool(frappe.db.get_value("Branch", branch, "eta_einvoice_enabled"))


def branch_eta_enabled(branch: str | None) -> bool:
	return branch_ereceipt_enabled(branch) or branch_einvoice_enabled(branch)


def branch_requires_einvoice_before_submit(branch: str | None) -> bool:
	if not branch:
		return False
	return bool(frappe.db.get_value("Branch", branch, "eta_require_einvoice_before_si_submit"))


def _password_from_branch(branch: str, fieldname: str) -> str:
	"""Read Frappe Password field — never use masked ``****`` values from SQL."""
	if not branch or not fieldname:
		return ""
	try:
		secret = (
			frappe.get_doc("Branch", branch).get_password(fieldname, raise_exception=False) or ""
		).strip()
	except Exception:
		secret = ""
	if secret and not _is_masked_secret(secret):
		return secret
	return ""


def _is_masked_secret(value: str | None) -> bool:
	"""Detect placeholder/masked secrets stored in DB instead of real credentials."""
	text = (value or "").strip()
	if not text:
		return True
	if set(text) <= {"*"}:
		return True
	if text in ("***", "********", "************"):
		return True
	return False


def _branch_secret(branch: str, fieldname: str, row_value: str | None = None) -> str:
	secret = _password_from_branch(branch, fieldname)
	if secret:
		return secret
	# Only accept row_value when it is not a Frappe password mask from get_value()
	candidate = (row_value or "").strip()
	if candidate and not _is_masked_secret(candidate):
		return candidate
	return ""


def _resolve_base_url(env: str, explicit_url: str | None) -> str:
	base_url = (explicit_url or "").strip().rstrip("/")
	if base_url:
		return base_url
	return ETA_DEFAULT_API_BASE.get((env or "preprod").strip(), ETA_DEFAULT_API_BASE["preprod"])


def branch_eta_is_configured(branch: str, kind: str = RECEIPT_KIND) -> bool:
	if kind == RECEIPT_KIND:
		if not branch_ereceipt_enabled(branch):
			return False
		row = _branch_row(
			branch,
			["eta_receipt_rin", "eta_receipt_client_id", "eta_receipt_client_secret", "eta_pos_device_serial"],
		)
		secret = _branch_secret(branch, "eta_receipt_client_secret", row.get("eta_receipt_client_secret"))
		return bool(
			(row.get("eta_receipt_rin") or "").strip()
			and (row.get("eta_receipt_client_id") or "").strip()
			and secret
			and (row.get("eta_pos_device_serial") or "").strip()
		)

	if not branch_einvoice_enabled(branch):
		return False
	row = _branch_row(branch, ["eta_invoice_rin", "eta_invoice_client_id", "eta_invoice_client_secret"])
	secret = _branch_secret(branch, "eta_invoice_client_secret", row.get("eta_invoice_client_secret"))
	return bool(
		(row.get("eta_invoice_rin") or "").strip()
		and (row.get("eta_invoice_client_id") or "").strip()
		and secret
	)


def get_eta_receipt_branch_settings(branch: str) -> frappe._dict:
	"""Settings for e-Receipt (POS) — own Client ID / Secret."""
	branch = (branch or "").strip()
	if not branch or not frappe.db.exists("Branch", branch):
		frappe.throw(_("Branch {0} does not exist.").format(branch), title=_("ETA"))
	if not branch_ereceipt_enabled(branch):
		frappe.throw(
			_("E-Receipt is not enabled on branch {0}. Enable it under Branch → Egypt ETA.").format(branch),
			title=_("E-Receipt"),
		)

	fields = [
		"company",
		"branch_code",
		"branch_name",
		"eta_receipt_environment",
		"eta_receipt_base_url",
		"eta_receipt_client_id",
		"eta_receipt_client_secret",
		"eta_receipt_rin",
		"eta_activity_code",
		"eta_company_trade_name",
		"eta_branch_code",
		"eta_pos_device_serial",
		"eta_pos_os_version",
		"eta_pos_model_framework",
		"eta_pos_preshared_key",
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
	]
	row = _branch_row(branch, fields)
	company = row.get("company")
	env = normalize_eta_environment(row.get("eta_receipt_environment"))
	base_url = _resolve_base_url(env, row.get("eta_receipt_base_url"))
	if env == ETA_ENV_PROD and "preprod" in base_url.lower():
		frappe.throw(
			_("E-Receipt API URL must be production ({0}), not preprod.").format(
				ETA_DEFAULT_API_BASE[ETA_ENV_PROD]
			),
			title=_("E-Receipt"),
		)
	rin = (row.get("eta_receipt_rin") or "").strip()
	trade_name = (row.get("eta_company_trade_name") or row.get("branch_name") or "").strip()
	if not trade_name and company:
		trade_name = frappe.db.get_value("Company", company, "company_name") or company

	return frappe._dict(
		{
			"branch": branch,
			"company": company,
			"kind": RECEIPT_KIND,
			"rin": rin,
			"company_trade_name": trade_name,
			"branch_code": (row.get("eta_branch_code") or row.get("branch_code") or "0").strip(),
			"activity_code": (row.get("eta_activity_code") or "4620").strip(),
			"device_serial_number": (row.get("eta_pos_device_serial") or "").strip(),
			"pos_os_version": (row.get("eta_pos_os_version") or "").strip(),
			"pos_model_framework": (row.get("eta_pos_model_framework") or "1").strip(),
			"pos_preshared_key": _branch_secret(branch, "eta_pos_preshared_key", row.get("eta_pos_preshared_key")),
			"eta_environment": env,
			"eta_base_url": base_url,
			"eta_client_id": row.get("eta_receipt_client_id"),
			"eta_client_secret": _branch_secret(branch, "eta_receipt_client_secret", row.get("eta_receipt_client_secret")),
			"address": {
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


def get_eta_invoice_branch_settings(branch: str) -> frappe._dict:
	"""Settings for e-Invoice — own Client ID / Secret + signing."""
	branch = (branch or "").strip()
	if not branch or not frappe.db.exists("Branch", branch):
		frappe.throw(_("Branch {0} does not exist.").format(branch), title=_("ETA"))
	if not branch_einvoice_enabled(branch):
		frappe.throw(
			_("E-Invoice is not enabled on branch {0}. Enable it under Branch → Egypt ETA.").format(branch),
			title=_("E-Invoice"),
		)

	fields = [
		"company",
		"branch_name",
		"eta_invoice_environment",
		"eta_invoice_base_url",
		"eta_invoice_client_id",
		"eta_invoice_client_secret",
		"eta_invoice_rin",
		"eta_signer_mode",
		"eta_signing_secret",
		"eta_signing_agent_url",
		"eta_usb_token_type",
		"eta_usb_signing_pin",
		"eta_windows_signer_command",
		"eta_certificate_reference",
		"eta_einvoice_submission_mode",
		"eta_einvoice_batch_size",
		"eta_einvoice_send_delay_hours",
	]
	row = _branch_row(branch, fields)
	env = normalize_eta_environment(row.get("eta_invoice_environment"))
	base_url = _resolve_base_url(env, row.get("eta_invoice_base_url"))

	return frappe._dict(
		{
			"branch": branch,
			"company": row.get("company"),
			"kind": INVOICE_KIND,
			"rin": (row.get("eta_invoice_rin") or "").strip(),
			"eta_environment": env,
			"eta_base_url": base_url,
			"eta_client_id": row.get("eta_invoice_client_id"),
			"eta_client_secret": _branch_secret(branch, "eta_invoice_client_secret", row.get("eta_invoice_client_secret")),
			"signer_mode": (row.get("eta_signer_mode") or "remote").strip().lower(),
			"signing_secret": row.get("eta_signing_secret") or _password_from_branch(branch, "eta_signing_secret"),
			"signing_agent_url": (row.get("eta_signing_agent_url") or "").strip(),
			"usb_token_type": (row.get("eta_usb_token_type") or "epass2003").strip(),
			"usb_signing_pin": _password_from_branch(branch, "eta_usb_signing_pin"),
			"windows_signer_command": row.get("eta_windows_signer_command"),
			"certificate_reference": row.get("eta_certificate_reference"),
			"require_einvoice_before_si_submit": int(
				frappe.db.get_value("Branch", branch, "eta_require_einvoice_before_si_submit") or 0
			),
			"submission_mode": (row.get("eta_einvoice_submission_mode") or "Manual").strip(),
			"batch_size": int(row.get("eta_einvoice_batch_size") or 10),
			"send_delay_hours": float(row.get("eta_einvoice_send_delay_hours") or 0),
		}
	)


def get_eta_branch_settings(branch: str, kind: str = RECEIPT_KIND) -> frappe._dict:
	if kind == INVOICE_KIND:
		return get_eta_invoice_branch_settings(branch)
	return get_eta_receipt_branch_settings(branch)


def get_branch_eta_credentials(branch: str, kind: str = RECEIPT_KIND) -> dict:
	settings = get_eta_branch_settings(branch, kind=kind)
	credentials = {
		"client_id": (settings.eta_client_id or "").strip(),
		"client_secret": (settings.eta_client_secret or "").strip(),
		"environment": (settings.eta_environment or "preprod").strip(),
	}
	if kind == RECEIPT_KIND:
		pos_os = (settings.pos_os_version or "").strip()
		if not pos_os:
			pos_os = "windows" if credentials["environment"] == ETA_ENV_PROD else "os"
		# Token headers match Temp-ETR / PowerBuilder: posserial, pososversion, presharedkey only.
		# Do NOT send posmodelframework on /connect/token — ETA returns unauthorized_client.
		credentials["pos_headers"] = {
			"posserial": (settings.device_serial_number or "").strip(),
			"pososversion": pos_os,
			"presharedkey": (settings.pos_preshared_key or "").strip(),
		}
		if not credentials["pos_headers"]["posserial"]:
			frappe.throw(
				_("POS Device Serial is required on Branch {0} for e-Receipt authentication.").format(branch),
				title=_("E-Receipt"),
			)
	return credentials


def validate_branch_eta_settings(doc, method=None) -> None:
	"""Branch.validate — separate checks for e-Receipt and e-Invoice."""
	if int(doc.get("eta_ereceipt_enabled") or 0):
		receipt_env = normalize_eta_environment(doc.eta_receipt_environment)
		if receipt_env == ETA_ENV_PROD:
			base = (doc.eta_receipt_base_url or "").strip()
			if base and "preprod" in base.lower():
				frappe.throw(
					_("Production e-Receipt cannot use a preprod API URL."),
					title=_("E-Receipt"),
				)
			if not base:
				doc.eta_receipt_base_url = ETA_DEFAULT_API_BASE[ETA_ENV_PROD]
		secret = _branch_secret(doc.name, "eta_receipt_client_secret", doc.eta_receipt_client_secret) if doc.name else ""
		if not secret and (doc.eta_receipt_client_secret or "").strip() and not doc.is_new():
			frappe.throw(
				_("E-Receipt: re-enter Client Secret and save (masked value cannot be used for ETA)."),
				title=_("E-Receipt"),
			)
		if not doc.is_new() and not (doc.eta_receipt_client_secret or "").strip():
			secret = (doc.get_password("eta_receipt_client_secret", raise_exception=False) or secret or "").strip()
		if not (doc.eta_receipt_rin or "").strip():
			frappe.throw(_("E-Receipt: Taxpayer RIN is required."), title=_("E-Receipt"))
		if not (doc.eta_receipt_client_id or "").strip() or not secret:
			frappe.throw(_("E-Receipt: Client ID and Client Secret are required."), title=_("E-Receipt"))
		if not (doc.eta_pos_device_serial or "").strip():
			frappe.throw(_("E-Receipt: POS Device Serial is required."), title=_("E-Receipt"))
		if not (doc.eta_activity_code or "").strip():
			frappe.throw(_("E-Receipt: Activity Code is required."), title=_("E-Receipt"))
		if not (doc.eta_branch_code or "").strip() and doc.branch_code:
			doc.eta_branch_code = doc.branch_code

	if int(doc.get("eta_einvoice_enabled") or 0):
		secret = _branch_secret(doc.name, "eta_invoice_client_secret", doc.eta_invoice_client_secret) if doc.name else ""
		if not secret and not doc.is_new():
			secret = (doc.get_password("eta_invoice_client_secret", raise_exception=False) or "").strip()
			if _is_masked_secret(secret):
				secret = ""
		if not secret and (doc.eta_invoice_client_secret or "").strip() and not doc.is_new():
			frappe.throw(
				_("E-Invoice: re-enter Client Secret and save (masked value cannot be used for ETA)."),
				title=_("E-Invoice"),
			)
		if not (doc.eta_invoice_rin or "").strip():
			frappe.throw(_("E-Invoice: Taxpayer RIN is required."), title=_("E-Invoice"))
		if not (doc.eta_invoice_client_id or "").strip() or not secret:
			frappe.throw(_("E-Invoice: Client ID and Client Secret are required."), title=_("E-Invoice"))
		mode = (doc.eta_signer_mode or "remote").strip().lower()
		if mode in ("signing_agent", "windows_app"):
			if not doc.is_new():
				pin_ok = bool((doc.get_password("eta_usb_signing_pin", raise_exception=False) or "").strip())
				if not pin_ok and not (doc.eta_usb_signing_pin or "").strip():
					frappe.throw(
						_("E-Invoice: USB Token PIN is required on Branch (Egypt ETA → USB Token PIN)."),
						title=_("E-Invoice"),
					)
		if mode == "signing_agent":
			url = (doc.eta_signing_agent_url or "").strip().lower()
			if not url:
				frappe.throw(_("E-Invoice: Signing Agent URL is required."), title=_("E-Invoice"))
		if mode == "windows_app" and not (doc.eta_windows_signer_command or "").strip():
			frappe.throw(_("E-Invoice: Windows Signer Command is required for USB mode."), title=_("E-Invoice"))
		if mode == "windows_app" and not (doc.eta_certificate_reference or "").strip():
			frappe.throw(_("E-Invoice: Certificate / Token Reference is required."), title=_("E-Invoice"))
