# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Brazil NF-e A1 certificate XML-DSig scaffold (homologação UAT prep)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.tax_engine.plugin.xmldsig_scaffold import sign_xml_enveloped


def sign_nfe_a1(
	xml_text: str,
	*,
	private_key_pem: str,
	certificate_pem: str = "",
	passphrase: str | None = None,
) -> dict[str, Any]:
	if not (private_key_pem or "").strip():
		frappe.throw(_("A1 private key (a1_private_key_pem) is required."), title=_("Brazil A1"))
	return sign_xml_enveloped(
		xml_text,
		private_key_pem=private_key_pem,
		certificate_pem=certificate_pem,
		passphrase=passphrase,
		signed_element_localname="infNFe",
		signer_label="a1:xmldsig-scaffold",
	)


def validate_sefaz_config(config: dict[str, Any]) -> list[str]:
	missing: list[str] = []
	if not (config.get("cnpj") or "").strip():
		missing.append(_("cnpj (or Branch Tax Registration Number)"))
	if not (config.get("sefaz_base_url") or "").strip():
		missing.append(_("sefaz_base_url or API Base URL"))
	if not (config.get("a1_private_key_pem") or "").strip():
		missing.append(_("a1_private_key_pem"))
	if not (config.get("a1_certificate_pem") or "").strip():
		missing.append(_("a1_certificate_pem"))
	return missing
