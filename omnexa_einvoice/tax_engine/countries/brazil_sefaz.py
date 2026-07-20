# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Brazil SEFAZ — NF-e authorization (sandbox mock + live HTTP)."""

from __future__ import annotations

import base64
import json
from typing import Any

import frappe
import requests
from frappe import _

from omnexa_einvoice.tax_engine.countries.brazil_a1_signer import validate_sefaz_config
from omnexa_einvoice.tax_engine.country_tax_settings import get_country_tax_settings, get_settings_password
from omnexa_einvoice.tax_engine.plugin.http_retry import build_idempotency_key, post_json_with_retry
from omnexa_einvoice.tax_engine.plugin.production_mode import allow_mock_api, is_live_production_settings
from omnexa_einvoice.tax_engine.plugin.production_validate import validate_production_settings
from omnexa_einvoice.tax_engine.plugin.specs import CountryPluginSpec


def get_brazil_sefaz_settings(company: str, *, branch: str | None = None) -> frappe._dict:
	settings = get_country_tax_settings(company, "BR", branch=branch)
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
			"sefaz_base_url": (config.get("sefaz_base_url") or (settings.get("api_base_url") if settings else "") or "").strip(),
			"uf": (config.get("uf") or config.get("cuf") or "35").strip(),
			"cnpj": (config.get("cnpj") or (settings.get("tax_registration_number") if settings else "") or "").strip(),
			"ambiente": (config.get("ambiente") or settings.get("api_environment") if settings else "homologacao") or "homologacao",
			"client_id": (settings.get("client_id") if settings else "") or "",
			"client_secret": get_settings_password(settings, "client_secret") if settings else None,
			"a1_certificate_pem": config.get("a1_certificate_pem") or "",
			"a1_private_key_pem": config.get("a1_private_key_pem") or "",
			"a1_passphrase": (config.get("a1_passphrase") or "").strip(),
		}
	)


def validate_brazil_sefaz_for_live(company: str, *, branch: str | None = None) -> None:
	sefaz = get_brazil_sefaz_settings(company, branch=branch)
	missing = validate_sefaz_config(
		{
			"cnpj": sefaz.cnpj,
			"sefaz_base_url": sefaz.sefaz_base_url,
			"a1_private_key_pem": sefaz.a1_private_key_pem,
			"a1_certificate_pem": sefaz.a1_certificate_pem,
		}
	)
	if missing:
		frappe.throw(
			_("Brazil live SEFAZ requires: {0}").format(", ".join(missing)),
			title=_("SEFAZ"),
		)


def _mock_sefaz(*, uuid: str, reference: str) -> dict[str, Any]:
	protocol = f"NFe{uuid.replace('-', '')[:44].upper()}"
	chave = protocol[:44]
	return {
		"ok": True,
		"mock": True,
		"status": "AUTORIZADO",
		"nfe_protocol": protocol,
		"chave_acesso": chave,
		"uuid": chave,
		"raw": {"protocolo": protocol, "chNFe": chave, "reference": reference},
		"mode": "mock",
		"framework": "NF-e-4.0",
	}


def submit_nfe_sefaz(
	*,
	company: str,
	spec: CountryPluginSpec,
	uuid: str,
	hash_b64: str,
	signed_xml: str,
	document: dict[str, Any] | None = None,
) -> dict[str, Any]:
	branch = (document or {}).get("branch") if document else None
	settings = validate_production_settings(company, "BR", phase="phase2", branch=branch)
	sefaz = get_brazil_sefaz_settings(company, branch=branch)
	reference = (document or {}).get("reference_name") or ""

	if allow_mock_api() or not sefaz.sefaz_base_url:
		return _mock_sefaz(uuid=uuid, reference=reference)

	if is_live_production_settings(settings):
		validate_brazil_sefaz_for_live(company, branch=branch)

	url = f"{sefaz.sefaz_base_url.rstrip('/')}/nfe/v1/authorize"
	headers = {"Accept": "application/json", "Content-Type": "application/json"}
	if sefaz.client_id and sefaz.client_secret:
		token = base64.b64encode(f"{sefaz.client_id}:{sefaz.client_secret}".encode()).decode("ascii")
		headers["Authorization"] = f"Basic {token}"

	payload = {
		"uuid": uuid,
		"invoiceHash": hash_b64,
		"xml": base64.b64encode(signed_xml.encode("utf-8")).decode("ascii"),
		"cUF": sefaz.uf,
		"cnpj": sefaz.cnpj,
		"tpAmb": 2 if sefaz.ambiente != "producao" else 1,
	}
	idem = build_idempotency_key(country_code="BR", uuid=uuid, document=document)
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
		body = {"raw": (res.text or "")[:8000]}

	if res.status_code >= 400:
		frappe.throw(_("SEFAZ error ({0}): {1}").format(res.status_code, body), title=_("SEFAZ"))

	chave = body.get("chNFe") or body.get("chave") or uuid
	return {
		"ok": True,
		"http_status": res.status_code,
		"status": body.get("cStat") or "AUTORIZADO",
		"chave_acesso": chave,
		"nfe_protocol": body.get("nProt") or body.get("protocolo"),
		"uuid": chave,
		"raw": body,
		"mode": "live",
		"framework": "NF-e-4.0",
	}


@frappe.whitelist()
def test_brazil_sefaz_connection(branch: str | None = None, company: str | None = None) -> dict[str, Any]:
	if not branch and company:
		branch = frappe.db.get_value("Branch", {"company": company}, "name")
	if not branch:
		frappe.throw(_("Select a branch."), title=_("SEFAZ"))
	comp = company or frappe.db.get_value("Branch", branch, "company")
	sefaz = get_brazil_sefaz_settings(comp, branch=branch)
	cfg = {
		"cnpj": sefaz.cnpj,
		"sefaz_base_url": sefaz.sefaz_base_url,
		"a1_private_key_pem": sefaz.a1_private_key_pem,
		"a1_certificate_pem": sefaz.a1_certificate_pem,
	}
	checklist = validate_sefaz_config(cfg)
	if allow_mock_api() or not sefaz.sefaz_base_url:
		mock = _mock_sefaz(uuid=frappe.generate_hash(length=10), reference="TEST")
		return {
			"ok": True,
			"message": _("SEFAZ sandbox OK (mock authorization)."),
			"chave_acesso": mock["chave_acesso"],
			"mode": "mock",
			"a1_ready": not checklist,
			"checklist": checklist or [_("Optional for mock: add A1 PEMs before homologação UAT.")],
		}
	if checklist:
		return {
			"ok": False,
			"message": _("Complete A1 + SEFAZ settings before live NF-e."),
			"checklist": checklist,
		}
	try:
		res = requests.get(sefaz.sefaz_base_url.rstrip("/"), timeout=30)
		return {
			"ok": res.status_code < 500,
			"message": _("SEFAZ URL reachable ({0}). A1 keys present — ready for homologação UAT.").format(
				res.status_code
			),
			"a1_ready": True,
		}
	except requests.RequestException as exc:
		return {"ok": False, "message": str(exc), "checklist": checklist}
