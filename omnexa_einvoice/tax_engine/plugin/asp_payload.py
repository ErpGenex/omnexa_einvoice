# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""ASP / government API JSON payloads per country engine family."""

from __future__ import annotations

import base64
import json
from typing import Any

from omnexa_einvoice.tax_engine.country_catalog import get_catalog_entry
from omnexa_einvoice.tax_engine.plugin.registry import get_engine


def asp_payload_type(engine_key: str) -> str:
	return {
		"cfdi": "cfdi",
		"gst_irn": "gst_irn",
		"fatturapa": "fatturapa",
		"ksef_fa2": "ksef_fa2",
		"nfe": "nfe",
		"pint_gulf": "peppol",
		"pint_ae": "peppol",
		"peppol_ubl": "peppol",
		"latam_invoice": "latam",
		"jofotara": "jofotara",
	}.get(engine_key, "generic")


def build_asp_payload(
	*,
	country_code: str,
	company: str,
	settings,
	spec,
	uuid: str,
	hash_b64: str,
	signed_xml: str,
	document: dict[str, Any] | None = None,
) -> dict[str, Any]:
	code = country_code.upper()
	entry = get_catalog_entry(code)
	engine = get_engine(code)
	document = document or {}
	buyer = document.get("buyer") or {}
	seller = document.get("seller") or {}
	invoice_b64 = base64.b64encode(signed_xml.encode("utf-8")).decode("ascii")
	payload_type = asp_payload_type(entry.engine if entry else "")

	base = {
		"uuid": uuid,
		"invoiceHash": hash_b64,
		"invoice": invoice_b64,
		"signedXml": invoice_b64,
		"country": code,
		"authority": spec.authority_code,
		"framework": engine.framework,
		"environment": (settings.get("api_environment") if settings else "sandbox") or "sandbox",
		"company": company,
		"invoiceNumber": document.get("reference_name") or "",
		"sellerTaxId": seller.get("tax_registration") or (settings.get("tax_registration_number") if settings else ""),
		"buyerTaxId": buyer.get("tax_registration") or "",
		"currency": document.get("currency") or (entry.currency if entry else ""),
	}

	if payload_type == "peppol":
		base.update(
			{
				"documentType": "Invoice",
				"processId": "urn:peppol:bis:billing",
				"customizationId": (entry.customization_id if entry else "") or base.get("framework"),
				"senderParticipantId": (settings.get("uae_peppol_sender_id") if settings else "") or "",
				"receiverParticipantId": (settings.get("uae_peppol_receiver_id") if settings else "")
				or buyer.get("peppol_id")
				or "",
			}
		)
	elif payload_type == "cfdi":
		base.update({"documentType": "CFDI", "version": "4.0", "tipoComprobante": "I"})
		try:
			cfg = json.loads(settings.configuration_json or "{}")
			if isinstance(cfg, dict):
				base["pacProvider"] = cfg.get("pac_provider") or ""
				base["pacUrl"] = (cfg.get("pac_base_url") or "").strip()
		except json.JSONDecodeError:
			pass
	elif payload_type == "gst_irn":
		base.update({"documentType": "eInvoice", "version": "1.1", "format": "JSON"})
		try:
			base["eInvoiceJson"] = json.loads(signed_xml) if signed_xml.strip().startswith("{") else {}
		except json.JSONDecodeError:
			base["eInvoiceJson"] = {}
	elif payload_type == "fatturapa":
		base.update({"documentType": "FatturaPA", "formato": "FPR12", "trasmissione": "FPR12"})
	elif payload_type == "ksef_fa2":
		base.update({"documentType": "FA", "ksefVersion": "FA2", "schema": "FA(2)"})
	elif payload_type == "nfe":
		base.update({"documentType": "NFe", "modelo": "55", "versao": "4.00"})
	elif payload_type == "latam":
		base.update({"documentType": "TaxInvoice", "latamCountry": code})
	elif payload_type == "jofotara":
		base.update({"documentType": "JoFotaraInvoice", "jordanApiVersion": "v1"})

	return base
