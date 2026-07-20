// Copyright (c) 2026, Omnexa and contributors
// License: MIT

frappe.ui.form.on("ZATCA Company Settings", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Generate CSR"), () => {
			frappe.call({
				method: "omnexa_einvoice.zatca.phase2.onboarding.generate_csr_for_settings",
				args: { settings_name: frm.doc.name },
				callback() {
					frm.reload_doc();
					frappe.show_alert({ message: __("CSR generated"), indicator: "green" });
				},
			});
		});

		frm.add_custom_button(__("Compliance CSID (OTP)"), () => {
			frappe.prompt(
				{ fieldname: "otp", fieldtype: "Data", label: __("OTP from Fatoora portal"), reqd: 1 },
				(values) => {
					frappe.call({
						method: "omnexa_einvoice.zatca.phase2.onboarding.onboard_compliance_csid",
						args: { settings_name: frm.doc.name, otp: values.otp },
						callback() {
							frm.reload_doc();
							frappe.show_alert({ message: __("Compliance CSID saved"), indicator: "green" });
						},
					});
				},
				__("ZATCA Compliance CSID"),
				__("Submit")
			);
		});

		frm.add_custom_button(__("Production CSID"), () => {
			frappe.call({
				method: "omnexa_einvoice.zatca.phase2.onboarding.onboard_production_csid",
				args: { settings_name: frm.doc.name },
				callback() {
					frm.reload_doc();
					frappe.show_alert({ message: __("Production CSID saved"), indicator: "green" });
				},
			});
		}, __("ZATCA Onboarding"));

		frm.add_custom_button(__("Validate compliance invoices"), () => {
			frappe.call({
				method: "omnexa_einvoice.zatca.phase2.compliance_validation.validate_compliance_invoices",
				args: { settings_name: frm.doc.name },
				callback(r) {
					frm.reload_doc();
					frappe.msgprint(__("Compliance validation OK: {0}", [JSON.stringify(r.message)]));
				},
			});
		}, __("ZATCA Onboarding"));
	},
});
