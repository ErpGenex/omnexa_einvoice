# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Country tax metadata — built from ``country_catalog`` + EG/SA."""

from __future__ import annotations

from dataclasses import dataclass

from omnexa_einvoice.tax_engine.country_catalog import (
	PLUGIN_CATALOG,
	PLUGIN_COUNTRY_CODES,
	branch_country_options,
	integration_tier_for_country,
	pipeline_enabled_for_tier,
	production_ready_for_tier,
)


@dataclass(frozen=True)
class CountryTaxMeta:
	country_code: str
	adapter_name: str
	label: str
	country_module: str
	integration_tier: str = "scaffold"
	pipeline_enabled: bool = True
	production_ready: bool = False
	document_types: tuple[str, ...] = ("invoice",)


def _build_registry() -> dict[str, CountryTaxMeta]:
	reg: dict[str, CountryTaxMeta] = {
		"EG": CountryTaxMeta(
			"EG",
			"einvoice_eta",
			"Egypt ETA",
			"egypt",
			integration_tier="production",
			pipeline_enabled=True,
			production_ready=True,
			document_types=("invoice", "receipt", "credit_note"),
		),
		"SA": CountryTaxMeta(
			"SA",
			"einvoice_zatca",
			"Saudi ZATCA",
			"saudi",
			integration_tier="production",
			pipeline_enabled=True,
			production_ready=True,
			document_types=("tax_invoice", "simplified_invoice", "credit_note"),
		),
	}
	for entry in PLUGIN_CATALOG:
		tier = integration_tier_for_country(entry.code)
		reg[entry.code] = CountryTaxMeta(
			entry.code,
			f"einvoice_{entry.code.lower()}",
			entry.label,
			entry.country_module,
			integration_tier=tier,
			pipeline_enabled=pipeline_enabled_for_tier(tier),
			production_ready=production_ready_for_tier(tier),
			document_types=("invoice", "credit_note"),
		)
	return reg


COUNTRY_REGISTRY: dict[str, CountryTaxMeta] = _build_registry()
BRANCH_COUNTRY_OPTIONS = branch_country_options()
