# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Hub adapters for non-EG / non-SA countries (plugin pipeline per country module)."""

from __future__ import annotations

from typing import Any

from frappe import _

from omnexa_core.omnexa_core.integration_hub import IntegrationHubError, IntegrationResult

from omnexa_einvoice.tax_engine.constants import COUNTRY_REGISTRY, CountryTaxMeta


class PluginCountryAdapter:
	"""Generic hub adapter; delegates metadata to ``tax_engine.countries.*``."""

	meta: CountryTaxMeta

	def __init__(self, meta: CountryTaxMeta):
		self.meta = meta

	@property
	def name(self) -> str:
		return self.meta.adapter_name

	@property
	def supported_document_types(self) -> set[str]:
		return set(self.meta.document_types)

	def process(self, payload: dict[str, Any]) -> IntegrationResult:
		reference = (payload.get("reference_name") or "").strip()
		if not reference:
			raise IntegrationHubError(_("reference_name is required for {0}.").format(self.meta.label))
		document_type = (payload.get("document_type") or "invoice").strip().lower()
		if document_type not in self.supported_document_types:
			raise IntegrationHubError(
				_("{0} supports document_type: {1}.").format(
					self.meta.label, ", ".join(sorted(self.supported_document_types))
				)
			)
		from omnexa_einvoice.tax_engine.countries import get_country_module

		mod = get_country_module(self.meta.country_code)
		if hasattr(mod, "process_hub_payload"):
			return mod.process_hub_payload(payload, meta=self.meta)
		if self.meta.pipeline_enabled:
			from omnexa_einvoice.tax_engine.plugin.service import run_phase1

			result = run_phase1(payload, country_code=self.meta.country_code)
			reference = (payload.get("reference_name") or "").strip()
			document_type = (payload.get("document_type") or "invoice").strip().lower()
			return IntegrationResult(
				status="completed",
				provider_reference=f"{self.meta.country_code}-{document_type.upper()}-{reference}",
				message=_("{0} Phase 1 completed.").format(self.meta.label),
				data={"phase1": result
	},
			)
		provider_ref = f"{self.meta.country_code}-{document_type.upper()}-{reference}"
		return IntegrationResult(
			status="queued",
			provider_reference=provider_ref,
			message=_("{0} submission queued (configure Country Tax Settings).").format(self.meta.label),
			data={
				"country_code": self.meta.country_code,
				"adapter": self.meta.adapter_name,
				"integration_tier": self.meta.integration_tier,
				"pipeline_enabled": self.meta.pipeline_enabled,
				"production_ready": self.meta.production_ready
	},
		)


def register_plugin_adapters(hub) -> None:
	"""Register plugin adapters and country_code mapping (skips EG/SA — registered separately)."""
	for code, meta in COUNTRY_REGISTRY.items():
		if code in ("EG", "SA"):
			continue
		adapter = PluginCountryAdapter(meta)
		hub.register(adapter)
		hub.register_country_adapter(code, adapter)
