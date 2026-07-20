# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Per-family signing for international plugin countries (not Egypt ETA / not ZATCA USB)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import frappe
from frappe import _

from omnexa_einvoice.tax_engine.country_catalog import get_catalog_entry, normalize_country_code
from omnexa_einvoice.tax_engine.plugin.production_mode import (
	is_live_production_settings,
	requires_real_api,
)
import base64
import hashlib

# Engine → expected national signing family (implementation matures per wave).
def sign_xml_scaffold(xml_text: str, *, country_code: str) -> dict[str, Any]:
	digest = hashlib.sha256(xml_text.encode("utf-8")).digest()
	hash_hex = digest.hex()
	return {
		"hash_hex": hash_hex,
		"hash_b64": base64.b64encode(digest).decode("ascii"),
		"signature_b64": base64.b64encode(f"{country_code}-SCAFFOLD:{hash_hex}".encode()).decode("ascii"),
		"signed_xml": xml_text,
		"signer": "scaffold",
	}


def _sign_with_certificate(xml_text: str, pem: str, key_pem: str, passphrase: str | None) -> dict[str, Any]:
	from cryptography.hazmat.primitives import hashes, serialization
	from cryptography.hazmat.primitives.asymmetric import padding

	private_key = serialization.load_pem_private_key(
		key_pem.encode() if isinstance(key_pem, str) else key_pem,
		password=passphrase.encode() if passphrase else None,
	)
	signature = private_key.sign(xml_text.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
	digest = hashlib.sha256(xml_text.encode("utf-8")).digest()
	hash_hex = digest.hex()
	signed = (
		xml_text.replace(
			"<?xml",
			f'<!-- ERPGENEX-SIG:{base64.b64encode(signature).decode("ascii")[:64]}... -->\n<?xml',
			1,
		)
		if "<?xml" in xml_text
		else xml_text
	)
	return {
		"hash_hex": hash_hex,
		"hash_b64": base64.b64encode(digest).decode("ascii"),
		"signature_b64": base64.b64encode(signature).decode("ascii"),
		"signed_xml": signed,
		"signer": "certificate",
	}


ENGINE_SIGNING_FAMILY: dict[str, str] = {
	"cfdi": "cades",
	"nfe": "xmldsig",
	"gst_irn": "digest",
	"fatturapa": "cades",
	"ksef_fa2": "ksef",
	"facturae": "xmldsig",
	"dian_ubl": "xmldsig",
	"xrechnung": "xmldsig",
	"facturx": "xmldsig",
	"pint_ae": "xmldsig",
	"pint_gulf": "xmldsig",
	"jofotara": "digest",
	"latam_invoice": "digest",
	"peppol_ubl": "xmldsig",
}


@dataclass(frozen=True)
class SigningContext:
	country_code: str
	signing_family: str
	mode: str
	config: dict[str, Any]
	settings: Any | None
	requires_real: bool
	live_production: bool


def signing_family_for_country(country_code: str) -> str:
	code = normalize_country_code(country_code)
	entry = get_catalog_entry(code)
	if not entry:
		return "xmldsig"
	return ENGINE_SIGNING_FAMILY.get(entry.engine, "xmldsig")


def build_signing_context(
	*,
	country_code: str,
	settings: Any | None,
	config: dict[str, Any],
) -> SigningContext:
	code = normalize_country_code(country_code)
	family = signing_family_for_country(code)
	mode = (settings.get("signing_mode") if settings else None) or config.get("signing_mode") or "scaffold"
	return SigningContext(
		country_code=code,
		signing_family=family,
		mode=str(mode).strip().lower(),
		config=config,
		settings=settings,
		requires_real=requires_real_api(settings),
		live_production=bool(settings and is_live_production_settings(settings)),
	)


def _has_national_signing_keys(ctx: SigningContext) -> bool:
	code = ctx.country_code
	cfg = ctx.config
	if code == "MX":
		return bool((cfg.get("csd_private_key_pem") or cfg.get("signing_private_key_pem") or "").strip())
	if code == "IN":
		return ctx.mode in ("digest", "gst") and bool((cfg.get("gstin") or "").strip())
	if code == "BR":
		return bool((cfg.get("a1_private_key_pem") or cfg.get("signing_private_key_pem") or "").strip())
	if code == "AE":
		return bool((cfg.get("asp_signing_private_key_pem") or cfg.get("signing_private_key_pem") or "").strip())
	if code == "IT":
		return bool((cfg.get("fatturapa_private_key_pem") or cfg.get("signing_private_key_pem") or "").strip())
	if code == "PL":
		return bool((cfg.get("ksef_token") or cfg.get("ksef_private_key_pem") or "").strip())
	if code in ("ES", "CO", "DE", "FR"):
		return bool((cfg.get("signing_private_key_pem") or "").strip())
	if code in ("AR", "CL", "PE", "JO"):
		return ctx.mode == "digest" or bool((cfg.get("signing_private_key_pem") or "").strip())
	return False


def _sign_national_wb_wc_wd(xml_text: str, ctx: SigningContext) -> dict[str, Any] | None:
	from omnexa_einvoice.tax_engine.countries.national_signers import (
		SIGNING_KEY_ALIASES,
		_key_from_config,
		sign_cufe_digest,
		sign_fatturapa_cades,
		sign_jofotara_digest,
		sign_ksef_fa2_token,
	)

	code = ctx.country_code
	priv = _key_from_config(ctx.config, SIGNING_KEY_ALIASES["private_key_pem"])
	cert = _key_from_config(ctx.config, SIGNING_KEY_ALIASES["certificate_pem"])

	if code == "IT" and ctx.mode in ("cades", "certificate") and priv:
		return sign_fatturapa_cades(
			xml_text,
			private_key_pem=ctx.config.get("fatturapa_private_key_pem") or priv,
			certificate_pem=ctx.config.get("fatturapa_certificate_pem") or cert,
			passphrase=ctx.config.get("signing_passphrase"),
		)

	if code == "PL" and ctx.mode in ("ksef", "token"):
		return sign_ksef_fa2_token(
			xml_text,
			ksef_token=(ctx.config.get("ksef_token") or "").strip(),
			private_key_pem=ctx.config.get("ksef_private_key_pem") or priv,
			certificate_pem=ctx.config.get("ksef_certificate_pem") or cert,
		)

	if code == "CO":
		if priv and ctx.mode in ("xmldsig", "certificate"):
			out = sign_xml_enveloped_wrapper(xml_text, ctx, localname="Invoice")
			if out:
				return out
		if ctx.mode in ("digest", "cufe", "xmldsig"):
			return sign_cufe_digest(xml_text, country_code="CO")

	if code in ("ES", "DE", "FR", "AE") and ctx.mode in ("xmldsig", "asp", "certificate") and priv:
		local = "CrossIndustryInvoice" if code == "FR" else "Invoice"
		return sign_xml_enveloped_wrapper(xml_text, ctx, localname=local)

	if code in ("AR", "CL", "PE") and ctx.mode in ("digest", "latam"):
		return sign_cufe_digest(xml_text, country_code=code)

	if code == "JO" and ctx.mode in ("digest", "jofotara"):
		return sign_jofotara_digest(xml_text)

	return None


def sign_xml_enveloped_wrapper(
	xml_text: str, ctx: SigningContext, *, localname: str
) -> dict[str, Any] | None:
	from omnexa_einvoice.tax_engine.countries.national_signers import SIGNING_KEY_ALIASES, _key_from_config
	from omnexa_einvoice.tax_engine.plugin.xmldsig_scaffold import sign_xml_enveloped

	priv = _key_from_config(ctx.config, SIGNING_KEY_ALIASES["private_key_pem"])
	if not priv:
		return None
	cert = _key_from_config(ctx.config, SIGNING_KEY_ALIASES["certificate_pem"])
	return sign_xml_enveloped(
		xml_text,
		private_key_pem=priv,
		certificate_pem=cert,
		passphrase=ctx.config.get("signing_passphrase") or ctx.config.get("asp_signing_passphrase"),
		signed_element_localname=localname,
		signer_label=f"xmldsig:{ctx.country_code.lower()}-scaffold",
	)


def _sign_india_digest(text: str, ctx: SigningContext) -> dict[str, Any] | None:
	if ctx.country_code != "IN" or ctx.mode not in ("digest", "gst"):
		return None
	if not (text or "").strip().startswith("{"):
		return None
	from omnexa_einvoice.tax_engine.countries.india_gst_digest import sign_gst_irn_digest

	secret = (ctx.config.get("gst_signing_secret") or "").strip()
	return sign_gst_irn_digest(text, signing_secret=secret)


def _sign_brazil_a1(xml_text: str, ctx: SigningContext) -> dict[str, Any] | None:
	if ctx.country_code != "BR" or ctx.mode not in ("a1", "certificate"):
		return None
	key = (ctx.config.get("a1_private_key_pem") or ctx.config.get("signing_private_key_pem") or "").strip()
	if not key:
		return None
	from omnexa_einvoice.tax_engine.countries.brazil_a1_signer import sign_nfe_a1

	cert = ctx.config.get("a1_certificate_pem") or ctx.config.get("signing_certificate_pem") or ""
	return sign_nfe_a1(
		xml_text,
		private_key_pem=key,
		certificate_pem=cert,
		passphrase=ctx.config.get("a1_passphrase") or ctx.config.get("signing_passphrase"),
	)


def _sign_uae_pint(xml_text: str, ctx: SigningContext) -> dict[str, Any] | None:
	if ctx.country_code != "AE" or ctx.mode not in ("xmldsig", "asp", "certificate"):
		return None
	key = (
		ctx.config.get("asp_signing_private_key_pem") or ctx.config.get("signing_private_key_pem") or ""
	).strip()
	if not key:
		return None
	from omnexa_einvoice.uae.pint_signer import sign_pint_ae_xml

	cert = ctx.config.get("asp_signing_certificate_pem") or ctx.config.get("signing_certificate_pem") or ""
	return sign_pint_ae_xml(
		xml_text,
		private_key_pem=key,
		certificate_pem=cert,
		passphrase=ctx.config.get("asp_signing_passphrase") or ctx.config.get("signing_passphrase"),
	)


def _sign_mexico_csd(xml_text: str, ctx: SigningContext) -> dict[str, Any] | None:
	"""Mexico CSD path when keys are configured (signing_mode=csd or certificate)."""
	if ctx.country_code != "MX":
		return None
	if ctx.mode not in ("csd", "certificate"):
		return None
	key_pem = (ctx.config.get("csd_private_key_pem") or ctx.config.get("signing_private_key_pem") or "").strip()
	if not key_pem:
		return None
	from omnexa_einvoice.tax_engine.countries.mexico_csd_signer import sign_cfdi_csd

	cert_pem = ctx.config.get("csd_certificate_pem") or ctx.config.get("signing_certificate_pem") or ""
	passphrase = ctx.config.get("csd_passphrase") or ctx.config.get("signing_passphrase")
	return sign_cfdi_csd(
		xml_text,
		private_key_pem=key_pem,
		certificate_pem=cert_pem,
		passphrase=passphrase,
	)


def sign_with_provider(xml_text: str, ctx: SigningContext) -> dict[str, Any]:
	"""Route to certificate, national family (future), or sandbox scaffold."""
	key_pem = ctx.config.get("signing_private_key_pem") or ctx.config.get("private_key_pem")
	cert_pem = ctx.config.get("signing_certificate_pem") or ctx.config.get("certificate_pem")

	for signer_fn in (
		_sign_india_digest,
		_sign_national_wb_wc_wd,
		_sign_mexico_csd,
		_sign_brazil_a1,
		_sign_uae_pint,
	):
		out = signer_fn(xml_text, ctx)
		if out:
			return out

	if ctx.mode == "certificate" and key_pem:
		try:
			out = _sign_with_certificate(
				xml_text,
				cert_pem or "",
				key_pem,
				ctx.config.get("signing_passphrase") or ctx.config.get("passphrase"),
			)
			out["signing_family"] = ctx.signing_family
			return out
		except Exception as exc:
			frappe.throw(_("Certificate signing failed: {0}").format(exc), title=_("Tax Signing"))

	if ctx.requires_real and ctx.live_production:
		if not _has_national_signing_keys(ctx):
			frappe.throw(
				_(
					"Live production for {0} requires national <b>{1}</b> signing "
					"(signing_mode=csd/certificate with valid keys, or a certified signing module). "
					"Scaffold signing is not allowed."
				).format(ctx.country_code, ctx.signing_family.upper()),
				title=_("Tax Signing"),
			)

	if ctx.requires_real and ctx.mode != "scaffold" and not key_pem:
		frappe.throw(
			_(
				"API environment is production for {0}. Configure signing_mode=certificate "
				"and keys in Configuration JSON, or use sandbox."
			).format(ctx.country_code),
			title=_("Tax Signing"),
		)

	out = sign_xml_scaffold(xml_text, country_code=ctx.country_code)
	out["signer"] = f"scaffold:{ctx.signing_family}"
	out["signing_family"] = ctx.signing_family
	return out
