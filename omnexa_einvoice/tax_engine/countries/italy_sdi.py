# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Italy SDI — FatturaPA submit (sandbox mock + live HTTP)."""

from __future__ import annotations

import base64
import json
from typing import Any

import frappe
import requests
from frappe import _

from omnexa_einvoice.tax_engine.countries.country_http_uat import (
	apply_basic_auth,
	connection_test_result,
	post_country_json,
)
from omnexa_einvoice.tax_engine.country_tax_settings import get_country_tax_settings, get_settings_password
from omnexa_einvoice.tax_engine.plugin.production_mode import allow_mock_api, is_live_production_settings
from omnexa_einvoice.tax_engine.plugin.production_validate import validate_production_settings
from omnexa_einvoice.tax_engine.plugin.specs import CountryPluginSpec


def get_italy_sdi_settings(company: str, *, branch: str | None = None) -> frappe._dict:
	settings = get_country_tax_settings(company, "IT", branch=branch)
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
			"sdi_base_url": (config.get("sdi_base_url") or (settings.get("api_base_url") if settings else "") or "").strip(),
			"sdi_submit_path": (config.get("sdi_submit_path") or "/sdi/v1/invoices").strip(),
			"partita_iva": (config.get("partita_iva") or (settings.get("tax_registration_number") if settings else "") or "").strip(),
			"codice_destinatario": (config.get("codice_destinatario") or "0000000").strip(),
			"client_id": (settings.get("client_id") if settings else "") or "",
			"client_secret": get_settings_password(settings, "client_secret") if settings else None,
			"fatturapa_private_key_pem": config.get("fatturapa_private_key_pem")
			or config.get("signing_private_key_pem")
			or "",
			"fatturapa_certificate_pem": config.get("fatturapa_certificate_pem")
			or config.get("signing_certificate_pem")
			or "",
		}
	)


def validate_italy_sdi_for_live(company: str, *, branch: str | None = None) -> None:
	from omnexa_einvoice.tax_engine.countries.country_http_uat import throw_if_missing, validate_required_fields

	sdi = get_italy_sdi_settings(company, branch=branch)
	throw_if_missing(
		validate_required_fields(
			{
				"partita_iva": sdi.partita_iva,
				"sdi_base_url": sdi.sdi_base_url,
				"fatturapa_private_key_pem": sdi.fatturapa_private_key_pem
	},
			[
				("partita_iva", _("partita_iva")),
				("sdi_base_url", _("sdi_base_url")),
				("fatturapa_private_key_pem", _("fatturapa_private_key_pem")),
			],
		),
		title=_("Italy SDI"),
	)


def _mock_sdi(*, uuid: str, reference: str) -> dict[str, Any]:
	sdi_id = f"SDI-{uuid[:12].upper()}"
	return {
		"ok": True,
		"mock": True,
		"status": "RC",
		"sdi_id": sdi_id,
		"uuid": sdi_id,
		"raw": {"sdiId": sdi_id, "reference": reference, "esito": "RC"
	},
		"mode": "mock",
		"framework": "FatturaPA"
	}


def submit_fatturapa_sdi(
	*,
	company: str,
	spec: CountryPluginSpec,
	uuid: str,
	hash_b64: str,
	signed_xml: str,
	document: dict[str, Any] | None = None,
) -> dict[str, Any]:
	branch = (document or {}).get("branch") if document else None
	settings = validate_production_settings(company, "IT", phase="phase2", branch=branch)
	sdi = get_italy_sdi_settings(company, branch=branch)
	reference = (document or {}).get("reference_name") or ""

	if allow_mock_api() or not sdi.sdi_base_url:
		return _mock_sdi(uuid=uuid, reference=reference)

	if is_live_production_settings(settings):
		validate_italy_sdi_for_live(company, branch=branch)

	url = f"{sdi.sdi_base_url.rstrip('/')}{sdi.sdi_submit_path}"
	headers = {"Accept": "application/json", "Content-Type": "application/json"
	}
	apply_basic_auth(headers, sdi.client_id, sdi.client_secret)

	payload = {
		"uuid": uuid,
		"invoiceHash": hash_b64,
		"xml": base64.b64encode(signed_xml.encode("utf-8")).decode("ascii"),
		"partitaIVA": sdi.partita_iva,
		"codiceDestinatario": sdi.codice_destinatario
	}
	res = post_country_json(
		country_code="IT",
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
		frappe.throw(_("Italy SDI error ({0}): {1}").format(res.status_code, body), title=_("Italy SDI"))

	sdi_id = body.get("sdiId") or body.get("id") or uuid
	return {
		"ok": True,
		"http_status": res.status_code,
		"status": body.get("esito") or "RC",
		"sdi_id": sdi_id,
		"uuid": sdi_id,
		"raw": body,
		"mode": "live",
		"framework": "FatturaPA"
	}


@frappe.whitelist()
def test_italy_sdi_connection(branch: str | None = None, company: str | None = None) -> dict[str, Any]:
	if not branch and company:
		branch = frappe.db.get_value("Branch", {"company": company
	}, "name")
	if not branch:
		frappe.throw(_("Select a branch."), title=_("Italy SDI"))
	comp = company or frappe.db.get_value("Branch", branch, "company")
	sdi = get_italy_sdi_settings(comp, branch=branch)
	if not sdi.partita_iva:
		return {"ok": False, "message": _("Set Partita IVA on Branch tax registration or configuration_json.partita_iva.")
	}
	from omnexa_einvoice.tax_engine.countries.country_http_uat import validate_required_fields

	checklist = validate_required_fields(
		{"sdi_base_url": sdi.sdi_base_url, "fatturapa_private_key_pem": sdi.fatturapa_private_key_pem
	},
		[
			("sdi_base_url", _("sdi_base_url")),
			("fatturapa_private_key_pem", _("fatturapa_private_key_pem")),
		],
	)
	mock = _mock_sdi(uuid=frappe.generate_hash(length=10), reference="TEST")
	return connection_test_result(
		allow_mock=allow_mock_api(),
		has_base_url=bool(sdi.sdi_base_url),
		checklist=checklist,
		mock_response={
			"ok": True,
			"message": _("Italy SDI sandbox OK (mock)."),
			"sdi_id": mock["sdi_id"],
			"mode": "mock"
	},
		base_url=sdi.sdi_base_url,
		ready_label=_("SDI ready for FatturaPA UAT."),
	)
