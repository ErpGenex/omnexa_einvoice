// Copyright (c) 2026, Omnexa and contributors
// License: MIT. See license.txt

const ETA_URLS = {
	preprod: "https://api.preprod.invoicing.eta.gov.eg",
	prod: "https://api.invoicing.eta.gov.eg",
};
const ETA_TOKEN_URLS = {
	preprod: "https://id.preprod.eta.gov.eg/connect/token",
	prod: "https://id.eta.gov.eg/connect/token",
};

function _fill_eta_urls(frm) {
	if (frm.doc.eta_ereceipt_enabled && !frm.doc.eta_receipt_base_url) {
		const env = frm.doc.eta_receipt_environment || "preprod";
		frm.set_value("eta_receipt_base_url", ETA_URLS[env] || ETA_URLS.preprod);
	}
	if (frm.doc.eta_einvoice_enabled && !frm.doc.eta_invoice_base_url) {
		const env = frm.doc.eta_invoice_environment || "preprod";
		frm.set_value("eta_invoice_base_url", ETA_URLS[env] || ETA_URLS.preprod);
	}
}

frappe.ui.form.on("Branch", {
	refresh(frm) {
		if (frm.doc.eta_ereceipt_enabled) {
			frm.dashboard.add_indicator(__("E-Receipt enabled"), "blue");
		}
		if (frm.doc.eta_einvoice_enabled) {
			frm.dashboard.add_indicator(__("E-Invoice enabled"), "green");
		}
		if (!frm.is_new() && (frm.doc.eta_ereceipt_enabled || frm.doc.eta_einvoice_enabled)) {
			frm.add_custom_button(__("Open E-Invoice workspace"), () => {
				frappe.set_route("Workspaces", "E-Invoice");
			});
		}
	},
	eta_ereceipt_enabled(frm) {
		if (frm.doc.eta_ereceipt_enabled && !frm.doc.eta_receipt_environment) {
			frm.set_value("eta_receipt_environment", "prod");
		}
		_fill_eta_urls(frm);
		if (frm.doc.eta_ereceipt_enabled && !frm.doc.eta_branch_code && frm.doc.branch_code) {
			frm.set_value("eta_branch_code", frm.doc.branch_code);
		}
	},
	eta_einvoice_enabled(frm) {
		if (frm.doc.eta_einvoice_enabled && !frm.doc.eta_invoice_environment) {
			frm.set_value("eta_invoice_environment", "preprod");
		}
		_fill_eta_urls(frm);
	},
	eta_receipt_environment(frm) {
		if (frm.doc.eta_ereceipt_enabled) {
			const env = frm.doc.eta_receipt_environment || "prod";
			frm.set_value("eta_receipt_base_url", ETA_URLS[env] || ETA_URLS.prod);
			const tokenUrl = ETA_TOKEN_URLS[env] || ETA_TOKEN_URLS.prod;
			frm.set_df_property(
				"eta_receipt_environment",
				"description",
				env === "prod"
					? __("Production — Token: {0} | API: {1}", [tokenUrl, ETA_URLS.prod])
					: __("Preprod — Token: {0} | API: {1}", [tokenUrl, ETA_URLS.preprod])
			);
			if (env === "prod") {
				frm.dashboard.add_indicator(__("E-Receipt: Production"), "green");
			}
		}
	},
	eta_invoice_environment(frm) {
		if (frm.doc.eta_einvoice_enabled) {
			frm.set_value("eta_invoice_base_url", ETA_URLS[frm.doc.eta_invoice_environment] || ETA_URLS.preprod);
		}
	},
	branch_code(frm) {
		if (frm.doc.eta_ereceipt_enabled && !frm.doc.eta_branch_code) {
			frm.set_value("eta_branch_code", frm.doc.branch_code);
		}
	},
});
