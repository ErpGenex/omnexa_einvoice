# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Register e-invoice adapters on the shared ``omnexa_core`` IntegrationHub."""


def register_einvoice_adapters(hub):
	from omnexa_einvoice.einvoice_adapters import EgyptETAAdapter, SaudiZatcaAdapter
	from omnexa_einvoice.tax_engine.adapters import register_plugin_adapters

	eg = EgyptETAAdapter()
	sa = SaudiZatcaAdapter()
	hub.register(eg)
	hub.register(sa)
	hub.register_country_adapter("EG", eg)
	hub.register_country_adapter("SA", sa)
	register_plugin_adapters(hub)
