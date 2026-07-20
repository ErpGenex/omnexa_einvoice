// Copyright (c) 2026, Omnexa and contributors
// License: MIT

/** Egypt ETA actions and fields — only when Branch country is EG. */

const ETA_UI_FIELDS = ["eta_section", "eta_billing_type"];

async function is_egypt_branch(frm) {
	if (!frm.doc.branch) {
		return true;
	}
	const country = await omnexa.einvoice.getBranchCountryCode(frm.doc.branch);
	return country === "EG";
}

async function toggle_eta_ui(frm) {
	const show = await is_egypt_branch(frm);
	for (const fieldname of ETA_UI_FIELDS) {
		if (frm.fields_dict[fieldname]) {
			frm.set_df_property(fieldname, "hidden", show ? 0 : 1);
		}
	}
	if (!show && frm.doc.eta_billing_type && frm.doc.eta_billing_type !== "Regular") {
		frm.set_value("eta_billing_type", "Regular");
	}
	return show;
}

frappe.ui.form.on("Sales Invoice", {
	async refresh(frm) {
		const show = await toggle_eta_ui(frm);
		if (!show || frm.is_new()) {
			return;
		}
		const billing = frm.doc.eta_billing_type || "Regular";
		if (billing === "Regular") {
			return;
		}
		const label =
			billing === "E-Receipt"
				? __("Create E-Receipt Queue")
				: __("Create E-Invoice Queue");
		frm.add_custom_button(label, async () => {
			const r = await frappe.call({
				method:
					"omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.ensure_submission_for_document",
				args: { doctype: "Sales Invoice", docname: frm.doc.name },
				freeze: true,
			});
			if (r.message?.name) {
				frappe.set_route("Form", "E Invoice Submission", r.message.name);
			}
		}, __("ETA"));
		if (
			billing === "E-Invoice" &&
			frm.doc.branch &&
			omnexa.einvoice &&
			omnexa.einvoice.showCloudSigningBridgeTest
		) {
			frm.add_custom_button(
				__("Test cloud ↔ PC signing"),
				async () => {
					await omnexa.einvoice.showCloudSigningBridgeTest({
						branch: frm.doc.branch,
					});
				},
				__("ETA")
			);
		}
	},
	async eta_billing_type(frm) {
		if (!(await is_egypt_branch(frm))) {
			return;
		}
		frm.set_df_property(
			"eta_billing_type",
			"description",
			frm.doc.eta_billing_type && frm.doc.eta_billing_type !== "Regular"
				? __("Requires ETA credentials on Branch {0}.", [frm.doc.branch || ""])
				: __("No ETA submission for regular invoices."),
		);
	},
	async branch(frm) {
		await toggle_eta_ui(frm);
		if ((await is_egypt_branch(frm)) && frm.doc.eta_billing_type) {
			frm.trigger("eta_billing_type");
		}
	},
});
