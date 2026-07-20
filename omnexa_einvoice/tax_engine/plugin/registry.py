# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Registry of per-country XML engines — built from ``country_catalog``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from omnexa_einvoice.tax_engine.country_catalog import PLUGIN_CATALOG, get_catalog_entry
from omnexa_einvoice.tax_engine.plugin.engines.brazil import build_nfe_xml
from omnexa_einvoice.tax_engine.plugin.engines.india import build_gst_irn_json
from omnexa_einvoice.tax_engine.plugin.engines.colombia_dian import build_dian_ubl_xml
from omnexa_einvoice.tax_engine.plugin.engines.france_facturx import build_facturx_xml
from omnexa_einvoice.tax_engine.plugin.engines.germany_xrechnung import build_xrechnung_xml
from omnexa_einvoice.tax_engine.plugin.engines.italy_fatturapa import build_fatturapa_xml
from omnexa_einvoice.tax_engine.plugin.engines.poland_ksef import build_ksef_fa2_xml
from omnexa_einvoice.tax_engine.plugin.engines.spain_facturae import build_facturae_xml
from omnexa_einvoice.tax_engine.plugin.engines.gulf import build_gulf_xml
from omnexa_einvoice.tax_engine.plugin.engines.jordan import build_jordan_xml
from omnexa_einvoice.tax_engine.plugin.engines.latam import build_latam_xml
from omnexa_einvoice.tax_engine.plugin.engines.mexico import build_cfdi_xml
from omnexa_einvoice.tax_engine.plugin.engines.peppol_intl import build_peppol_xml
from omnexa_einvoice.tax_engine.plugin.specs import get_spec

BuildXmlFn = Callable[[dict[str, Any]], str]


@dataclass(frozen=True)
class CountryEngineMeta:
	country_code: str
	framework: str
	authority_code: str
	build_xml: BuildXmlFn
	uses_dedicated_module: bool = False


def _gulf_builder(code: str) -> BuildXmlFn:
	def _build(document: dict[str, Any]) -> str:
		return build_gulf_xml(document, country_code=code)

	return _build


def _peppol_builder(code: str) -> BuildXmlFn:
	def _build(document: dict[str, Any]) -> str:
		return build_peppol_xml(document, country_code=code)

	return _build


def _latam_builder(code: str) -> BuildXmlFn:
	def _build(document: dict[str, Any]) -> str:
		return build_latam_xml(document, country_code=code)

	return _build


def _engine_for_entry(entry) -> CountryEngineMeta:
	code = entry.code
	if entry.engine == "cfdi":
		return CountryEngineMeta(code, entry.framework, entry.authority, build_cfdi_xml)
	if entry.engine == "gst_irn":
		return CountryEngineMeta(code, entry.framework, entry.authority, build_gst_irn_json)
	if entry.engine == "fatturapa":
		return CountryEngineMeta(code, entry.framework, entry.authority, build_fatturapa_xml)
	if entry.engine == "ksef_fa2":
		return CountryEngineMeta(code, entry.framework, entry.authority, build_ksef_fa2_xml)
	if entry.engine == "facturae":
		return CountryEngineMeta(code, entry.framework, entry.authority, build_facturae_xml)
	if entry.engine == "dian_ubl":
		return CountryEngineMeta(code, entry.framework, entry.authority, build_dian_ubl_xml)
	if entry.engine == "xrechnung":
		return CountryEngineMeta(code, entry.framework, entry.authority, build_xrechnung_xml)
	if entry.engine == "facturx":
		return CountryEngineMeta(code, entry.framework, entry.authority, build_facturx_xml)
	if entry.engine == "nfe":
		return CountryEngineMeta(code, entry.framework, entry.authority, build_nfe_xml)
	if entry.engine == "pint_gulf":
		return CountryEngineMeta(code, entry.framework, entry.authority, _gulf_builder(code))
	if entry.engine == "jofotara":
		return CountryEngineMeta(code, entry.framework, entry.authority, build_jordan_xml)
	if entry.engine == "latam_invoice":
		return CountryEngineMeta(code, entry.framework, entry.authority, _latam_builder(code))
	if entry.engine == "pint_ae":
		return CountryEngineMeta(
			code, entry.framework, entry.authority, lambda d: d.get("_xml") or "", uses_dedicated_module=True
		)
	return CountryEngineMeta(code, entry.framework, entry.authority, _peppol_builder(code))


def _build_engines() -> dict[str, CountryEngineMeta]:
	return {entry.code: _engine_for_entry(entry) for entry in PLUGIN_CATALOG}


ENGINES: dict[str, CountryEngineMeta] = _build_engines()


def get_engine(country_code: str) -> CountryEngineMeta:
	code = (country_code or "").strip().upper()
	engine = ENGINES.get(code)
	if engine:
		return engine
	spec = get_spec(code)
	from omnexa_einvoice.tax_engine.plugin.xml_builder import build_invoice_xml

	return CountryEngineMeta(
		code,
		"GENERIC",
		spec.authority_code,
		lambda doc, s=spec: build_invoice_xml(doc, s),
	)


def is_dedicated_module(country_code: str) -> bool:
	return get_engine(country_code).uses_dedicated_module
