# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Per-country plugin specifications — built from ``country_catalog``."""

from __future__ import annotations

from dataclasses import dataclass

from omnexa_einvoice.tax_engine.country_catalog import PLUGIN_CATALOG, UBL_NS


@dataclass(frozen=True)
class CountryPluginSpec:
	country_code: str
	authority_code: str
	default_currency: str
	xml_root_tag: str
	xml_namespace: str
	submit_path: str
	phase2_requires_api: bool = True


def _build_specs() -> dict[str, CountryPluginSpec]:
	specs: dict[str, CountryPluginSpec] = {}
	for entry in PLUGIN_CATALOG:
		root = "Invoice"
		ns = UBL_NS
		if entry.engine == "cfdi":
			root, ns = "cfdi:Comprobante", "http://www.sat.gob.mx/cfd/4"
		elif entry.engine == "gst_irn":
			root, ns = "GstIrnDocument", "urn:erpgenex:gst:irn:1.1"
		elif entry.engine == "fatturapa":
			root, ns = "FatturaElettronica", "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"
		elif entry.engine == "ksef_fa2":
			root, ns = "FA", "http://crd.gov.pl/wzor/2023/06/29/12648/"
		elif entry.engine == "nfe":
			root, ns = "nfeProc", "http://www.portalfiscal.inf.br/nfe"
		elif entry.engine == "jofotara":
			root, ns = "JoFotaraInvoice", "https://jofotara.gov.jo/invoice/v1"
		elif entry.engine == "latam_invoice":
			root, ns = "LatamTaxInvoice", f"urn:erpgenex:latam:{entry.code.lower()}"
		specs[entry.code] = CountryPluginSpec(
			entry.code,
			entry.authority,
			entry.currency,
			root,
			ns,
			entry.submit_path,
		)
	return specs


PLUGIN_SPECS: dict[str, CountryPluginSpec] = _build_specs()


def get_spec(country_code: str) -> CountryPluginSpec:
	code = (country_code or "").strip().upper()
	spec = PLUGIN_SPECS.get(code)
	if not spec:
		raise ValueError(f"No plugin spec for {code}")
	return spec
