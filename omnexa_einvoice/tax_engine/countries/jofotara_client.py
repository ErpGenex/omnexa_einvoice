# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Jordan JoFotara / ISTD invoice submit (UAT scaffold)."""

from __future__ import annotations

import base64
import json
from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.tax_engine.countries.country_http_uat import (
	apply_basic_auth,
	apply_bearer,
	connection_test_result,
	parse_configuration,
	post_country_json,
	throw_if_missing,
	validate_required_fields,
)
from omnexa_einvoice.tax_engine.country_tax_settings import get_country_tax_settings, get_settings_password
from omnexa_einvoice.tax_engine.plugin.production_mode import allow_mock_api, is_live_production_settings
from omnexa_einvoice.tax_engine.plugin.production_validate import validate_production_settings
from omnexa_einvoice.tax_engine.plugin.specs import CountryPluginSpec


def get_jofotara_settings(company: str, *, branch: str | None = None) -> frappe._dict:
	settings = get_country_tax_settings(company, "JO", branch=branch)
	config = parse_configuration(settings)
	return frappe._dict(
		{
			"jofotara_base_url": (
				config.get("jofotara_base_url") or (settings.get("api_base_url") if settings else "") or ""
			).strip(),
			"jofotara_submit_path": (config.get("jofotara_submit_path") or "/api/v1/invoices").strip(),
			"tin": (config.get("tin") or (settings.get("tax_registration_number") if settings else "") or "").strip(),
			"client_id": (settings.get("client_id") if settings else "") or "",
			"client_secret": get_settings_password(settings, "client_secret") if settings else None,
			"api_token": get_settings_password(settings, "asp_api_key") if settings else None}
	)


def validate_jofotara_for_live(company: str, *, branch: str | None = None) -> None:
	row = get_jofotara_settings(company, branch=branch)
	throw_if_missing(
		validate_required_fields(
			{"tin": row.tin, "jofotara_base_url": row.jofotara_base_url
	},
			[("tin", _("tin")), ("jofotara_base_url", _("jofotara_base_url"))],
		),
		title=_("JoFotara"),
	)


def _mock_jo(*, uuid: str, reference: str) -> dict[str, Any]:
	ref = f"JO-{uuid[:12].upper()}"
	return {
		"ok": True,
		"mock": True,
		"status": "ACCEPTED",
		"uuid": ref,
		"authority_reference": ref,
		"raw": {"reference": reference
	},
		"mode": "mock",
		"framework": "JoFotara"
	}


def submit_jofotara_invoice(
	*,
	company: str,
	spec: CountryPluginSpec,
	uuid: str,
	hash_b64: str,
	signed_xml: str,
	document: dict[str, Any] | None = None,
) -> dict[str, Any]:
	branch = (document or {}).get("branch") if document else None
	settings = validate_production_settings(company, "JO", phase="phase2", branch=branch)
	row = get_jofotara_settings(company, branch=branch)
	reference = (document or {}).get("reference_name") or ""

	if allow_mock_api() or not row.jofotara_base_url:
		return _mock_jo(uuid=uuid, reference=reference)

	if is_live_production_settings(settings):
		validate_jofotara_for_live(company, branch=branch)

	url = f"{row.jofotara_base_url.rstrip('/')}{row.jofotara_submit_path}"
	headers = {"Accept": "application/json", "Content-Type": "application/json"
	}
	apply_basic_auth(headers, row.client_id, row.client_secret)
	apply_bearer(headers, row.api_token)
	config = parse_configuration(get_country_tax_settings(company, "JO", branch=branch))
	payload = {
		"uuid": uuid,
		"invoiceHash": hash_b64,
		"xml": base64.b64encode(signed_xml.encode("utf-8")).decode("ascii"),
		"tin": row.tin,
		"reference": reference
	}
	res = post_country_json(
		country_code="JO",
		url=url,
		headers=headers,
		payload=payload,
		document=document,
		uuid=uuid,
		config=config,
	)
	try:
		body = res.json() if res.text else {}
	except Exception:
		body = {"raw": (res.text or "")[:8000]
	}

	if res.status_code >= 400:
		frappe.throw(_("JoFotara error ({0}): {1}").format(res.status_code, body), title=_("JoFotara"))

	auth_ref = body.get("reference") or body.get("uuid") or uuid
	return {
		"ok": True,
		"http_status": res.status_code,
		"status": body.get("status") or "ACCEPTED",
		"uuid": auth_ref,
		"authority_reference": auth_ref,
		"raw": body,
		"mode": "live",
		"framework": "JoFotara"
	}


@frappe.whitelist()
def test_jofotara_connection(branch: str | None = None, company: str | None = None) -> dict[str, Any]:
	if not branch and company:
		branch = frappe.db.get_value("Branch", {"company": company
	}, "name")
	if not branch:
		frappe.throw(_("Select a branch."), title=_("JoFotara"))
	comp = company or frappe.db.get_value("Branch", branch, "company")
	row = get_jofotara_settings(comp, branch=branch)
	if not row.tin:
		return {"ok": False, "message": _("Set Jordan TIN on Branch tax registration.")
	}
	checklist = validate_required_fields(
		{"jofotara_base_url": row.jofotara_base_url
	},
		[("jofotara_base_url", _("jofotara_base_url"))],
	)
	mock = _mock_jo(uuid=frappe.generate_hash(length=8), reference="TEST")
	return connection_test_result(
		allow_mock=allow_mock_api(),
		has_base_url=bool(row.jofotara_base_url),
		checklist=checklist,
		mock_response={
			"ok": True,
			"message": _("JoFotara sandbox OK (mock)."),
			"authority_reference": mock["uuid"],
			"mode": "mock"
	},
		base_url=row.jofotara_base_url,
		ready_label=_("JoFotara ready for ISTD UAT."),
	)
