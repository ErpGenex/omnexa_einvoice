# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Poland KSeF — FA(2) invoice submit (sandbox mock + live HTTP)."""

from __future__ import annotations

import base64
import json
from typing import Any

import frappe
import requests
from frappe import _

from omnexa_einvoice.tax_engine.countries.country_http_uat import (
	apply_basic_auth,
	apply_bearer,
	connection_test_result,
	post_country_json,
	validate_required_fields,
)
from omnexa_einvoice.tax_engine.country_tax_settings import get_country_tax_settings, get_settings_password
from omnexa_einvoice.tax_engine.plugin.production_mode import allow_mock_api, is_live_production_settings
from omnexa_einvoice.tax_engine.plugin.production_validate import validate_production_settings
from omnexa_einvoice.tax_engine.plugin.specs import CountryPluginSpec


def get_poland_ksef_settings(company: str, *, branch: str | None = None) -> frappe._dict:
	settings = get_country_tax_settings(company, "PL", branch=branch)
	config: dict[str, Any] = {}
	if settings and settings.get("configuration_json"):
		try:
			config = json.loads(settings.configuration_json)
			if not isinstance(config, dict):
				config = {}
		except json.JSONDecodeError:
			config = {}
	return frappe._dict(
		{
			"ksef_base_url": (config.get("ksef_base_url") or (settings.get("api_base_url") if settings else "") or "").strip(),
			"ksef_submit_path": (config.get("ksef_submit_path") or "/api/v2/invoices").strip(),
			"nip": (config.get("nip") or (settings.get("tax_registration_number") if settings else "") or "").strip(),
			"token": get_settings_password(settings, "asp_api_key") if settings else None,
			"client_id": (settings.get("client_id") if settings else "") or "",
			"client_secret": get_settings_password(settings, "client_secret") if settings else None,
			"ksef_private_key_pem": config.get("ksef_private_key_pem") or config.get("signing_private_key_pem") or "",
			"ksef_certificate_pem": config.get("ksef_certificate_pem") or config.get("signing_certificate_pem") or "",
		}
	)


def validate_poland_ksef_for_live(company: str, *, branch: str | None = None) -> None:
	from omnexa_einvoice.tax_engine.countries.country_http_uat import throw_if_missing, validate_required_fields

	ksef = get_poland_ksef_settings(company, branch=branch)
	missing = validate_required_fields(
		{"nip": ksef.nip, "ksef_base_url": ksef.ksef_base_url},
		[("nip", _("nip")), ("ksef_base_url", _("ksef_base_url"))],
	)
	if not ksef.token and not ksef.ksef_private_key_pem:
		missing.append(_("ksef token (asp_api_key) or ksef_private_key_pem"))
	throw_if_missing(missing, title=_("KSeF"))


def _mock_ksef(*, uuid: str, reference: str) -> dict[str, Any]:
	ksef_ref = f"KSEF-{uuid[:12].upper()}"
	return {
		"ok": True,
		"mock": True,
		"status": "ACCEPTED",
		"ksef_number": ksef_ref,
		"uuid": ksef_ref,
		"raw": {"ksefReferenceNumber": ksef_ref, "reference": reference},
		"mode": "mock",
		"framework": "KSeF-FA2",
	}


def submit_ksef_invoice(
	*,
	company: str,
	spec: CountryPluginSpec,
	uuid: str,
	hash_b64: str,
	signed_xml: str,
	document: dict[str, Any] | None = None,
) -> dict[str, Any]:
	branch = (document or {}).get("branch") if document else None
	settings = validate_production_settings(company, "PL", phase="phase2", branch=branch)
	ksef = get_poland_ksef_settings(company, branch=branch)
	reference = (document or {}).get("reference_name") or ""

	if allow_mock_api() or not ksef.ksef_base_url:
		return _mock_ksef(uuid=uuid, reference=reference)

	if is_live_production_settings(settings):
		validate_poland_ksef_for_live(company, branch=branch)

	url = f"{ksef.ksef_base_url.rstrip('/')}{ksef.ksef_submit_path}"
	headers = {"Accept": "application/json", "Content-Type": "application/json"}
	apply_bearer(headers, ksef.token)
	if not headers.get("Authorization"):
		apply_basic_auth(headers, ksef.client_id, ksef.client_secret)

	payload = {
		"uuid": uuid,
		"invoiceHash": hash_b64,
		"invoiceXml": base64.b64encode(signed_xml.encode("utf-8")).decode("ascii"),
		"nip": ksef.nip,
	}
	res = post_country_json(
		country_code="PL",
		url=url,
		headers=headers,
		payload=payload,
		document=document,
		uuid=uuid,
	)

	try:
		body = res.json() if res.text else {}
	except Exception:
		body = {"raw": (res.text or "")[:8000]}

	if res.status_code >= 400:
		frappe.throw(_("KSeF error ({0}): {1}").format(res.status_code, body), title=_("KSeF"))

	ksef_ref = body.get("ksefReferenceNumber") or body.get("referenceNumber") or uuid
	return {
		"ok": True,
		"http_status": res.status_code,
		"status": body.get("status") or "ACCEPTED",
		"ksef_number": ksef_ref,
		"uuid": ksef_ref,
		"raw": body,
		"mode": "live",
		"framework": "KSeF-FA2",
	}


@frappe.whitelist()
def test_poland_ksef_connection(branch: str | None = None, company: str | None = None) -> dict[str, Any]:
	if not branch and company:
		branch = frappe.db.get_value("Branch", {"company": company}, "name")
	if not branch:
		frappe.throw(_("Select a branch."), title=_("KSeF"))
	comp = company or frappe.db.get_value("Branch", branch, "company")
	ksef = get_poland_ksef_settings(comp, branch=branch)
	if not ksef.nip:
		return {"ok": False, "message": _("Set NIP on Branch tax registration or configuration_json.nip.")}
	checklist = validate_required_fields(
		{"ksef_base_url": ksef.ksef_base_url},
		[("ksef_base_url", _("ksef_base_url"))],
	)
	if not ksef.token and not ksef.ksef_private_key_pem:
		checklist.append(_("ksef token or ksef_private_key_pem"))
	mock = _mock_ksef(uuid=frappe.generate_hash(length=10), reference="TEST")
	return connection_test_result(
		allow_mock=allow_mock_api(),
		has_base_url=bool(ksef.ksef_base_url),
		checklist=checklist,
		mock_response={
			"ok": True,
			"message": _("KSeF sandbox OK (mock)."),
			"ksef_number": mock["ksef_number"],
			"mode": "mock",
		},
		base_url=ksef.ksef_base_url,
		ready_label=_("KSeF ready for FA(2) UAT."),
	)
