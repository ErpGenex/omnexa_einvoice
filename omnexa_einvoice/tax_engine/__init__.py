# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""
Multi-country tax routing (branch-based).

Does NOT replace Egypt ETA or ZATCA pipelines — only resolves which provider
applies for a branch. Existing Egypt code paths remain the default.
"""

from omnexa_einvoice.tax_engine.constants import COUNTRY_REGISTRY
from omnexa_einvoice.tax_engine.registry import resolve_adapter_name
from omnexa_einvoice.tax_engine.router import is_egypt_branch, resolve_tax_provider_for_branch

__all__ = [
	"COUNTRY_REGISTRY",
	"is_egypt_branch",
	"resolve_adapter_name",
	"resolve_tax_provider_for_branch",
]
