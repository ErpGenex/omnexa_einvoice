# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Spain AEAT / FACe — Facturae submit (sandbox mock + live HTTP)."""

from __future__ import annotations

import base64
import json
from typing import Any

import frappe
import requests
from frappe import _

from omnexa_einvoice.tax_engine.countries._eu_authority_uat import validate_eu_client_for_live
from omnexa_einvoice.tax_engine.countries.country_http_uat import (
	apply_basic_auth,
	connection_test_result,
	post_country_json,
	validate_required_fields,
)
from omnexa_einvoice.tax_engine.country_tax_settings import get_country_tax_settings, get_settings_password
from omnexa_einvoice.tax_engine.plugin.production_mode import allow_mock_api, is_live_production_settings
from omnexa_einvoice.tax_engine.plugin.production_validate import validate_production_settings
from omnexa_einvoice.tax_engine.plugin.specs import CountryPluginSpec


def get_spain_aeat_settings(company: str, *, branch: str | None = None) -> frappe._dict:
	settings = get_country_tax_settings(company, "ES", branch=branch)
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
			"aeat_base_url": (config.get("aeat_base_url") or (settings.get("api_base_url") if settings else "") or "").strip(),
			"aeat_submit_path": (config.get("aeat_submit_path") or "/facturae/v1/submit").strip(),
			"nif": (config.get("nif") or (settings.get("tax_registration_number") if settings else "") or "").strip(),
			"client_id": (settings.get("client_id") if settings else "") or "",
			"client_secret": get_settings_password(settings, "client_secret") if settings else None}
	)


def _mock_aeat(*, uuid: str, reference: str) -> dict[str, Any]:
	registro = f"ES-{uuid[:12].upper()}"
	return {
		"ok": True,
		"mock": True,
		"status": "ACCEPTED",
		"registro_id": registro,
		"uuid": registro,
		"raw": {"registroId": registro, "reference": reference
	},
		"mode": "mock",
		"framework": "Facturae"
	}


def submit_facturae_aeat(
	*,
	company: str,
	spec: CountryPluginSpec,
	uuid: str,
	hash_b64: str,
	signed_xml: str,
	document: dict[str, Any] | None = None,
) -> dict[str, Any]:
	branch = (document or {}).get("branch") if document else None
	settings = validate_production_settings(company, "ES", phase="phase2", branch=branch)
	cfg = get_spain_aeat_settings(company, branch=branch)
	reference = (document or {}).get("reference_name") or ""

	if allow_mock_api() or not cfg.aeat_base_url:
		return _mock_aeat(uuid=uuid, reference=reference)

	if is_live_production_settings(settings):
		validate_eu_client_for_live(
			cfg,
			title=_("Spain AEAT"),
			tax_field="nif",
			tax_label=_("nif"),
			url_field="aeat_base_url",
			url_label=_("aeat_base_url"),
		)

	url = f"{cfg.aeat_base_url.rstrip('/')}{cfg.aeat_submit_path}"
	headers = {"Accept": "application/json", "Content-Type": "application/json"
	}
	apply_basic_auth(headers, cfg.client_id, cfg.client_secret)

	payload = {
		"uuid": uuid,
		"invoiceHash": hash_b64,
		"xml": base64.b64encode(signed_xml.encode("utf-8")).decode("ascii"),
		"nif": cfg.nif
	}
	res = post_country_json(
		country_code="ES",
		url=url,
		headers=headers,
		payload=payload,
		document=document,
		uuid=uuid,
	)

	try:
		body = res.json() if res.text else {}
	except Exception:
		body = {"raw": (res.text or "")[:8000]
	}

	if res.status_code >= 400:
		frappe.throw(_("Spain AEAT error ({0}): {1}").format(res.status_code, body), title=_("Spain AEAT"))

	registro = body.get("registroId") or body.get("id") or uuid
	return {
		"ok": True,
		"http_status": res.status_code,
		"status": body.get("status") or "ACCEPTED",
		"registro_id": registro,
		"uuid": registro,
		"raw": body,
		"mode": "live",
		"framework": "Facturae"
	}


@frappe.whitelist()
def test_spain_aeat_connection(branch: str | None = None, company: str | None = None) -> dict[str, Any]:
	if not branch and company:
		branch = frappe.db.get_value("Branch", {"company": company
	}, "name")
	if not branch:
		frappe.throw(_("Select a branch."), title=_("Spain AEAT"))
	comp = company or frappe.db.get_value("Branch", branch, "company")
	cfg = get_spain_aeat_settings(comp, branch=branch)
	if not cfg.nif:
		return {"ok": False, "message": _("Set NIF on tax registration or configuration_json.nif.")
	}
	checklist = validate_required_fields(
		{"aeat_base_url": cfg.aeat_base_url
	},
		[("aeat_base_url", _("aeat_base_url"))],
	)
	mock = _mock_aeat(uuid=frappe.generate_hash(length=10), reference="TEST")
	return connection_test_result(
		allow_mock=allow_mock_api(),
		has_base_url=bool(cfg.aeat_base_url),
		checklist=checklist,
		mock_response={
			"ok": True,
			"message": _("Spain AEAT sandbox OK (mock)."),
			"registro_id": mock["registro_id"],
			"mode": "mock"
	},
		base_url=cfg.aeat_base_url,
		ready_label=_("AEAT / VeriFactu UAT ready."),
	)
