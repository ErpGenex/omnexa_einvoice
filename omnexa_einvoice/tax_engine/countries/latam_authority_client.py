# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Argentina AFIP / Chile SII / Peru SUNAT — authority submit (UAT scaffold)."""

from __future__ import annotations

import base64
import json
from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.tax_engine.countries.country_http_uat import (
	apply_basic_auth,
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

LATAM_AUTHORITY_CODES = frozenset({"AR", "CL", "PE"})
AUTHORITY_LABELS = {"AR": "AFIP", "CL": "SII", "PE": "SUNAT"
	}


def get_latam_authority_settings(company: str, country_code: str, *, branch: str | None = None) -> frappe._dict:
	code = (country_code or "").upper()
	settings = get_country_tax_settings(company, code, branch=branch)
	config = parse_configuration(settings)
	tax_key = {"AR": "cuit", "CL": "rut", "PE": "ruc"
	}.get(code, "tax_id")
	return frappe._dict(
		{
			"country_code": code,
			"authority_base_url": (
				config.get("authority_base_url") or (settings.get("api_base_url") if settings else "") or ""
			).strip(),
			"authority_submit_path": (
				config.get("authority_submit_path") or config.get("submit_path") or f"/{code.lower()}/v1/invoices"
			).strip(),
			"tax_id": (config.get(tax_key) or (settings.get("tax_registration_number") if settings else "") or "").strip(),
			"client_id": (settings.get("client_id") if settings else "") or "",
			"client_secret": get_settings_password(settings, "client_secret") if settings else None,
			"signing_private_key_pem": config.get("signing_private_key_pem") or "",
			"signing_certificate_pem": config.get("signing_certificate_pem") or ""
	}
	)


def validate_latam_for_live(company: str, country_code: str, *, branch: str | None = None) -> None:
	code = (country_code or "").upper()
	row = get_latam_authority_settings(company, code, branch=branch)
	tax_label = {"AR": "cuit", "CL": "rut", "PE": "ruc"
	}.get(code, "tax_id")
	throw_if_missing(
		validate_required_fields(
			{"tax_id": row.tax_id, "authority_base_url": row.authority_base_url
	},
			[
				("tax_id", tax_label),
				("authority_base_url", _("authority_base_url or API Base URL")),
			],
		),
		title=AUTHORITY_LABELS.get(code, code),
	)


def _mock_latam(*, country_code: str, uuid: str, reference: str) -> dict[str, Any]:
	ref = f"{country_code}-AUTH-{uuid[:12].upper()}"
	return {
		"ok": True,
		"mock": True,
		"status": "ACCEPTED",
		"authority_reference": ref,
		"uuid": ref,
		"cufe": ref if country_code == "CO" else None,
		"raw": {"reference": reference, "authorityRef": ref
	},
		"mode": "mock",
		"framework": f"{AUTHORITY_LABELS.get(country_code, country_code)}-LATAM",
	}


def submit_latam_authority(
	*,
	company: str,
	country_code: str,
	spec: CountryPluginSpec,
	uuid: str,
	hash_b64: str,
	signed_xml: str,
	document: dict[str, Any] | None = None,
) -> dict[str, Any]:
	code = (country_code or "").upper()
	if code not in LATAM_AUTHORITY_CODES:
		frappe.throw(_("Unsupported LATAM authority country: {0}").format(code))

	branch = (document or {}).get("branch") if document else None
	settings = validate_production_settings(company, code, phase="phase2", branch=branch)
	row = get_latam_authority_settings(company, code, branch=branch)
	reference = (document or {}).get("reference_name") or ""

	if allow_mock_api() or not row.authority_base_url:
		return _mock_latam(country_code=code, uuid=uuid, reference=reference)

	if is_live_production_settings(settings):
		validate_latam_for_live(company, code, branch=branch)

	url = f"{row.authority_base_url.rstrip('/')}{row.authority_submit_path}"
	headers = {"Accept": "application/json", "Content-Type": "application/json"
	}
	apply_basic_auth(headers, row.client_id, row.client_secret)
	config = parse_configuration(get_country_tax_settings(company, code, branch=branch))
	payload = {
		"country": code,
		"uuid": uuid,
		"invoiceHash": hash_b64,
		"xml": base64.b64encode(signed_xml.encode("utf-8")).decode("ascii"),
		"taxId": row.tax_id,
		"framework": spec.authority_code,
		"reference": reference
	}
	res = post_country_json(
		country_code=code,
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
		frappe.throw(
			_("{0} error ({1}): {2}").format(AUTHORITY_LABELS.get(code, code), res.status_code, body),
			title=AUTHORITY_LABELS.get(code, code),
		)

	auth_ref = body.get("authorityRef") or body.get("reference") or body.get("id") or uuid
	return {
		"ok": True,
		"http_status": res.status_code,
		"status": body.get("status") or "ACCEPTED",
		"authority_reference": auth_ref,
		"uuid": auth_ref,
		"raw": body,
		"mode": "live",
		"framework": spec.framework
	}


@frappe.whitelist()
def test_latam_authority_connection(
	country_code: str,
	branch: str | None = None,
	company: str | None = None,
) -> dict[str, Any]:
	code = (country_code or "").upper()
	if not branch and company:
		branch = frappe.db.get_value("Branch", {"company": company
	}, "name")
	if not branch:
		frappe.throw(_("Select a branch."), title=AUTHORITY_LABELS.get(code, code))
	comp = company or frappe.db.get_value("Branch", branch, "company")
	row = get_latam_authority_settings(comp, code, branch=branch)
	tax_label = {"AR": "CUIT", "CL": "RUT", "PE": "RUC"
	}.get(code, "Tax ID")
	if not row.tax_id:
		return {"ok": False, "message": _("Set {0} on Branch tax registration.").format(tax_label)
	}
	checklist = validate_required_fields(
		{"authority_base_url": row.authority_base_url
	},
		[("authority_base_url", _("authority_base_url or API Base URL"))],
	)
	mock = _mock_latam(country_code=code, uuid=frappe.generate_hash(length=10), reference="TEST")
	return connection_test_result(
		allow_mock=allow_mock_api(),
		has_base_url=bool(row.authority_base_url),
		checklist=checklist,
		mock_response={
			"ok": True,
			"message": _("{0} sandbox OK (mock).").format(AUTHORITY_LABELS.get(code, code)),
			"authority_reference": mock["authority_reference"],
			"mode": "mock"
	},
		base_url=row.authority_base_url,
		ready_label=_("{0} ready for authority UAT.").format(AUTHORITY_LABELS.get(code, code)),
	)
