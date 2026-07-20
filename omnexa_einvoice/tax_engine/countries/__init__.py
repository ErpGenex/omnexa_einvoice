# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Per-country tax modules — generic plugin handler or dedicated module."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

from omnexa_einvoice.tax_engine.constants import COUNTRY_REGISTRY
from omnexa_einvoice.tax_engine.countries._plugin_country import make_country_handlers


def get_country_module(country_code: str):
	code = (country_code or "").strip().upper()
	meta = COUNTRY_REGISTRY.get(code)
	if not meta:
		raise ValueError(f"Unknown country code: {code}")
	if meta.country_module == "generic":
		ph, ds = make_country_handlers(code)
		return SimpleNamespace(
			META=meta,
			process_hub_payload=ph,
			dispatch_sales_invoice=ds,
		)
	return importlib.import_module(f"omnexa_einvoice.tax_engine.countries.{meta.country_module}")


def dispatch_sales_invoice_for_country(country_code: str, doc, *, branch: str | None = None, **kwargs):
	mod = get_country_module(country_code)
	if not hasattr(mod, "dispatch_sales_invoice"):
		from omnexa_einvoice.tax_engine.constants import COUNTRY_REGISTRY

		meta = COUNTRY_REGISTRY[country_code]
		from omnexa_einvoice.tax_engine.countries._base import dispatch_sales_invoice_scaffold

		return dispatch_sales_invoice_scaffold(doc, meta=meta, branch=branch, **kwargs)
	return mod.dispatch_sales_invoice(doc, branch=branch, **kwargs)
