# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Submit PINT AE UBL to Accredited Service Provider (ASP) API."""

from __future__ import annotations

import base64
from typing import Any

import frappe
import requests
from frappe import _

from omnexa_einvoice.tax_engine.plugin.http_retry import build_idempotency_key, post_json_with_retry
from omnexa_einvoice.tax_engine.plugin.production_mode import allow_mock_api, is_live_production_settings
from omnexa_einvoice.tax_engine.plugin.production_validate import validate_production_settings
from omnexa_einvoice.uae.pint_signer import validate_asp_config
from omnexa_einvoice.uae.settings import parse_uae_config, uae_effective_settings


def validate_uae_asp_for_live(company: str, *, branch: str | None = None) -> None:
	settings = uae_effective_settings(company, branch=branch)
	cfg = parse_uae_config(settings)
	cfg["api_base_url"] = settings.api_base_url or ""
	cfg["peppol_sender_id"] = settings.peppol_sender_id or ""
	cfg["seller_tin"] = settings.seller_tin or ""
	missing = validate_asp_config(cfg, settings)
	if missing:
		frappe.throw(
			_("UAE live ASP requires: {0}").format(", ".join(missing)),
			title=_("UAE e-Invoice"),
		)


def submit_to_asp(
	*,
	company: str,
	uuid: str,
	hash_b64: str,
	signed_xml: str,
	document: dict[str, Any],
) -> dict[str, Any]:
	branch = document.get("branch") if document else None
	validate_production_settings(company, "AE", phase="phase2", branch=branch)
	settings = uae_effective_settings(company, branch=branch)

	base = (settings.api_base_url or "").strip().rstrip("/")
	path = settings.asp_submit_path or "/einvoice/v1/submit"
	if not base:
		if allow_mock_api():
			asp_ref = f"AE-ASP-{uuid[:12].upper()}" if uuid else "AE-ASP-MOCK"
			return {
				"ok": True,
				"mock": True,
				"status": "ACCEPTED",
				"authority": "UAE_PEPPOL",
				"uuid": asp_ref,
				"asp_reference": asp_ref,
				"peppol_sender": settings.peppol_sender_id,
			}
		frappe.throw(_("API Base URL missing on Country Tax Settings (UAE)."), title=_("UAE e-Invoice"))

	if is_live_production_settings(settings):
		validate_uae_asp_for_live(company, branch=branch)

	url = f"{base}{path}"
	headers = {"Accept": "application/json", "Content-Type": "application/json"}
	client_id = settings.client_id or ""
	secret = ""
	if settings.get("name"):
		try:
			doc = frappe.get_doc("Country Tax Settings", settings.name)
			secret = doc.get_password("client_secret", raise_exception=False) or ""
		except Exception:
			pass
	if client_id and secret:
		token = base64.b64encode(f"{client_id}:{secret}".encode()).decode("ascii")
		headers["Authorization"] = f"Basic {token}"

	buyer = document.get("buyer") or {}
	payload = {
		"country": "AE",
		"framework": "PINT-AE",
		"uuid": uuid,
		"invoiceHash": hash_b64,
		"invoice": base64.b64encode(signed_xml.encode("utf-8")).decode("ascii"),
		"senderParticipantId": settings.peppol_sender_id,
		"receiverParticipantId": settings.peppol_receiver_id or buyer.get("peppol_id") or "",
		"sellerTin": settings.seller_tin,
		"buyerTin": buyer.get("tax_registration") or "",
		"invoiceNumber": document.get("reference_name") or "",
		"customizationId": settings.customization_id,
		"profileId": settings.profile_id,
	}
	idem = build_idempotency_key(country_code="AE", uuid=uuid, document=document)
	headers["Idempotency-Key"] = idem
	timeout = int(frappe.conf.get("tax_plugin_api_timeout") or 120)
	max_retries = int(frappe.conf.get("tax_plugin_max_retries") or 2)
	res = post_json_with_retry(
		url,
		headers=headers,
		payload=payload,
		timeout=timeout,
		max_retries=max_retries,
	)

	try:
		body = res.json() if res.text else {}
	except Exception:
		body = {"raw": (res.text or "")[:4000]}

	if res.status_code >= 400:
		frappe.throw(_("UAE ASP error ({0}): {1}").format(res.status_code, body), title=_("UAE e-Invoice"))

	asp_ref = body.get("reference") or body.get("documentId") or uuid
	return {
		"ok": True,
		"http_status": res.status_code,
		"raw": body,
		"status": body.get("status") or body.get("documentStatus") or "ACCEPTED",
		"uuid": asp_ref,
		"asp_reference": asp_ref,
	}


@frappe.whitelist()
def test_uae_asp_connection(branch: str | None = None, company: str | None = None) -> dict[str, Any]:
	if not branch and company:
		branch = frappe.db.get_value("Branch", {"company": company}, "name")
	if not branch:
		frappe.throw(_("Select a branch."), title=_("UAE ASP"))
	comp = company or frappe.db.get_value("Branch", branch, "company")
	settings = uae_effective_settings(comp, branch=branch)
	if not settings.seller_tin and not settings.get("tax_registration_number"):
		return {
			"ok": False,
			"message": _("Set UAE seller TIN / tax registration on Branch Country Tax tab."),
		}
	base = (settings.api_base_url or "").strip()
	cfg = parse_uae_config(settings)
	cfg["api_base_url"] = base
	cfg["peppol_sender_id"] = settings.peppol_sender_id or ""
	cfg["seller_tin"] = settings.seller_tin or ""
	checklist = validate_asp_config(cfg, settings)
	if allow_mock_api() or not base:
		asp_ref = f"AE-ASP-{frappe.generate_hash(length=10).upper()}"
		return {
			"ok": True,
			"message": _("UAE ASP sandbox OK (mock)."),
			"asp_reference": asp_ref,
			"mode": "mock",
			"asp_ready": not checklist,
			"checklist": checklist or [_("Optional for mock: ASP URL + signing key before accredited ASP UAT.")],
		}
	if checklist:
		return {
			"ok": False,
			"message": _("Complete UAE ASP / Peppol settings before live submit."),
			"checklist": checklist,
		}
	try:
		res = requests.get(base.rstrip("/"), timeout=30)
		return {
			"ok": res.status_code < 500,
			"message": _("ASP URL reachable ({0}). Signing key present — ready for ASP UAT.").format(
				res.status_code
			),
			"asp_ready": True,
		}
	except requests.RequestException as exc:
		return {"ok": False, "message": str(exc), "checklist": checklist}
