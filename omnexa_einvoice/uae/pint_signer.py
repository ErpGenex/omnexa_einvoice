# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""UAE PINT AE — XML-DSig scaffold on UBL Invoice (ASP UAT prep)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.tax_engine.plugin.xmldsig_scaffold import sign_xml_enveloped


def sign_pint_ae_xml(
	xml_text: str,
	*,
	private_key_pem: str,
	certificate_pem: str = "",
	passphrase: str | None = None,
) -> dict[str, Any]:
	if not (private_key_pem or "").strip():
		frappe.throw(
			_("ASP signing private key (asp_signing_private_key_pem) is required."),
			title=_("UAE PINT"),
		)
	return sign_xml_enveloped(
		xml_text,
		private_key_pem=private_key_pem,
		certificate_pem=certificate_pem,
		passphrase=passphrase,
		signed_element_localname="Invoice",
		signer_label="asp:xmldsig-scaffold",
	)


def validate_asp_config(config: dict[str, Any], settings: Any | None = None) -> list[str]:
	missing: list[str] = []
	tin = (config.get("seller_tin") or "").strip()
	if settings and not tin:
		tin = (getattr(settings, "seller_tin", None) or getattr(settings, "tax_registration_number", None) or "").strip()
	if not tin:
		missing.append(_("UAE seller TIN / tax registration"))
	if not (config.get("api_base_url") or "").strip():
		missing.append(_("API Base URL"))
	if not (config.get("peppol_sender_id") or "").strip():
		missing.append(_("peppol_sender_id or uae_peppol_sender_id"))
	if not (config.get("asp_signing_private_key_pem") or config.get("signing_private_key_pem") or "").strip():
		missing.append(_("asp_signing_private_key_pem"))
	return missing
