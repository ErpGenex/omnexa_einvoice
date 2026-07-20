// Copyright (c) 2026, Omnexa and contributors
// License: MIT

frappe.ui.form.on("Country Tax Settings", {
	country_code(frm) {
		if (frm.doc.country_code === "AE") {
			frm.set_df_property("tax_authority_name", "read_only", 0);
			if (!frm.doc.tax_authority_name) {
				frm.set_value("tax_authority_name", __("UAE FTA / Peppol PINT AE"));
			}
		}
	},
	uae_seller_tin(frm) {
		if (frm.doc.country_code === "AE" && frm.doc.uae_seller_tin) {
			frm.set_value("tax_registration_number", frm.doc.uae_seller_tin);
		}
	},
});
