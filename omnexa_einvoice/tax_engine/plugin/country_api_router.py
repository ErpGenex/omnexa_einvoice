# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Route Phase 2 submit to country-specific API clients."""

from __future__ import annotations

from typing import Any

from omnexa_einvoice.tax_engine.plugin.specs import CountryPluginSpec, get_spec


def submit_country_invoice(
	*,
	country_code: str,
	company: str,
	uuid: str,
	hash_b64: str,
	signed_xml: str,
	document: dict[str, Any] | None = None,
) -> dict[str, Any]:
	code = (country_code or "").strip().upper()
	spec = get_spec(code)

	if code == "IN":
		from omnexa_einvoice.tax_engine.countries.india_gsp import submit_gst_irn

		return submit_gst_irn(
			company=company,
			spec=spec,
			uuid=uuid,
			hash_b64=hash_b64,
			signed_xml=signed_xml,
			document=document,
		)

	if code == "MX":
		from omnexa_einvoice.tax_engine.countries.mexico_pac_client import submit_cfdi_timbrado

		return submit_cfdi_timbrado(
			company=company,
			spec=spec,
			uuid=uuid,
			hash_b64=hash_b64,
			signed_xml=signed_xml,
			document=document,
		)

	if code == "IT":
		from omnexa_einvoice.tax_engine.countries.italy_sdi import submit_fatturapa_sdi

		return submit_fatturapa_sdi(
			company=company,
			spec=spec,
			uuid=uuid,
			hash_b64=hash_b64,
			signed_xml=signed_xml,
			document=document,
		)

	if code == "BR":
		from omnexa_einvoice.tax_engine.countries.brazil_sefaz import submit_nfe_sefaz

		return submit_nfe_sefaz(
			company=company,
			spec=spec,
			uuid=uuid,
			hash_b64=hash_b64,
			signed_xml=signed_xml,
			document=document,
		)

	if code == "PL":
		from omnexa_einvoice.tax_engine.countries.poland_ksef_client import submit_ksef_invoice

		return submit_ksef_invoice(
			company=company,
			spec=spec,
			uuid=uuid,
			hash_b64=hash_b64,
			signed_xml=signed_xml,
			document=document,
		)

	if code == "ES":
		from omnexa_einvoice.tax_engine.countries.spain_aeat import submit_facturae_aeat

		return submit_facturae_aeat(
			company=company,
			spec=spec,
			uuid=uuid,
			hash_b64=hash_b64,
			signed_xml=signed_xml,
			document=document,
		)

	if code == "CO":
		from omnexa_einvoice.tax_engine.countries.colombia_dian_client import submit_dian_invoice

		return submit_dian_invoice(
			company=company,
			spec=spec,
			uuid=uuid,
			hash_b64=hash_b64,
			signed_xml=signed_xml,
			document=document,
		)

	if code == "DE":
		from omnexa_einvoice.tax_engine.countries.germany_xrechnung_client import submit_xrechnung_invoice

		return submit_xrechnung_invoice(
			company=company,
			spec=spec,
			uuid=uuid,
			hash_b64=hash_b64,
			signed_xml=signed_xml,
			document=document,
		)

	if code == "FR":
		from omnexa_einvoice.tax_engine.countries.france_pdp import submit_facturx_pdp

		return submit_facturx_pdp(
			company=company,
			spec=spec,
			uuid=uuid,
			hash_b64=hash_b64,
			signed_xml=signed_xml,
			document=document,
		)

	if code == "AE":
		from omnexa_einvoice.uae.api_client import submit_to_asp

		return submit_to_asp(
			company=company,
			uuid=uuid,
			hash_b64=hash_b64,
			signed_xml=signed_xml,
			document=document or {},
		)

	if code in ("AR", "CL", "PE"):
		from omnexa_einvoice.tax_engine.countries.latam_authority_client import submit_latam_authority

		return submit_latam_authority(
			company=company,
			country_code=code,
			spec=spec,
			uuid=uuid,
			hash_b64=hash_b64,
			signed_xml=signed_xml,
			document=document,
		)

	if code == "JO":
		from omnexa_einvoice.tax_engine.countries.jofotara_client import submit_jofotara_invoice

		return submit_jofotara_invoice(
			company=company,
			spec=spec,
			uuid=uuid,
			hash_b64=hash_b64,
			signed_xml=signed_xml,
			document=document,
		)

	from omnexa_einvoice.tax_engine.plugin.api_client import submit_invoice_api

	return submit_invoice_api(
		country_code=code,
		company=company,
		spec=spec,
		uuid=uuid,
		hash_b64=hash_b64,
		signed_xml=signed_xml,
		document=document,
	)
