# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Per-country e-invoice print design tokens (colors, authority, layout)."""

from __future__ import annotations

from dataclasses import dataclass

from omnexa_einvoice.tax_engine.country_catalog import PLUGIN_CATALOG, get_catalog_entry


@dataclass(frozen=True)
class EInvoicePrintDesign:
	country_code: str
	label_en: str
	label_ar: str
	framework: str
	authority: str
	primary_color: str
	accent_color: str
	header_bg: str
	rtl: bool
	invoice_title_en: str
	invoice_title_ar: str
	footer_en: str
	footer_ar: str
	template_family: str


_FAMILY_STYLES: dict[str, dict[str, str]] = {
	"eg_eta": {
		"primary": "#0B5E3C",
		"accent": "#C9A227",
		"header_bg": "#E8F5EE",
		"title_en": "Tax Invoice",
		"title_ar": "فاتورة ضريبية",
		"footer_en": "Egyptian Tax Authority (ETA) — e-Invoice",
		"footer_ar": "مصلحة الضرائب المصرية — فاتورة إلكترونية"
	},
	"sa_zatca": {
		"primary": "#006C35",
		"accent": "#C8A951",
		"header_bg": "#E6F4EC",
		"title_en": "Tax Invoice",
		"title_ar": "فاتورة ضريبية",
		"footer_en": "ZATCA — Fatoora e-Invoice",
		"footer_ar": "هيئة الزكاة والضريبة والجمارك — فاتورة إلكترونية"
	},
	"gulf_pint": {
		"primary": "#0F3D75",
		"accent": "#00A3E0",
		"header_bg": "#E8F0FA",
		"title_en": "Tax Invoice",
		"title_ar": "فاتورة ضريبية",
		"footer_en": "PINT e-Invoice (Gulf)",
		"footer_ar": "فاتورة إلكترونية — دول الخليج"
	},
	"peppol_eu": {
		"primary": "#003399",
		"accent": "#FFCC00",
		"header_bg": "#E8EEF9",
		"title_en": "Tax Invoice",
		"title_ar": "فاتورة ضريبية",
		"footer_en": "PEPPOL BIS Billing 3.0",
		"footer_ar": "فاتورة إلكترونية — PEPPOL"
	},
	"mx_cfdi": {
		"primary": "#006341",
		"accent": "#C8102E",
		"header_bg": "#E8F2ED",
		"title_en": "CFDI Invoice",
		"title_ar": "فاتورة CFDI",
		"footer_en": "Mexico SAT — CFDI 4.0",
		"footer_ar": "المكسيك SAT — CFDI"
	},
	"br_nfe": {
		"primary": "#009C3B",
		"accent": "#FFDF00",
		"header_bg": "#E8F7EE",
		"title_en": "NF-e Invoice",
		"title_ar": "فاتورة NF-e",
		"footer_en": "Brazil SEFAZ — NF-e",
		"footer_ar": "البرازيل SEFAZ — NF-e"
	},
	"latam": {
		"primary": "#1E3A5F",
		"accent": "#E67E22",
		"header_bg": "#EEF2F7",
		"title_en": "Electronic Tax Invoice",
		"title_ar": "فاتورة ضريبية إلكترونية",
		"footer_en": "Latin America e-Invoice",
		"footer_ar": "فاتورة إلكترونية — أمريكا اللاتينية"
	},
	"jordan": {
		"primary": "#007A3D",
		"accent": "#CE1126",
		"header_bg": "#E8F4ED",
		"title_en": "Tax Invoice",
		"title_ar": "فاتورة ضريبية",
		"footer_en": "Jordan ISTD — JoFotara",
		"footer_ar": "الأردن — JoFotara"}
	}


def _template_family(code: str, engine: str) -> str:
	if code == "EG":
		return "eg_eta"
	if code == "SA":
		return "sa_zatca"
	if code == "JO":
		return "jordan"
	if engine == "cfdi":
		return "mx_cfdi"
	if engine == "nfe":
		return "br_nfe"
	if engine == "pint_gulf" or engine == "pint_ae":
		return "gulf_pint"
	if engine == "latam_invoice":
		return "latam"
	return "peppol_eu"


def get_print_design(country_code: str) -> EInvoicePrintDesign:
	code = (country_code or "EG").strip().upper()
	if code == "EG":
		family = "eg_eta"
		return EInvoicePrintDesign(
			country_code="EG",
			label_en="Egypt",
			label_ar="مصر",
			framework="ETA",
			authority="ETA",
			primary_color=_FAMILY_STYLES[family]["primary"],
			accent_color=_FAMILY_STYLES[family]["accent"],
			header_bg=_FAMILY_STYLES[family]["header_bg"],
			rtl=True,
			invoice_title_en=_FAMILY_STYLES[family]["title_en"],
			invoice_title_ar=_FAMILY_STYLES[family]["title_ar"],
			footer_en=_FAMILY_STYLES[family]["footer_en"],
			footer_ar=_FAMILY_STYLES[family]["footer_ar"],
			template_family=family,
		)
	if code == "SA":
		family = "sa_zatca"
		return EInvoicePrintDesign(
			country_code="SA",
			label_en="Saudi Arabia",
			label_ar="السعودية",
			framework="ZATCA",
			authority="ZATCA",
			primary_color=_FAMILY_STYLES[family]["primary"],
			accent_color=_FAMILY_STYLES[family]["accent"],
			header_bg=_FAMILY_STYLES[family]["header_bg"],
			rtl=True,
			invoice_title_en=_FAMILY_STYLES[family]["title_en"],
			invoice_title_ar=_FAMILY_STYLES[family]["title_ar"],
			footer_en=_FAMILY_STYLES[family]["footer_en"],
			footer_ar=_FAMILY_STYLES[family]["footer_ar"],
			template_family=family,
		)
	entry = get_catalog_entry(code)
	if not entry:
		family = "peppol_eu"
		return EInvoicePrintDesign(
			country_code=code,
			label_en=code,
			label_ar=code,
			framework="E-Invoice",
			authority=code,
			primary_color=_FAMILY_STYLES[family]["primary"],
			accent_color=_FAMILY_STYLES[family]["accent"],
			header_bg=_FAMILY_STYLES[family]["header_bg"],
			rtl=False,
			invoice_title_en=_FAMILY_STYLES[family]["title_en"],
			invoice_title_ar=_FAMILY_STYLES[family]["title_ar"],
			footer_en=_FAMILY_STYLES[family]["footer_en"],
			footer_ar=_FAMILY_STYLES[family]["footer_ar"],
			template_family=family,
		)
	family = _template_family(code, entry.engine)
	style = _FAMILY_STYLES[family]
	return EInvoicePrintDesign(
		country_code=code,
		label_en=entry.label.split("(")[0].strip() if "(" in entry.label else entry.label,
		label_ar=entry.label_ar,
		framework=entry.framework,
		authority=entry.authority,
		primary_color=style["primary"],
		accent_color=style["accent"],
		header_bg=style["header_bg"],
		rtl=code in ("AE", "OM", "BH", "KW", "QA", "JO", "SA", "EG"),
		invoice_title_en=style["title_en"],
		invoice_title_ar=style["title_ar"],
		footer_en=f"{entry.framework} — {entry.authority}",
		footer_ar=f"{entry.label_ar} — {entry.framework}",
		template_family=family,
	)


def all_country_codes_for_print() -> list[str]:
	return ["EG", "SA", *sorted(e.code for e in PLUGIN_CATALOG)]
