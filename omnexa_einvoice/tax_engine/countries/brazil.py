# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""Brazil NF-e."""

from omnexa_einvoice.tax_engine.constants import COUNTRY_REGISTRY
from omnexa_einvoice.tax_engine.countries._plugin_country import make_country_handlers

META = COUNTRY_REGISTRY["BR"]
process_hub_payload, dispatch_sales_invoice = make_country_handlers("BR")
