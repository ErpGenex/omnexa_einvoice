# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""
Single source of truth for supported tax countries (plugin + EG/SA).

Engine types:
  cfdi, nfe, gst_irn, fatturapa, ksef_fa2, facturae, dian_ubl, xrechnung, facturx,
  pint_ae, pint_gulf, jofotara, peppol_ubl, latam_invoice

integration_tier (honest readiness):
  production — government-grade path (EG, SA)
  sandbox    — national format + test API path (IN, MX, AE, …)
  scaffold   — pipeline/XML smoke only (most EU/LATAM until dedicated build)
"""

from __future__ import annotations

from dataclasses import dataclass

import frappe

PEPPOL_BIS_PROFILE = "urn:peppol:bis:billing"
PEPPOL_EU_CUSTOMIZATION = "urn:cen.eu:en16931:2017#compliant#urn:peppol:pint:billing-1@eu-1"
UBL_NS = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"


@dataclass(frozen=True)
class CountryCatalogEntry:
	code: str
	label: str
	label_ar: str
	currency: str
	authority: str
	framework: str
	engine: str
	country_module: str = "generic"
	vat_percent: str = "0"
	customization_id: str = ""
	submit_path: str = "/einvoice/v1/submit"
	xml_markers: tuple[str, ...] = ()


def _peppol_entry(
	code: str,
	label: str,
	label_ar: str,
	currency: str,
	authority: str,
	vat: str,
	customization: str = "",
	markers: tuple[str, ...] = (),
) -> CountryCatalogEntry:
	return CountryCatalogEntry(
		code=code,
		label=label,
		label_ar=label_ar,
		currency=currency,
		authority=authority,
		framework="PEPPOL-UBL",
		engine="peppol_ubl",
		vat_percent=vat,
		customization_id=customization or PEPPOL_EU_CUSTOMIZATION,
		xml_markers=markers or ("CustomizationID", "AccountingSupplierParty", UBL_NS),
	)


# International plugin countries (not EG/SA)
PLUGIN_CATALOG: tuple[CountryCatalogEntry, ...] = (
	# ——— Americas ———
	CountryCatalogEntry(
		"MX", "Mexico SAT (CFDI)", "المكسيك", "MXN", "SAT_CFDI", "CFDI-4.0", "cfdi",
		xml_markers=("cfdi:Comprobante", "http://www.sat.gob.mx/cfd/4"),
	),
	CountryCatalogEntry(
		"BR", "Brazil NF-e", "البرازيل", "BRL", "SEFAZ_NFE", "NF-e-4.0", "nfe",
		submit_path="/nfe/v1/invoices",
		xml_markers=("nfeProc", "http://www.portalfiscal.inf.br/nfe"),
	),
	CountryCatalogEntry(
		"CO", "Colombia e-Invoicing", "كولومبيا", "COP", "DIAN_CO", "DIAN-UBL", "dian_ubl",
		vat_percent="19",
		submit_path="/dian/v1/invoices",
		xml_markers=("ProfileID", "DIAN 2.1", "DianExtensions", "CUFE-SHA384"),
	),
	CountryCatalogEntry(
		"CL", "Chile e-Invoicing", "تشيلي", "CLP", "SII_CL", "DTE-CL", "latam_invoice",
		vat_percent="19",
		xml_markers=("LatamTaxInvoice", "CL"),
	),
	CountryCatalogEntry(
		"PE", "Peru e-Invoicing", "بيرو", "PEN", "SUNAT_PE", "UBL-LATAM", "latam_invoice",
		vat_percent="18",
		xml_markers=("LatamTaxInvoice", "PE"),
	),
	CountryCatalogEntry(
		"AR", "Argentina e-Invoicing", "الأرجنتين", "ARS", "AFIP_AR", "UBL-LATAM", "latam_invoice",
		vat_percent="21",
		xml_markers=("LatamTaxInvoice", "AR"),
	),
	# ——— Middle East & Gulf ———
	CountryCatalogEntry(
		"AE", "UAE e-Invoicing", "الإمارات", "AED", "UAE_PEPPOL", "PINT-AE", "pint_ae",
		country_module="uae",
		vat_percent="5",
		xml_markers=("CustomizationID", PEPPOL_BIS_PROFILE, "pint-ae"),
	),
	CountryCatalogEntry(
		"OM", "Oman e-Invoicing", "عمان", "OMR", "OMAN_FTA", "PINT-UBL", "pint_gulf",
		vat_percent="5",
		customization_id="urn:peppol:international:tax:data:1p0::PINT#urn:peppol:poac:om:2025-Q2:pint-om-1p0@om-1p0",
		xml_markers=("pint-om", "AccountingSupplierParty"),
	),
	CountryCatalogEntry(
		"BH", "Bahrain e-Invoicing", "البحرين", "BHD", "NBR_BH", "PINT-UBL", "pint_gulf",
		vat_percent="10",
		customization_id="urn:peppol:international:tax:data:1p0::PINT#urn:peppol:poac:bh:2025-Q2:pint-bh-1p0@bh-1p0",
		xml_markers=("pint-bh",),
	),
	CountryCatalogEntry(
		"KW", "Kuwait e-Invoicing", "الكويت", "KWD", "KUWAIT_TAX", "PINT-UBL", "pint_gulf",
		customization_id="urn:peppol:international:tax:data:1p0::PINT#urn:peppol:poac:kw:2025-Q2:pint-kw-1p0@kw-1p0",
		xml_markers=("pint-kw",),
	),
	CountryCatalogEntry(
		"QA", "Qatar e-Invoicing", "قطر", "QAR", "QATAR_GTA", "PINT-UBL", "pint_gulf",
		customization_id="urn:peppol:international:tax:data:1p0::PINT#urn:peppol:poac:qa:2025-Q2:pint-qa-1p0@qa-1p0",
		xml_markers=("pint-qa",),
	),
	CountryCatalogEntry(
		"JO", "Jordan e-Invoicing", "الأردن", "JOD", "JOFOTARA", "JoFotara", "jofotara",
		submit_path="/api/v1/invoices",
		xml_markers=("JoFotaraInvoice", "jofotara.gov.jo"),
	),
	# ——— Europe ———
	CountryCatalogEntry(
		"IT", "Italy e-Invoicing", "إيطاليا", "EUR", "IT_ADE", "FatturaPA", "fatturapa",
		vat_percent="22",
		submit_path="/sdi/v1/invoices",
		xml_markers=("FatturaElettronica", "FatturaElettronicaBody", "CodiceDestinatario"),
	),
	CountryCatalogEntry(
		"ES", "Spain e-Invoicing", "إسبانيا", "EUR", "ES_AEAT", "Facturae", "facturae",
		vat_percent="21",
		submit_path="/facturae/v1/submit",
		xml_markers=("fe:Facturae", "SchemaVersion", "InvoiceIssuerType"),
	),
	CountryCatalogEntry(
		"DE", "Germany e-Invoicing", "ألمانيا", "EUR", "DE_BMF", "XRechnung", "xrechnung",
		vat_percent="19",
		submit_path="/xrechnung/v1/invoices",
		xml_markers=("BuyerReference", "Leitweg", "CustomizationID"),
	),
	CountryCatalogEntry(
		"FR", "France e-Invoicing", "فرنسا", "EUR", "FR_DGFIP", "Factur-X", "facturx",
		vat_percent="20",
		submit_path="/facturx/v1/submit",
		xml_markers=("CrossIndustryInvoice", "GuidelineSpecifiedDocumentContextParameter"),
	),
	_peppol_entry("NL", "Netherlands e-Invoicing", "هولندا", "EUR", "NL_BELASTING", "21"),
	_peppol_entry("BE", "Belgium e-Invoicing", "بلجيكا", "EUR", "BE_FOD", "21"),
	_peppol_entry("DK", "Denmark e-Invoicing", "الدنمارك", "DKK", "DK_SKAT", "25"),
	_peppol_entry("NO", "Norway e-Invoicing", "النرويج", "NOK", "NO_SKATTEETATEN", "25"),
	_peppol_entry("SE", "Sweden e-Invoicing", "السويد", "SEK", "SE_SKV", "25"),
	_peppol_entry("FI", "Finland e-Invoicing", "فنلندا", "EUR", "FI_VEROHALLINTO", "25.5"),
	_peppol_entry("PT", "Portugal e-Invoicing", "البرتغال", "EUR", "PT_AT", "23"),
	CountryCatalogEntry(
		"PL", "Poland e-Invoicing", "بولندا", "PLN", "PL_KAS", "KSeF-FA2", "ksef_fa2",
		vat_percent="23",
		submit_path="/api/v2/invoices",
		xml_markers=("FA", "Podmiot1", "Podmiot2", "Fa"),
	),
	_peppol_entry("RO", "Romania e-Invoicing", "رومانيا", "RON", "RO_ANAF", "19"),
	# ——— Asia-Pacific ———
	CountryCatalogEntry(
		"IN", "India e-Invoicing", "الهند", "INR", "GST_IN", "GST-IRN", "gst_irn",
		vat_percent="18",
		submit_path="/einvoice/v1/generate-irn",
		xml_markers=("Version", "TranDtls", "DocDtls", "SellerDtls", "BuyerDtls", "ItemList"),
	),
	CountryCatalogEntry(
		"SG", "Singapore e-Invoicing", "سنغافورة", "SGD", "IRAS_SG", "PEPPOL-UBL", "peppol_ubl",
		vat_percent="9",
		customization_id="urn:peppol:poac:sg:2024:pint-sg-1@sg-1",
	),
	CountryCatalogEntry(
		"ID", "Indonesia e-Invoicing", "إندونيسيا", "IDR", "DJP_ID", "PEPPOL-UBL", "peppol_ubl",
		vat_percent="11",
		customization_id="urn:peppol:poac:id:2024:einvoice-1@id-1",
	),
	CountryCatalogEntry(
		"KR", "South Korea e-Invoicing", "كوريا الجنوبية", "KRW", "NTS_KR", "PEPPOL-UBL", "peppol_ubl",
		vat_percent="10",
		customization_id="urn:peppol:poac:kr:2024:einvoice-1@kr-1",
	),
	CountryCatalogEntry(
		"JP", "Japan e-Invoicing", "اليابان", "JPY", "NTA_JP", "PEPPOL-UBL", "peppol_ubl",
		vat_percent="10",
		customization_id="urn:peppol:poac:jp:2024:qualified-invoice-1@jp-1",
	),
	CountryCatalogEntry(
		"CN", "China e-Invoicing", "الصين", "CNY", "GTAX_CN", "PEPPOL-UBL", "peppol_ubl",
		vat_percent="13",
		customization_id="urn:peppol:poac:cn:2024:fapiao-ubl-1@cn-1",
	),
	# ——— Africa ———
	CountryCatalogEntry(
		"ZA", "South Africa e-Invoicing", "جنوب أفريقيا", "ZAR", "SARS_ZA", "PEPPOL-UBL", "peppol_ubl",
		vat_percent="15",
		customization_id="urn:peppol:poac:za:2024:einvoice-1@za-1",
	),
	CountryCatalogEntry(
		"KE", "Kenya e-Invoicing", "كينيا", "KES", "KRA_KE", "PEPPOL-UBL", "peppol_ubl",
		vat_percent="16",
		customization_id="urn:peppol:poac:ke:2024:einvoice-1@ke-1",
	),
	CountryCatalogEntry(
		"UG", "Uganda e-Invoicing", "أوغندا", "UGX", "URA_UG", "PEPPOL-UBL", "peppol_ubl",
		vat_percent="18",
		customization_id="urn:peppol:poac:ug:2024:einvoice-1@ug-1",
	),
	# ——— Turkey ———
	CountryCatalogEntry(
		"TR", "Turkey e-Invoicing", "تركيا", "TRY", "GIB_TR", "e-Fatura", "peppol_ubl",
		vat_percent="20",
		customization_id="urn:peppol:poac:tr:2024:e-fatura-1@tr-1",
		xml_markers=("CustomizationID", "TR"),
	),
)

PLUGIN_CATALOG_BY_CODE: dict[str, CountryCatalogEntry] = {e.code: e for e in PLUGIN_CATALOG}
PLUGIN_COUNTRY_CODES: frozenset[str] = frozenset(PLUGIN_CATALOG_BY_CODE.keys())

# Honest integration maturity (not the same as «smoke test passes»).
COUNTRY_INTEGRATION_TIERS: dict[str, str] = {
	"EG": "production",
	"SA": "production",
	# Phase 1 — national engine work in progress
	"IN": "sandbox",
	"MX": "sandbox",
	"IT": "sandbox",
	"BR": "sandbox",
	"PL": "sandbox",
	# Phase 2
	"AE": "sandbox",
	"ES": "sandbox",
	"CO": "sandbox",
	"DE": "sandbox",
	"FR": "sandbox"
	}


def integration_tier_for_country(country_code: str) -> str:
	code = normalize_country_code(country_code)
	return COUNTRY_INTEGRATION_TIERS.get(code, "scaffold")


def pipeline_enabled_for_tier(tier: str) -> bool:
	return tier in ("scaffold", "sandbox", "production")


def production_ready_for_tier(tier: str) -> bool:
	return tier == "production"


def get_catalog_entry(country_code: str) -> CountryCatalogEntry | None:
	return PLUGIN_CATALOG_BY_CODE.get((country_code or "").strip().upper())


def normalize_country_code(raw: str | None) -> str:
	"""Extract ISO code from stored value or «DE — Germany» select label."""
	text = (raw or "EG").strip()
	if not text:
		return "EG"
	if " — " in text:
		text = text.split(" — ", 1)[0].strip()
	if " - " in text and len(text) > 4:
		text = text.split(" - ", 1)[0].strip()
	return text.upper()[:2] if len(text) >= 2 else text.upper()


def country_display_name(country_code: str, *, lang: str | None = None) -> str:
	"""Human-readable country name for Branch UI (EN or AR)."""
	code = normalize_country_code(country_code)
	current_lang = lang or getattr(frappe.local, "lang", "en")
	use_ar = (current_lang or "en").startswith("ar")
	if code == "EG":
		return "مصر" if use_ar else "Egypt"
	if code == "SA":
		return "السعودية" if use_ar else "Saudi Arabia"
	entry = get_catalog_entry(code)
	if not entry:
		return code
	if use_ar and entry.label_ar:
		return entry.label_ar
	label = entry.label.split("(")[0].strip() if "(" in entry.label else entry.label
	for suffix in (" e-Invoicing", " e-Invoice", " (CFDI)", " NF-e"):
		if label.endswith(suffix):
			label = label[: -len(suffix)].strip()
	return label


def branch_country_select_options(*, lang: str | None = None) -> list[dict[str, str]]:
	"""Options for Branch country_code select: code + display label."""
	codes = sorted({"EG", "SA", *PLUGIN_COUNTRY_CODES})
	out: list[dict[str, str]] = []
	for code in codes:
		name = country_display_name(code, lang=lang)
		out.append(
			{
				"code": code,
				"name": name,
				"label": f"{code} — {name}"
	}
		)
	return out


def branch_country_label_for_code(country_code: str, *, lang: str | None = None) -> str:
	"""Canonical Select value «CODE — name» for a country."""
	code = normalize_country_code(country_code)
	for row in branch_country_select_options(lang=lang):
		if row["code"] == code:
			return row["label"]
	return code


def branch_country_options() -> str:
	"""Branch.country_code Select options — one row per country (CODE — name)."""
	return "\n".join(row["label"] for row in branch_country_select_options())


def country_tax_settings_options() -> str:
	return "\n".join(sorted(PLUGIN_COUNTRY_CODES))


def xml_markers_for_country(country_code: str) -> tuple[str, ...]:
	entry = get_catalog_entry(country_code)
	if entry and entry.xml_markers:
		return entry.xml_markers
	return ("CustomizationID", UBL_NS)
