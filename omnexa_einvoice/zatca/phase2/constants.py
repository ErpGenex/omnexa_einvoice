# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""ZATCA Fatoora API paths (ZATCA technical documentation)."""

ZATCA_HOST = "https://gw-fatoora.zatca.gov.sa"

ENVIRONMENT_PORTALS = {
	"sandbox": "developer-portal",
	"simulation": "simulation",
	"production": "core",
}

PATH_COMPLIANCE_CSID = "/e-invoicing/{portal}/compliance"
PATH_PRODUCTION_CSID = "/e-invoicing/{portal}/production/csids"
PATH_COMPLIANCE_INVOICE = "/e-invoicing/{portal}/compliance/invoices"
PATH_REPORTING = "/e-invoicing/{portal}/invoices/reporting/single"
PATH_CLEARANCE = "/e-invoicing/{portal}/invoices/clearance/single"

API_VERSION_HEADER = "V2"
ACCEPT_LANGUAGE = "en"
